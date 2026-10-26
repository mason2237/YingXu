"""Bounded subtitle preparation in private staging; never writes to media folders."""
from dataclasses import dataclass
from contextlib import contextmanager
import locale
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import subprocess
from threading import Timer
from time import monotonic
from uuid import uuid4
import zipfile
import zlib

from ..core import check_cancelled
from ..operations import file_mark, StalePlan
from .downloads import MAX_DOWNLOAD_BYTES, inspect_download, safe_filename

MAX_ENTRIES = 200
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_EXPANDED_BYTES = 32 * 1024 * 1024
MAX_RATIO = 200
SUBTITLES = frozenset({".srt", ".ass", ".ssa", ".vtt", ".sub", ".sup"})


@contextmanager
def native_archive_stream(path, *, member=None, timeout=15):
    """Windows' bundled libarchive streams to stdout; it never extracts to disk."""
    executable = Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/tar.exe'
    if not executable.is_file():
        raise ValueError('系统缺少 tar 解压器；ZIP 仍可使用，RAR / 7z 请改选 ZIP 版本。')
    command = [str(executable), '-tvf' if member is None else '-xOf', str(path)]
    if member is not None:
        # bsdtar matches member arguments as globs, including square brackets.
        literal = ''.join({'[':'\\[',']':'\\]'}.get(char,char) for char in member)
        command += ['--',literal]
    process = subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    expired = []
    def stop():
        expired.append(True)
        try: process.kill()
        except OSError: pass
    timer = Timer(max(.1,timeout),stop);timer.daemon = True;timer.start()
    try:
        yield process.stdout
        code = process.wait(timeout=2)
        if expired: raise ValueError('解压耗时超过限制，已停止此压缩包。')
        if code: raise ValueError('压缩包损坏、需要密码或系统不支持此格式。')
    finally:
        timer.cancel();process.stdout.close()
        if process.poll() is None: process.kill()
        process.wait(timeout=3)


def native_archive_entries(path, deadline):
    with native_archive_stream(path,timeout=deadline-monotonic()) as stream:
        raw = stream.read(256*1024+1)
        if len(raw)>256*1024: raise ValueError('压缩目录超过 256 KiB，未解压。')
    try: text = raw.decode('utf-8')
    except UnicodeDecodeError: text = raw.decode(locale.getpreferredencoding(False))
    lines = text.splitlines()
    if len(lines)>MAX_ENTRIES: raise ValueError('压缩条目超过 200 个，未解压。')
    entries, names = [],set()
    for line in lines:
        parts = line.split(None,8)
        if len(parts)!=9 or not re.fullmatch(r'[-d][rwxStTs-]{9}',parts[0]):
            raise ValueError('压缩包含链接、特殊条目或无法识别的目录，未解压。')
        name = parts[8]
        safe = _member_name(zipfile.ZipInfo(name))
        key = str(safe).casefold()
        if key in names: raise ValueError('压缩包包含重复文件名，未解压。')
        names.add(key)
        if parts[0].startswith('d'): continue
        try: size = int(parts[4])
        except ValueError: raise ValueError('压缩目录中的文件大小无法识别。')
        if not 0<=size<=MAX_FILE_BYTES: raise ValueError('压缩包内单份文件超过 8 MiB。')
        entries.append((name,size,safe))
    if sum(size for _,size,_ in entries)>MAX_EXPANDED_BYTES:
        raise ValueError('压缩包展开大小超过 32 MiB。')
    return entries


@dataclass(frozen=True)
class PreparedSubtitle:
    path: Path
    original_name: str
    mark: object


def private_path(path, root):
    """Reject links/junctions, including staging ancestors, before cache writes."""
    path, root = Path(path).absolute(), Path(root).absolute()
    if not path.is_relative_to(root):
        raise ValueError("下载不属于此暂存目录。")
    for part in (path, *path.parents):
        if part.is_symlink() or part.is_junction():
            raise ValueError("暂存路径包含链接或目录联接，未导入。")
    if path.resolve(strict=True) != path:
        raise ValueError("暂存路径已经变化，未导入。")
    return path


def _check_zip_directory(path):
    # Bound the central directory before ZipFile allocates its entry objects.
    # ZIP64/multivolume are unnecessary for these small subtitle packages.
    with path.open("rb") as stream:
        stream.seek(max(0, path.stat().st_size - 65557))
        tail = stream.read(65557)
    position = tail.rfind(b"PK\x05\x06")
    if position < 0 or len(tail) - position < 22:
        raise ValueError("ZIP 目录缺失或已损坏。")
    _, disk, start_disk, count, total, size, offset, comment = struct.unpack_from("<4s4H2LH", tail, position)
    if (disk or start_disk or count != total or total > MAX_ENTRIES or size > 256 * 1024
            or offset == 0xffffffff or len(tail) - position != 22 + comment):
        raise ValueError("ZIP 条目过多、目录异常或使用了不支持的分卷 / ZIP64 格式。")


