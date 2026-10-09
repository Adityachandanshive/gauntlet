import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from packages.tracing import add_meta, bench_id, traceable
from packages.sandbox.docker_sandbox import DockerSandbox


def edit(box, file, old, new):
    src = box.run(f"cat /repo/{file}").stdout
    if old not in src:
        raise ValueError(f"text not found in {file}")
    box.write_file(f"/repo/{file}", src.replace(old, new, 1))


def _validate(task: dict, repeats: int = 5) -> dict:
    v = {"task_id": task["id"], "reasons": []}
    boxes = []
    try:
        sb = DockerSandbox()
        boxes.append(sb)
        v["sandbox_id"] = sb.name
        sb.run("apt-get update -qq && apt-get install -y -qq git", timeout=300)
        r = sb.run(f"git clone --depth 1 {task['repo']} /repo", timeout=300)
        if not r.ok:
            return {**v, "status": "rejected", "reasons": ["clone failed"]}
        v["commit"] = sb.run("cd /repo && git rev-parse HEAD").stdout.strip()
        sb.run(f"cd /repo && {task['setup_cmd']}", timeout=900)
        cp = sb.checkpoint()

        base = sb.fork(cp); boxes.append(base)
        r = base.run(f"cd /repo && {task['test_cmd']}", timeout=900)
        v["baseline"] = "pass" if r.ok else "fail"
        if not r.ok:
            v["reasons"].append("baseline suite fails")

        d = task["defect"]
        work = sb.fork(cp); boxes.append(work)
        edit(work, d["file"], d["old"], d["new"])
        fails = []
        for _ in range(repeats):
            r = work.run(f"cd /repo && {task['task_test_cmd']}", timeout=600)
            fails.append(r.exit_code)
        v["task_test_before_fix"] = "fail" if all(c == 1 for c in fails) else "unexpected"
        if not all(c == 1 for c in fails):
            v["reasons"].append(f"task test not consistently failing: {fails}")

        edit(work, d["file"], d["new"], d["old"])
        passes = []
        for _ in range(repeats):
            r = work.run(f"cd /repo && {task['task_test_cmd']}", timeout=600)
            passes.append(r.exit_code)
        v["reference_fix"] = "pass" if all(c == 0 for c in passes) else "fail"
        if not all(c == 0 for c in passes):
            v["reasons"].append(f"reference fix not consistently passing: {passes}")
        full = work.run(f"cd /repo && {task['test_cmd']}", timeout=900)
        v["full_suite_after_fix"] = "pass" if full.ok else "fail"
        if not full.ok:
            v["reasons"].append("full suite fails after fix")

        v["repeatability"] = f"{sum(c == 1 for c in fails) + sum(c == 0 for c in passes)}/{2 * repeats}"
        v["status"] = "accepted" if not v["reasons"] else "rejected"
        return v
    except Exception as e:
        return {**v, "status": "rejected", "reasons": v["reasons"] + [f"error: {e}"]}
    finally:
        for b in boxes:
            b.destroy()


@traceable(name="validation")
def validate(task: dict, repeats: int = 5) -> dict:
    add_meta(benchmark_id=bench_id(), repository=task["repo"], task_id=task["id"],
             model=None, attempt=None, tavily_enabled=False)
    v = _validate(task, repeats)
    add_meta(success=v["status"] == "accepted", status=v["status"],
             sandbox_id=v.get("sandbox_id"), commit=v.get("commit"))
    return v


if __name__ == "__main__":
    task = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    verdict = validate(task)
    print(json.dumps(verdict, indent=2))
    Path("data/verdicts").mkdir(parents=True, exist_ok=True)
    Path(f"data/verdicts/{task['id']}.json").write_text(json.dumps(verdict, indent=2))