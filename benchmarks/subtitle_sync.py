"""Independent cold/hot synthetic speech benchmark, separate from correctness tests."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.audio_fixtures import audio_case
from tests.integration.test_noqt_host import ROOT
from yingxu.adapters.sync_worker import SyncWorker
from yingxu.domain.subtitle_document import parse_document
from yingxu.domain.sync_models import transform

parser=argparse.ArgumentParser();parser.add_argument('--cases',choices=['synthetic'],default='synthetic');parser.add_argument('--workers',type=int,choices=[1],default=1);parser.parse_args()
with tempfile.TemporaryDirectory(dir=ROOT/'work/test-results') as directory:
    root=Path(directory);video,text=audio_case(root);worker=SyncWorker(ROOT,root)
    worker.configure_ffmpeg(ROOT/'.venv-sync/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe')
    results=[]
    for label in ('cold','hot'):
        start=time.monotonic();result=worker.align(parse_document(transform(text,'srt',2500),'srt'),video,mode='audio',track=0)
        results.append({'case':label,'seconds':round(time.monotonic()-start,3),'cacheHit':result.get('cacheHit'),'status':result['status'],'mediaBytes':video.stat().st_size,'workers':1,'metrics':result.get('metrics')})
    print(json.dumps(results,indent=2))
