"""Pinned read handle on Windows; never follows the final symlink or rewrites text."""
import codecs
from contextlib import contextmanager, ExitStack
import hashlib
import os
from pathlib import Path

from ..domain.errors import ProtocolError
from ..domain.matching import check_cancelled
from ..domain.subtitle_document import MAX_BYTES, SubtitleRead

ENCODINGS=frozenset({'auto','utf-8','utf-8-sig','utf-16-le','utf-16-be','utf-32-le','utf-32-be','gb18030','big5','shift_jis'})
BOMS=((codecs.BOM_UTF32_LE,'utf-32'),(codecs.BOM_UTF32_BE,'utf-32'),
      (codecs.BOM_UTF8,'utf-8-sig'),(codecs.BOM_UTF16_LE,'utf-16'),(codecs.BOM_UTF16_BE,'utf-16'))


@contextmanager
def read_handle(path):
    path=Path(path)
    if not path.is_absolute() or path.is_symlink():raise ProtocolError('UNSAFE_PATH','字幕路径无效或为链接')
    if os.name=='nt':
        from .windows_files import WindowsFile
        with ExitStack() as stack:
            # Pin non-root ancestors so a directory cannot be replaced by a
            # junction between validation and reading the registered file.
            for parent in reversed(path.parents):
                if parent!=parent.parent:stack.enter_context(WindowsFile(parent,directory=True))
            handle=stack.enter_context(WindowsFile(path))
            yield handle.stream
    else:
        # Portable validation path; production Windows uses its existing handle guard.
        descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            import stat
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise ValueError('字幕不是普通文件')
            yield stream


class LocalSubtitleReader:
    def read(self, path, *, encoding='auto', should_stop=None):
        if encoding not in ENCODINGS:raise ValueError('不支持该编码')
        format=Path(path).suffix.casefold().lstrip('.')
        with read_handle(path) as stream:
            before=os.fstat(stream.fileno())
            if before.st_size>MAX_BYTES:
                return SubtitleRead(format,None,'','',issue='文件超过 8 MiB，未完整检查')
            parts=[];size=0
            while block:=stream.read(min(65536,MAX_BYTES+1-size)):
                check_cancelled(should_stop);size+=len(block)
                if size>MAX_BYTES:raise ValueError('字幕大小在读取过程中超过限制')
                parts.append(block)
            after=os.fstat(stream.fileno())
            if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
                raise ProtocolError('FILE_CHANGED','读取时字幕发生变化，请重新检查')
        raw=b''.join(parts);digest=hashlib.sha256(raw).hexdigest()
        if format not in {'srt','ass','ssa','vtt'}:return SubtitleRead(format,'','',digest,bytes_read=size)
        chosen=encoding
        if encoding=='auto':
            chosen=next((codec for bom,codec in BOMS if raw.startswith(bom)),'utf-8')
            if chosen=='utf-8' and b'\0' in raw:
                candidates=[]
                for codec in ('utf-16-le','utf-16-be'):
                    try:candidates.append((codec,raw.decode(codec,errors='strict')[:160]))
                    except UnicodeError:pass
                return SubtitleRead(format,None,'',digest,tuple(candidates),'发现无 BOM 的宽字符数据，请手动选择编码。',size)
        try:
            text=raw.decode(chosen,errors='strict')
            if text.startswith('\ufeff'):text=text[1:]
            return SubtitleRead(format,text,chosen,digest,bytes_read=size)
        except UnicodeError:
            candidates=[]
            for codec in ('gb18030','big5','shift_jis'):
                try:
                    text=raw.decode(codec,errors='strict')
                    candidates.append((codec,text[:160]))
                except UnicodeError:pass
            return SubtitleRead(format,None,chosen,digest,tuple(candidates),
                '无法按所选编码严格解码。请选择编码核对；原文件未改写。',size)
