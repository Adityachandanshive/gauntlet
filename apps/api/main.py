import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from packages.scoring.score import leaderboard, load_runs  # noqa: E402

app = FastAPI(title="Gauntlet")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

JOBS = ROOT / "data" / "jobs"
JOBS.mkdir(parents=True, exist_ok=True)
RUNS = str(ROOT / "data" / "runs")
RUN_LOCK = threading.Lock()  # one benchmark at a time (credits + Docker limits)

GITHUB_RE = re.compile(r"^https://github\.com/[\w.-]+/[\w.-]+$")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,29}$")
ALLOWED_MODELS = {"MODEL_CHEAP", "MODEL_SOLVER"}


def read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def collect_tasks(prefix: str = ""):
    by_task = {}
    for r in load_runs(RUNS, task_prefix=prefix or None):
        d = by_task.setdefault(r["task_id"], {}).setdefault(r["model"], [0, 0])
        d[1] += 1
        d[0] += 1 if r["solved"] else 0
    items = {}
    for p in sorted((ROOT / "data" / "verdicts").glob("*.json")):
        v = read_json(p)
        if not v["task_id"].startswith(prefix):
            continue
        items[v["task_id"]] = {"id": v["task_id"], "status": v["status"],
                               "reasons": v.get("reasons", []),
                               "repeatability": v.get("repeatability")}
    for p in sorted((ROOT / "tasks").glob("*.json")):
        t = read_json(p)
        if not t["id"].startswith(prefix):
            continue
        it = items.setdefault(t["id"], {"id": t["id"], "status": "accepted",
                                        "reasons": [], "repeatability": None})
        it["file"] = t["defect"]["file"]
        it["instruction"] = t.get("instruction", "")
    for tid, it in items.items():
        it["results"] = {m: {"solved": s, "attempts": a}
                         for m, (s, a) in by_task.get(tid, {}).items()}
    return list(items.values())


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/leaderboard")
def get_leaderboard():
    return leaderboard(RUNS)


@app.get("/api/tasks")
def list_tasks(prefix: str = ""):
    return collect_tasks(prefix)


@app.get("/api/tasks/{task_id}")
def task_detail(task_id: str):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", task_id):
        raise HTTPException(404, "unknown task")
    tp, vp = ROOT / "tasks" / f"{task_id}.json", ROOT / "data" / "verdicts" / f"{task_id}.json"
    if not tp.exists() and not vp.exists():
        raise HTTPException(404, "unknown task")
    runs = [r for r in load_runs(RUNS) if r["task_id"] == task_id]
    return {
        "task": read_json(tp) if tp.exists() else None,
        "verdict": read_json(vp) if vp.exists() else None,
        "runs": [{k: r[k] for k in ("model", "attempt", "solved", "steps", "tokens", "seconds",
                                    "diff_lines", "diff")} for r in runs],
    }


class BenchmarkRequest(BaseModel):
    repo: str
    name: str | None = None
    models: list[str] = ["MODEL_CHEAP", "MODEL_SOLVER"]
    attempts: int = Field(2, ge=1, le=3)

    @field_validator("repo")
    @classmethod
    def _repo(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        if v.endswith(".git"):
            v = v[:-4]
        if not GITHUB_RE.match(v):
            raise ValueError("repo must look like https://github.com/owner/name")
        return v

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        if v is None or v == "":
            return None
        v = v.strip().lower()
        if not NAME_RE.match(v):
            raise ValueError("name must be lowercase letters, digits and dashes")
        return v

    @field_validator("models")
    @classmethod
    def _models(cls, v: list[str]) -> list[str]:
        v = list(dict.fromkeys(v))
        if not v or not set(v) <= ALLOWED_MODELS:
            raise ValueError(f"models must be a non-empty subset of {sorted(ALLOWED_MODELS)}")
        return v


def make_name(repo: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", repo.rsplit("/", 1)[-1].lower()).strip("-")[:20] or "repo"
    return f"{base}-{uuid.uuid4().hex[:4]}"


def run_job(job_id: str, req: BenchmarkRequest):
    jf, log = JOBS / f"{job_id}.json", JOBS / f"{job_id}.log"
    env = {**os.environ, "GAUNTLET_BENCHMARK_ID": job_id,
           "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    state = {"id": job_id, "request": req.model_dump(), "created": time.time()}

    def status(s, **kw):
        state.update(status=s, updated=time.time(), **kw)
        jf.write_text(json.dumps(state))

    try:
        status("generating")
        with open(log, "w", encoding="utf-8") as lf:
            subprocess.run([sys.executable, "-m", "packages.taskgen.generate", req.repo, req.name],
                           cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT, check=True, env=env)
            tasks = sorted(str(p) for p in (ROOT / "tasks").glob(f"{req.name}-*.json"))
            if not tasks:
                status("failed", error="No candidate task passed validation for this repository.")
                return
            for m in req.models:
                status("solving", model=m, n_tasks=len(tasks))
                subprocess.run([sys.executable, "scripts/run_agent.py", "--model", m,
                                "--attempts", str(req.attempts), "--benchmark-id", job_id, *tasks],
                               cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT, check=True, env=env)
        status("done", n_tasks=len(tasks), model=None)
    except Exception as e:
        status("failed", error=str(e))
    finally:
        RUN_LOCK.release()


@app.post("/api/benchmarks")
def create_benchmark(req: BenchmarkRequest):
    if not req.name:
        req.name = make_name(req.repo)
    if (list((ROOT / "tasks").glob(f"{req.name}-*.json"))
            or list((ROOT / "data" / "verdicts").glob(f"{req.name}-*.json"))):
        raise HTTPException(409, "That benchmark name is already used.")
    if not RUN_LOCK.acquire(blocking=False):
        raise HTTPException(409, "Another benchmark is running. Try again when it finishes.")
    job_id = uuid.uuid4().hex[:10]
    (JOBS / f"{job_id}.json").write_text(json.dumps(
        {"id": job_id, "status": "queued", "request": req.model_dump(), "created": time.time()}))
    threading.Thread(target=run_job, args=(job_id, req), daemon=True).start()
    return {"id": job_id}


@app.get("/api/benchmarks/{job_id}")
def get_benchmark(job_id: str):
    if not re.fullmatch(r"[0-9a-f]{10}", job_id):
        raise HTTPException(404, "unknown job")
    p = JOBS / f"{job_id}.json"
    if not p.exists():
        raise HTTPException(404, "unknown job")
    job = read_json(p)
    name = (job.get("request") or {}).get("name")
    prefix = f"{name}-" if name else None
    lg = JOBS / f"{job_id}.log"
    return {
        **job,
        "leaderboard": leaderboard(RUNS, task_prefix=prefix) if prefix else [],
        "tasks": collect_tasks(prefix) if prefix else [],
        "log": lg.read_text(encoding="utf-8", errors="replace")[-4000:] if lg.exists() else "",
    }