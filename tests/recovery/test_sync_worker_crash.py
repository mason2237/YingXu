import ctypes
from ctypes import wintypes
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from yingxu.adapters.sync_process_tree import ProcessTree
from tests.integration.test_noqt_host import ROOT


class SyncTreeTests(unittest.TestCase):
    def test_close_waits_for_descendant_file_handles(self):
        if sys.platform!='win32':self.skipTest('Windows Job Object test')
        with tempfile.TemporaryDirectory(dir=ROOT/'work/test-results') as directory:
            locked=Path(directory)/'locked.txt'
            leaf='import sys,time;f=open(sys.argv[1],"w");print("ready",flush=True);time.sleep(120)'
            launcher='import subprocess,sys,time;subprocess.Popen([sys.executable,"-c",sys.argv[1],sys.argv[2]]);time.sleep(120)'
            tree=ProcessTree([sys.executable,'-c',launcher,leaf,str(locked)],stdout=subprocess.PIPE)
            try:
                self.assertEqual(tree.process.stdout.readline(),b'ready\r\n')
                tree.close();locked.unlink();self.assertFalse(locked.exists())
                tree.process.wait(timeout=5)
            finally:tree.close();tree.process.stdout.close()

    def test_parent_crash_reclaims_child(self):
        if sys.platform!='win32':self.skipTest('Windows Job Object test')
        with tempfile.TemporaryDirectory(dir=ROOT/'work/test-results') as directory:
            path=Path(directory)/'parent.py'
            path.write_text('import sys,time\nfrom yingxu.adapters.sync_process_tree import ProcessTree\ntree=ProcessTree([sys.executable,"-c","import time;time.sleep(120)"],stdout=-1)\nprint(tree.process.pid,flush=True)\ntime.sleep(120)\n')
            parent=subprocess.Popen([sys.executable,'-S',str(path)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                env={**__import__('os').environ,'PYTHONPATH':str(ROOT)},text=True)
            try:
                line=parent.stdout.readline();self.assertTrue(line,line+parent.stderr.read() if parent.poll() is not None else line)
                pid=int(line);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
                kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
                kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];kernel.WaitForSingleObject.restype=wintypes.DWORD
                kernel.CloseHandle.argtypes=[wintypes.HANDLE]
                handle=kernel.OpenProcess(0x00100000,False,pid);self.assertTrue(handle)
                try:parent.kill();parent.wait(timeout=10);self.assertEqual(kernel.WaitForSingleObject(handle,5000),0)
                finally:kernel.CloseHandle(handle)
            finally:
                if parent.poll() is None:parent.kill();parent.wait()
                parent.stdout.close();parent.stderr.close()
