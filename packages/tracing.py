import os

from dotenv import load_dotenv

load_dotenv()

from langsmith import get_current_run_tree, traceable  # noqa: E402,F401


def add_meta(**kw):
    rt = get_current_run_tree()
    if rt:
        rt.add_metadata(kw)


def bench_id() -> str:
    return os.getenv("GAUNTLET_BENCHMARK_ID", "local")


def flush():
    try:
        from langsmith.run_trees import get_cached_client
        get_cached_client().flush()
    except Exception:
        pass