def _member_name(info):
    name = info.orig_filename.replace("\\", "/")
    parts = name.rstrip("/").split("/")
    if (not name or len(name) > 600 or name.startswith("/") or "\x00" in name
            or any(part in {"", ".", ".."} or re.search(r'[<>:"|?*\x00-\x1f]', part)
                   or part.endswith((" ", "."))
                   or re.match(r"^(CON|PRN|AUX|NUL|COM[0-9¹²³]|LPT[0-9¹²³])(?:\.|$)", part, re.I)
                   for part in parts)):
        raise ValueError("ZIP 包含不安全的路径或文件名，整个包未导入。")
    mode = info.external_attr >> 16
    if stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR} or info.flag_bits & 1:
        raise ValueError("ZIP 包含链接、特殊文件或加密内容，未导入。")
    return PurePosixPath(name)


def _validate_subtitle(path):
    if inspect_download(path) != "subtitle_candidate":
        raise ValueError("不是可导入的字幕文件。")
    if path.suffix.lower() == ".sub":
        with path.open("rb") as stream:
            if stream.read(4) == b"\x00\x00\x01\xba":
                raise ValueError("VobSub 需要 IDX/SUB 配对，本阶段暂不导入此格式。")


def prepare_download(path, root, expected_mark, *, should_stop=None, budget=None):
    """Return safe cached copies and skipped names. Original downloads are retained."""
    path = private_path(path, root)
    if file_mark(path) != expected_mark:
        raise StalePlan("下载文件已变化，请重新下载后导入。")
    if not 0 < expected_mark.size <= MAX_DOWNLOAD_BYTES:
        raise ValueError("下载为空或超出 64 MiB 限制。")
    output = path.parent / ("prepared-" + uuid4().hex)
    output.mkdir(exist_ok=False)
    files, skipped = [], []
    expanded = 0
    if budget is None:
        budget = {"bytes":MAX_EXPANDED_BYTES,"files":MAX_ENTRIES}

    def copy_stream(reader, name, expected_size):
        nonlocal expanded
        if not 0 < expected_size <= MAX_FILE_BYTES:
            raise ValueError("字幕为空或单份超过 8 MiB。")
        if expected_size > budget["bytes"] or budget["files"] <= 0:
            raise ValueError("本批导入已达到文件数量或解压大小限制。")
        directory = output / uuid4().hex
        directory.mkdir(exist_ok=False)
        budget["files"] -= 1
        target = directory / safe_filename(name)
        written = 0
        with target.open("xb") as writer:
            while True:
                check_cancelled(should_stop)
                chunk = reader.read(65536)
                if not chunk:
                    break
                written += len(chunk)
                expanded += len(chunk)
                if written > min(MAX_FILE_BYTES, expected_size) or expanded > MAX_EXPANDED_BYTES:
                    raise ValueError("字幕解压大小超出限制。")
                budget["bytes"] -= len(chunk)
                writer.write(chunk)
        if written != expected_size:
            raise ValueError("字幕长度与压缩目录不一致。")
        _validate_subtitle(target)
        return PreparedSubtitle(target, name, file_mark(target))

    try:
        if path.suffix.lower() in {'.rar','.7z'}:
            deadline = monotonic()+20
            for member,size,name in native_archive_entries(path,deadline):
                check_cancelled(should_stop)
                if name.suffix.lower() not in SUBTITLES:
                    skipped.append(f'{name.name}：不是支持的独立字幕');continue
                try:
                    if monotonic()>=deadline: raise ValueError('解压耗时超过限制。')
                    with native_archive_stream(path,member=member,timeout=deadline-monotonic()) as reader:
                        prepared = copy_stream(reader,name.name,size)
                    files.append(prepared)
                except ValueError as error: skipped.append(f'{name.name}：{error}')
        elif path.suffix.lower() == ".zip":
            _check_zip_directory(path)
            with zipfile.ZipFile(path) as archive:
                infos = archive.infolist()
                if len(infos) > MAX_ENTRIES:
                    raise ValueError("ZIP 条目超过 200 个。")
                names, entries = set(), []
                for info in infos:
                    check_cancelled(should_stop)
                    name = _member_name(info)
                    key = str(name).casefold()
                    if key in names:
                        raise ValueError("ZIP 包含重复文件名，未导入。")
                    names.add(key)
                    if info.is_dir():
                        continue
                    if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                        raise ValueError("ZIP 使用不支持的压缩算法。")
                    if (info.file_size > MAX_FILE_BYTES or info.file_size / max(1, info.compress_size) > MAX_RATIO):
                        raise ValueError("ZIP 单份文件过大或压缩比异常，未导入。")
                    if name.suffix.lower() not in SUBTITLES:
                        skipped.append(f"{name.name}：不是支持的独立字幕")
                        continue
                    entries.append((info, name.name))
                if sum(info.file_size for info, _ in entries) > MAX_EXPANDED_BYTES:
                    raise ValueError("ZIP 字幕总大小超过 32 MiB。")
                for info, name in entries:
                    with archive.open(info) as reader:
                        try:
                            files.append(copy_stream(reader, name, info.file_size))
                        except ValueError as error:
                            skipped.append(f"{name}：{error}")
        elif path.suffix.lower() in SUBTITLES:
            with path.open("rb") as reader:
                files.append(copy_stream(reader, path.name, expected_mark.size))
        else:
            raise ValueError("不支持此字幕格式。")
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError, zlib.error, EOFError) as error:
        raise ValueError("字幕包已损坏或格式不受支持，未导入。") from error
    if file_mark(path) != expected_mark:
        raise StalePlan("检查时下载文件发生变化，未导入。")
    if not files:
        raise ValueError("没有可导入的独立字幕。" + "；".join(skipped[:3]))
    return files, skipped
