"""Windows handle guards: validate and rename/delete the opened object, not a raced path."""
import ctypes as C
import hashlib
import os
from pathlib import Path

from ..domain.errors import ProtocolError
from ..domain.matching import check_cancelled
from ..domain.operations import FileVersion


class FileTime(C.Structure):
    _fields_ = [('low', C.c_uint32), ('high', C.c_uint32)]

    @classmethod
    def number(cls, value):
        return cls(value & 0xffffffff, value >> 32)

    def value(self):
        return self.low | self.high << 32


class FileInformation(C.Structure):
    _fields_ = [('attributes', C.c_uint32), ('created', FileTime), ('accessed', FileTime),
                ('modified', FileTime), ('volume', C.c_uint32), ('size_high', C.c_uint32),
                ('size_low', C.c_uint32), ('links', C.c_uint32),
                ('index_high', C.c_uint32), ('index_low', C.c_uint32)]


class RenameInformation(C.Structure):
    _fields_ = [('replace', C.c_ubyte), ('root', C.c_void_p),
                ('length', C.c_uint32), ('name', C.c_wchar * 1)]


def api():
    if os.name != 'nt':
        raise ProtocolError('UNSUPPORTED_PLATFORM', '文件执行目前仅支持 Windows；可继续使用只读业务原型。')
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [C.c_wchar_p, C.c_uint32, C.c_uint32, C.c_void_p,
                                   C.c_uint32, C.c_uint32, C.c_void_p]
    kernel.CreateFileW.restype = C.c_void_p
    kernel.CloseHandle.argtypes = [C.c_void_p]
    kernel.GetFileInformationByHandle.argtypes = [C.c_void_p, C.POINTER(FileInformation)]
    kernel.SetFileInformationByHandle.argtypes = [C.c_void_p, C.c_int, C.c_void_p, C.c_uint32]
    kernel.SetFileTime.argtypes = [C.c_void_p, C.POINTER(FileTime), C.POINTER(FileTime), C.POINTER(FileTime)]
    kernel.GetFinalPathNameByHandleW.argtypes = [C.c_void_p, C.c_wchar_p, C.c_uint32, C.c_uint32]
    return kernel


def failure():
    number = C.get_last_error()
    if number in {32, 33, 303}:
        raise ProtocolError('FILE_IN_USE', '文件正在被其他程序占用，请关闭占用后重新预览。')
    if number in {80, 183}:
        raise FileExistsError(number, '目标位置已被占用，未覆盖已有文件。')
    raise C.WinError(number)


