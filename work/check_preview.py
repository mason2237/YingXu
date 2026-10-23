"""Run actual Qt windows and read-only scanning against temporary samples."""
import sys
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from yingxu.qt_ui.design import configure
from yingxu.qt_ui.window import Workspace
from yingxu.qt_ui.worker import collect_media


def wait_idle(window):
    deadline = time.monotonic() + 15
    while window.worker and time.monotonic() < deadline:
        QTest.qWait(20)
    assert window.worker is None, "Scan timed out"
    QTest.qWait(60)


def capture(window, name):
    window.raise_()
    window.activateWindow()
    QTest.qWait(120)
    pixmap = window.screen().grabWindow(int(window.winId()))
    assert not pixmap.isNull()
    prefix = os.environ.get("YINGXU_CAPTURE_PREFIX", "stage2")
    assert pixmap.save(str(ROOT / "outputs" / f"{prefix}_{name}.png"))


def snapshot(folder):
    return {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob("*") if p.is_file()}


app = QApplication(sys.argv)
configure(app)
errors = []
def record_error(*args):
    errors.append(repr(args[1]))
    sys.__excepthook__(*args)


sys.excepthook = record_error
window = Workspace()
window.show()
QTest.qWait(150)
assert window.worker is None and not window.scan.isEnabled()
capture(window, "initial")
with tempfile.TemporaryDirectory(prefix="preview-", dir=ROOT / "work") as temp:
    folder = Path(temp) / "剧集示例"
    folder.mkdir()
    videos, subtitles = folder / "视频", folder / "字幕"
    videos.mkdir()
    subtitles.mkdir()
    for number in range(1, 9):
        stem = f"漫长的季节.S01E{number:02d}"
        (videos / f"{stem}.mkv").write_bytes(b"video fixture")
        if number < 7:
            (subtitles / f"漫长的季节.S01E{number:02d}.字幕组.chs.srt").write_text("字幕样本", encoding="utf-8")
    long_name = "旅行日记." + "山川湖海与城市之间的慢生活_" * 7
    (videos / f"{long_name}.mp4").write_bytes(b"long video")
    (subtitles / f"{long_name}.eng.srt").write_bytes(b"long subtitle")
    (videos / "AAAA.S02E01.mp4").write_bytes(b"review video")
    (subtitles / "ZZZZ.S02E01.srt").write_bytes(b"review subtitle")
    before = snapshot(folder)
    with patch("yingxu.qt_ui.window.QFileDialog.getExistingDirectory", return_value=str(folder)):
        QTest.mouseClick(window.choose, Qt.MouseButton.LeftButton)
    assert window.folder == folder and window.scan.isEnabled()

    def slow_collect(*args):
        time.sleep(0.4)
        return collect_media(*args)

    with patch("yingxu.qt_ui.worker.collect_media", side_effect=slow_collect):
        QTest.mouseClick(window.scan, Qt.MouseButton.LeftButton)
        assert not window.choose.isEnabled() and window.worker
        capture(window, "scanning")
        wait_idle(window)
    assert window.model.rowCount() == 10
    assert sum(not r.subtitles for r in window.model.records) == 2
    assert any(r.state == "需确认" for r in window.model.records)
    assert window.inspector.isVisible()
    assert window.table.viewport().height() > 400
    assert window.table.horizontalScrollBar().maximum() == 0
    # Disclosure remains stable when rapidly reversed and with motion disabled.
    with patch("yingxu.qt_ui.interactions.motion_allowed", return_value=True):
        window.inspector.paths_toggle.click()
        QTest.qWait(40)
        window.inspector.paths_toggle.click()
        QTest.qWait(200)
        assert not window.inspector.path_disclosure.isVisible()
    with patch("yingxu.qt_ui.interactions.motion_allowed", return_value=False):
        window.inspector.paths_toggle.click()
        assert window.inspector.path_disclosure.isVisible()
        assert str(window.inspector.record.video) in window.inspector.paths.toPlainText()
        window.inspector.paths_toggle.click()
        assert not window.inspector.path_disclosure.isVisible()
    # Select a typical matched episode for the main screenshot.
    matched_index = next(i for i, r in enumerate(window.model.records)
                         if r.subtitles and r.state == "待整理")
    window.table.selectRow(matched_index)
    capture(window, "wide")
    QTest.mouseClick(window.inspector.copy, Qt.MouseButton.LeftButton)
    QTest.qWait(80)  # Let the Windows clipboard ownership event complete.
    expected = window.model.records[matched_index].subtitles[0].target.name
    assert app.clipboard().text() == expected, (app.clipboard().text(), expected, window.inspector.record)
    window.table.setFocus()
    QTest.keyClick(window.table, Qt.Key.Key_Down)
    assert window.inspector.record == window.model.records[window.table.currentIndex().row()]
    long_index = next(i for i, r in enumerate(window.model.records) if r.video.name.startswith("旅行"))
    window.table.selectRow(long_index)
    window.resize(1000, 700)
    QTest.qWait(80)
    assert not window.inspector.isVisible()
    capture(window, "narrow")
    QTest.mouseClick(window.details_button, Qt.MouseButton.LeftButton)
    QTest.qWait(80)
    assert window.inspector.isVisible()
    assert window.inspector.video.toPlainText() == window.model.records[long_index].video.name
    assert window.table.horizontalScrollBar().maximum() == 0
    capture(window, "narrow_details")
    assert snapshot(folder) == before
    # Changing options invalidates preview instead of leaving stale target paths.
    window.move.setChecked(True)
    assert window.model.rowCount() == 0
    window.start_scan()
    wait_idle(window)
    assert all(m.target.parent == r.video.parent for r in window.model.records for m in r.subtitles)
    assert snapshot(folder) == before
    window.resize(1240, 840)
    empty = folder / "空目录"
    empty.mkdir()
    window.set_folder(empty)
    window.start_scan()
    wait_idle(window)
    assert window.model.rowCount() == 0 and "没有找到视频" in window.empty_title.text()
    window.search.setText("任意搜索词")
    assert "没有找到视频" in window.empty_title.text() and not window.preview_button.isEnabled()
    window.search.clear()
    capture(window, "empty")
    (empty / "只有视频.mp4").write_bytes(b"video only")
    window.start_scan()
    wait_idle(window)
    assert window.model.records[0].state == "未匹配"
    window.set_folder(folder / "不存在")
    window.start_scan()
    wait_idle(window)
    assert "无法读取" in window.empty_title.text() and window.scan.isEnabled()
    # Closing during a background task is deferred until QThread has finished.
    window.set_folder(videos)
    with patch("yingxu.qt_ui.worker.collect_media", side_effect=slow_collect):
        window.start_scan()
        window.close()
        assert window._pending_close and window.isVisible()
        wait_idle(window)
    assert not window.isVisible()
assert not errors, errors
print("PASS: real scan and UI, 10 records, wide/narrow layouts, keyboard selection, copy, option invalidation, empty/no-subtitle/missing path, deferred close; no media mutations")
