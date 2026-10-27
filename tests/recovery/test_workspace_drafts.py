"""Actual host restarts preserve drafts/queues without replaying external effects."""
import json
import os
from pathlib import Path
import time
import unittest

from tests.integration import test_subtitle_inbox as inbox
from tests.integration.test_noqt_host import Client


class WorkspaceDraftTests(unittest.TestCase):
    scan = inbox.InboxTests.scan

    def setUp(self):
        inbox.InboxTests.setUp(self)

    def restart(self, *, crash=False):
        if crash:
            process=self.client.process
            process.kill();process.wait(timeout=10)
            for pipe in (process.stdin,process.stdout,process.stderr):pipe.close()
        else:self.client.close()
        self.client=Client(self.profile)
        for _ in range(1000):
            state=self.client.call('app.state')
            if not state['busy']:return state
        self.fail('Draft restoration did not finish')

    def context_now(self):
        summary=self.client.call('app.state')['summary']
        return {'scanId':summary['scanId'],'revision':summary['revision']}

    def test_force_exit_restores_manual_review_and_skip_but_not_permission(self):
        (self.media/'Other.mkv').write_bytes(b'unchanged second video')
        (self.media/'Spare.en.srt').write_text('1\n00:00:01,000 --> 00:00:02,000\nHello\n',encoding='utf8')
        self.scan()
        candidate=self.client.job('review.candidates',{**self.context,'rowId':'video-1'})['entries'][0]
        self.client.job('review.assign',{**self.context,'rowId':'video-1','subtitleId':candidate['subtitleId']})
        context=self.context_now()
        self.client.job('review.skip',{**context,'rowId':'video-2','skipped':True})
        before={p.name:p.read_bytes() for p in self.media.iterdir()}
        state=self.restart(crash=True)
        self.assertTrue(state['draft']['restored'])
        context=self.context_now()
        first=self.client.call('review.details',{**context,'rowId':'video-1'})
        second=self.client.call('review.details',{**context,'rowId':'video-2'})
        self.assertEqual(first['subtitles'][0]['name'],'Spare.en.srt')
        self.assertTrue(first['subtitles'][0]['manual'])
        self.assertEqual(second['state'],'已跳过')
        self.assertEqual({p.name:p.read_bytes() for p in self.media.iterdir()},before)
        with self.assertRaisesRegex(RuntimeError,'STALE_PLAN'):
            self.client.call('organize.confirmAndStart',{'scanId':context['scanId'],'reviewRevision':context['revision'],
                'snapshotId':'old','confirmationToken':'old','acknowledged':True})

    def test_subtitle_edited_with_same_size_and_time_blocks_old_draft(self):
        subtitle=self.media/'Atlas.S01E001.chs.srt'
        subtitle.write_bytes(b'original subtitle')
        self.scan();self.client.close()
        mark=subtitle.stat();subtitle.write_bytes(b'modified subtitle')
        os.utime(subtitle,ns=(mark.st_atime_ns,mark.st_mtime_ns))
        state=self.restart()
        self.assertFalse(state['draft']['restored'])
        self.assertIn('变化',state['draft']['message'])
        self.assertEqual(subtitle.read_bytes(),b'modified subtitle')

    def select(self, identifier):
        self.client.call('online.start',{'taskId':identifier,'query':'Atlas','provider':'subhd'})
        frame=next(value for value in reversed(self.client.events) if value.get('type')=='browser.search')
        self.client.feed({'type':'browser.result','taskId':identifier,'effectId':frame['effectId'],'generation':frame['generation'],
            'status':'results','final':True,'raw':json.dumps({'status':'ready','rows':[
                {'url':'https://subhd.me/a/TEST123','title':'Atlas','release':'Atlas S01E001','metadata':'双语'}]})})
        candidate=self.client.call('online.candidates',{'taskId':identifier})['rows'][0]
        self.client.call('online.select',{'taskId':identifier,'candidateId':candidate['candidateId']})

    def test_batch_queue_restores_paused_and_requires_new_confirmation(self):
        (self.media/'Atlas.S01E002.mkv').write_bytes(b'unchanged second video')
        self.scan();self.client.call('subtitle.open',self.context)
        ids=[row['taskId'] for row in self.client.call('online.query')['tasks']]
        for identifier in ids:self.select(identifier)
        self.client.call('online.download',{'taskIds':ids,'acknowledged':True})
        state=self.restart(crash=True)
        self.assertTrue(state['draft']['restored'])
        query=self.client.call('online.query')
        self.assertEqual(query['total'],2);self.assertEqual(query['pausedCount'],2)
        self.assertFalse(any(frame.get('type') in {'browser.search','browser.arm'} for frame in self.client.events))
        with self.assertRaisesRegex(RuntimeError,'CONFIRMATION_REQUIRED'):
            self.client.call('online.resumeQueue',{'acknowledged':False})
        self.client.call('online.resumeQueue',{'acknowledged':True})
        arms=[frame for frame in self.client.events if frame.get('type')=='browser.arm']
        self.assertEqual(arms[-1]['taskId'],ids[0])
        self.client.call('online.cancel',{'taskId':ids[0]})
        arms=[frame for frame in self.client.events if frame.get('type')=='browser.arm']
        self.assertEqual(arms[-1]['taskId'],ids[1])


if __name__=='__main__':unittest.main()
