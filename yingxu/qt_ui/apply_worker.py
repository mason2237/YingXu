"""Run confirmed file changes away from the UI thread."""
from PySide6.QtCore import QThread, Signal

from ..operations import HistoryStore, PlanSnapshot, run_batch


class ApplyWorker(QThread):
    progress = Signal(int, int, str)
    result = Signal(object)
    failed = Signal(str)

    def __init__(self, snapshot: PlanSnapshot, history: HistoryStore, parent=None):
        super().__init__(parent)
        self.snapshot = snapshot
        self.history = history
        self._stop_requested = False

    def request_stop(self):
        self._stop_requested = True

    def run(self):
        try:
            result = run_batch(
                self.snapshot,
                should_stop=lambda: self._stop_requested,
                progress=lambda done, total, name: self.progress.emit(done, total, name),
                history=self.history,
            )
            self.result.emit(result)
        except Exception as error:
            self.failed.emit(str(error))
