"""Local read-only media inventory. No GUI or application-layer dependency."""
import os
from pathlib import Path
from ..domain.matching import VIDEO_EXTS, SUB_EXTS, check_cancelled


def collect_media(folder: Path, recursive: bool = True, *, should_stop=None,
                  progress=None, on_error=None) -> tuple[list[Path], list[Path]]:
    videos: list[Path] = []
    subtitles: list[Path] = []
    visited = 0
    if recursive:
        for current, dirs, files in os.walk(folder, onerror=on_error or (lambda _error: None)):
            check_cancelled(should_stop)
            dirs.sort(key=str.casefold)
            for filename in files:
                check_cancelled(should_stop)
                visited += 1
                path = Path(current) / filename
                suffix = path.suffix.casefold()
                if suffix in VIDEO_EXTS:
                    videos.append(path)
                elif suffix in SUB_EXTS:
                    subtitles.append(path)
            if progress:
                progress(visited, len(videos), len(subtitles))
    else:
        try:
            for path in folder.iterdir():
                check_cancelled(should_stop)
                visited += 1
                if not path.is_file():
                    continue
                suffix = path.suffix.casefold()
                if suffix in VIDEO_EXTS:
                    videos.append(path)
                elif suffix in SUB_EXTS:
                    subtitles.append(path)
                if progress and visited % 100 == 0:
                    progress(visited, len(videos), len(subtitles))
        except OSError as error:
            if on_error:
                on_error(error)
    check_cancelled(should_stop)
    if progress:
        progress(visited, len(videos), len(subtitles))
    key = lambda path: (str(path.parent).casefold(), path.name.casefold())
    videos.sort(key=key)
    subtitles.sort(key=key)
    return videos, subtitles



class LocalFilesystem:
    def collect(self, folder, recursive=True, **options):
        return collect_media(folder, recursive, **options)

    def exists(self, path):
        try:
            Path(path).lstat()
            return True
        except FileNotFoundError:
            return False

    def inside(self, path, root):
        return not path.is_symlink() and path.resolve(strict=True).is_relative_to(root)

    def directory_mark(self, folder):
        from .legacy_operations import dir_mark
        mark = dir_mark(folder)
        with os.scandir(folder):
            pass
        return mark

    def file_mark(self, path):
        from .legacy_operations import file_mark
        return file_mark(path)

    def fingerprint(self, path):
        from dataclasses import asdict
        import hashlib
        path = Path(path)
        before = self.file_mark(path)
        value = {'mark':asdict(before)}
        if path.suffix.casefold() in SUB_EXTS:
            with path.open('rb') as stream:
                value['digest'] = hashlib.file_digest(stream,'sha256').hexdigest()
        if self.file_mark(path) != before:
            raise ValueError('读取草稿时文件发生变化，请重新扫描。')
        return value
