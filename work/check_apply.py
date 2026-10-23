"""Run the Stage 4 confirmation and result flow in real Qt windows."""
import sys
import tempfile
import time
import json
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from yingxu.operations import HistoryStore
from yingxu.qt_ui.design import configure
from yingxu.qt_ui.flow import HistoryDialog, PreviewDialog, ResultDialog
from yingxu.qt_ui.window import Workspace


def wait_until(predicate, seconds=15):
    deadline = time.monotonic() + seconds
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(20)
    assert predicate(), "Timed out waiting for Qt worker"


def capture(widget, name):
    widget.raise_()
    widget.activateWindow()
    QTest.qWait(100)
    pixmap = widget.screen().grabWindow(int(widget.winId()))
    assert pixmap.save(str(ROOT / "outputs" / f"stage4_{name}.png"))


def snapshot(folder):
    return {path.name: path.read_bytes() for path in folder.iterdir() if path.is_file()}


app = QApplication(sys.argv)
configure(app)
errors = []


def record_error(kind, error, tb):
    errors.append(repr(error))
    sys.__excepthook__(kind, error, tb)


sys.excepthook = record_error
with tempfile.TemporaryDirectory(prefix="flow-", dir=ROOT / "work") as temp:
    root = Path(temp)
    media = root / "media"
    media.mkdir()
    names = (
        "剧集.S01E01.mkv", "剧集.S01E02.mkv", "剧集.S01E03.mkv",
        "剧集.S01E04.mkv", "剧集.S01E05.mkv",
        "字幕组.S01E01.chs.srt", "剧集.S01E02.字幕组.chs.srt",
        "剧集.S01E02.字幕组.eng.srt", "剧集.S01E04.chs.srt",
        "字幕组.S01E05.chs.srt",
    )
    for name in names:
        (media / name).write_bytes(name.encode("utf-8"))
    before = snapshot(media)
    window = Workspace()
    window.history = HistoryStore(root / "records" / "history.jsonl")
    window.show()
    window.set_folder(media)
    window.start_scan()
    wait_until(lambda: window.worker is None)
    assert window.preview_button.isEnabled()
    window.search.setText("没有这条视频")
    assert window.proxy.rowCount() == 0 and window.preview_button.isEnabled()
    window.search.clear()
    assert window.proxy.rowCount() == 5 and window.preview_button.isEnabled()
    capture(window, "workspace")

    def inspect_pending():
        dialog = app.activeModalWidget()
        assert isinstance(dialog, PreviewDialog)
        assert dialog.snapshot.pending_count >= 1
        assert not dialog.execute.isEnabled()
        dialog.reject()

    QTimer.singleShot(50, inspect_pending)
    QTest.mouseClick(window.preview_button, Qt.MouseButton.LeftButton)
    assert snapshot(media) == before
    # Resolve the low-confidence match, leave one episode unmatched and skip one.
    low = next(i for i, row in enumerate(window.review.rows) if row.video.name.endswith("E01.mkv"))
    skipped = next(i for i, row in enumerate(window.review.rows) if row.video.name.endswith("E05.mkv"))
    window._select_video(window.review.rows[low].video)
    window.confirm_current()
    window._select_video(window.review.rows[skipped].video)
    window.toggle_skip()
    assert snapshot(media) == before

    frozen = {}

    def approve_preview():
        dialog = app.activeModalWidget()
        assert isinstance(dialog, PreviewDialog)
        assert not dialog.snapshot.pending_count
        assert len(dialog.snapshot.changes) == 3
        frozen["changes"] = dialog.snapshot.changes
        capture(dialog, "preview")
        assert not dialog.execute.isEnabled()
        dialog.acknowledge.setChecked(True)
        assert dialog.execute.isEnabled()
        dialog.execute.click()

    QTimer.singleShot(50, approve_preview)
    QTest.mouseClick(window.preview_button, Qt.MouseButton.LeftButton)

    captured_result = []

    def close_result():
        dialog = app.activeModalWidget()
        if isinstance(dialog, ResultDialog):
            assert dialog.result.count("success") == 3
            assert dialog.result.count("unchanged") == 1
            assert dialog.result.count("skipped") == 1
            assert dialog.result.count("unmatched") == 1
            capture(dialog, "result")
            captured_result.append(dialog.result)
            dialog.accept()
        elif not captured_result:
            QTimer.singleShot(20, close_result)

    QTimer.singleShot(20, close_result)
    wait_until(lambda: window.apply_worker is None and bool(captured_result))
    result = captured_result[0]
    assert window.last_result is result and window.latest_button.isVisible()
    for item in frozen["changes"]:
        assert not item.source.exists()
        assert item.target.read_bytes() == before[item.source.name]
    assert (media / "剧集.S01E04.chs.srt").exists()
    assert (media / "字幕组.S01E05.chs.srt").exists()
    record = window.history.recent()[0]
    assert [entry["status"] for entry in record["items"]] == [item.status for item in result.items]
    assert [entry["target"] for entry in record["items"]] == [str(item.target) if item.target else None for item in result.items]
    report = root / "result.json"
    export_dialog = ResultDialog(result, window.history, window)
    with patch("yingxu.qt_ui.flow.QFileDialog.getSaveFileName", return_value=(str(report), "JSON 文件 (*.json)")), \
         patch("yingxu.qt_ui.flow.QMessageBox.information"):
        export_dialog._export()
    assert json.loads(report.read_text(encoding="utf-8"))["run_id"] == result.run_id
    export_dialog.close()

    def close_history():
        dialog = app.activeModalWidget()
        assert isinstance(dialog, HistoryDialog)
        assert dialog.tree.topLevelItemCount() >= 1
        capture(dialog, "history")
        dialog.accept()

    QTimer.singleShot(50, close_history)
    QTest.mouseClick(window.history_button, Qt.MouseButton.LeftButton)

    # A destination created after preview must block the run without renaming.
    stale = root / "stale"
    stale.mkdir()
    video = stale / "剧集.S01E06.mkv"
    subtitle = stale / "剧集.S01E06.字幕组.chs.srt"
    video.write_bytes(b"video six")
    subtitle.write_bytes(b"subtitle six")
    window.set_folder(stale)
    window.start_scan()
    wait_until(lambda: window.worker is None)
    stale_target = []

    def approve_stale_preview():
        dialog = app.activeModalWidget()
        assert isinstance(dialog, PreviewDialog)
        assert len(dialog.snapshot.changes) == 1 and not dialog.snapshot.pending_count
        target = dialog.snapshot.changes[0].target
        target.write_bytes(b"new target occupant")
        stale_target.append(target)
        dialog.acknowledge.setChecked(True)
        dialog.execute.click()

    QTimer.singleShot(50, approve_stale_preview)
    QTest.mouseClick(window.preview_button, Qt.MouseButton.LeftButton)
    blocked = []

    def close_blocked_result():
        dialog = app.activeModalWidget()
        if isinstance(dialog, ResultDialog):
            assert dialog.result.count("blocked") == 1 and dialog.result.issue
            capture(dialog, "blocked")
            blocked.append(dialog.result)
            dialog.accept()
        elif not blocked:
            QTimer.singleShot(20, close_blocked_result)

    QTimer.singleShot(20, close_blocked_result)
    wait_until(lambda: window.apply_worker is None and bool(blocked))
    assert subtitle.read_bytes() == b"subtitle six"
    assert stale_target[0].read_bytes() == b"new target occupant"
    window.close()

assert not errors, errors
print("PASS: preview gate, explicit confirmation, three real subtitle changes, skip/unmatched/unchanged, result/history UI, stale target blocking")
