import json
import statistics
from collections import defaultdict
from pathlib import Path

# (input $/1M tokens, output $/1M tokens): copy your real values here
PRICE = {"MODEL_CHEAP": (0.06, 0.24), "MODEL_SOLVER": (0.30, 0.90), "MODEL_JUDGE": (1.0, 3.0)}


def load_runs(runs_dir="data/runs", task_prefix=None):
    out = []
    for p in Path(runs_dir).glob("*.json"):
        r = json.loads(p.read_text(encoding="utf-8"))
        if task_prefix and not r["task_id"].startswith(task_prefix):
            continue
        r["attempt"] = int(p.stem.rsplit("-", 1)[1])
        out.append(r)
    return out


def leaderboard(runs_dir="data/runs", task_prefix=None):
    by = defaultdict(lambda: defaultdict(dict))
    for r in load_runs(runs_dir, task_prefix):
        by[r["model"]][r["task_id"]][r["attempt"]] = r
    rows = []
    for model, tasks in by.items():
        n = len(tasks)
        allr = [r for t in tasks.values() for r in t.values()]
        solved = [r for r in allr if r["solved"]]
        pin, pout = PRICE.get(model, (0.0, 0.0))
        cost = sum(r.get("prompt_tokens", 0) * pin + r.get("completion_tokens", 0) * pout
                   for r in allr) / 1e6
        rows.append({
            "model": model, "tasks": n, "attempts": len(allr),
            "pass_at_1": sum(1 for t in tasks.values() if t.get(0, {}).get("solved")) / n,
            "pass_at_2": sum(1 for t in tasks.values()
                             if any(t.get(i, {}).get("solved") for i in (0, 1))) / n,
            "median_seconds": statistics.median(r["seconds"] for r in solved) if solved else None,
            "avg_tokens": statistics.mean(r["tokens"] for r in allr),
            "total_cost_usd": round(cost, 4),
            "cost_per_solved": round(cost / len(solved), 4) if solved else None,
        })
    rows.sort(key=lambda r: (-r["pass_at_1"], -r["pass_at_2"]))
    return rows