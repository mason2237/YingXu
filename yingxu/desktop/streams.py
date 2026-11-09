"""Inherited standard streams for private frozen workers, independent of services."""
import ctypes
import io
import os
import sys


def attach_inherited_streams():
    """Windowed PyInstaller clears sys streams even when its parent supplied pipes."""
    if os.name != 'nt':return
    import msvcrt
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetStdHandle.argtypes = [ctypes.c_uint32];kernel.GetStdHandle.restype = ctypes.c_void_p
    for name, number, flags, mode in [('stdin', -10, os.O_RDONLY, 'rb'),
                                      ('stdout', -11, os.O_WRONLY, 'wb'), ('stderr', -12, os.O_WRONLY, 'wb')]:
        current = getattr(sys, name, None)
        if current is not None:
            if hasattr(current, 'reconfigure'):
                current.reconfigure(encoding='utf-8', errors='replace', newline='\n', write_through=True)
            continue
        handle = kernel.GetStdHandle(number & 0xffffffff)
        if not handle or handle == ctypes.c_void_p(-1).value:
            stream = open(os.devnull, mode, buffering=0)
        else:
            stream = os.fdopen(msvcrt.open_osfhandle(handle, flags | os.O_BINARY), mode, buffering=0)
        setattr(sys, name, io.TextIOWrapper(stream, encoding='utf-8', errors='replace', newline='\n', write_through=True))

