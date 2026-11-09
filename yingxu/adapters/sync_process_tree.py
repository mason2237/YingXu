"""Own only this worker tree. A Windows parent crash closes a kill-on-close Job."""
import ctypes
from ctypes import wintypes
import os
import signal
import subprocess
import time


class ProcessTree:
    def __init__(self,args,**options):
        self.job=None;self.process=None
        if os.name!='nt':self.process=subprocess.Popen(args,start_new_session=True,**options);return
        kernel=ctypes.WinDLL('kernel32',use_last_error=True);self.kernel=kernel
        class Basic(ctypes.Structure):
            _fields_=[('processTime',ctypes.c_longlong),('jobTime',ctypes.c_longlong),('flags',wintypes.DWORD),
                ('minimum',ctypes.c_size_t),('maximum',ctypes.c_size_t),('active',wintypes.DWORD),('affinity',ctypes.c_size_t),('priority',wintypes.DWORD),('scheduling',wintypes.DWORD)]
        class IO(ctypes.Structure):_fields_=[(name,ctypes.c_ulonglong) for name in ('read','write','other','readBytes','writeBytes','otherBytes')]
        class Extended(ctypes.Structure):_fields_=[('basic',Basic),('io',IO),('processMemory',ctypes.c_size_t),('jobMemory',ctypes.c_size_t),('peakProcess',ctypes.c_size_t),('peakJob',ctypes.c_size_t)]
        kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR];kernel.CreateJobObjectW.restype=wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD];kernel.SetInformationJobObject.restype=wintypes.BOOL
        kernel.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE];kernel.AssignProcessToJobObject.restype=wintypes.BOOL
        kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
        self.job=kernel.CreateJobObjectW(None,None)
        if not self.job:raise ctypes.WinError(ctypes.get_last_error())
        self.extended_type=Extended
        limit=Extended();limit.basic.flags=0x2000|0x200;limit.jobMemory=1024*1024*1024
        if not kernel.SetInformationJobObject(self.job,9,ctypes.byref(limit),ctypes.sizeof(limit)):self.close();raise ctypes.WinError(ctypes.get_last_error())
        try:
            self.process=subprocess.Popen(args,creationflags=0x08000000|0x00000004,**options)
            if not kernel.AssignProcessToJobObject(self.job,int(self.process._handle)):raise ctypes.WinError(ctypes.get_last_error())
            resume=ctypes.WinDLL('ntdll').NtResumeProcess;resume.argtypes=[wintypes.HANDLE];resume.restype=ctypes.c_long
            if resume(int(self.process._handle))!=0:raise RuntimeError('Unable to resume owned sync worker')
        except BaseException:
            self.close()
            if self.process and self.process.poll() is None:self.process.kill();self.process.wait()
            raise

    def close(self):
        if self.job:
            job,self.job=self.job,None
            handles=[]
            try:
                query=self.kernel.QueryInformationJobObject;query.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD,ctypes.c_void_p];query.restype=wintypes.BOOL
                class Pids(ctypes.Structure):
                    _fields_=[('assigned',wintypes.DWORD),('listed',wintypes.DWORD),('pids',ctypes.c_size_t*1024)]
                pids=Pids()
                if not query(job,3,ctypes.byref(pids),ctypes.sizeof(pids),None):raise ctypes.WinError(ctypes.get_last_error())
                open_process=self.kernel.OpenProcess;open_process.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];open_process.restype=wintypes.HANDLE
                for pid in pids.pids[:pids.listed]:
                    handle=open_process(0x00100000,False,pid)
                    if handle:handles.append(handle)
                terminate=self.kernel.TerminateJobObject;terminate.argtypes=[wintypes.HANDLE,wintypes.UINT];terminate.restype=wintypes.BOOL
                if not terminate(job,1):raise ctypes.WinError(ctypes.get_last_error())
                # Termination is asynchronous. Keep the Job handle until all
                # descendants have released handles before temporary cleanup.
                class Account(ctypes.Structure):
                    _fields_=[(n,ctypes.c_longlong) for n in ('user','kernel','periodUser','periodKernel')]+[(n,wintypes.DWORD) for n in ('faults','total','active','terminated')]
                deadline=time.monotonic()+5
                wait=self.kernel.WaitForSingleObject;wait.argtypes=[wintypes.HANDLE,wintypes.DWORD];wait.restype=wintypes.DWORD
                for handle in handles:
                    if wait(handle,max(0,int((deadline-time.monotonic())*1000)))!=0:raise TimeoutError('Owned descendant did not release its handles')
                while True:
                    account=Account()
                    if not query(job,1,ctypes.byref(account),ctypes.sizeof(account),None):raise ctypes.WinError(ctypes.get_last_error())
                    if not account.active:break
                    if time.monotonic()>=deadline:raise TimeoutError('Owned worker tree did not exit before cleanup')
                    time.sleep(.01)
            finally:
                for handle in handles:self.kernel.CloseHandle(handle)
                self.kernel.CloseHandle(job)
        elif os.name!='nt' and self.process:
            try:os.killpg(self.process.pid,signal.SIGKILL)
            except ProcessLookupError:pass

    def stats(self):
        if os.name!='nt' or not self.process:return {}
        if self.job:
            class Basic(ctypes.Structure):_fields_=[(n,ctypes.c_longlong) for n in ('user','kernel','periodUser','periodKernel')]+[(n,wintypes.DWORD) for n in ('faults','total','active','terminated')]
            class IO(ctypes.Structure):_fields_=[(n,ctypes.c_ulonglong) for n in ('readOps','writeOps','otherOps','readBytes','writeBytes','otherBytes')]
            class Account(ctypes.Structure):_fields_=[('basic',Basic),('io',IO)]
            account=Account();extended=self.extended_type()
            query=self.kernel.QueryInformationJobObject;query.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD,ctypes.c_void_p];query.restype=wintypes.BOOL
            if query(self.job,8,ctypes.byref(account),ctypes.sizeof(account),None) and query(self.job,9,ctypes.byref(extended),ctypes.sizeof(extended),None):
                return {'scope':'entire owned Job, including Python launcher and FFmpeg; excludes parent hashing',
                    'peakJobMemoryBytes':extended.peakJob,'readBytes':account.io.readBytes,'writeBytes':account.io.writeBytes,
                    'cpuSeconds':(account.basic.user+account.basic.kernel)/1e7,'processCount':account.basic.total}
        class Memory(ctypes.Structure):_fields_=[('size',wintypes.DWORD),('faults',wintypes.DWORD),*[(n,ctypes.c_size_t) for n in ('peak','working','quotaPeakPaged','quotaPaged','quotaPeakNonPaged','quotaNonPaged','pagefile','peakPagefile')]]
        class IO(ctypes.Structure):_fields_=[(name,ctypes.c_ulonglong) for name in ('readOps','writeOps','otherOps','readBytes','writeBytes','otherBytes')]
        memory=Memory();memory.size=ctypes.sizeof(memory);io=IO();handle=wintypes.HANDLE(int(self.process._handle))
        psapi=ctypes.WinDLL('psapi');psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD]
        self.kernel.GetProcessIoCounters.argtypes=[wintypes.HANDLE,ctypes.c_void_p]
        if not psapi.GetProcessMemoryInfo(handle,ctypes.byref(memory),memory.size) or not self.kernel.GetProcessIoCounters(handle,ctypes.byref(io)):return {}
        times=[wintypes.FILETIME() for _ in range(4)];self.kernel.GetProcessTimes.argtypes=[wintypes.HANDLE,*([ctypes.c_void_p]*4)]
        self.kernel.GetProcessTimes(handle,*[ctypes.byref(t) for t in times])
        ticks=lambda t:(t.dwHighDateTime<<32)|t.dwLowDateTime
        return {'scope':'worker only; excludes FFmpeg and parent validation reads','peakWorkingSetBytes':memory.peak,
                'readBytes':io.readBytes,'writeBytes':io.writeBytes,'cpuSeconds':(ticks(times[2])+ticks(times[3]))/1e7}
