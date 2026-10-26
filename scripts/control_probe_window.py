"""Native lifecycle checks, restricted to the HWND/PID of the launched test app."""
import ctypes as C
from ctypes import wintypes as W
import json
import sys

user=C.WinDLL('user32',use_last_error=True)
user.SetProcessDpiAwarenessContext.argtypes=[C.c_void_p];user.SetProcessDpiAwarenessContext(C.c_void_p(-4))
user.GetWindowThreadProcessId.argtypes=[C.c_void_p,C.POINTER(C.c_uint32)]
user.ShowWindow.argtypes=[C.c_void_p,C.c_int]
user.SetWindowPos.argtypes=[C.c_void_p,C.c_void_p,C.c_int,C.c_int,C.c_int,C.c_int,C.c_uint32]
user.GetWindowRect.argtypes=[C.c_void_p,C.POINTER(W.RECT)]
user.IsIconic.argtypes=[C.c_void_p]
handle=C.c_void_p(int(sys.argv[1]));expected=int(sys.argv[2]);pid=C.c_uint32()
if not user.GetWindowThreadProcessId(handle,C.byref(pid)) or pid.value!=expected:
    raise RuntimeError('Test HWND does not belong to the launched process')
action=sys.argv[3]
if action=='minimize':user.ShowWindow(handle,6)
elif action=='restore':user.ShowWindow(handle,9)
elif action=='resize':
    width,height=int(sys.argv[4]),int(sys.argv[5])
    if not (900<=width<=1800 and 650<=height<=1200):raise ValueError('Unexpected test window size')
    if not user.SetWindowPos(handle,None,0,0,width,height,0x2|0x4|0x10):raise OSError(C.get_last_error())
else:raise ValueError('Unsupported lifecycle check')
bounds=W.RECT();user.GetWindowRect(handle,C.byref(bounds))
print(json.dumps({'minimized':bool(user.IsIconic(handle)),'width':bounds.right-bounds.left,'height':bounds.bottom-bounds.top}))
