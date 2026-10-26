"""Private download staging only. No extraction, import, or media-directory writes."""
import json
from pathlib import Path, PureWindowsPath
import re
from uuid import uuid4, UUID
from urllib.parse import urlsplit

from .zimuku import source_url

MAX_DOWNLOAD_BYTES = 64 * 1024 * 1024
MAX_SESSION_BYTES = 256 * 1024 * 1024
MAX_SESSION_FILES = 20
EXTENSIONS = frozenset({".srt", ".ass", ".ssa", ".vtt", ".sub", ".sup", ".idx", ".zip", ".rar", ".7z"})


def same_origin_blob(url, page_url, hosts):
    """Accept a provider's locally generated file only from its exact HTTPS origin.

    Request page/task, type, size and content checks remain in the receiver.
    Data URLs, opaque origins and local/browser schemes are never allowed here.
    """
    if not isinstance(url, str) or not url.startswith('blob:') or len(url) > 2048:
        return False
    inner_url = url[5:]
    if not source_url(page_url, hosts) or not source_url(inner_url, hosts):
        return False
    try:
        inner, page = urlsplit(inner_url), urlsplit(page_url)
        if (inner.scheme, inner.hostname, inner.port or 443) != (page.scheme, page.hostname, page.port or 443):
            return False
        if inner.query or inner.fragment or not inner.path.startswith('/'):
            return False
        UUID(inner.path[1:])
        return True
    except (ValueError, AttributeError):
        return False


def safe_filename(suggested):
    name = PureWindowsPath(suggested).name
    extension = Path(name).suffix.lower()
    if extension not in EXTENSIONS:
        raise ValueError("仅接收字幕或 ZIP / RAR / 7z 字幕压缩包。")
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "_", Path(name).stem)
    stem = re.sub(r"[\u202a-\u202e\u2066-\u2069]", "", stem).strip(" .")[:110] or "subtitle"
    if re.match(r"^(CON|PRN|AUX|NUL|COM[0-9¹²³]|LPT[0-9¹²³])(?:\.|$)", stem, re.I):
        stem = "_" + stem
    return stem + extension


def reserve_download(root, suggested):
    name = safe_filename(suggested)
    directory = Path(root) / uuid4().hex
    directory.mkdir(parents=True, exist_ok=False)
    return directory / name


def inspect_download(path):
    """Recognize a candidate, without treating its name as a matching guarantee."""
    size = path.stat().st_size
    if not 0 < size <= MAX_DOWNLOAD_BYTES:
        raise ValueError("下载为空或超过 64 MiB 限制。")
    with path.open("rb") as stream:
        head = stream.read(65536)
    suffix = path.suffix.lower()
    signatures = {".zip": (b"PK\x03\x04", b"PK\x05\x06"),
                  ".rar": (b"Rar!\x1a\x07",), ".7z": (b"7z\xbc\xaf\x27\x1c",)}
    if suffix in signatures:
        if not head.startswith(signatures[suffix]):
            raise ValueError("下载内容不是对应压缩格式，可能是错误页或验证页。")
        return "archive_pending"
    if suffix == ".sup" and head.startswith(b"PG"):
        return "subtitle_candidate"
    if suffix == ".sub" and head.startswith(b"\x00\x00\x01\xba"):
        return "subtitle_candidate"
    if head.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = head.decode("utf-16", errors="replace")
    else:
        try:
            text = head.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = head.decode("gb18030", errors="replace")
    if head.startswith(b"MZ") or re.search(r"(?i)<!doctype\s+html|<html(?:\s|>)", text[:2048]):
        raise ValueError("收到的是程序或网页，不能作为字幕导入。")
    recognizable = {
        ".srt": r"(?m)\d{1,3}:\d\d:\d\d[,.]\d{3}\s*-->\s*\d{1,3}:\d\d:\d\d",
        ".ass": r"(?im)^\[Events\]", ".ssa": r"(?im)^\[Events\]",
        ".vtt": r"\AWEBVTT(?:\s|$)", ".sub": r"(?m)^\{\d+\}\{\d+\}",
        ".idx": r"(?im)^# VobSub index file",
    }
    if suffix not in recognizable or not re.search(recognizable[suffix], text):
        raise ValueError("未识别到有效字幕结构，保留在暂存区供检查。")
    return "subtitle_candidate"


def write_receipt(path, data):
    """Each unique directory gets one receipt; never overwrite an existing file."""
    with path.with_name("receipt.json").open("x", encoding="utf-8") as stream:
        json.dump({"schema": 1, "fileName": path.name, **data}, stream, ensure_ascii=False, indent=2)
