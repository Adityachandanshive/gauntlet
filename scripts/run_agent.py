import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from packages.agents.loop import prepare, apply_defect, run_attempt

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, help="MODEL_CHEAP | MODEL_SOLVER | MODEL_JUDGE")
ap.add_argument("--attempts", type=int, default=1)
ap.add_argument("tasks", nargs="+")
a = ap.parse_args()

tasks = [json.loads(Path(p).read_text(encoding="utf-8")) for p in a.tasks]
base, cp = prepare(tasks[0])          # assumes all tasks share one repo
Path("data/runs").mkdir(parents=True, exist_ok=True)
results = []
try:
    for t in tasks:
        for n in range(a.attempts):
            box = base.fork(cp)
            try:
                apply_defect(box, t)
                r = run_attempt(box, t, a.model)
            finally:
                box.destroy()
            results.append(r)
            Path(f"data/runs/{t['id']}-{a.model}-{n}.json").write_text(json.dumps(r, indent=2))
            print(f"{t['id']} {a.model} attempt {n}: solved={r['solved']} steps={r['steps']} "
                  f"tokens={r['tokens']} time={r['seconds']}s diff_lines={r['diff_lines']}")
finally:
    base.destroy()

print(f"\n{a.model}: {sum(r['solved'] for r in results)}/{len(results)} solved")