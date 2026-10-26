"""Read session readiness; optionally hold a temporary display wake request."""
import ctypes as C
import json
import struct
import sys


def status():
    user=C.WinDLL('user32');kernel=C.WinDLL('kernel32');wts=C.WinDLL('wtsapi32')
    class Last(C.Structure):_fields_=[('size',C.c_uint32),('time',C.c_uint32)]
    last=Last(C.sizeof(Last),0);user.GetLastInputInfo(C.byref(last));kernel.GetTickCount64.restype=C.c_uint64
    sid=C.c_uint32();kernel.ProcessIdToSessionId(kernel.GetCurrentProcessId(),C.byref(sid))
    buf=C.c_void_p();size=C.c_uint32()
    wts.WTSQuerySessionInformationW.argtypes=[C.c_void_p,C.c_uint32,C.c_int,C.POINTER(C.c_void_p),C.POINTER(C.c_uint32)]
    wts.WTSFreeMemory.argtypes=[C.c_void_p]
    result={'idleSeconds':round(((kernel.GetTickCount64()&0xffffffff)-last.time)/1000),'osPreferencesChanged':False}
    if wts.WTSQuerySessionInformationW(None,sid.value,25,C.byref(buf),C.byref(size)):
        raw=C.string_at(buf,min(size.value,24));result['sessionUnlocked']=struct.unpack_from('<i',raw,16)[0]==1
        wts.WTSFreeMemory(buf)
    return result


def main():
    kernel=C.WinDLL('kernel32');kernel.SetThreadExecutionState.argtypes=[C.c_uint32];kernel.SetThreadExecutionState.restype=C.c_uint32
    hold='--keep-awake' in sys.argv
    result=status()
    if hold:result['displayWakeRequest']=bool(kernel.SetThreadExecutionState(0x80000002))
    try:
        print(json.dumps(result),flush=True)
        if hold:sys.stdin.buffer.read(1)
    finally:
        if hold:kernel.SetThreadExecutionState(0x80000000)


if __name__=='__main__':main()
