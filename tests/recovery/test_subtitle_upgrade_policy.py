"""Generated files: staging, restart, changed-content refusal and undo."""
from pathlib import Path
import json
import os
import tempfile
import unittest

from tests.integration.test_noqt_host import Client,ROOT

GOOD='1\n00:00:01,000 --> 00:00:03,000\nGenerated text\n'
BAD='1\n00:00:03,000 --> 00:00:01,000\nGenerated text\n'


class SubtitleUpgradeRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='needs-',dir=ROOT/'work/test-results');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.media=self.root/'媒体';self.media.mkdir();self.profile=self.root/'profile'
        (self.media/'Film.2024.mkv').write_bytes(b'generated video')
        self.original=self.media/'Film.2024.en.srt';self.original.write_text(BAD,encoding='utf8')
        (self.media/'候选').mkdir();self.candidate=self.media/'候选/Film.2024.en.srt';self.candidate.write_text(GOOD,encoding='utf8')
        self.client=Client(self.profile);self.addCleanup(lambda:self.client.close())
        self.client.call('requirements.configure',{'languages':['english'],'allowSDH':False,'includeForced':False})
        self.scan()

    def scan(self):
        self.client.choose(self.media)
        self.client.call('embedded.configure',{'enabled':False,'language':'chinese'})
        folder=self.client.call('app.state')['summary']['folderId']
        self.client.job('scan.start',{'folderId':folder,'recursive':True,'move':False})
        self.context=self.context_now()

    def context_now(self):
        summary=self.client.call('app.state')['summary'];return {'scanId':summary['scanId'],'revision':summary['revision']}

    def inspect(self):
        report=self.client.job('requirements.check',self.context)
        page=self.client.call('requirements.query',{**self.context,'needsId':report['needsId']})
        return report,page

    def stage(self):
        report,page=self.inspect();self.assertEqual(report['reviewVideos'],1);self.assertEqual(report['upgradeCount'],1)
        params={**self.context,'needsId':report['needsId'],'offerId':page['rows'][0]['offers'][0]['offerId'],'acknowledged':True}
        self.client.job('requirements.stage',params);self.context=self.context_now()

    def test_stage_restart_confirm_execute_and_undo_preserve_original(self):
        self.stage();self.assertEqual(self.original.read_text(encoding='utf8'),BAD);self.assertTrue(self.candidate.exists())
        detail=self.client.details({**self.context,'rowId':'video-1'})
        self.assertEqual(detail['state'],'需确认');self.assertEqual(detail['subtitles'][0]['preservedOriginal'],self.original.name)
        self.assertNotEqual(detail['subtitles'][0]['targetPath'],str(self.original))
        preview=self.client.job('preview.create',self.context);self.assertFalse(preview['canExecute'])
        self.client.close();self.client=Client(self.profile);self.context=self.context_now()
        detail=self.client.details({**self.context,'rowId':'video-1'});self.assertEqual(detail['subtitles'][0]['preservedOriginal'],self.original.name)
        self.client.job('review.confirm',{**self.context,'rowId':'video-1'});self.context=self.context_now()
        preview=self.client.job('preview.create',self.context)
        result=self.client.job('organize.confirmAndStart',{'scanId':self.context['scanId'],'reviewRevision':self.context['revision'],
            'snapshotId':preview['snapshotId'],'confirmationToken':preview['confirmationToken'],'acknowledged':True})
        self.assertEqual(self.original.read_text(encoding='utf8'),BAD);self.assertFalse(self.candidate.exists())
        self.assertTrue((self.media/'Film.2024_2.en.srt').exists() or (self.media/'Film.2024_1.en.srt').exists())
        undo=self.client.job('operation.undoPreview',{'runId':result['batchId']})
        self.client.job('operation.confirm',{'runId':undo['runId'],'snapshotId':undo['snapshotId'],'confirmationToken':undo['confirmationToken'],'acknowledged':True})
        self.assertEqual(self.original.read_text(encoding='utf8'),BAD);self.assertEqual(self.candidate.read_text(encoding='utf8'),GOOD)

    def test_same_size_same_mtime_edit_refuses_stage_and_retains_files(self):
        report,page=self.inspect();stamp=self.candidate.stat()
        changed=GOOD.replace('text','edit');self.candidate.write_text(changed,encoding='utf8');os.utime(self.candidate,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
        with self.assertRaisesRegex(RuntimeError,'FILE_CHANGED'):
            self.client.job('requirements.stage',{**self.context,'needsId':report['needsId'],'offerId':page['rows'][0]['offers'][0]['offerId'],'acknowledged':True})
        self.assertEqual(self.original.read_text(encoding='utf8'),BAD);self.assertEqual(self.candidate.read_text(encoding='utf8'),changed)

    def test_policy_change_preserves_manual_choice_revokes_confirmations_and_old_preview(self):
        self.client.job('review.confirm',{**self.context,'rowId':'video-1'});self.context=self.context_now()
        preview=self.client.job('preview.create',self.context)
        self.client.job('requirements.configure',{'languages':['english','simplified'],'allowSDH':False,'includeForced':False});self.context=self.context_now()
        with self.assertRaisesRegex(RuntimeError,'STALE_PLAN'):self.client.call('preview.query',{'snapshotId':preview['snapshotId']})
        self.client.close();self.client=Client(self.profile);self.context=self.context_now()
        detail=self.client.details({**self.context,'rowId':'video-1'});self.assertEqual(detail['state'],'需确认')
        self.assertEqual(set(self.client.call('requirements.policy')['languages']),{'english','simplified'})
        self.assertEqual(self.original.read_text(encoding='utf8'),BAD)

    def test_rescan_satisfied_variants_do_not_create_download_tasks(self):
        self.original.write_text(GOOD,encoding='utf8');self.candidate.unlink();self.scan()
        report,_page=self.inspect();self.assertEqual(report['satisfiedVideos'],1)
        with self.assertRaisesRegex(RuntimeError,'NOT_FOUND'):self.client.call('subtitle.open',{**self.context,'needsId':report['needsId']})
        self.assertEqual(self.client.call('online.query')['total'],0)
        self.assertLessEqual(self.client.max_bytes,8192)

    def test_manual_lock_and_false_acknowledgement_never_replace_association(self):
        report,page=self.inspect()
        with self.assertRaisesRegex(RuntimeError,'CONFIRMATION_REQUIRED'):
            self.client.call('requirements.stage',{**self.context,'needsId':report['needsId'],'offerId':page['rows'][0]['offers'][0]['offerId'],'acknowledged':False})
        self.client.job('review.confirm',{**self.context,'rowId':'video-1'});self.context=self.context_now()
        report,_page=self.inspect();self.assertEqual(report['upgradeCount'],0)
        self.assertEqual(self.original.read_text(encoding='utf8'),BAD)

    def test_crash_between_policy_save_and_checkpoint_does_not_restore_old_approval(self):
        details=self.client.details({**self.context,'rowId':'video-1'})
        identifier=details['subtitles'][0]['subtitleId']
        self.client.job('review.assign',{**self.context,'rowId':'video-1','subtitleId':identifier,'replaceId':identifier});self.context=self.context_now()
        self.client.job('review.confirm',{**self.context,'rowId':'video-1'});self.client.close()
        # Simulate durable settings written just before interruption of draft publication.
        (self.profile/'subtitle-policy.json').write_text(json.dumps({'languages':['simplified'],'allowSDH':False,'includeForced':False}),encoding='utf8')
        self.client=Client(self.profile);self.context=self.context_now()
        details=self.client.details({**self.context,'rowId':'video-1'})
        self.assertTrue(details['subtitles'][0]['manual']);self.assertFalse(details['subtitles'][0]['confirmed'])
        self.assertEqual(details['state'],'需确认');self.assertTrue(self.candidate.exists())

    def test_snapshot_cannot_be_reused_in_a_new_page_session(self):
        report,_page=self.inspect();self.client.close();self.client=Client(self.profile);self.context=self.context_now()
        with self.assertRaisesRegex(RuntimeError,'STALE_NEEDS'):
            self.client.call('requirements.query',{**self.context,'needsId':report['needsId']})

    def test_candidate_edited_after_staging_blocks_new_final_preview(self):
        self.stage();self.candidate.write_text(GOOD.replace('text','edit'),encoding='utf8')
        self.client.job('review.confirm',{**self.context,'rowId':'video-1'});self.context=self.context_now()
        with self.assertRaisesRegex(RuntimeError,'FILE_CHANGED'):self.client.job('preview.create',self.context)
        self.assertEqual(self.original.read_text(encoding='utf8'),BAD)

    def test_usable_local_upgrade_candidate_prevents_duplicate_download_task(self):
        report,_page=self.inspect()
        with self.assertRaisesRegex(RuntimeError,'NOT_FOUND'):self.client.call('subtitle.open',{**self.context,'needsId':report['needsId']})
        self.assertEqual(self.client.call('online.query')['total'],0)
        self.assertFalse(any(frame.get('type')=='browser.search' for frame in self.client.events))
        self.assertEqual(self.original.read_text(encoding='utf8'),BAD)


if __name__=='__main__':unittest.main()
