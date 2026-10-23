"""Own background work outside the object published to JavaScript."""
import platform
from uuid import uuid4

import PySide6
from PySide6.QtCore import QObject, Signal, Slot, qVersion
from PySide6.QtWebEngineCore import qWebEngineChromiumVersion

from .protocol import ProtocolError
from .workers import SampleWorker


class FoundationService(QObject):
    changed = Signal(str)
    idle = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.job = None

    def state(self):
        return {"stage": 5, "status": "running" if self.worker else "ready",
                "executionAvailable": False, "job": self.job,
                "runtime": {"python": platform.python_version(),
                            "pyside": PySide6.__version__, "qt": qVersion(),
                            "chromium": qWebEngineChromiumVersion()}}

    def start_sample(self):
        if self.worker:
            raise ProtocolError("BUSY", "样本检查仍在进行。", retryable=True)
        self.job = {"jobId": uuid4().hex, "status": "running", "phase": "starting",
                    "message": "正在准备临时样本…", "total": None, "result": None}
        self.worker = SampleWorker(self)
        self.worker.phase.connect(self.on_phase)
        self.worker.result.connect(self.on_result)
        self.worker.failed.connect(self.on_failure)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()
        return {"jobId": self.job["jobId"]}

    @Slot(str, str)
    def on_phase(self, phase, message):
        self.job.update(phase=phase, message=message)
        self.changed.emit("job.progress")

    @Slot(object)
    def on_result(self, result):
        self.job.update(status="completed", phase="completed", result=result,
                        message="原有核心调用通过，样本名称和内容保持一致。")
        self.changed.emit("job.completed")

    @Slot(str)
    def on_failure(self, message):
        self.job.update(status="failed", phase="failed", message=message)
        self.changed.emit("job.failed")

    @Slot()
    def on_finished(self):
        worker, self.worker = self.worker, None
        worker.deleteLater()
        self.changed.emit("job.idle")
        self.idle.emit()
