import importlib.util
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from PIL import ImageGrab

source = Path(__file__).resolve().parents[1] / "outputs" / "映序_字幕整理器.py"
spec = importlib.util.spec_from_file_location("organizer", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module.clean_token("漫长的季节") == "漫长的季节"
assert module.similarity(Path("Show.S01E01.mp4"), Path("Show.S01E02.srt")) == 0
app = module.SubtitleOrganizerApp()
errors = []
app.root.report_callback_exception = lambda *args: errors.append(str(args))


def wait_idle():
    deadline = time.monotonic() + 10
    while app.busy and time.monotonic() < deadline:
        app.root.update()
        time.sleep(0.02)
    app.root.update()
    assert not app.busy, "Background operation timed out"


with tempfile.TemporaryDirectory(dir=source.parent.parent / "work") as temporary:
    folder = Path(temporary)
    videos_dir = folder / "Videos"
    subs_dir = folder / "Subtitles"
    videos_dir.mkdir()
    subs_dir.mkdir()
    for name in ("漫长的季节.S01E01.mp4", "漫长的季节.S01E02.mp4", "旅行日记.mp4"):
        (videos_dir / name).touch()
    for name in ("漫长的季节.S01E01.字幕组.chs.srt", "漫长的季节.S01E02.字幕组.chs.srt"):
        (subs_dir / name).write_text("sample subtitle", encoding="utf-8")
    app.folder = folder
    app.folder_var.set(str(folder))
    app.scan_folder()
    wait_idle()
    assert app.video_count == 3 and app.subtitle_count == 2
    assert all(row["target"].parent == subs_dir for row in app.plan if row["target"])
    app._render_table()
    app._refresh_counts()
    app._set_busy(False, "扫描完成 · 示例数据", "")
    app._set_filter("需检查")
    assert len(app.row_iids) == 1
    app._set_filter("全部")
    index = next(i for i, row in enumerate(app.plan) if row["subtitle"])
    app.selected_index = index
    app._update_inspector()
    app.skip_selected()
    assert app.plan[index]["status"] == "已跳过"
    app.skip_selected()
    assert app.plan[index]["status"] == "待整理"
    app.plan[index]["status"] = "需确认"
    app._set_busy(False, "检查确认操作", "")
    assert str(app.apply_button.cget("state")) == "normal"  # another ready item remains
    app.confirm_selected()
    assert app.plan[index]["status"] == "待整理"
    app.search_var.set("旅行")
    app._render_table()
    assert len(app.row_iids) == 1
    app._clear_search()
    app.selected_index = index
    app._render_table()
    app._update_inspector()
    app.status_var.set("扫描完成 · 3 个视频 · 2 份字幕 · 1 项需要检查")
    app.progress.configure(value=100)
    app.progress_label.configure(text="扫描完成")
    app.root.update()
    app.root.lift()
    app.root.attributes("-topmost", True)
    app.root.update()
    time.sleep(0.6)
    app.root.update()
    x, y = app.root.winfo_rootx(), app.root.winfo_rooty()
    width, height = app.root.winfo_width(), app.root.winfo_height()
    ImageGrab.grab(bbox=(x, y, x + width, y + height)).save(source.parent / "stage1_ui.png")
    print("WINDOW", width, height)
    print("TABLE_HEIGHT", app.tree.winfo_height())
    before = {p: p.read_bytes() for p in folder.rglob("*") if p.is_file()}
    with patch("tkinter.messagebox.askyesno", return_value=False) as confirmation:
        app.apply_plan()
        confirmation.assert_called_once()
    assert not app.busy
    assert {p: p.read_bytes() for p in folder.rglob("*") if p.is_file()} == before
    # A target created after preview must be kept, and its source must survive.
    other = next(row for i, row in enumerate(app.plan) if i != index and row["subtitle"])
    other["target"].write_text("do not overwrite", encoding="utf-8")
    with patch("tkinter.messagebox.askyesno", return_value=True) as confirmation:
        app.apply_plan()
        confirmation.assert_called_once()
    wait_idle()
    assert app.plan[index]["status"] == "已整理"
    assert app.plan[index]["target"].read_text(encoding="utf-8") == "sample subtitle"
    assert other["status"] == "整理失败"
    assert other["target"].read_text(encoding="utf-8") == "do not overwrite"
    assert other["subtitle"].read_text(encoding="utf-8") == "sample subtitle"
    assert all(p.read_bytes() == data for p, data in before.items() if p.suffix == ".mp4")
    assert not errors, errors
    app.root.destroy()
print("PASS: real scan, filtering, skip/restore, confirmation, cancel leaves files intact, rename, late conflict prevents overwrite")
