import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from packages.models.client import chat
from packages.sandbox.docker_sandbox import DockerSandbox

SYSTEM = """You are a software engineer fixing a bug in a Python repository at /repo.
Reply with exactly ONE JSON object per turn and nothing else. Actions:
{"action":"list_files","path":"."}
{"action":"read_file","path":"relative/path.py","start":1,"end":200}
{"action":"search","pattern":"text"}
{"action":"run","cmd":"shell command"}
{"action":"edit","path":"relative/path.py","old":"exact existing text","new":"replacement"}
{"action":"finish","summary":"what you changed"}
Files are shown in chunks of up to 250 lines; use start/end to see more.
Copy 'old' exactly from read_file output, without the line-number prefix.
Run the tests with pytest to find failures. Make the smallest change that fixes the bug.
Call finish only after the tests pass."""


def prepare(task: dict) -> tuple:
    """Clone, install, then checkpoint. Returns (box, checkpoint)."""
    sb = DockerSandbox()
    sb.run("apt-get update -qq && apt-get install -y -qq git", timeout=300)
    sb.run(f"git clone --depth 1 {task['repo']} /repo", timeout=300)
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
    elif act == "edit":
        if a["path"].startswith("tests") or "/tests/" in a["path"]:
            return "ERROR: editing tests is not allowed."
        src = box.run(f"cat /repo/{a['path']}").stdout
        if src.count(a["old"]) != 1:
            return f"ERROR: 'old' text found {src.count(a['old'])} times; must match exactly once."
        box.write_file(f"/repo/{a['path']}", src.replace(a["old"], a["new"], 1))
        return "edit applied"
    else:
        return "ERROR: unknown action"
    out = (r.stdout + r.stderr).strip() or "(no output)"
    if act == "run":
        return out[-3000:]
    return out[:6000]



def run_attempt(box, task: dict, model_env: str, max_steps: int = 25) -> dict:  
  def compact(msgs, keep=8, limit=400):
    """Shrink old observations so token usage doesn't grow quadratically."""
    out = []
    for idx, m in enumerate(msgs):
        old = 2 <= idx < len(msgs) - keep
        if old and m["role"] == "user" and len(m["content"]) > limit:
            m = {**m, "content": m["content"][:limit] + " ...[truncated]"}
        out.append(m)
    return out

def compact(msgs, keep=8, limit=400):
    """Shrink old observations so token usage doesn't grow quadratically."""
    out = []
    for idx, m in enumerate(msgs):
        old = 2 <= idx < len(msgs) - keep
        if old and m["role"] == "user" and len(m["content"]) > limit:
            m = {**m, "content": m["content"][:limit] + " ...[truncated]"}
        out.append(m)
    return out


def run_attempt(box, task: dict, model_env: str, max_steps: int = 25) -> dict:
    pre = box.run(f"cd /repo && {task['test_cmd']} 2>&1 | tail -40", timeout=600)
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content":
            f"Bug report:\n{task['instruction']}\n\n"
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
            obs = execute(box, act)
        except Exception as e:
            obs = f"ERROR: {e}"
        steps.append({"i": i, "action": act, "obs": obs[:500]})
        msgs.append({"role": "assistant", "content": json.dumps(act)})
        msgs.append({"role": "user", "content": obs})
    final = box.run(f"cd /repo && {task['test_cmd']}", timeout=900)
    diff = box.run("cd /repo && git diff").stdout
    return {
        "task_id": task["id"], "model": model_env, "solved": final.ok,
        "finished": finished, "steps": len(steps), "tokens": tokens,
        "prompt_tokens": prompt_tok, "completion_tokens": completion_tok,
        "seconds": round(time.time() - start, 1),
        "diff_lines": len(diff.splitlines()), "diff": diff[:4000], "trace": steps,
    }