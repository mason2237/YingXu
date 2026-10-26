"""Sample the composed HDR test window with Windows Graphics Capture, no OS changes.

The capture stays in memory. Only the requested calibration rectangle is sampled;
no screenshot or unrelated desktop pixels are written to disk.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
import json
from pathlib import Path
import statistics
import struct
import sys
import time
from uuid import UUID

HRESULT=C.c_int32
UINT=C.c_uint32
PTR=C.c_void_p


class GUID(C.Structure):
    _fields_=[('a',UINT),('b',C.c_uint16),('c',C.c_uint16),('d',C.c_ubyte*8)]

    def __init__(self, value):
        super().__init__();C.memmove(C.byref(self),UUID(value).bytes_le,16)


class Rect(C.Structure):
    _fields_=[(key,C.c_int32) for key in ('left','top','right','bottom')]


class TextureDesc(C.Structure):
    _fields_=[(key,UINT) for key in ('width','height','mips','array','format','samples','quality','usage','bind','cpu','misc')]


class Mapped(C.Structure):
    _fields_=[('data',PTR),('pitch',UINT),('depth',UINT)]


def call(obj, index, restype, argtypes, *args):
    table=C.cast(obj,C.POINTER(C.POINTER(PTR))).contents
    return C.WINFUNCTYPE(restype,PTR,*argtypes)(table[index])(obj,*args)


def check(result, operation):
    if result < 0:
        raise OSError(f'{operation}: 0x{result & 0xffffffff:08x}')


def query(obj, guid):
    result=PTR();check(call(obj,0,HRESULT,[C.POINTER(GUID),C.POINTER(PTR)],C.byref(GUID(guid)),C.byref(result)),'QueryInterface')
    return result


def sample_window(handle, rect, scale):
    # Optional diagnostic wheels are isolated from the application's venv.
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'work/tools/hdr-python'))
    from winrt.runtime import init_apartment, ApartmentType
    from winrt.windows.graphics.capture import Direct3D11CaptureFramePool
    from winrt.windows.graphics.capture.interop import create_for_window
    from winrt.windows.graphics.directx import DirectXPixelFormat
    from winrt.windows.graphics.directx.direct3d11.interop import (
        create_direct3d11_device_from_dxgi_device, get_dxgi_surface_from_object)
    init_apartment(ApartmentType.MULTI_THREADED)
    def step(name):
        if '--debug' in sys.argv:print('capture: '+name,file=sys.stderr,flush=True)
    step('apartment')
    owned=[];session=pool=frame=None;mapped=False;context=PTR();staging=PTR()
    def keep(value):owned.append(value);return value
    try:
        user=C.WinDLL('user32');user.SetProcessDpiAwarenessContext.argtypes=[PTR];user.SetProcessDpiAwarenessContext(PTR(-4))
        user.ClientToScreen.argtypes=[PTR,C.POINTER(W.POINT)];user.GetWindowRect.argtypes=[PTR,C.POINTER(Rect)]
        origin=W.POINT();user.ClientToScreen(PTR(handle),C.byref(origin))
        bounds=Rect();C.WinDLL('dwmapi').DwmGetWindowAttribute(PTR(handle),9,C.byref(bounds),C.sizeof(bounds))
        device=PTR();feature=UINT();create=C.WinDLL('d3d11').D3D11CreateDevice
        create.argtypes=[PTR,UINT,PTR,UINT,PTR,UINT,UINT,C.POINTER(PTR),C.POINTER(UINT),C.POINTER(PTR)];create.restype=HRESULT
        check(create(None,1,None,0x20,None,0,7,C.byref(device),C.byref(feature),C.byref(context)),'D3D11CreateDevice')
        keep(device);keep(context);dxgi=keep(query(device,'54ec77fa-1377-44e6-8c32-88fd5f44c84c'))
        winrt_device=create_direct3d11_device_from_dxgi_device(dxgi.value)
        step('device')
        item=create_for_window(handle)
        step('item')
        if item.size.width != bounds.right-bounds.left or item.size.height != bounds.bottom-bounds.top:
            user.GetWindowRect(PTR(handle),C.byref(bounds))
        pool=Direct3D11CaptureFramePool.create_free_threaded(winrt_device,DirectXPixelFormat.R16_G16_B16_A16_FLOAT,2,item.size)
        session=pool.create_capture_session(item);session.is_cursor_capture_enabled=False;session.start_capture()
        step('session')
        started=time.monotonic();deadline=started+4;frames_seen=0
        while time.monotonic()<deadline:
            next_frame=pool.try_get_next_frame()
            if next_frame:
                if frame:frame.close()
                frame=next_frame;frames_seen+=1
                if frames_seen>=3 and time.monotonic()-started>=.25:break
            time.sleep(.01)
        if frame is None:raise OSError('Windows Graphics Capture returned no window frame')
        step('frame')
        surface=keep(PTR(get_dxgi_surface_from_object(frame.surface)))
        texture=keep(query(surface,'6f15aaf2-d208-4e89-9ab4-489535d34f9c'))
        desc=TextureDesc();call(texture,10,None,[C.POINTER(TextureDesc)],C.byref(desc))
        if desc.format!=10:raise OSError(f'Window capture format {desc.format} is not float HDR')
        desc.usage=3;desc.bind=0;desc.cpu=0x20000;desc.misc=0
        check(call(device,5,HRESULT,[C.POINTER(TextureDesc),PTR,C.POINTER(PTR)],C.byref(desc),None,C.byref(staging)),'CreateTexture2D')
        keep(staging);call(context,47,None,[PTR,PTR],staging,texture)
        data=Mapped();check(call(context,14,HRESULT,[PTR,UINT,UINT,UINT,C.POINTER(Mapped)],staging,0,1,0,C.byref(data)),'Map');mapped=True
        step('mapped')
        x=origin.x-bounds.left+int(rect['x']*scale);y=origin.y-bounds.top+int(rect['y']*scale)
        width=int(rect['width']*scale);height=int(rect['height']*scale);samples=[]
        for band in range(3):
            values=[]
            for dy in (-6,-3,0,3,6):
                for dx in (-6,-3,0,3,6):
                    px=x+int(width*(band+.5)/3)+dx;py=y+height//2+dy
                    if not (0<=px<desc.width and 0<=py<desc.height):raise OSError('Sample outside window')
                    rgba=struct.unpack('<4e',C.string_at(data.data+py*data.pitch+px*8,8));values.append(sum(rgba[:3])/3)
            samples.append(round(statistics.median(values),5))
        verified=samples[0]>.1 and samples[1]>samples[0]*1.25 and samples[2]>samples[0]*1.5
        return {'verified':verified,'format':'R16G16B16A16_FLOAT','method':'Windows Graphics Capture window',
                'linearScRgbSamples':samples,'abovePaperWhiteRatio':round(samples[2]/max(.001,samples[0]),3),
                'textureSize':[desc.width,desc.height],'warmupFrames':frames_seen,'physicalPeakMeasured':False,'osSettingsChanged':False}
    finally:
        if mapped:call(context,15,None,[PTR,UINT],staging,0)
        for obj in reversed(owned):
            if obj:call(obj,2,UINT,[])
        if frame:frame.close()
        if session:session.close()
        if pool:pool.close()
        # Close the capture objects before process teardown.
        frame=session=pool=None
        if 'winrt_device' in locals():winrt_device=None
        if 'item' in locals():item=None
        # This one-shot helper exits immediately. Leave its MTA initialized
        # until process teardown: WinRT's deferred release can outlive close().


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--handle',type=int,required=True)
    parser.add_argument('--rect',type=json.loads,required=True)
    parser.add_argument('--scale',type=float,default=1)
    parser.add_argument('--debug',action='store_true')
    args=parser.parse_args()
    try:result=sample_window(args.handle,args.rect,args.scale)
    except (OSError,ValueError,ImportError) as error:result={'verified':False,'error':str(error)}
    print(json.dumps(result,ensure_ascii=True))


if __name__=='__main__':main()
