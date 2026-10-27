"""Test only: resize/minimize a diagnostics window whose owner PID is verified."""
import argparse
import ctypes
from ctypes import wintypes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('handle', type=int)
    parser.add_argument('pid', type=int)
    parser.add_argument('action', choices=('resize','minimize','restore'))
    parser.add_argument('--width', type=int, default=1280)
    args = parser.parse_args()
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    pid = wintypes.DWORD()
    user.GetWindowThreadProcessId(args.handle, ctypes.byref(pid))
    if pid.value != args.pid:
        raise RuntimeError('Diagnostic window is not owned by this test process')
    if args.action == 'resize':
        if not 940 <= args.width <= 1600:
            raise ValueError('Test size outside expected range')
        user.SetWindowPos.argtypes = [wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
        if not user.SetWindowPos(args.handle, None, 0, 0, args.width, 820, 0x16):
            raise ctypes.WinError(ctypes.get_last_error())
    else:
        user.ShowWindow.argtypes = [wintypes.HWND,ctypes.c_int]
        user.ShowWindow(args.handle, 6 if args.action == 'minimize' else 9)


if __name__ == '__main__':
    main()
