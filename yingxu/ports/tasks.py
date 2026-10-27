"""Tasks run off the owner thread; completion callbacks return to that thread."""
from typing import Protocol


class TaskRunner(Protocol):
    def start(self, work, progress, complete, failed): ...
    def close(self) -> None: ...
