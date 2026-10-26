"""Actual scan/bridge safety for embedded subtitles and saved language rules."""
import json
from pathlib import Path
import tempfile
from time import sleep
import unittest
from unittest.mock import patch
from uuid import uuid4

from PySide6.QtCore import QCoreApplication, QSettings
from PySide6.QtTest import QTest
from tests.media_fixtures import mkv, mp4
from yingxu.core import check_cancelled
from yingxu.operations import HistoryStore
from yingxu.web_ui.embedded_settings import EmbeddedSettings
from yingxu.web_ui.workspace_bridge import WorkspaceBridge

ROOT=Path(__file__).resolve().parents[2]


class EmbeddedContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='embedded-web-',dir=ROOT/'work/test-results')
        self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.media=self.root/'视频';self.media.mkdir()
        self.chinese=mkv(self.media/'中文电影.mkv',[('zho','简体中文',False)])
        self.english=mp4(self.media/'English.mp4','eng')
        self.before={p.name:p.read_bytes() for p in self.media.iterdir()}
        self.bridge=WorkspaceBridge(history=HistoryStore(self.root/'history.jsonl'))
        self.service=self.bridge.service
        self.service.embedded_settings=EmbeddedSettings(QSettings(str(self.root/'settings.ini'),QSettings.Format.IniFormat))
        self.responses=[];self.bridge.reply.connect(lambda raw:self.responses.append(json.loads(raw)))
        self.sid=None;self.sid=self.send('app.hello')['data']['sessionId']
        self.service.accept_folder(self.media)

    def tearDown(self):
        if self.service.worker:
            self.service.worker.stop.set();self.wait()

    def send(self,action,params=None):
        self.bridge.request(json.dumps({'v':1,'requestId':uuid4().hex,'sessionId':self.sid,'action':action,'params':params or {}}))
        return self.responses[-1]

    def wait(self):
        for _ in range(2000):
            if self.service.worker is None:return
            QTest.qWait(5)
        raise AssertionError('Embedded scan did not settle')

    def scan(self):
        reply=self.send('scan.start',{'folderId':self.service.folder_id,'recursive':True,'move':False})
        self.assertTrue(reply['ok'],reply);self.wait()
        self.assertEqual(self.service.job['status'],'completed',self.service.job)

    def params(self,**extra):
        return {'scanId':self.service.data.scan_id,'revision':self.service.data.revision,**extra}

    def row(self,path):return next(row for row in self.service.data.rows if row['video']['name']==path.name)

    def test_scan_accepts_correct_language_and_excludes_it_from_search(self):
        self.scan();good=self.row(self.chinese);bad=self.row(self.english)
        self.assertEqual(good['state'],'已符合');self.assertTrue(good['embeddedSatisfied'])
        self.assertFalse(good['subtitles']);self.assertFalse(bad['embeddedSatisfied'])
        self.assertEqual(bad['state'],'未匹配')
        self.assertEqual(self.service.summary()['embeddedSatisfiedCount'],1)
        tasks=self.service.subtitle_tasks(self.params())
        self.assertEqual([task['rowId'] for task in tasks],[bad['rowId']])
        rejected=self.send('subtitle.open',self.params(rowId=good['rowId']))
        self.assertEqual(rejected['error']['code'],'ALREADY_SATISFIED')
        self.assertEqual(self.before,{p.name:p.read_bytes() for p in self.media.iterdir()})

    def test_language_change_invalidates_preview_and_reuses_unchanged_metadata(self):
        self.scan()
        preview=self.send('preview.create',self.params());self.assertTrue(preview['ok']);self.wait()
        self.assertIsNotNone(self.service.ticket)
        reply=self.send('embedded.configure',{'enabled':True,'language':'english'})
        self.assertTrue(reply['ok'],reply);self.assertIsNone(self.service.data);self.assertIsNone(self.service.ticket)
        with patch('yingxu.web_ui.workspace_service.ProbeSession.probe',side_effect=AssertionError('Unchanged metadata should be cached')):
            self.scan()
        self.assertTrue(self.row(self.english)['embeddedSatisfied'])
        self.assertFalse(self.row(self.chinese)['embeddedSatisfied'])
        restored=EmbeddedSettings(QSettings(str(self.root/'settings.ini'),QSettings.Format.IniFormat))
        self.assertEqual(restored.options['language'],'english')

    def test_manual_override_and_restore_are_review_only(self):
        self.scan();row=self.row(self.chinese)
        reply=self.send('review.embedded',self.params(rowId=row['rowId'],use=False))
        self.assertTrue(reply['ok']);self.wait();self.assertEqual(self.row(self.chinese)['state'],'未匹配')
        self.assertNotIn(row['embedded']['reason'],self.row(self.chinese)['basis'])
        reply=self.send('review.embedded',self.params(rowId=row['rowId'],use=True))
        self.assertTrue(reply['ok']);self.wait();self.assertTrue(self.row(self.chinese)['embeddedSatisfied'])
        self.assertEqual(self.before,{p.name:p.read_bytes() for p in self.media.iterdir()})

    def test_unknown_parameters_and_wrong_types_cannot_add_paths_or_commands(self):
        self.scan()
        for params in ({'enabled':'true','language':'chinese'},{'enabled':True,'language':'shell'},
                       {'enabled':True,'language':'chinese','path':'../outside'},
                       {'enabled':True,'language':'chinese','command':'anything'}):
            with self.subTest(params=params):self.assertFalse(self.send('embedded.configure',params)['ok'])
        row=self.row(self.chinese)
        self.assertFalse(self.send('review.embedded',self.params(rowId=row['rowId'],use='true'))['ok'])
        self.assertTrue(self.row(self.chinese)['embeddedSatisfied'])

    def test_failed_settings_save_keeps_current_review_and_policy(self):
        self.scan();old=self.service.data
        class BrokenSettings:
            def value(self,*args):return ''
            def setValue(self,*args):pass
            def sync(self):pass
            def status(self):return QSettings.Status.AccessError
        self.service.embedded_settings=EmbeddedSettings(BrokenSettings())
        reply=self.send('embedded.configure',{'enabled':True,'language':'english'})
        self.assertEqual(reply['error']['code'],'SAVE_FAILED')
        self.assertIs(self.service.data,old);self.assertEqual(self.service.embedded_settings.options['language'],'chinese')

    def test_disabled_check_does_not_start_a_reader_or_auto_pass(self):
        self.assertTrue(self.send('embedded.configure',{'enabled':False,'language':'chinese'})['ok'])
        with patch('yingxu.web_ui.workspace_service.ProbeSession.probe',side_effect=AssertionError('Reader should not run')):
            self.scan()
        self.assertFalse(self.row(self.chinese)['embeddedSatisfied'])

    def test_cancelling_metadata_scan_never_publishes_partial_passes(self):
        def slow_probe(reader,path):
            while not reader.should_stop():sleep(.01)
            check_cancelled(reader.should_stop)
        with patch('yingxu.web_ui.workspace_service.ProbeSession.probe',slow_probe):
            reply=self.send('scan.start',{'folderId':self.service.folder_id,'recursive':True,'move':False})
            self.assertTrue(reply['ok'])
            self.assertTrue(self.send('scan.cancel',{'jobId':reply['data']['jobId']})['ok']);self.wait()
        self.assertEqual(self.service.job['status'],'cancelled');self.assertIsNone(self.service.data)
        self.assertEqual(self.before,{p.name:p.read_bytes() for p in self.media.iterdir()})


if __name__=='__main__':unittest.main()
