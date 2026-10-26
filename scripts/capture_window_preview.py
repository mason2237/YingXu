"""One SDR screenshot of the test application's own visible window."""
import ctypes as C
from ctypes import wintypes as W
from pathlib import Path
import sys
from PySide6.QtGui import QGuiApplication, QImage

user=C.WinDLL('user32');user.SetProcessDpiAwarenessContext.argtypes=[C.c_void_p];user.SetProcessDpiAwarenessContext(C.c_void_p(-4))
user.IsWindow.argtypes=[C.c_void_p];user.GetWindowRect.argtypes=[C.c_void_p,C.POINTER(W.RECT)]
handle=C.c_void_p(int(sys.argv[1]));bounds=W.RECT()
if not user.IsWindow(handle) or not user.GetWindowRect(handle,C.byref(bounds)):
    raise RuntimeError('Test window is unavailable')
app=QGuiApplication([])
if '--print-window' in sys.argv:
    expected=next((arg.split('=',1)[1] for arg in sys.argv if arg.startswith('--process-id=')),None)
    pid=C.c_uint32();user.GetWindowThreadProcessId.argtypes=[C.c_void_p,C.POINTER(C.c_uint32)]
    if not expected or not user.GetWindowThreadProcessId(handle,C.byref(pid)) or pid.value!=int(expected):
        raise RuntimeError('Capture HWND does not belong to the test process')
    gdi=C.WinDLL('gdi32');width,height=bounds.right-bounds.left,bounds.bottom-bounds.top
    user.GetWindowDC.argtypes=[C.c_void_p];user.GetWindowDC.restype=C.c_void_p
    user.ReleaseDC.argtypes=[C.c_void_p,C.c_void_p]
    user.PrintWindow.argtypes=[C.c_void_p,C.c_void_p,C.c_uint]
    gdi.CreateCompatibleDC.argtypes=[C.c_void_p];gdi.CreateCompatibleDC.restype=C.c_void_p
    gdi.CreateCompatibleBitmap.argtypes=[C.c_void_p,C.c_int,C.c_int];gdi.CreateCompatibleBitmap.restype=C.c_void_p
    gdi.SelectObject.argtypes=[C.c_void_p,C.c_void_p];gdi.SelectObject.restype=C.c_void_p
    gdi.DeleteObject.argtypes=[C.c_void_p];gdi.DeleteDC.argtypes=[C.c_void_p]
    gdi.GetDIBits.argtypes=[C.c_void_p,C.c_void_p,C.c_uint,C.c_uint,C.c_void_p,C.c_void_p,C.c_uint]
    class Header(C.Structure):
        _fields_=[('size',W.DWORD),('width',W.LONG),('height',W.LONG),('planes',W.WORD),('bits',W.WORD),
                  ('compression',W.DWORD),('imageSize',W.DWORD),('x',W.LONG),('y',W.LONG),('used',W.DWORD),('important',W.DWORD)]
    source=user.GetWindowDC(handle);destination=gdi.CreateCompatibleDC(source)
    bitmap=gdi.CreateCompatibleBitmap(source,width,height);previous=gdi.SelectObject(destination,bitmap)
    try:
        if not user.PrintWindow(handle,destination,2):raise RuntimeError('Test window PrintWindow capture unavailable')
        header=Header(C.sizeof(Header),width,-height,1,32,0,0,0,0,0,0)
        pixels=C.create_string_buffer(width*height*4)
        if gdi.GetDIBits(destination,bitmap,0,height,pixels,C.byref(header),0)!=height:raise RuntimeError('Window pixels unavailable')
        image=QImage(pixels.raw,width,height,QImage.Format_RGB32).copy()
        if not image.save(str(Path(sys.argv[2]))):raise RuntimeError('Window image save failed')
    finally:
        gdi.SelectObject(destination,previous);gdi.DeleteObject(bitmap);gdi.DeleteDC(destination);user.ReleaseDC(handle,source)
    sys.exit(0)
# Capture the composited desktop region. GetDC(hwnd) returns black for modern
# hardware-accelerated child surfaces and is not a product-rendering verdict.
image=app.primaryScreen().grabWindow(0,bounds.left,bounds.top,bounds.right-bounds.left,bounds.bottom-bounds.top)
if image.isNull() or not image.save(str(Path(sys.argv[2]))):
    raise RuntimeError('System window screenshot failed')
