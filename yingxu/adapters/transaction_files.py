"""Windows move sessions, app-owned buffers and same-directory atomic copy commits."""
from contextlib import ExitStack
import os
from pathlib import Path
import shutil
from uuid import uuid4

from ..domain.errors import ProtocolError
from .legacy_operations import dir_mark, file_mark
from .windows_files import WindowsFile


class LocalTransactionFiles:
    def __init__(self, buffer_root):
        self.buffer_root = Path(buffer_root).absolute()
        self.buffer_root.mkdir(parents=True, exist_ok=True)
        with WindowsFile(self.buffer_root, directory=True) as directory:
            self.buffer_identity = directory.identity()

    def inspect(self, path, *, digest=True):
        try:
            with WindowsFile(path) as file:
                return file.version(digest=digest)
        except FileNotFoundError:
            return None

    def parent(self, path):
        with WindowsFile(Path(path).parent, directory=True) as directory:
            return directory.identity()

    def freeze(self, item, should_stop):
        value = {'video': str(item.video), 'source': str(item.source) if item.source else None,
                 'target': str(item.target) if item.target else None, 'action': item.action,
                 'source_version': None, 'video_version': None, 'source_parent': None, 'target_parent': None}
        if item.action != 'rename':
            return value
        source = item.source.parent.resolve(strict=True) / item.source.name
        target = item.target.parent.resolve(strict=True) / item.target.name
        video = item.video.parent.resolve(strict=True) / item.video.name
        with WindowsFile(video) as opened_video, WindowsFile(source) as opened_source:
            if file_mark(video) != item.video_mark or file_mark(source) != item.source_mark or dir_mark(target.parent) != item.target_dir_mark:
                raise ProtocolError('STALE_PLAN', '文件或目录已变化，请重新扫描并预览。')
            if self.inspect(target, digest=False) is not None:
                raise ProtocolError('TARGET_EXISTS', '目标已存在，未覆盖已有文件。')
            value.update(video=str(video), source=str(source), target=str(target),
                         video_version=opened_video.version(digest=False),
                         source_version=opened_source.version(should_stop=should_stop),
                         source_parent=self.parent(source), target_parent=self.parent(target))
        return value

    def allocate_buffer(self, run_id, index):
        return str(self.buffer_root / f'{run_id}-{index}-{uuid4().hex}.buffer')

    def allocate_stage(self, spec, run_id, index):
        return str(Path(spec['target']).parent / f'.yingxu-{run_id}-{index}-{uuid4().hex}.part')

    def session(self, spec, *, missing_source=False):
        return MoveSession(self, spec, missing_source)


class MoveSession:
    def __init__(self, files, spec, missing_source):
        self.files, self.spec, self.missing_source = files, spec, missing_source
        self.stack = ExitStack()
        self.source = None

    def directory(self, path, expected):
        directory = self.stack.enter_context(WindowsFile(path, directory=True))
        if directory.identity() != expected:
            raise ProtocolError('DIRECTORY_CHANGED', '目录已被替换，未自动继续。')
        return directory

    def __enter__(self):
        try:
            self.directory(self.files.buffer_root, self.files.buffer_identity)
            self.directory(Path(self.spec['target']).parent, self.spec['target_parent'])
            if not self.missing_source:
                self.directory(Path(self.spec['source']).parent, self.spec['source_parent'])
                self.source = self.stack.enter_context(WindowsFile(self.spec['source'], delete=True))
                self.source.expect(self.spec['source_version'])
            if self.spec['video_version'] is not None:
                video = self.stack.enter_context(WindowsFile(self.spec['video']))
                video.expect(self.spec['video_version'], digest=False)
            return self
        except BaseException:
            self.stack.close()
            raise

    def ensure_space(self, directory):
        if shutil.disk_usage(directory).free < self.spec['source_version']['size'] + 8 * 1024 * 1024:
            raise ProtocolError('NOT_ENOUGH_SPACE', '可用空间不足；源文件和已有备份均保留。')

    def write_buffer(self, path, created, checkpoint):
        if Path(path).parent != self.files.buffer_root:
            raise ProtocolError('UNSAFE_PATH', '备份位置不属于应用缓存。')
        self.ensure_space(self.files.buffer_root)
        with WindowsFile(path, create=True) as writer:
            created(writer.version(digest=False))
            return writer.copy_from(self.source, self.spec['source_version'], checkpoint)

    def stage(self, buffer_path, buffer_version, destination, created, checkpoint):
        if Path(buffer_path).parent != self.files.buffer_root or Path(destination).parent != Path(self.spec['target']).parent:
            raise ProtocolError('UNSAFE_PATH', '临时文件位置不符合固定计划。')
        self.ensure_space(Path(destination).parent)
        with WindowsFile(buffer_path) as reader:
            reader.expect(buffer_version)
            with WindowsFile(destination, create=True) as writer:
                created(writer.version(digest=False))
                return writer.copy_from(reader, self.spec['source_version'], checkpoint)

    def rename_source(self):
        self.source.expect(self.spec['source_version'])
        self.source.rename(self.spec['target'])
        return self.source.version()

    def commit_stage(self, path, version):
        if Path(path).parent != Path(self.spec['target']).parent:
            raise ProtocolError('UNSAFE_PATH', '提交临时文件不属于目标目录。')
        file = self.stack.enter_context(WindowsFile(path, delete=True))
        file.expect(version)
        file.rename(self.spec['target'])
        return file.version()  # Keep the committed target guarded until source deletion.

    def guard_target(self, version):
        target = self.stack.enter_context(WindowsFile(self.spec['target']))
        target.expect(version)

    def remove_source(self):
        self.source.expect(self.spec['source_version'])
        self.source.remove()
        if self.files.inspect(self.spec['source'], digest=False) is not None:
            raise ProtocolError('SOURCE_DELETE_PENDING', '目标已完成，源文件尚待占用解除，请稍后恢复核对。')

    def __exit__(self, *_):
        self.stack.close()
