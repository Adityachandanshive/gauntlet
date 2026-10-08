import shlex
import subprocess
import time
import uuid

from .base import ExecResult, Sandbox


class DockerSandbox(Sandbox):
    def __init__(self, image: str = "python:3.12-slim", network: bool = True):
        self.image = image
        self.name = f"gauntlet-{uuid.uuid4().hex[:10]}"
        args = ["docker", "run", "-d", "--name", self.name,
                "--memory", "2g", "--cpus", "2"]
        if not network:
            args += ["--network", "none"]
        args += [image, "sleep", "infinity"]
        subprocess.run(args, check=True, capture_output=True, text=True)

    def run(self, cmd: str, timeout: int = 120) -> ExecResult:
        start = time.time()
        p = subprocess.run(
            ["docker", "exec", self.name, "timeout", str(timeout), "bash", "-c", cmd],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        return ExecResult(p.stdout, p.stderr, p.returncode, time.time() - start)

    def write_file(self, path: str, content: str) -> None:
        d = path.rsplit("/", 1)[0] or "/"
         
       
        subprocess.run(
            ["docker", "exec", "-i", self.name, "bash", "-c",
             f"mkdir -p {shlex.quote(d)} && cat > {shlex.quote(path)}"],
            input=content.encode("utf-8"), check=True,
        )

    def checkpoint(self) -> str:
        p = subprocess.run(["docker", "commit", self.name],
                           capture_output=True, text=True, check=True)
        return p.stdout.strip()

    def fork(self, checkpoint: str) -> "DockerSandbox":
        return DockerSandbox(image=checkpoint)

    def destroy(self) -> None:
        subprocess.run(["docker", "rm", "-f", self.name], capture_output=True)