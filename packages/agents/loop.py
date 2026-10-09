import json
import shlex
import os
import re
import sys
import time
from pathlib import Path
from packages.agents.editing import apply_edit, replace_lines
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from packages.tracing import add_meta, traceable
from packages.models.client import chat
from packages.sandbox.docker_sandbox import DockerSandbox

SYSTEM = """You are a software engineer fixing a bug in a Python repository at /repo.
Reply with exactly ONE JSON object per turn and nothing else. Actions:
{"action":"list_files","path":"."}
{"action":"read_file","path":"relative/path.py","start":1,"end":200}
{"action":"search","pattern":"text"}
{"action":"run","cmd":"shell command"}
{"action":"edit","path":"relative/path.py","old":"exact existing text","new":"replacement"}
{"action":"replace_lines","path":"relative/path.py","start":231,"end":233,"new":"replacement lines, with correct indentation"}
{"action":"finish","summary":"what you changed"}
Files are shown in chunks of up to 250 lines; use start/end to see more.
Copy 'old' exactly from read_file output, without the line-number prefix.
Run the tests with pytest to find failures. Make the smallest change that fixes the bug.
Call finish only after the tests pass.If an edit fails, use replace_lines with the line numbers from read_file (start..end inclusive are replaced). Re-read the file after any edit, because line numbers shift."""


def prepare(task: dict) -> tuple:
    """Clone, install, checkpoint. Returns (box, checkpoint); box.commit = repo HEAD."""
    sb = DockerSandbox()
    sb.run("apt-get update -qq && apt-get install -y -qq git", timeout=300)
    sb.run(f"git clone --depth 1 {task['repo']} /repo", timeout=300)
    sb.commit = sb.run("cd /repo && git rev-parse HEAD").stdout.strip()
    sb.run(f"cd /repo && {task['setup_cmd']}", timeout=900)
    return sb, sb.checkpoint()


def apply_defect(box, task):
    d = task["defect"]
    src = box.run(f"cat /repo/{d['file']}").stdout
    box.write_file(f"/repo/{d['file']}", src.replace(d["old"], d["new"], 1))
    box.run("cd /repo && git -c user.email=a@b -c user.name=x commit -qam bug")


def parse_action(text: str):
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    for m in re.finditer(r"\{.*\}", text, flags=re.S):
        try:
            return json.loads(m.group(0))
        except Exception:
            continue
    return None


@traceable(run_type="tool", name="tool_call",
           process_inputs=lambda inp: {"action": inp.get("a")})
def execute(box, a: dict) -> str:
    act = a.get("action")
    if act == "list_files":
        r = box.run(f"cd /repo && ls -1 {a.get('path', '.')} | head -80")
    elif act == "read_file":
        s, e = int(a.get("start", 1)), int(a.get("end", 250))
        r = box.run(f"cd /repo && cat -n {a['path']} | sed -n '{s},{e}p'")
    elif act == "search":
        pat = a["pattern"].replace("'", "'\\''")
        r = box.run(f"cd /repo && grep -rn --include='*.py' '{pat}' . | head -40")
    elif act == "run":
        r = box.run(f"cd /repo && {a['cmd']}", timeout=300)
    elif act in ("edit", "replace_lines"):
        path = a["path"]
        if path.startswith("tests") or "/tests/" in path:
            if box.run(f"test -f /repo/{path}").exit_code != 0:
                base = path.rsplit("/", 1)[-1]
                near = box.run(f"cd /repo && git ls-files | grep -i -F {shlex.quote(base)} | head -5").stdout.strip()
                return (f"ERROR: file '{path}' does not exist. Paths are relative to /repo. "
                    + (f"Similar files:\n{near}" if near else "Use list_files or search to find the real path."))
    
        src = box.run(f"cat /repo/{path}").stdout
        if act == "edit":
            new_src, note = apply_edit(src, a["old"], a["new"])
        else:
            new_src, note = replace_lines(src, int(a["start"]), int(a["end"]), a["new"])
        if new_src is None:
            return f"ERROR: {note}"
        box.write_file(f"/repo/{path}", new_src)
        return f"edit applied ({note})"
    else:
        return "ERROR: unknown action"
    out = (r.stdout + r.stderr).strip() or "(no output)"
    if act == "run":
        return out[-3000:]
    return out[:6000]