class WindowsFile:
    def __init__(self, path, *, delete=False, create=False, directory=False):
        self.path = Path(path)
        self.kernel = api()
        self.stream = None
        access = 0x80000000 | (0x40000000 if create else 0) | (0x10000 if delete or create else 0)
        if directory:
            access = 0x80  # FILE_READ_ATTRIBUTES
        flags = 0x00200000 | (0x02000000 if directory else 0x80)  # Do not follow final reparse points.
        handle = self.kernel.CreateFileW(str(self.path), access, 3 if directory else 1,
                                        None, 1 if create else 3, flags, None)
        if handle == C.c_void_p(-1).value:
            failure()
        self.handle = handle
        try:
            info = self.information()
            if info.attributes & 0x400 or bool(info.attributes & 0x10) != directory:
                raise ProtocolError('UNSAFE_PATH', '该路径是链接或文件类型已变化，未自动处理。')
            if not (info.index_low or info.index_high):
                raise ProtocolError('UNSUPPORTED_FILE_ID', '此文件系统未提供可核对的文件身份，未自动处理。')
            if not directory:
                import msvcrt
                descriptor = msvcrt.open_osfhandle(handle, os.O_BINARY | (os.O_RDWR if create else os.O_RDONLY))
                self.stream = os.fdopen(descriptor, 'r+b' if create else 'rb', buffering=0)
        except BaseException:
            self.close()
            raise

    def information(self):
        value = FileInformation()
        if not self.kernel.GetFileInformationByHandle(self.handle, C.byref(value)):
            failure()
        return value

    def identity(self):
        info = self.information()
        volume = f'{info.volume:08x}'
        return {'identity': f'{volume}:{info.index_high:08x}{info.index_low:08x}', 'volume': volume}

    def version(self, *, digest=True, should_stop=None):
        before = self.information()
        value = ''
        if digest:
            self.stream.seek(0)
            hashed = hashlib.sha256()
            while block := self.stream.read(1024 * 1024):
                check_cancelled(should_stop)
                hashed.update(block)
            value = hashed.hexdigest()
        after = self.information()
        if (before.size_high, before.size_low, before.modified.value()) != (after.size_high, after.size_low, after.modified.value()):
            raise ProtocolError('FILE_CHANGED', '读取期间文件发生变化，请重新预览。')
        return FileVersion(self.identity()['identity'], f'{after.volume:08x}',
                           after.size_low | after.size_high << 32,
                           after.modified.value(), after.created.value(), value).to_dict()

    def expect(self, expected, *, digest=True):
        observed = self.version(digest=digest)
        if observed != expected:
            raise ProtocolError('FILE_CHANGED', '文件身份或内容与预览不一致，未自动继续。')
        return observed

    def copy_from(self, reader, expected, checkpoint=lambda point: None):
        reader.stream.seek(0)
        digest = hashlib.sha256()
        while block := reader.stream.read(1024 * 1024):
            remaining = memoryview(block)
            while remaining:
                written = self.stream.write(remaining)
                if not written:
                    raise OSError('备份写入未完成，原文件保留。')
                remaining = remaining[written:]
            digest.update(block)
            checkpoint('chunk')
        if digest.hexdigest() != expected['digest']:
            raise ProtocolError('FILE_CHANGED', '复制内容未通过校验，源文件与临时文件均保留。')
        self.stream.flush()
        os.fsync(self.stream.fileno())
        created, modified = FileTime.number(expected['created']), FileTime.number(expected['modified'])
        if not self.kernel.SetFileTime(self.handle, C.byref(created), None, C.byref(modified)):
            failure()
        os.fsync(self.stream.fileno())
        version = self.version(digest=True)
        if version['size'] != expected['size'] or version['digest'] != expected['digest']:
            raise ProtocolError('COPY_INCOMPLETE', '落盘副本校验失败，原文件与临时文件均保留。')
        return version

    def rename(self, destination):
        encoded = str(Path(destination)).encode('utf-16-le')
        offset = RenameInformation.name.offset
        buffer = C.create_string_buffer(max(C.sizeof(RenameInformation), offset + len(encoded) + 2))
        value = C.cast(buffer, C.POINTER(RenameInformation)).contents
        value.replace = 0
        value.root = None
        value.length = len(encoded)
        C.memmove(C.addressof(buffer) + offset, encoded, len(encoded))
        if not self.kernel.SetFileInformationByHandle(self.handle, 3, buffer, len(buffer)):
            failure()
        result = C.create_unicode_buffer(32768)
        length = self.kernel.GetFinalPathNameByHandleW(self.handle, result, len(result), 0)
        if not length or length >= len(result):
            failure()
        actual = result.value
        if actual.startswith('\\\\?\\UNC\\'):
            actual = '\\\\' + actual[8:]
        elif actual.startswith('\\\\?\\'):
            actual = actual[4:]
        if os.path.normcase(os.path.abspath(actual)) != os.path.normcase(os.path.abspath(destination)):
            raise ProtocolError('COMMIT_PATH_MISMATCH', '系统返回的目标路径与计划不一致，已停止后续处理。')

    def remove(self):
        flags = C.c_uint32(3)  # DELETE | POSIX_SEMANTICS; never ignore read-only attributes.
        if not self.kernel.SetFileInformationByHandle(self.handle, 21, C.byref(flags), C.sizeof(flags)):
            if C.get_last_error() not in {50, 87}:
                failure()
            delete = C.c_int(1)
            if not self.kernel.SetFileInformationByHandle(self.handle, 4, C.byref(delete), C.sizeof(delete)):
                failure()
        self.close()

    def close(self):
        if self.stream is not None:
            self.stream.close()
            self.stream = None
            self.handle = None
        elif getattr(self, 'handle', None) is not None:
            self.kernel.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
