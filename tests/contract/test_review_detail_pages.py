"""Large, legitimate metadata stays complete over bounded versioned replies."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from uuid import uuid4

from yingxu.application.reviewing import ReviewData
from yingxu.desktop.host import Host
from yingxu.desktop.messages import MAX_BYTES, dumps
from yingxu.domain.media import track_info
from yingxu.domain.review import ReviewPlan, path_key

ROOT = Path(__file__).resolve().parents[2]


class ReviewDetailPageContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='detail-pages-', dir=ROOT/'work/test-results')
        self.root = Path(self.temp.name)
        self.media = self.root/'media';self.media.mkdir()
        self.video = self.media/'Series.S02E01.1080p.NF.WEB-DL.mkv'
        self.video.write_bytes(b'generated unchanged video')
        self.frames = []
        self.host = Host(self.root/'profile', send=self.frames.append)
        self.sid = self.call('app.hello')['data']['sessionId']
        while self.host.workspace.worker: self.host.loop.tick()
        self.host.workspace.accept_folder(self.media)
        self.tracks = [track_info(SimpleNamespace(language='zho', title=f'简体中文 {i} '+('标题🙂'*80),
                      format='ASS', codec_id='', forced='No', default='Yes'), i) for i in range(1, 65)]
        metadata = {'status':'ok', 'tracks':self.tracks, 'satisfied':True,
                    'acceptedTrackIds':[track['trackId'] for track in self.tracks],
                    'reason':'内嵌字幕语言符合要求', 'policy':'chinese', 'policyLabel':'中文（双语优先）'}
        review = ReviewPlan([self.video], [], exists=lambda path:False, embedded={path_key(self.video):metadata})
        self.data = ReviewData(review, self.host.workspace.register)
        self.host.workspace.data = self.data
        self.context = {'scanId':self.data.scan_id, 'revision':self.data.revision, 'rowId':'video-1'}

    def tearDown(self):
        self.host.close();self.temp.cleanup()

    def call(self, action, params=None):
        rid = uuid4().hex
        self.host.receive({'v':2,'type':'request','requestId':rid,
                           'sessionId':None if action=='app.hello' else self.sid,
                           'action':action,'params':params or {}})
        return next(frame for frame in reversed(self.frames) if frame.get('requestId')==rid and frame['type']=='reply')

    def test_sixty_four_unicode_tracks_round_trip_without_relaxing_message_limit(self):
        self.assertGreater(len(json.dumps(self.data.rows[0], ensure_ascii=False).encode('utf8')), MAX_BYTES)
        header = self.call('review.details', self.context)
        self.assertTrue(header['ok'], header)
        self.assertEqual(header['data']['detailCounts']['tracks'], 64)
        self.assertEqual(header['data']['embedded']['tracks'], [])
        self.assertTrue(header['data']['embeddedSatisfied'])
        listing = self.call('review.query', {k:v for k,v in self.context.items() if k!='rowId'})['data']
        self.assertEqual(listing['total'], 1)
        self.assertEqual(len(listing['rows'][0]['embedded']['tracks']), 2)
        self.assertEqual(listing['rows'][0]['embedded']['trackCount'], 64)
        actual = []
        while len(actual) < 64:
            frame = self.call('review.detailPage', {**self.context,'section':'tracks','offset':len(actual),'limit':20})
            self.assertTrue(frame['ok'], frame)
            page = frame['data'];self.assertTrue(page['entries'])
            actual.extend(page['entries'])
            self.assertEqual(page['nextOffset'], len(actual) if len(actual)<64 else None)
        self.assertEqual(actual, self.tracks)
        self.assertTrue(all(len(dumps(frame).encode('utf8'))<=MAX_BYTES for frame in self.frames))
        self.assertEqual(self.video.read_bytes(), b'generated unchanged video')

    def test_each_page_is_version_bound_and_sections_are_whitelisted(self):
        for section in ('subtitles','warnings','basis'):
            page = self.call('review.detailPage', {**self.context,'section':section})
            self.assertTrue(page['ok'], page)
            self.assertEqual(page['data']['entries'], self.data.detail_entries(0, section))
        for params in ({'section':'__dict__'}, {'section':'tracks','offset':True}, {'section':'tracks','path':str(self.video)}):
            self.assertEqual(self.call('review.detailPage', {**self.context,**params})['error']['code'], 'INVALID_REQUEST')
        self.host.workspace.data = self.data.updated('review.skip', {'rowId':'video-1','skipped':True})
        stale = self.call('review.detailPage', {**self.context,'section':'tracks','offset':1})
        self.assertEqual(stale['error']['code'], 'STALE_REVIEW')


if __name__ == '__main__': unittest.main()
