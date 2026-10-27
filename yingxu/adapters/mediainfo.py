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

from ..domain.matching import check_cancelled
from ..domain.media import MAX_RESPONSE, MAX_READ, EngineUnavailable, track_info

_library_checked = False

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
            command.extend(["-m", "yingxu.adapters.mediainfo", "--probe"])
        else:
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


if __name__ == '__main__':
    if sys.argv[1:] != ['--probe']:
        raise SystemExit(2)
    raise SystemExit(probe_main())
