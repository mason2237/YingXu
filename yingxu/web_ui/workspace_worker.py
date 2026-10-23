"""One cooperative task at a time; all completion signals return to the GUI thread."""
from threading import Event
from time import monotonic
from PySide6.QtCore import QThread, Signal

from ..core import ScanCancelled
from ..operations import StalePlan
from .protocol import ProtocolError


class WorkspaceWorker(QThread):
    progress = Signal(int, object, str, str)
    result = Signal(object)
    failed = Signal(str, str)

    def __init__(self, work, parent=None):
        super().__init__(parent); self.work = work; self.stop = Event();self._last_report = 0;self._phase = None

    def report(self, done, total, message, phase):
        now = monotonic()
        if not self.stop.is_set() and (phase != self._phase or done == total or now-self._last_report >= .06):
            self._last_report = now;self._phase = phase
            self.progress.emit(done, total, message, phase)

    def run(self):
        try:
            self.result.emit(self.work(self))
        except ScanCancelled as error:
            self.failed.emit("CANCELLED", str(error))
        except ProtocolError as error:
            self.failed.emit(error.code,error.message)
        except StalePlan as error:
            self.failed.emit("STALE_PLAN",str(error))
        except PermissionError as error:
            self.failed.emit("PERMISSION_DENIED",str(error))
        except FileNotFoundError as error:
            self.failed.emit("NOT_FOUND",str(error))
        except FileExistsError as error:
            self.failed.emit("TARGET_EXISTS",str(error))
        except OSError as error:
            self.failed.emit("PATH_UNREADABLE",str(error))
        except (ValueError, IndexError) as error:
            self.failed.emit("INVALID_REQUEST",str(error))
        except Exception:
            self.failed.emit("INTERNAL_ERROR","本地任务未完成，请重新扫描核对文件状态。")
