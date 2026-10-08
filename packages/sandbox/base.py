from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ExecResult:
    stdout: str
    stderr: str
    exit_code: int
    duration: float

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


class Sandbox(ABC):
    @abstractmethod
    def run(self, cmd: str, timeout: int = 120) -> ExecResult: ...

    @abstractmethod
    def write_file(self, path: str, content: str) -> None: ...

    @abstractmethod
    def checkpoint(self) -> str: ...

    @abstractmethod
    def fork(self, checkpoint: str) -> "Sandbox": ...

    @abstractmethod
    def destroy(self) -> None: ...