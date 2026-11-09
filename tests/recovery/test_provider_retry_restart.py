from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from yingxu.adapters.sqlite_workflow_store import SQLiteWorkflowStore
from yingxu.adapters.sqlite_checkpoint import SQLiteCheckpoints
from yingxu.adapters.subtitle_sites.browser_provider import BrowserSiteProvider
from yingxu.application.subtitles import SubtitleWorkflow
from yingxu.application.discovery import Discovery
from yingxu.domain.models import SubtitlePhase


class ProviderRetryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);root=Path(self.temp.name)
        self.store=SQLiteWorkflowStore(root/'tasks.sqlite3');self.addCleanup(self.store.close)
        self.checkpoints=SQLiteCheckpoints(root/'workspace.sqlite3');self.addCleanup(self.checkpoints.close)
        self.now=100.;self.frames=[]
        data=SimpleNamespace(scan_id='scan',revision=1,index=lambda _r:0)
        self.workspace=SimpleNamespace(drafts=SimpleNamespace(store=self.checkpoints),data=data,busy=False,session_id='session',
            emit=lambda *_a:None,require_idle=lambda:None)
        self.workflow=SubtitleWorkflow(self.store);self.task=self.workflow.create_task('scan',1)
        self.discovery=self.make()
        self.discovery.restore_pending=False
        self.discovery.entries[self.task.task_id]={'rowId':'video-1','videoName':'Film.mkv','query':'Film','provider':'subhd','candidates':[]}

    def make(self):return Discovery(self.workspace,self.workflow,BrowserSiteProvider(),self.frames.append,
        SimpleNamespace(read=lambda:{'language':'bilingual'}),clock=lambda:self.now,jitter=lambda:.5)

    def start(self):
        self.discovery.dispatch('online.start',{'taskId':self.task.task_id,'query':'Film','provider':'subhd'},'start')
        return self.frames[-1]

    def failed(self,frame,**extra):
        return self.discovery.browser_result({'taskId':frame['taskId'],'effectId':frame['effectId'],'generation':frame['generation'],
            'status':'failed','message':'temporary',**extra})

    def test_wait_new_effect_stale_callback_cancel_and_limit(self):
        frame=self.start();self.failed(frame,statusCode=429,retryAfter='30')
        self.discovery.tick();self.assertEqual(len(self.frames),1)
        self.now+=30;self.discovery.tick();second=self.frames[-1];self.assertNotEqual(frame['effectId'],second['effectId'])
        self.assertFalse(self.failed(frame,statusCode=503))
        self.failed(second,statusCode=503)
        self.discovery.dispatch('online.cancel',{'taskId':self.task.task_id},'cancel');count=len(self.frames)
        self.now+=100;self.discovery.tick();self.assertEqual(len(self.frames),count)
        self.assertEqual(self.workflow.get_task(self.task.task_id).phase,SubtitlePhase.CANCELLED)

    def test_restart_pauses_retry_and_preserves_provider_stop(self):
        frame=self.start();self.failed(frame,statusCode=503)
        restored=self.make();restored.restore();self.now+=100
        restored.tick();self.assertIsNone(restored.entries[self.task.task_id]['retry']['nextAttempt'])
        restored.dispatch('online.provider',{'provider':'subhd','enabled':False},'stop')
        self.assertIn('subhd',self.make().disabled)

    def test_manual_and_auth_do_not_auto_retry(self):
        frame=self.start();self.failed(frame,statusCode=403)
        self.now+=100;self.discovery.tick();self.assertEqual(len(self.frames),1)

    def test_three_automatic_retries_then_wait_for_user(self):
        frame=self.start()
        for _ in range(3):
            self.failed(frame,statusCode=503);self.now+=100;self.discovery.tick();frame=self.frames[-1]
        count=len(self.frames);self.failed(frame,statusCode=503);self.now+=100;self.discovery.tick()
        self.assertEqual(len(self.frames),count);self.assertEqual(count,4)
