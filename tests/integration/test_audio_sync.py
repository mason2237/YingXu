from pathlib import Path
import os
import tempfile
import time
import unittest
from tests.audio_fixtures import audio_case
from tests.integration.test_noqt_host import ROOT
from yingxu.adapters.sync_worker import SyncWorker
from yingxu.adapters.speech_cache import SpeechCache
from yingxu.domain.subtitle_document import parse_document
from yingxu.domain.sync_models import transform


class AudioSyncTests(unittest.TestCase):
    def test_real_audio_offset_drift_cache_and_silence_wrong_track(self):
        ffmpeg=Path(os.environ.get('YINGXU_TEST_FFMPEG',ROOT/'.venv-sync/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe'))
        if not ffmpeg.is_file():self.skipTest('Optional audio integration requires explicitly configured local FFmpeg; see DEVELOPMENT.md')
        with tempfile.TemporaryDirectory(dir=ROOT/'work/test-results') as directory:
            root=Path(directory);worker=SyncWorker(Path(os.environ.get('YINGXU_TEST_SYNC_ROOT',ROOT)),root)
            if not worker.available():self.skipTest('Optional synchronization runtime is not installed')
            worker.configure_ffmpeg(ffmpeg)
            audio,text=audio_case(root);outcomes=[]
            for scale in (1.,25/24):
                shifted=parse_document(transform(text,'srt',2500,scale),'srt');start=time.monotonic()
                result=worker.align(shifted,audio,mode='audio',track=0);outcomes.append({**result,'seconds':time.monotonic()-start})
                self.assertEqual(result['status'],'succeeded',result)
                aligned=parse_document(transform(transform(text,'srt',2500,scale),'srt',result['offsetMs'],result['scale']),'srt')
                expected=parse_document(text,'srt');self.assertLessEqual(max(abs(a.start-b.start) for a,b in zip(aligned.cues,expected.cues)),300)
            self.assertFalse(outcomes[0]['cacheHit']);self.assertTrue(outcomes[1]['cacheHit'])
            cache_file=next(worker.speech_cache.root.glob('*.npy'));cache_file.write_bytes(b'corrupt')
            rebuilt=worker.align(parse_document(transform(text,'srt',2500),'srt'),audio,mode='audio',track=0)
            self.assertEqual(rebuilt['status'],'succeeded');self.assertFalse(rebuilt['cacheHit'])
            source=parse_document(transform(text,'srt',2500),'srt')
            start=time.monotonic();bad=worker.align(source,audio,mode='audio',track=1,timeout=15)
            self.assertNotEqual(bad['status'],'succeeded');self.assertLess(time.monotonic()-start,15)
            silent,_=audio_case(root,count=40,silent=True)
            self.assertNotEqual(worker.align(source,silent,mode='audio',track=0)['status'],'succeeded')
            wrong,_=audio_case(root,seed=107)
            self.assertNotEqual(worker.align(source,wrong,mode='audio',track=0)['status'],'succeeded')
            sparse,_=audio_case(root,count=3)
            self.assertNotEqual(worker.align(source,sparse,mode='audio',track=0)['status'],'succeeded')
            # A cut moving one half by eight seconds cannot be certified as a
            # single affine correction by the independent three-window gate.
            from dataclasses import replace
            from yingxu.domain.subtitle_document import SubtitleDocument
            cut=SubtitleDocument('srt',tuple(replace(c,start=c.start+(8000 if i>=20 else 0),end=c.end+(8000 if i>=20 else 0)) for i,c in enumerate(source.cues)),(),())
            self.assertNotEqual(worker.align(cut,audio,mode='audio',track=0)['status'],'succeeded')
            import json
            (ROOT/'work/test-results/audio-sync-results.json').write_text(json.dumps(outcomes,indent=2)+'\n',encoding='utf8')

    def test_content_cache_invalidates_middle_only_same_time_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();media=root/'media.mkv';media.write_bytes(b'A'*200000)
            cache=SpeechCache(root/'cache');first=cache.prepare(media,0,'tool');stamp=media.stat()
            raw=bytearray(media.read_bytes());raw[100000]=66;media.write_bytes(raw);os.utime(media,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
            self.assertNotEqual(first['key'],cache.prepare(media,0,'tool')['key'])
