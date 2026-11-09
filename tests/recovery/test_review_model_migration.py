"""Legacy decisions survive model upgrades, while old approval cannot survive."""
from pathlib import Path
from types import SimpleNamespace
from copy import deepcopy
import tempfile
import unittest

from yingxu.adapters.local_filesystem import LocalFilesystem
from yingxu.adapters.sqlite_checkpoint import SQLiteCheckpoints
from yingxu.application.drafts import Drafts
from yingxu.application.reviewing import ReviewData
from yingxu.domain.errors import ProtocolError
from yingxu.domain.review import REVIEW_MODEL, ReviewPlan


class ReviewModelMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        video=self.root/'Film.S01E01.mkv';video.write_bytes(b'generated video')
        sub=self.root/'Film.S01E01.en.srt';sub.write_bytes(b'generated subtitle')
        self.fs=LocalFilesystem()
        self.store=SQLiteCheckpoints(self.root/'state.sqlite3')
        self.addCleanup(self.store.close)
        self.drafts=Drafts(self.store,self.fs)
        review=ReviewPlan([video],[sub],exists=self.fs.exists)
        review.remove(0,sub);review.assign(0,sub);review.confirm(0)
        self.data=ReviewData(review,lambda p:p.name,revision=7)
        self.workspace=SimpleNamespace(folder=self.root,folder_mark=self.fs.directory_mark(self.root),
            options={'move':False,'recursive':True},embedded={'enabled':True,'language':'chinese'})
        self.saved=self.drafts.capture(self.workspace,self.data)

    def test_old_draft_retains_manual_choice_and_requires_reconfirmation(self):
        legacy=deepcopy(self.saved);legacy.pop('reviewModel')
        self.store.save('workspace',legacy)
        before={p:p.read_bytes() for p in self.data.review.videos+self.data.review.subtitles}
        data=self.drafts.restore(self.store.load('workspace'),lambda p:p.name)[2]
        self.assertEqual(data.revision,8)
        self.assertEqual(data.review.rows[0].matches[0].source,self.data.review.rows[0].matches[0].source)
        self.assertTrue(data.review.rows[0].matches[0].manual)
        self.assertFalse(data.review.rows[0].matches[0].confirmed)
        self.assertEqual(data.review.state(0),'需确认')
        self.assertTrue(any('规则' in s or '模型' in s for s in data.rows[0]['basis']))
        self.assertEqual(self.store.load('workspace'),legacy,'Read-only restoration must retain the old checkpoint')
        self.assertEqual(before,{p:p.read_bytes() for p in before})

    def test_current_round_trip_keeps_variants_skip_and_review_flags(self):
        data=self.drafts.restore(self.saved,lambda p:p.name)[2]
        self.assertEqual(data.revision,7)
        self.assertTrue(data.review.rows[0].matches[0].confirmed)
        self.assertEqual(self.saved['reviewModel'],REVIEW_MODEL)
        data.review.skip(0)
        saved=self.drafts.capture(self.workspace,data)
        self.assertEqual(self.drafts.restore(saved,lambda p:p.name)[2].review.state(0),'已跳过')

    def test_unknown_model_is_rejected_without_resetting_persistent_data(self):
        value=deepcopy(self.saved);value['reviewModel']='future-99'
        self.store.save('workspace',value)
        with self.assertRaisesRegex(ProtocolError,'版本'):self.drafts.restore(value,lambda p:p.name)
        self.assertEqual(self.store.load('workspace'),value)


if __name__=='__main__':unittest.main()
