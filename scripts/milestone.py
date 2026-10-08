import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from packages.sandbox.docker_sandbox import DockerSandbox


def tail(s, n=12):
    return "\n".join(s.strip().splitlines()[-n:])


ap = argparse.ArgumentParser()
ap.add_argument("repo")
ap.add_argument("--file", required=True)
ap.add_argument("--old", required=True)
ap.add_argument("--new", required=True)
a = ap.parse_args()

sb = DockerSandbox()
fork = None
try:
    print("== setup ==")
    r = sb.run("apt-get update -qq && apt-get install -y -qq git", timeout=300)
    print("git install exit:", r.exit_code)
    r = sb.run(f"git clone --depth 1 {a.repo} /repo", timeout=300)
    print("clone exit:", r.exit_code, tail(r.stderr, 3))
    r = sb.run("cd /repo && pip install -q -e . pytest 2>&1 | tail -3", timeout=600)
    print(tail(r.stdout, 3))

    print("== baseline ==")
    base = sb.run("cd /repo && pytest -q -x 2>&1 | tail -8", timeout=600)
    print(base.stdout)

    cp = sb.checkpoint()
    fork = sb.fork(cp)
    print("checkpoint:", cp[:19], "| forked:", fork.name)

    print("== inject bug in fork ==")
    path = f"/repo/{a.file}"
    src = fork.run(f"cat {path}").stdout
    if a.old not in src:
        sys.exit(f"'{a.old}' not found in {a.file}")
    fork.write_file(path, src.replace(a.old, a.new, 1))

    broken = fork.run("cd /repo && pytest -q 2>&1 | tail -8", timeout=600)
    print(broken.stdout)

    orig = sb.run("cd /repo && pytest -q 2>&1 | tail -3", timeout=600)
    print("== original still clean? ==")
    print(orig.stdout)
finally:
    if fork:
        fork.destroy()
    sb.destroy()
