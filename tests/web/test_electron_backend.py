"""Architecture prototype safety and real Python service integration."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from uuid import uuid4

from PySide6.QtCore import QCoreApplication, QSettings
from PySide6.QtTest import QTest

from yingxu.desktop_host.backend import Host, PreviewBridge, PreviewService, ALLOWED
from yingxu.operations import HistoryStore

ROOT=Path(__file__).resolve().parents[2]


class ElectronBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'work/test-results',prefix='electron-contract-')
        self.root=Path(self.temp.name);self.media=self.root/'中文 & 视频';self.media.mkdir()
        self.settings=QSettings(str(self.root/'embedded.ini'),QSettings.IniFormat)
        self.settings.setValue('subtitles/embedded/v1',json.dumps({'enabled':False,'language':'chinese'}))
        self.bridge=PreviewBridge(history=HistoryStore(self.root/'history.jsonl'),embedded_settings=self.settings,service_type=PreviewService)
        self.responses=[];self.bridge.reply.connect(lambda raw:self.responses.append(json.loads(raw)))
        self.sid=self.send('app.hello')['data']['sessionId']

    def tearDown(self):
        worker=self.bridge.service.worker
        if worker:worker.stop.set();self.wait_idle()
        self.temp.cleanup()

    def send(self, action, params=None, rid=None, sid=None):
        self.bridge.request(json.dumps({'v':1,'requestId':rid or uuid4().hex,
            'sessionId':None if action=='app.hello' else sid or getattr(self,'sid',None),'action':action,'params':params or {}}))
        return self.responses[-1]

    def wait_idle(self):
        for _ in range(2000):
            if self.bridge.service.worker is None:return
            QTest.qWait(5)
        self.fail('Worker did not finish')

    def scan(self):
        (self.media/'Atlas.S01E01.1080p.mkv').write_bytes(b'test video')
        (self.media/'Atlas.S01E01.chs.srt').write_text('test subtitle',encoding='utf8')
        service=self.bridge.service;service.accept_folder(self.media)
        response=self.send('scan.start',{'folderId':service.folder_id,'recursive':True,'move':False})
        self.assertTrue(response['ok'],response);self.wait_idle()
        self.assertEqual(service.job['status'],'completed')
        return response

    def test_capabilities_and_path_boundary(self):
        self.assertNotIn('organize.confirmAndStart',ALLOWED)
        self.assertNotIn('subtitle.open',ALLOWED)
        state=self.send('app.state')['data']
        self.assertFalse(state['executionAvailable']);self.assertFalse(state['downloadAvailable'])
        self.assertTrue(state['reviewReadOnly'])
        bad=self.send('folder.choose',{'path':str(self.media)})
        self.assertEqual(bad['error']['code'],'INVALID_REQUEST')
        self.assertIsNone(self.bridge.service.folder)

    def test_real_scan_preview_cannot_execute_even_with_issued_consent(self):
        self.scan();service=self.bridge.service
        before={p.name:p.read_bytes() for p in self.media.iterdir()}
        summary=service.summary();context={'scanId':summary['scanId'],'revision':summary['revision']}
        self.assertTrue(self.send('preview.create',context)['ok']);self.wait_idle()
        plan=service.job['result'];self.assertGreater(plan['changeCount'],0)
        reply=self.send('organize.confirmAndStart',{'scanId':plan['scanId'],'reviewRevision':plan['revision'],
            'snapshotId':plan['snapshotId'],'confirmationToken':plan['confirmationToken'],'acknowledged':True})
        self.assertEqual(reply['error']['code'],'PROTOTYPE_ONLY')
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.media.iterdir()})
        self.assertFalse((self.root/'history.jsonl').exists())

    def test_duplicate_scan_and_stale_session(self):
        (self.media/'A.mkv').write_bytes(b'video')
        service=self.bridge.service;service.accept_folder(self.media)
        params={'folderId':service.folder_id,'recursive':True,'move':False};rid=uuid4().hex
        first=self.send('scan.start',params,rid=rid);self.wait_idle()
        repeated=self.send('scan.start',params,rid=rid)
        self.assertEqual(first,repeated)
        self.bridge.reset_page()
        self.assertEqual(self.send('app.state')['error']['code'],'STALE_SESSION')

    def test_online_and_review_writes_denied(self):
        self.scan();summary=self.bridge.service.summary()
        rows=self.send('review.query',{'scanId':summary['scanId'],'revision':summary['revision']})['data']['rows']
        context={'scanId':summary['scanId'],'revision':summary['revision'],'rowId':rows[0]['rowId']}
        for action,params in [('subtitle.open',context),('review.skip',{**context,'skipped':True})]:
            self.assertEqual(self.send(action,params)['error']['code'],'PROTOTYPE_ONLY')

    def test_old_or_mismatched_native_dialog_cannot_register_folder(self):
        host=Host(self.root/'host');frames=[];host.send=frames.append
        host.receive({'type':'request','raw':json.dumps({'v':1,'requestId':'hello','sessionId':None,'action':'app.hello','params':{}})})
        sid=host.bridge.session_id
        host.receive({'type':'request','raw':json.dumps({'v':1,'requestId':'choose','sessionId':sid,'action':'folder.choose','params':{}})})
        host.receive({'type':'native.result','requestId':'choose','sessionId':sid,'action':'file.copyName','path':str(self.media)})
        self.assertIsNone(host.bridge.service.folder)
        host.receive({'type':'reset'})
        host.receive({'type':'native.result','requestId':'choose','sessionId':sid,'action':'folder.choose','path':str(self.media)})
        self.assertIsNone(host.bridge.service.folder);self.assertFalse(host.bridge.service.native_busy)

    def test_stdio_backend_clean_eof_shutdown(self):
        request={'type':'request','raw':json.dumps({'v':1,'requestId':'hello','sessionId':None,'action':'app.hello','params':{}})}
        runtimes=[Path(sys.executable)]
        windowless=Path(sys.executable).with_name('pythonw.exe')
        if windowless.exists():runtimes.append(windowless)
        for runtime in runtimes:
            with self.subTest(runtime=runtime.name):
                process=subprocess.run([str(runtime),'-u','-m','yingxu.desktop_host.backend','--profile',str(self.root/runtime.stem)],
                    input=json.dumps(request)+'\n',text=True,capture_output=True,cwd=ROOT,timeout=10)
                self.assertEqual(process.returncode,0,process.stderr)
                frames=[json.loads(line) for line in process.stdout.splitlines()]
                self.assertEqual(frames[0]['type'],'ready')
                reply=next(json.loads(frame['raw']) for frame in frames if frame['type']=='reply')
                self.assertTrue(reply['ok']);self.assertFalse(reply['data']['state']['executionAvailable'])
                self.assertFalse(process.stderr)


if __name__=='__main__':unittest.main()
