from pathlib import Path
import random
import tempfile
import unittest
import sys
import os
from yingxu.adapters.sync_worker import SyncWorker
from yingxu.domain.subtitle_document import parse_document
from yingxu.domain.sync_models import transform
from yingxu.domain.sync_quality import reference_quality
from tests.integration.test_noqt_host import ROOT


class ReferenceSyncTests(unittest.TestCase):
    def test_zero_exit_false_success_or_missing_output_is_not_success(self):
        document=parse_document('1\n00:00:01,000 --> 00:00:02,000\nText\n','srt')
        with tempfile.TemporaryDirectory(dir=ROOT/'work/test-results') as directory:
            root=Path(directory);script=root/'fake.py';script.write_text('import sys\nsys.stdin.read()\nprint(\'{"v":1,"retval":0,"sync_was_successful":true,"offset_seconds":0,"framerate_scale_factor":1}\')\n')
            worker=SyncWorker(ROOT,root);worker.command=lambda:[sys.executable,str(script)]
            self.assertEqual(worker.align(document,document)['status'],'low_quality')

    def test_timeout_stops_worker(self):
        document=parse_document('1\n00:00:01,000 --> 00:00:02,000\nText\n','srt')
        with tempfile.TemporaryDirectory(dir=ROOT/'work/test-results') as directory:
            root=Path(directory);script=root/'slow.py';script.write_text('import time\ntime.sleep(30)\n')
            worker=SyncWorker(ROOT,root);worker.command=lambda:[sys.executable,str(script)]
            with self.assertRaises(TimeoutError):worker.align(document,document,timeout=.1)

    def test_real_fixed_engine_offset_drift_and_wrong_reference(self):
        rng=random.Random(20261109);position=15000;parts=[]
        for i in range(100):
            position+=rng.randint(2000,8000);duration=rng.randint(600,2500)
            from yingxu.domain.sync_models import stamp
            parts.append(f'{i+1}\n{stamp(position,"srt","00:00:00,000")} --> {stamp(position+duration,"srt","00:00:00,000")}\nGenerated {i}\n');position+=duration
        text='\n'.join(parts);reference=parse_document(text,'srt')
        with tempfile.TemporaryDirectory(dir=ROOT/'work/test-results') as directory:
            worker=SyncWorker(Path(os.environ.get('YINGXU_TEST_SYNC_ROOT',ROOT)),Path(directory))
            if not worker.available():self.skipTest('Optional fixed engine is not installed; local candidate validation runs this test with the real engine')
            for scale in (1.,25/24):
                shifted=transform(text,'srt',2500,scale);source=parse_document(shifted,'srt')
                result=worker.align(source,reference);self.assertEqual(result['status'],'succeeded',result)
                aligned=parse_document(transform(shifted,'srt',result['offsetMs'],result['scale']),'srt')
                self.assertLessEqual(max(abs(a.start-b.start) for a,b in zip(aligned.cues,reference.cues)),30)
                self.assertTrue(reference_quality(aligned,reference)['accepted'])
            self.assertFalse(reference_quality(reference,parse_document('1\n00:00:01,000 --> 00:00:03,000\nWrong\n','srt'))['accepted'])
