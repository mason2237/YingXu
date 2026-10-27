"""Generated files only; shared by execution, transport and crash checks."""
from pathlib import Path

from yingxu.adapters.legacy_operations import PlannedItem, PlanSnapshot, dir_mark, file_mark


def noop(*args):
    pass


def make_plan(root, execution, *, count=1, destination=None, size=64):
    root = Path(root)
    sources = root / '原字幕'
    targets = Path(destination) if destination else root / '视频'
    sources.mkdir(exist_ok=True)
    targets.mkdir(exist_ok=True)
    items = []
    for index in range(count):
        video = targets / f'剧集.S01E{index+1:02}.mkv'
        source = sources / f'字幕组.S01E{index+1:02}.chs.srt'
        target = targets / f'剧集.S01E{index+1:02}.chs.srt'
        video.write_bytes(b'video must remain unchanged')
        source.write_bytes((f'subtitle-{index}\n'.encode() * (size // 11 + 1))[:size])
        items.append(PlannedItem(video, source, target, 'rename', file_mark(video), file_mark(source), dir_mark(targets)))
    snapshot = PlanSnapshot('generated', '', tuple(items))
    identifier = execution.freeze(snapshot, {'scanId': 'generated', 'revision': 1}, lambda: False, noop)
    return identifier, items


def approve(execution, identifier, *, purpose='execute', session='test-session'):
    preview = execution.issue(identifier, session, purpose)
    execution.claim(identifier, preview['snapshotId'], session, preview['confirmationToken'], True, purposes=(purpose,))
    return preview


def media_snapshot(*directories):
    return {str(path): path.read_bytes() for directory in directories for path in Path(directory).iterdir() if path.is_file()}
