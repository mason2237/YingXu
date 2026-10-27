"""Checkpoint corruption and safe cache ageing use only generated local files."""
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from yingxu.adapters.sqlite_checkpoint import SQLiteCheckpoints
from yingxu.adapters.subtitle_artifacts import LocalSubtitleArtifacts
from yingxu.domain.errors import ProtocolError


class CheckpointTests(unittest.TestCase):
    def test_corrupt_checkpoint_is_not_reinitialized(self):
        with tempfile.TemporaryDirectory() as directory:
            store=SQLiteCheckpoints(Path(directory)/'workspace.sqlite3')
            try:
                store.save('workspace',{'v':1,'choice':'skip'})
                store.connection.execute("UPDATE checkpoints SET body='{}' WHERE key='workspace'")
                with self.assertRaisesRegex(ProtocolError,'摘要'):store.load('workspace')
                self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM checkpoints').fetchone()[0],1)
            finally:store.close()

    def test_old_imported_payload_reclaimed_without_touching_pinned_or_edited_files(self):
        with tempfile.TemporaryDirectory() as directory:
            store=LocalSubtitleArtifacts(Path(directory)/'cache')
            record=store.reserve({'offerId':uuid4().hex,'page':'https://subhd.me/a/TEST','url':'https://subhd.me/sub.srt',
                'name':'test.srt','mime':'text/plain','total':100},{'provider':'subhd','video':'generated.mkv'})
            store.path(record['id']).write_text('1\n00:00:01,000 --> 00:00:02,000\nHello\n',encoding='utf8')
            store.prepare(record['id'],lambda:False)
            store.update(record['id'],imported=True,createdAt=100)
            prepared=store.prepared(record['id'])[0];parent_id=prepared.parent.stat().st_ino
            self.assertFalse(store.maintenance_due(now=101))
            self.assertTrue(store.maintenance_due(now=100+31*86400))
            result=store.maintain([prepared],now=100+31*86400)
            self.assertGreater(result['releasedBytes'],0)
            self.assertFalse(store.path(record['id']).exists())
            self.assertTrue(prepared.exists());self.assertEqual(prepared.parent.stat().st_ino,parent_id)
            prepared.write_text('edited by user',encoding='utf8')
            result=store.compact(record['id'],[])
            self.assertEqual(result['releasedBytes'],0)
            self.assertEqual(prepared.read_text(encoding='utf8'),'edited by user')


if __name__=='__main__':unittest.main()
