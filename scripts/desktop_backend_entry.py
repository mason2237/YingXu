"""Frozen private helper modes. The public application entry is Electron's EXE."""
import ctypes
import io
import os
import sys
from yingxu.desktop.streams import attach_inherited_streams



def main():
    attach_inherited_streams()
    if '--read-embedded-subtitles' in sys.argv:
        from yingxu.adapters.mediainfo import probe_main
        return probe_main()
    if '--desktop-backend' in sys.argv:
        sys.argv.remove('--desktop-backend')
        from yingxu.desktop.host import main as start
        return start()
    return 2


if __name__ == '__main__':sys.exit(main())
