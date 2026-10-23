"""Only the diagnostic fixture is exposed in stage 5, not user folder access."""
import tempfile
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from ..core import collect_media
from ..review import ReviewPlan, language_of
from .. import operations  # Import the existing execution module; never call it here.


def inspect_sample(report):
    with tempfile.TemporaryDirectory(prefix="yingxu-stage5-") as temp:
        folder = Path(temp)
        names = ["示例剧.S01E01.mkv", "示例剧.S01E02.mkv",
                 "示例剧.S01E01.字幕组.chs.srt", "示例剧.S01E01.字幕组.eng.srt",
                 "示例剧.S01E02.字幕组.chs.srt"]
        for name in names:
            (folder / name).write_bytes("仅用于架构验证的临时样本".encode("utf-8"))
        before = {p.name: p.read_bytes() for p in folder.iterdir()}
        report("scanning", "正在使用原有核心读取临时样本…")
        videos, subtitles = collect_media(folder)
        report("matching", "正在使用原有审阅模型计算匹配与目标名称…")
        review = ReviewPlan(videos, subtitles)
        rows = [{
            "rowId": f"sample-{index}", "videoName": row.video.name,
            "state": review.state(index), "subtitles": [{
                "name": match.source.name, "targetName": match.target.name,
                "language": language_of(match.source), "score": match.score,
            } for match in row.matches],
        } for index, row in enumerate(review.rows)]
        unchanged = before == {p.name: p.read_bytes() for p in folder.iterdir()}
        if not unchanged:
            raise RuntimeError("样本只读检查未通过。")
        return {"videoCount": len(videos), "subtitleCount": len(subtitles),
                "rows": rows, "unchanged": unchanged,
                "modules": ["core", "review", "operations"],
                "executionAvailable": False}


class SampleWorker(QThread):
    phase = Signal(str, str)
    result = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            self.result.emit(inspect_sample(self.phase.emit))
        except Exception:
            # No user paths or tracebacks are sent across the channel.
            self.failed.emit("临时样本检查失败，请重试。")
