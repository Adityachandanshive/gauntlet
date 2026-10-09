import os
import shlex
import shutil
import subprocess
import time
import uuid

from dotenv import load_dotenv

from .base import ExecResult, Sandbox

load_dotenv()
DOCKER = os.getenv("DOCKER_BIN") or shutil.which("docker.exe") or shutil.which("docker") or "docker"


class DockerSandbox(Sandbox):
    def __init__(self, image: str = "python:3.12-slim", network: bool = True):
        self.image = image
        self.name = f"gauntlet-{uuid.uuid4().hex[:10]}"
        args = [DOCKER, "run", "-d", "--name", self.name, "--memory", "2g", "--cpus", "2"]
        if not network:
            args += ["--network", "none"]
        args += [image, "sleep", "infinity"]
        p = subprocess.run(args, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"docker run failed: {p.stderr.strip()}")

    def run(self, cmd: str, timeout: int = 120) -> ExecResult:
        start = time.time()
        p = subprocess.run(
            [DOCKER, "exec", self.name, "timeout", str(timeout), "bash", "-c", cmd],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        return ExecResult(p.stdout, p.stderr, p.returncode, time.time() - start)

    def write_file(self, path: str, content: str) -> None:
        d = path.rsplit("/", 1)[0] or "/"
        subprocess.run(
            [DOCKER, "exec", "-i", self.name, "bash", "-c",
             f"mkdir -p {shlex.quote(d)} && cat > {shlex.quote(path)}"],
            input=content.encode("utf-8"), check=True,
        )

    def checkpoint(self) -> str:
        p = subprocess.run([DOCKER, "commit", self.name],
                           capture_output=True, text=True, check=True)
        return p.stdout.strip()

    def fork(self, checkpoint: str) -> "DockerSandbox":
        return DockerSandbox(image=checkpoint)

    def destroy(self) -> None:
        subprocess.run([DOCKER, "rm", "-f", self.name], capture_output=True)