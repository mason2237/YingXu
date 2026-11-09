"""Optional isolated process; bounded logs and results, no shell arguments from UI."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import math
import hashlib
import os
from contextlib import ExitStack
from .sync_process_tree import ProcessTree
from .speech_cache import SpeechCache,file_digest
from .subtitle_reader import read_handle
from .json_settings import JSONSettings

from ..domain.matching import check_cancelled
from ..domain.subtitle_document import parse_document
from ..domain.sync_models import canonical_srt


class SyncWorker:
    def __init__(self,root,profile):
        self.root,self.profile=Path(root),Path(profile)
        self.speech_cache=SpeechCache(self.profile/'speech-cache')
        self.settings=JSONSettings(self.profile/'sync-tools.json',{'ffmpeg':'','digest':''})

    def configure_ffmpeg(self,path):
        path=Path(path).absolute()
        if not path.name.lower().startswith('ffmpeg') or path.suffix.lower()!='.exe':raise ValueError('请选择本机 ffmpeg.exe。')
        digest=file_digest(path)
        with read_handle(path):
            tree=ProcessTree([str(path),'-version'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            try:
                raw=tree.process.communicate(timeout=10)[0]
                if tree.process.returncode or not raw.startswith(b'ffmpeg version') or len(raw)>65536:raise ValueError('所选程序未返回 FFmpeg 版本。')
            finally:tree.close()
        self.settings.write({'ffmpeg':str(path),'digest':digest})
        return {'configured':True,'digest':digest,'version':raw.decode(errors='replace').splitlines()[0][:100]}

    def audio_tool(self):
        value=self.settings.read();path=Path(value['ffmpeg']) if value['ffmpeg'] else None
        return path if path and path.is_file() else None

    def command(self):
        frozen=self.root/'python/YingXuSync.exe'
        if frozen.is_file():return [str(frozen)]
        python=self.root/'.venv-sync/Scripts/python.exe'
        return [str(python),str(self.root/'scripts/sync_worker_entry.py')] if python.is_file() else []

    def available(self):return bool(self.command())

    def align(self,source,reference,*,should_stop=None,mode='reference',ffmpeg=None,track=0,timeout=120):
        if not self.available():return {'status':'failed','reason':'可选 ffsubsync 引擎未安装。'}
        check_cancelled(should_stop);work=self.profile/'worker';work.mkdir(parents=True,exist_ok=True)
        cache=None
        with ExitStack() as held,tempfile.TemporaryDirectory(dir=work) as directory:
            if mode=='audio':
                ffmpeg=self.audio_tool()
                if not ffmpeg:return {'status':'failed','reason':'请先选择本机 FFmpeg。'}
                held.enter_context(read_handle(ffmpeg));held.enter_context(read_handle(Path(reference)))
                if file_digest(ffmpeg,should_stop)!=self.settings.read()['digest']:return {'status':'failed','reason':'FFmpeg 已变化，请重新选择核对。'}
                cache=self.speech_cache.prepare(Path(reference),track,self.settings.read()['digest'],should_stop)
                if cache['hit']:
                    held.enter_context(read_handle(cache['path']))
                    if file_digest(cache['path'],should_stop)!=cache['digest']:return {'status':'failed','reason':'音频分析缓存发生变化，请重试。'}
            directory=Path(directory);input=directory/'input.srt';output=directory/'output.srt'
            input.write_text(canonical_srt(source),encoding='utf8')
            if mode=='reference':
                ref=directory/'reference.srt';ref.write_text(canonical_srt(reference),encoding='utf8')
            else:ref=Path(reference)
            request={'v':1,'mode':mode,'source':str(input),'reference':str(ref),'output':str(output)}
            if mode=='audio':request.update(ffmpeg=str(ffmpeg),track=track,cache=str(cache['path']),cacheHit=cache['hit'])
            with (directory/'log.txt').open('wb') as log:
                tree=ProcessTree(self.command(),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,
                    env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'});process=tree.process
                try:
                    process.stdin.write(json.dumps(request).encode());process.stdin.close()
                    deadline=time.monotonic()+timeout
                    while process.poll() is None:
                        check_cancelled(should_stop)
                        if time.monotonic()>deadline:raise TimeoutError('同步引擎超时，未生成可采用结果。')
                        time.sleep(.05)
                    raw=process.stdout.read(8193)
                    metrics=tree.stats()
                    if process.returncode or len(raw)>8192:return {'status':'failed','reason':'同步引擎未正常完成。'}
                    result=json.loads(raw)
                    if cache and result.get('analysisComplete') is True:self.speech_cache.commit(cache)
                    if result.get('retval')!=0 or result.get('sync_was_successful') is not True or not output.is_file():return {'status':'low_quality','reason':(result.get('quality') or {}).get('reason','引擎没有确认可信同步结果。')}
                    if output.stat().st_size>8*1024*1024:raise ValueError('引擎输出超出限制')
                    parsed=parse_document(output.read_text(encoding='utf8'),'srt')
                    originals=[c for c in source.cues if c.kind!='comment']
                    if len(parsed.cues)!=len(originals) or not parsed.complete or parsed.issues:return {'status':'failed','reason':'引擎输出丢失或破坏字幕条目。'}
                    scale,offset=result.get('framerate_scale_factor'),result.get('offset_seconds')
                    if type(scale) not in {int,float} or type(offset) not in {int,float} or not math.isfinite(scale) or not math.isfinite(offset) or not .9<=scale<=1.1 or abs(offset)>86400:return {'status':'failed','reason':'引擎时间参数无效。'}
                    if any(new.text!=f'Text {i}' or abs(new.start-(old.start*scale+offset*1000))>30 or abs(new.end-(old.end*scale+offset*1000))>30 for i,(old,new) in enumerate(zip(originals,parsed.cues),1)):
                        return {'status':'failed','reason':'引擎结果与声明的调整或条目不一致。'}
                    return {'status':'succeeded','scale':scale,'offsetMs':round(offset*1000),'engine':'ffsubsync-0.5.1',
                        'metrics':metrics,**({'quality':result.get('quality',{}),'cacheHit':cache['hit']} if cache else {})}
                finally:
                    tree.close()
                    if process.poll() is None:process.kill();process.wait(timeout=10)
                    process.stdout.close()
                    log.flush()
                    self.profile.joinpath('last-sync.log').write_bytes((directory/'log.txt').read_bytes()[-65536:])