def compact(msgs, keep=8, limit=400):
    """Shrink old observations so token usage doesn't grow quadratically."""
    out = []
    for idx, m in enumerate(msgs):
        old = 2 <= idx < len(msgs) - keep
        if old and m["role"] == "user" and len(m["content"]) > limit:
            m = {**m, "content": m["content"][:limit] + " ...[truncated]"}
        out.append(m)
    return out


@traceable(run_type="tool", name="final_tests",
           process_inputs=lambda inp: {"cmd": inp.get("cmd")})
def final_tests(box, cmd: str) -> dict:
    r = box.run(f"cd /repo && {cmd}", timeout=900)
    return {"ok": r.ok, "exit_code": r.exit_code, "output_tail": (r.stdout + r.stderr)[-3000:]}


def _attempt_inputs(inp):
    t = inp.get("task") or {}
    return {"task_id": t.get("id"), "bug_report": t.get("instruction"),
            "model": inp.get("model_env")}


def _attempt_outputs(out):
     return {k: v for k, v in (out or {}).items() if k != "trace"}


@traceable(name="agent_attempt", run_type="chain",
           process_inputs=_attempt_inputs, process_outputs=_attempt_outputs)
def run_attempt(box, task: dict, model_env: str, max_steps: int = 25,
                tavily_enabled: bool = False, benchmark_id: str = "local",
                commit: str | None = None, attempt: int = 0) -> dict:
    add_meta(benchmark_id=benchmark_id, repository=task["repo"], commit=commit,
             task_id=task["id"], model=model_env, model_id=os.getenv(model_env),
             attempt=attempt, tavily_enabled=tavily_enabled, sandbox_id=box.name,
             defect_file=task["defect"]["file"])

    pre = box.run(f"cd /repo && {task['test_cmd']} 2>&1 | tail -40", timeout=600)
    msgs =     tree = box.run("cd /repo && git ls-files '*.py' | grep -v -E '(^|/)(tests?|docs|misc|examples)/' | head -80").stdout.strip()
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content":
            f"Bug report:\n{task['instruction']}\n\n"
            f"Python source files in /repo (paths are relative to /repo):\n{tree}\n\n"
            f"Current test results ({task['test_cmd']}):\n{pre.stdout[-2500:]}"},
    ]
    
    start, tokens, steps, finished = time.time(), 0, [], False
    prompt_tok = completion_tok = 0
    for i in range(max_steps):
        reply, usage = chat(model_env, compact(msgs), max_tokens=3000, temperature=0.2)
        tokens += usage.total_tokens
        prompt_tok += usage.prompt_tokens
        completion_tok += usage.completion_tokens
        act = parse_action(reply)
        if not act:
            msgs.append({"role": "assistant", "content": reply or "(empty)"})
            msgs.append({"role": "user", "content": "Reply with ONE valid JSON action."})
            steps.append({"i": i, "error": "unparseable"})
            continue
        if act.get("action") == "finish":
            finished = True
            steps.append({"i": i, "action": act})
            break
        try:
            obs = execute(box, act, langsmith_extra={"tags": [str(act.get("action", "?"))]})
        except Exception as e:
            obs = f"ERROR: {e}"
        steps.append({"i": i, "action": act, "obs": obs[:500]})
        msgs.append({"role": "assistant", "content": json.dumps(act)})
        msgs.append({"role": "user", "content": obs})

    final = final_tests(box, task["test_cmd"])
    diff = box.run("cd /repo && git diff").stdout
    edited = box.run("cd /repo && git diff --name-only").stdout.split()
    add_meta(success=final["ok"], stop_reason="finished" if finished else "max_steps",
             steps=len(steps), edited_files=edited,
             edited_defect_file=task["defect"]["file"] in edited)
    return {
        "task_id": task["id"], "model": model_env, "solved": final["ok"],
        "finished": finished, "steps": len(steps), "tokens": tokens,
        "prompt_tokens": prompt_tok, "completion_tokens": completion_tok,
        "seconds": round(time.time() - start, 1),
        "diff_lines": len(diff.splitlines()), "diff": diff[:4000], "trace": steps,
    }