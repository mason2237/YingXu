"""Exercise the Stage 3 review workflow in a real Qt window."""
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import Qt, QMimeData, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from yingxu.qt_ui.design import configure
from yingxu.qt_ui.window import Workspace
from yingxu.qt_ui.worker import collect_media


def wait_idle(window):
    limit = time.monotonic() + 15
    while window.worker and time.monotonic() < limit:
        QTest.qWait(20)
    assert window.worker is None


def snapshot(folder):
    return {str(path.relative_to(folder)): path.read_bytes()
            for path in folder.rglob("*") if path.is_file()}


app = QApplication(sys.argv)
configure(app)
errors = []
def record_error(kind, error, tb):
    errors.append(repr(error))
    sys.__excepthook__(kind, error, tb)


sys.excepthook = record_error
window = Workspace()
window.show()
QTest.qWait(100)
with tempfile.TemporaryDirectory(prefix="review-", dir=ROOT / "work") as temp:
    folder = Path(temp)
    videos = [folder / f"剧集.S01E{number:02d}.mkv" for number in range(1, 4)]
    subtitles = [folder / name for name in (
        "剧集.S01E01.chs.srt", "剧集.S01E01.eng.srt", "剧集.S01E01.zh-cn.ass",
        "剧集.S01E02.chs.srt", "完全不同.S09E09.eng.srt")]
    for path in videos + subtitles:
        path.write_bytes(path.name.encode())
    before = snapshot(folder)

    # A real directory drag should choose the folder and start the same scan flow.
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(folder))])
    enter = QDragEnterEvent(window.rect().center(), Qt.DropAction.CopyAction, mime,
                           Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    window.dragEnterEvent(enter)
    assert enter.isAccepted()
    drop = QDropEvent(window.rect().center(), Qt.DropAction.CopyAction, mime,
                      Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    window.dropEvent(drop)
    wait_idle(window)
    assert window.folder == folder and window.model.rowCount() == 3
    assert len(window.review.rows[0].matches) == 2
    assert window.review.owner(subtitles[2]) is None
    assert snapshot(folder) == before

    window.search.setText("S01E02")
    assert window.proxy.rowCount() == 1
    assert window._current_video() == videos[1]
    window.search.clear()
    window.table.sortByColumn(1, Qt.SortOrder.DescendingOrder)
    window._select_video(videos[2])
    assert window._current_video() == videos[2]
    window.state_filter.setCurrentText("未匹配")
    assert window.proxy.rowCount() == 1
    window.state_filter.setCurrentText("全部")
    window._select_video(videos[2])
    index = next(i for i in range(window.inspector.candidate.count())
                 if window.inspector.candidate.itemData(i) == subtitles[4])
    window.inspector.candidate.setCurrentIndex(index)
    assert "冲突" in window.inspector.candidate_info.text()
    QTest.mouseClick(window.inspector.replace, Qt.MouseButton.LeftButton)
    assert window.review.rows[2].matches[0].manual
    assert window.review.state(2) == "需确认"
    assert window._current_video() == videos[2]
    window.confirm_current()
    assert window.review.state(2) == "待整理"
    window.toggle_skip()
    assert window.review.state(2) == "已跳过"
    window.toggle_skip()
    assert window.review.state(2) == "待整理"
    window._select_video(videos[1])
    index = next(i for i in range(window.inspector.candidate.count())
                 if window.inspector.candidate.itemData(i) == subtitles[0])
    window.inspector.candidate.setCurrentIndex(index)
    assert not window.inspector.replace.isEnabled()
    assert snapshot(folder) == before

    # Reveal candidate comparison for an actual UI screenshot.
    window.table.sortByColumn(-1, Qt.SortOrder.AscendingOrder)
    window._select_video(videos[0])
    QTest.mouseClick(window.inspector.adjust, Qt.MouseButton.LeftButton)
    QTest.qWait(120)
    window.raise_()
    window.activateWindow()
    QTest.qWait(100)
    assert window.screen().grabWindow(int(window.winId())).save(str(ROOT / "outputs" / "stage3_review.png"))
    window.resize(1000, 700)
    QTest.qWait(80)
    assert not window.inspector.isVisible()
    QTest.mouseClick(window.details_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(window.inspector.adjust, Qt.MouseButton.LeftButton)
    QTest.qWait(100)
    assert window.inspector.isVisible() and window.table.horizontalScrollBar().maximum() == 0
    assert window.screen().grabWindow(int(window.winId())).save(str(ROOT / "outputs" / "stage3_narrow_review.png"))

    # Cancel while the worker is active. Its eventual result must be discarded.
    def slow_collect(*args):
        time.sleep(0.3)
        return collect_media(*args)
    with patch("yingxu.qt_ui.worker.collect_media", side_effect=slow_collect):
        window.start_scan()
        QTest.mouseClick(window.cancel_scan, Qt.MouseButton.LeftButton)
        wait_idle(window)
    assert window.review is None and window.model.rowCount() == 0
    assert "取消" in window.status.text()
    assert snapshot(folder) == before
window.close()
assert not errors, errors
print("PASS: drag scan, multi-language preview, search, sort, filters, stable selection, manual review, skip/restore, cancel; no media mutations")
