"""Read-only scanner. All GUI changes are delivered by queued Qt signals."""
import os
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from ..core import collect_media
from ..review import ReviewPlan


class ScanWorker(QThread):
    phase = Signal(str)
    result = Signal(object, int, int)
    failed = Signal(str)

    def __init__(self, folder: Path, recursive: bool, move: bool, parent=None):
        super().__init__(parent)
        self.folder, self.recursive, self.move = folder, recursive, move

    def run(self):
        try:
            # Validate the root explicitly; the legacy collector suppresses OSError.
            with os.scandir(self.folder):
                pass
            self.phase.emit("正在读取视频与字幕文件…")
            videos, subtitles = collect_media(self.folder, self.recursive)
            self.phase.emit(f"已发现 {len(videos)} 个视频、{len(subtitles)} 份字幕，正在计算匹配…")
            review = ReviewPlan(videos, subtitles, self.move)
            self.result.emit(review, len(videos), len(subtitles))
        except Exception as error:
            self.failed.emit(str(error))
