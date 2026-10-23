"""Frozen subtitle changes, guarded execution, and local result records."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import errno
import json
import os
from pathlib import Path
import shutil
import stat
import sys
from typing import Callable
from uuid import uuid4

from .core import is_same_path
from .review import ReviewPlan, path_key


class StalePlan(Exception):
    """The frozen preview no longer describes the files on disk."""


@dataclass(frozen=True)
class FileMark:
    device: int
    inode: int
    size: int
    modified_ns: int
    created_ns: int


@dataclass(frozen=True)
class DirMark:
    device: int
    inode: int


def dir_mark(path: Path) -> DirMark:
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode):
        raise StalePlan(f"目标位置不是文件夹：{path}")
    return DirMark(info.st_dev, info.st_ino)


def file_mark(path: Path) -> FileMark:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise StalePlan(f"不是普通文件：{path}")
    return FileMark(info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def path_present(path: Path) -> bool:
    try:
        path.lstat()
        return True
    except FileNotFoundError:
        return False


@dataclass(frozen=True)
class PlannedItem:
    video: Path
    source: Path | None
    target: Path | None
    action: str  # rename, unchanged, skipped, unmatched, pending
    video_mark: FileMark | None = None
    source_mark: FileMark | None = None
    target_dir_mark: DirMark | None = None


@dataclass(frozen=True)
class PlanSnapshot:
    snapshot_id: str
    created_at: str
    items: tuple[PlannedItem, ...]

    @property
    def changes(self) -> tuple[PlannedItem, ...]:
        return tuple(item for item in self.items if item.action == "rename")

    @property
    def pending_count(self) -> int:
        return sum(item.action == "pending" for item in self.items)


def snapshot_from_review(review: ReviewPlan) -> PlanSnapshot:
    """Freeze exact target names and file identity at preview time."""
    items: list[PlannedItem] = []
    destinations: set[str] = set()
    sources: set[str] = set()
    for index, row in enumerate(review.rows):
        state = review.state(index)
        if not row.matches:
            items.append(PlannedItem(row.video, None, None, "skipped" if row.skipped else "unmatched"))
            continue
        for match in row.matches:
            source, target = match.source, match.target
            if target is None:
                raise StalePlan(f"缺少目标名称：{source}")
            source_key, target_key = path_key(source), path_key(target)
            if source_key in sources or target_key in destinations:
                raise StalePlan("预览中有重复的源字幕或目标名称，请重新扫描")
            sources.add(source_key)
            destinations.add(target_key)
            action = ("skipped" if row.skipped else "pending" if state == "需确认" else
                      "unchanged" if is_same_path(source, target) else "rename")
            if action == "rename":
                if path_present(target):
                    raise StalePlan(f"目标名称已被占用，请重新扫描：{target}")
                if not target.parent.is_dir():
                    raise StalePlan(f"目标文件夹不存在：{target.parent}")
                items.append(PlannedItem(row.video, source, target, action,
                                         file_mark(row.video), file_mark(source), dir_mark(target.parent)))
            else:
                items.append(PlannedItem(row.video, source, target, action))
    return PlanSnapshot(uuid4().hex, datetime.now(timezone.utc).isoformat(), tuple(items))


def _verify_item(item: PlannedItem):
    assert item.source is not None and item.target is not None
    try:
        if file_mark(item.video) != item.video_mark:
            raise StalePlan(f"视频文件已变化，请重新扫描：{item.video}")
        if file_mark(item.source) != item.source_mark:
            raise StalePlan(f"源字幕已变化，请重新扫描：{item.source}")
        if dir_mark(item.target.parent) != item.target_dir_mark:
            raise StalePlan(f"目标文件夹已变化，请重新扫描：{item.target.parent}")
    except FileNotFoundError as error:
        raise StalePlan(f"预览中的文件已消失，请重新扫描：{error.filename}") from error
    if path_present(item.target):
        raise StalePlan(f"目标名称已被占用，请重新扫描：{item.target}")
    if not item.target.parent.is_dir():
        raise StalePlan(f"目标文件夹已不存在：{item.target.parent}")


def verify_snapshot(snapshot: PlanSnapshot):
    """Check every planned rename before the first file is changed."""
    for item in snapshot.changes:
        _verify_item(item)


def _copy_across_devices(item: PlannedItem):
    """Exclusive destination creation; delete the source only after a checked copy."""
    assert item.source is not None and item.target is not None
    created: FileMark | None = None
    try:
        with item.source.open("rb") as reader, item.target.open("xb") as writer:
            created = file_mark(item.target)
            shutil.copyfileobj(reader, writer, length=1024 * 1024)
            writer.flush()
            os.fsync(writer.fileno())
        if file_mark(item.source) != item.source_mark:
            raise StalePlan(f"复制时源字幕发生变化：{item.source}")
        # The destination is owned by this operation only while its identity is unchanged.
        if created and (file_mark(item.target).device, file_mark(item.target).inode) != (created.device, created.inode):
            raise StalePlan(f"复制时目标文件被替换：{item.target}")
        item.source.unlink()
    except Exception:
        if created:
            try:
                info = file_mark(item.target)
                if (info.device, info.inode) == (created.device, created.inode):
                    item.target.unlink()
            except FileNotFoundError:
                pass
        raise


def _move_without_overwrite(item: PlannedItem):
    """Windows rename refuses an occupied target; other platforms use an exclusive link."""
    assert item.source is not None and item.target is not None
    if sys.platform == "win32":
        try:
            os.rename(item.source, item.target)
            return
        except OSError as error:
            if error.errno != errno.EXDEV:
                raise
    else:
        try:
            os.link(item.source, item.target, follow_symlinks=False)
        except OSError as error:
            if error.errno != errno.EXDEV:
                raise
        else:
            try:
                item.source.unlink()
            except Exception:
                item.target.unlink()
                raise
            return
    _copy_across_devices(item)


@dataclass(frozen=True)
class ItemResult:
    video: Path
    source: Path | None
    target: Path | None
    status: str  # success, error, blocked, cancelled, skipped, unmatched, unchanged
    error: str = ""


@dataclass
class BatchResult:
    run_id: str
    snapshot_id: str
    started_at: str
    finished_at: str
    items: tuple[ItemResult, ...]
    issue: str = ""
    history_error: str = ""

    def count(self, status: str) -> int:
        return sum(item.status == status for item in self.items)

    def to_record(self) -> dict:
        return {
            "run_id": self.run_id, "snapshot_id": self.snapshot_id,
            "started_at": self.started_at, "finished_at": self.finished_at,
            "issue": self.issue,
            "items": [{"video": str(item.video), "source": str(item.source) if item.source else None,
                       "target": str(item.target) if item.target else None,
                       "status": item.status, "error": item.error} for item in self.items],
        }


def run_batch(snapshot: PlanSnapshot, *, should_stop: Callable[[], bool] = lambda: False,
              progress: Callable[[int, int, str], None] = lambda done, total, name: None,
              history: HistoryStore | None = None) -> BatchResult:
    """Apply only the frozen destinations; report every planned item."""
    started = datetime.now(timezone.utc).isoformat()
    issue = ""
    try:
        if snapshot.pending_count:
            raise StalePlan("仍有待确认的匹配，请先确认或跳过")
        verify_snapshot(snapshot)
    except (StalePlan, OSError) as error:
        issue = str(error)
    done = 0
    total = len(snapshot.changes)
    stopped = False
    items = []
    for item in snapshot.items:
        if item.action != "rename":
            status = "skipped" if item.action == "pending" else item.action
            items.append(ItemResult(item.video, item.source, item.target, status))
            continue
        if issue:
            result = ItemResult(item.video, item.source, item.target, "blocked", issue)
        elif stopped or should_stop():
            stopped = True
            result = ItemResult(item.video, item.source, item.target, "cancelled", "用户在此项开始前停止")
        else:
            try:
                _verify_item(item)
                _move_without_overwrite(item)
                result = ItemResult(item.video, item.source, item.target, "success")
            except StalePlan as error:
                issue = str(error)
                result = ItemResult(item.video, item.source, item.target, "blocked", issue)
            except OSError as error:
                result = ItemResult(item.video, item.source, item.target, "error", str(error))
        items.append(result)
        done += 1
        progress(done, total, item.source.name if item.source else "")
    finished = datetime.now(timezone.utc).isoformat()
    result = BatchResult(uuid4().hex, snapshot.snapshot_id, started, finished, tuple(items), issue)
    if history is not None:
        try:
            history.append(result)
        except OSError as error:
            result.history_error = str(error)
    return result


class HistoryStore:
    def __init__(self, path: Path | None = None):
        if path is None:
            base = os.environ.get("YINGXU_HISTORY_DIR")
            path = Path(base) / "history.jsonl" if base else Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "YingXu" / "history.jsonl"
        self.path = Path(path)

    def append(self, result: BatchResult):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(result.to_record(), ensure_ascii=False, separators=(",", ":")) + "\n"
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())

    def recent(self, limit: int = 30) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as handle:
            lines = deque(handle, maxlen=limit)
        entries = []
        for line in reversed(lines):
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries


def export_result(result: BatchResult, path: Path):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(result.to_record(), handle, ensure_ascii=False, indent=2)
        handle.write("\n")
