"""Read embedded subtitle metadata locally. Never extract or change media.

The DLL runs in a bounded helper process. Its input is an already opened local
file buffer, so container references cannot turn into network/file requests.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
from queue import Queue, Empty
import re
import subprocess
import sys
from threading import Thread
from time import monotonic
from uuid import uuid4

from .core import check_cancelled

LANGUAGES = {
    "chinese": "中文（双语优先）", "bilingual": "仅中英双语",
    "simplified": "简体中文", "traditional": "繁体中文",
    "english": "英语", "japanese": "日语", "korean": "韩语", "any": "任意语言（含未标注）",
}
DEFAULT_OPTIONS = {"enabled": True, "language": "chinese"}
MAX_RESPONSE = 256 * 1024
MAX_READ = 16 * 1024 * 1024
_library_checked = False


class EngineUnavailable(RuntimeError):
    pass


def clean(value, limit=256):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _families(value):
    value = value.casefold()
    groups = {
        "zh": r"\b(?:zh(?:-[a-z]+)?|zho|chi|chinese|chs|cht)\b|中文|简体|繁体|簡體|繁體|简中|簡中|繁中",
        "en": r"\b(?:en(?:-[a-z]+)?|eng|english)\b|英语|英語",
        "ja": r"\b(?:ja|jpn|japanese)\b|日语|日語",
        "ko": r"\b(?:ko|kor|korean)\b|韩语|韓語",
    }
    return {key for key, pattern in groups.items() if re.search(pattern, value)}


def track_info(track, number):
    raw, title = clean(track.language, 80), clean(track.title)
    declared, named = _families(raw), _families(title)
    if not declared and raw and raw.casefold() not in {"und", "undefined", "unknown"}:
        declared = {"other"}
    bilingual = bool(re.search(r"中英|简英|繁英|簡英|(?:chs|cht|chinese|中文|简中|繁中)\W{0,8}(?:eng|english|英文|英语)|(?:eng|english|英文|英语)\W{0,8}(?:chs|cht|chinese|中文|简中|繁中)", title, re.I))
    if bilingual: named |= {"zh", "en"}
    ambiguous = bool(declared and named and declared.isdisjoint(named))
    families = set() if ambiguous else declared or named
    if bilingual and not ambiguous:
        families |= {"zh", "en"}
    script = ""
    if "zh" in families:
        simplified = bool(re.search(r"zh-(?:cn|sg|hans)|简体|簡體|简中|簡中|简英|簡英|\bchs\b|\bsc\b|\bsimplified\b", raw+" "+title, re.I))
        traditional = bool(re.search(r"zh-(?:tw|hk|mo|hant)|繁体|繁體|繁中|繁英|\bcht\b|\btc\b|\btraditional\b", raw+" "+title, re.I))
        script = "simplified" if simplified and not traditional else "traditional" if traditional and not simplified else ""
    labels = {"zh": "简体中文" if script == "simplified" else "繁体中文" if script == "traditional" else "中文",
              "en": "英语", "ja": "日语", "ko": "韩语"}
    label = "中英双语" if {"zh", "en"} <= families else " / ".join(labels.get(key, raw) for key in sorted(families))
    if not label:
        label = "语言标注冲突" if ambiguous else raw if raw and raw.casefold() not in {"und", "undefined", "unknown"} else "语言未标注"
    codec = clean(track.format or track.codec_id, 80) or "未知格式"
    yes = lambda value: clean(value).casefold() in {"yes", "true", "1"}
    forced = yes(track.forced) or bool(re.search(r"\bforced\b|强制|強制|(?:仅|僅).{0,3}(?:歌曲|对白|對白)|signs?\s*(?:&|and|/)\s*songs?", title, re.I))
    commentary = bool(re.search(r"\bcommentary\b|导演.{0,2}(?:评论|解说)|導演.{0,2}(?:評論|解說)", title, re.I))
    return {"trackId": f"track-{number}", "title": title, "language": label,
            "declaredLanguage": raw, "families": sorted(families), "script": script,
            "codec": codec, "kind": "bitmap" if re.search(r"pgs|vobsub|dvb|rle", codec, re.I) else "text",
            "default": yes(track.default), "forced": forced, "commentary": commentary,
            "ambiguous": ambiguous, "languageSource": "metadata+title" if declared and bilingual and not {"zh","en"} <= declared else "metadata" if declared else "title" if families else "unknown"}


def assess(info, options):
    """Unknown/contradictory language never silently passes a language rule."""
    result = deepcopy(info)
    tracks = result.get("tracks", [])
    language = options["language"]
    accepted = []
    for track in tracks:
        family = set(track["families"])
        allowed = (language == "any" or
                   language == "chinese" and "zh" in family or
                   language == "bilingual" and {"zh", "en"} <= family or
                   language in {"simplified", "traditional"} and track["script"] == language or
                   language == "english" and "en" in family or
                   language == "japanese" and "ja" in family or
                   language == "korean" and "ko" in family)
        if allowed and not track["forced"] and not track["commentary"] and (not track["ambiguous"] or language == "any"):
            accepted.append(track["trackId"])
    satisfied = result.get("status") == "ok" and bool(accepted)
    if satisfied:
        reason = f"内嵌字幕符合“{LANGUAGES[language]}”，已通过，无需外挂字幕。"
    elif result.get("status") == "disabled":
        reason = "未启用视频内字幕检查。"
    elif result.get("status") != "ok":
        reason = result.get("error") or "未能读取视频内字幕信息，保留外挂匹配结果。"
    elif not tracks:
        reason = "未发现独立字幕轨；烧录在画面中的字幕无法通过轨道信息判断。"
    elif all(track["forced"] or track["commentary"] for track in tracks):
        reason = "仅有强制/片段或评论字幕，不按完整字幕自动通过。"
    elif result.get("truncated"):
        reason = "本次仅检查前 64 条字幕轨，未确认满足语言要求，请人工核对。"
    elif any(track["ambiguous"] or not track["families"] for track in tracks):
        reason = "内嵌字幕语言未标明或标注冲突，保留待处理，请核对语言。"
    else:
        reason = f"内嵌语言不符合“{LANGUAGES[language]}”，继续匹配外挂字幕。"
    result.update(satisfied=satisfied, acceptedTrackIds=accepted if satisfied else [],
                  policy=language, policyLabel=LANGUAGES[language], reason=reason)
    return result


class _BudgetFile:
    mode = "rb"

    def __init__(self, handle):
        self.handle, self.remaining = handle, MAX_READ
        self.deadline = monotonic() + 3

    def read(self, size):
        if monotonic() > self.deadline or size > self.remaining:
            raise ValueError("字幕轨道读取超过预算，保留待处理。")
        value = self.handle.read(size)
        self.remaining -= len(value)
        return value

    def seek(self, *args):
        return self.handle.seek(*args)

    def tell(self):
        return self.handle.tell()


def read_metadata(path):
    global _library_checked
    from pymediainfo import MediaInfo
    import pymediainfo
    library = Path(pymediainfo.__file__).with_name("MediaInfo.dll")
    if not library.is_file():
        raise EngineUnavailable("本地字幕读取组件缺失，请完整解压运行包。")
    if not _library_checked:
        if not MediaInfo.can_parse(library_file=str(library)):
            raise EngineUnavailable("本地字幕读取组件未能加载，请完整解压运行包。")
        _library_checked = True
    path = Path(path)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError("视频路径无效或为链接，请重新扫描。")
    with path.open("rb") as handle:
        info = MediaInfo.parse(_BudgetFile(handle), library_file=str(library), parse_speed=0,
            full=False, buffer_size=64 * 1024,
            mediainfo_options={"File_ReferencedFiles_Ignore":"1", "File_TestContinuousFileNames":"0"})
    if not any(track.track_type == "Video" for track in info.tracks):
        return {"status": "invalid", "tracks": [], "error": "未识别到有效视频容器，未按内嵌字幕通过。"}
    tracks = [track_info(track, number) for number, track in enumerate(
        (track for track in info.tracks if track.track_type == "Text"), 1)]
    return {"status": "ok", "tracks": tracks[:64], "truncated": len(tracks) > 64}


def probe_main():
    """Internal read-only JSON-lines helper; no GUI, commands, URLs or output files."""
    input_stream = getattr(sys.stdin, "buffer", None)
    output_stream = getattr(sys.stdout, "buffer", None)
    if os.name == "nt" and (input_stream is None or output_stream is None):
        # Windowed PyInstaller sets sys.stdin/stdout to None even when Popen
        # supplied pipes. Use only those inherited handles, never a console.
        import ctypes
        import msvcrt
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetStdHandle.argtypes = [ctypes.c_uint32]
        kernel.GetStdHandle.restype = ctypes.c_void_p
        def pipe(number, flags, mode):
            handle = kernel.GetStdHandle(number & 0xffffffff)
            if not handle or handle == ctypes.c_void_p(-1).value:
                raise OSError("解析进程未提供通信管道")
            return os.fdopen(msvcrt.open_osfhandle(handle, flags | os.O_BINARY), mode, buffering=0)
        if input_stream is None: input_stream = pipe(-10, os.O_RDONLY, "rb")
        if output_stream is None: output_stream = pipe(-11, os.O_WRONLY, "wb")
    if input_stream is None or output_stream is None:
        return 2
    for line in iter(lambda: input_stream.readline(32769), b""):
        nonce = None
        try:
            if len(line) > 32768:
                return 2
            request = json.loads(line)
            if set(request) != {"id", "path"} or not isinstance(request["path"], str):
                return 2
            nonce = request["id"]
            if not isinstance(nonce, str) or not re.fullmatch(r"[0-9a-f]{32}", nonce):
                return 2
            result = read_metadata(request["path"])
        except (ImportError, EngineUnavailable):
            result = {"status": "unavailable", "tracks": [], "error": "本地字幕读取组件不可用，请使用完整运行包。"}
        except Exception:
            result = {"status": "error", "tracks": [], "error": "视频内字幕读取失败，保留外挂匹配结果。"}
        output = json.dumps({"id": nonce, "result": result}, ensure_ascii=True, allow_nan=False).encode("utf-8")
        output_stream.write(output + b"\n");output_stream.flush()
        if result["status"] in {"error", "unavailable"}:
            return 0  # Discard any native parser state after a failed read.
    return 0


class ProbeSession:
    """Reuse one helper per scan, with cancellation and per-video hard timeouts."""
    def __init__(self, should_stop=lambda: False):
        self.should_stop, self.process, self.queue = should_stop, None, None
        self.unavailable = False

    def __enter__(self): return self

    def __exit__(self, *_args): self.close()

    def close(self):
        process, self.process = self.process, None
        if process is None: return
        if process.poll() is None:
            process.terminate()
            try: process.wait(timeout=1)
            except subprocess.TimeoutExpired: process.kill();process.wait(timeout=1)
        for pipe in (process.stdin, process.stdout):
            if pipe: pipe.close()

    def _start(self):
        self.close()
        command = [sys.executable]
        if not getattr(sys, "frozen", False):
            command.append(str(Path(__file__).resolve().parents[1] / "run.py"))
        command.append("--read-embedded-subtitles")
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        self.queue = Queue(maxsize=2)
        process, queue = self.process, self.queue
        def receive():
            try:
                while line := process.stdout.readline(MAX_RESPONSE + 1):
                    if len(line) > MAX_RESPONSE: break
                    queue.put(line, timeout=1)
            except (OSError, ValueError): pass
            finally:
                try: queue.put_nowait(None)
                except Exception: pass
        Thread(target=receive, daemon=True).start()

    def probe(self, path):
        check_cancelled(self.should_stop)
        if self.unavailable:
            return {"status": "unavailable", "tracks": [], "error": "内嵌字幕读取组件不可用，未自动通过。"}
        first = self.process is None or self.process.poll() is not None
        try:
            if first: self._start()
            nonce = uuid4().hex
            self.process.stdin.write(json.dumps({"id": nonce, "path": str(path)}, ensure_ascii=True).encode("utf-8") + b"\n")
            self.process.stdin.flush()
            deadline = monotonic() + (8 if first else 4)
            while monotonic() < deadline:
                check_cancelled(self.should_stop)
                try: line = self.queue.get(timeout=.05)
                except Empty: continue
                if line is None: raise ValueError("解析进程结束")
                reply = json.loads(line)
                if reply.get("id") != nonce: raise ValueError("解析响应无效")
                result = reply["result"]
                if result["status"] in {"error", "unavailable"}:
                    self.unavailable = result["status"] == "unavailable"
                    self.close()
                return result
            self.close()
            return {"status": "error", "tracks": [], "error": "内嵌字幕读取超时，保留待处理。"}
        except (OSError, ValueError, KeyError):
            self.close()
            return {"status": "error", "tracks": [], "error": "内嵌字幕解析未完成，未自动通过。"}
