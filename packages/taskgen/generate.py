import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from packages.tracing import add_meta, bench_id, flush, traceable
from packages.models.client import chat
from packages.sandbox.docker_sandbox import DockerSandbox
from packages.validator.validate import validate

PROMPT = """You are creating benchmark tasks for coding agents.
Below is a source file from a Python repository whose test suite currently passes.

Propose {n} DIFFERENT small, realistic bugs to inject into this file. Rules:
- Each bug must change behavior so that existing tests should fail.
- "old" must be an EXACT, unique snippet copied from the file (1-3 lines).
- "new" is the buggy replacement. Keep it syntactically valid.
- "instruction" describes the wrong behavior a user would observe. Do NOT mention
  file names, function names, line numbers, or the fix.
- Return ONLY a JSON list, no commentary:
[{{"old": "...", "new": "...", "instruction": "..."}}]

FILE: {path}
````python
{code}
```"""


def parse_json(text: str):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"\[.*\]", text, flags=re.S)
    return json.loads(m.group(0)) if m else []


@traceable(name="propose_candidates", process_outputs=lambda o: {"candidates": len(o)})
def generate(repo: str, max_files: int = 8, per_file: int = 6):
    sb = DockerSandbox()
    try:
        sb.run("apt-get update -qq && apt-get install -y -qq git", timeout=300)
        sb.run(f"git clone --depth 1 {repo} /repo", timeout=300)
        add_meta(benchmark_id=bench_id(), repository=repo, model="MODEL_JUDGE",
                 commit=sb.run("cd /repo && git rev-parse HEAD").stdout.strip(),
                 sandbox_id=sb.name, tavily_enabled=False)
        listing = sb.run(
            "cd /repo && git ls-files '*.py' | grep -v -E 'test|setup|conf|docs|examples' "
            "| xargs wc -l | sort -rn | sed -n '2,14p'").stdout
        files = [l.split()[1] for l in listing.splitlines() if len(l.split()) == 2][:max_files]
        out = []
        for f in files:
            code = sb.run(f"cat /repo/{f}").stdout[:12000]
            reply, usage = chat("MODEL_JUDGE", [{"role": "user", "content":
                PROMPT.format(n=per_file, path=f, code=code)}], max_tokens=12000)
            try:
                ideas = parse_json(reply)
            except Exception:
                print(f"[{f}] could not parse model output")
                continue
            for i in ideas:
                if code.count(i.get("old", "\0")) != 1:
                    print(f"[{f}] skipped: 'old' not unique/found")
                    continue
                out.append({"file": f, **i})
        return out
    finally:
        sb.destroy()


@traceable(name="task_generation")
def main(repo: str, name: str):
    add_meta(benchmark_id=bench_id(), repository=repo, model="MODEL_JUDGE",
             tavily_enabled=False)
    ideas = generate(repo)
    print(f"{len(ideas)} candidates")
    Path("tasks").mkdir(exist_ok=True)
    Path("data/verdicts").mkdir(parents=True, exist_ok=True)
    accepted = 0
    for n, c in enumerate(ideas, 1):
        task = {
            "id": f"{name}-{n:03d}", "repo": repo,
            "setup_cmd": "pip install -q -e . pytest",
            "test_cmd": "pytest -q", "task_test_cmd": "pytest -q",
            "instruction": c["instruction"],
            "defect": {"file": c["file"], "old": c["old"], "new": c["new"]},
        }
        v = validate(task, repeats=3)
        Path(f"data/verdicts/{task['id']}.json").write_text(
            json.dumps({**v, "defect": task["defect"]}, indent=2))
        print(task["id"], v["status"], v["reasons"])
        if v["status"] == "accepted":
            accepted += 1
            Path(f"tasks/{task['id']}.json").write_text(json.dumps(task, indent=2))
    add_meta(candidates=len(ideas), accepted=accepted, success=accepted > 0)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
    flush()
