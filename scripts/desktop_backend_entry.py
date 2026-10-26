"""Frozen private helper modes. The public application entry is Electron's EXE."""
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
        if getattr(sys, name, None) is not None:continue
        handle = kernel.GetStdHandle(number & 0xffffffff)
        if not handle or handle == ctypes.c_void_p(-1).value:
            stream = open(os.devnull, mode, buffering=0)
        else:
            stream = os.fdopen(msvcrt.open_osfhandle(handle, flags | os.O_BINARY), mode, buffering=0)
        setattr(sys, name, io.TextIOWrapper(stream, encoding='utf-8', errors='replace', newline='\n', write_through=True))


def main():
    attach_inherited_streams()
    if '--read-embedded-subtitles' in sys.argv:
        from yingxu.embedded_subtitles import probe_main
        return probe_main()
    if '--desktop-backend' in sys.argv:
        sys.argv.remove('--desktop-backend')
        from yingxu.desktop_host.backend import main as start
        return start()
    if '--subtitle-browser' in sys.argv:
        sys.argv.remove('--subtitle-browser')
        from yingxu.desktop_host.subtitle_process import main as start
        return start()
    return 2


if __name__ == '__main__':sys.exit(main())
