import json
import statistics
from collections import defaultdict
from pathlib import Path

# USD per 1M tokens (blended input/output). Fill from the Token Factory catalog;
# only the Ultra figure came from the earlier notes, so verify all three.
# (input $/1M, output $/1M): fill these from the Token Factory pricing page
PRICE = {"MODEL_CHEAP": (0.0, 0.0), "MODEL_SOLVER": (0.0, 0.0), "MODEL_JUDGE": (1.0, 3.0)}

runs = defaultdict(lambda: defaultdict(dict))   # model -> task -> attempt -> result
for p in Path("data/runs").glob("*.json"):
    r = json.loads(p.read_text(encoding="utf-8"))
    attempt = int(p.stem.rsplit("-", 1)[1])
    runs[r["model"]][r["task_id"]][attempt] = r

print(f"{'model':14}{'tasks':>6}{'pass@1':>8}{'pass@2':>8}{'med_s':>8}{'tok/att':>9}{'$/solved':>10}")
for model, tasks in runs.items():
    n = len(tasks)
    p1 = sum(1 for t in tasks.values() if t.get(0, {}).get("solved")) / n
    p2 = sum(1 for t in tasks.values()
             if any(t.get(i, {}).get("solved") for i in (0, 1))) / n
    allr = [r for t in tasks.values() for r in t.values()]
    solved = [r for r in allr if r["solved"]]
    med = statistics.median(r["seconds"] for r in solved) if solved else float("nan")
    tok = statistics.mean(r["tokens"] for r in allr)
    cost =    pin, pout = PRICE.get(model, (0.0, 0.0))
    cost = sum(r.get("prompt_tokens", 0) * pin + r.get("completion_tokens", 0) * pout
               for r in allr) / 1e6
    per = cost / len(solved) if solved else float("nan")
    print(f"{model:14}{n:>6}{p1:>8.0%}{p2:>8.0%}{med:>8.1f}{tok:>9.0f}{per:>10.4f}")