"""Restricted optional ffsubsync 0.5.1 worker; no GUI or arbitrary CLI forwarding."""
import contextlib
import json
from pathlib import Path
import sys
import os
if not getattr(sys,'frozen',False):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


class LimitedLog:
    def __init__(self,stream):self.stream,self.left=stream,65536
    def write(self,value):
        part=value[:self.left];self.left-=len(part)
        if part:self.stream.write(part)
        return len(value)
    def flush(self):self.stream.flush()
    def isatty(self):return False


def main():
    if sys.stdin is None or sys.stdout is None:
        from yingxu.desktop.streams import attach_inherited_streams
        attach_inherited_streams()
    request=json.loads(sys.stdin.buffer.read(8193))
    if not isinstance(request,dict) or set(request)-{'v','source','reference','output','mode','ffmpeg','track','cache','cacheHit'} or request.get('v')!=1:raise ValueError('Invalid sync request')
    source,reference,output=(Path(request[k]) for k in ('source','reference','output'))
    if not all(p.is_absolute() for p in (source,reference,output)) or output.parent!=source.parent or output.exists() or output.is_symlink():raise ValueError('Invalid worker paths')
    if request.get('mode') not in {'reference','audio'}:raise ValueError('Invalid sync mode')
    with contextlib.redirect_stdout(LimitedLog(sys.stderr)),contextlib.redirect_stderr(LimitedLog(sys.stderr)):
        import ffsubsync
        from ffsubsync.ffsubsync import make_parser,run
        if ffsubsync.__version__!='0.5.1':raise ValueError('Unsupported engine version')
        args=[str(reference),'-i',str(source),'-o',str(output),'--skip-sync-on-low-quality','--vad','webrtc','--encoding','utf-8']
        if request.get('mode')=='audio':
            if type(request.get('track')) is not int or not 0<=request['track']<=31:raise ValueError('Select an audio track')
            args+=['--reference-stream',f'a:{request["track"]}','--ffmpeg-path',request['ffmpeg'],'--max-duration-seconds','14400']
        if request.get('mode')=='audio':
            import numpy as np
            from ffsubsync.ffsubsync import make_reference_pipe,try_sync,validate_and_transform_args
            from yingxu.domain.subtitle_document import parse_document,SubtitleDocument,Cue
            from yingxu.domain.sync_models import transform
            from yingxu.domain.sync_quality import reference_quality
            parsed_args=validate_and_transform_args(make_parser().parse_args(args))
            cache=Path(request['cache'])
            if not cache.is_absolute() or cache.suffix!='.npy' or cache.parent.name!='speech-cache':raise ValueError('Invalid speech cache')
            if request.get('cacheHit'):
                speech=np.load(cache,mmap_mode='r',allow_pickle=False)
                if speech.ndim!=1 or speech.dtype!=np.uint8 or speech.size>1440000 or np.any(speech>1):raise ValueError('Invalid speech array')
            else:
                pipe=make_reference_pipe(parsed_args);pipe.fit(str(reference));speech=(np.asarray(pipe.transform(str(reference)))>=1).astype(np.uint8)
                if speech.ndim!=1 or speech.size>1440000:raise ValueError('Audio analysis exceeds four-hour limit')
                temporary=cache.with_suffix('.part')
                with temporary.open('wb') as stream:np.save(stream,speech,allow_pickle=False);stream.flush();os.fsync(stream.fileno())
                os.replace(temporary,cache)
            class CachedReference:
                def transform(self,*_args):return speech.astype(float)
                def __getitem__(self,_index):return self
            result={'retval':0};try_sync(parsed_args,CachedReference(),result)
            result['analysisComplete']=True
            if result.get('sync_was_successful'):
                edges=np.diff(np.concatenate(([0],speech,[0])));starts=np.flatnonzero(edges==1);ends=np.flatnonzero(edges==-1)
                if len(starts)>50000 or speech.sum()<500 or speech.mean()>.9:
                    result.update(sync_was_successful=False,quality={'accepted':False,'reason':'静音、对白过少或恒定声音不足以可靠对齐。'})
                else:
                    ref_doc=SubtitleDocument('speech',tuple(Cue(str(i),0,int(a)*10,int(b)*10,'speech') for i,(a,b) in enumerate(zip(starts,ends))),(),())
                    aligned=parse_document(transform(source.read_text(encoding='utf8'),'srt',round(result['offset_seconds']*1000),result['framerate_scale_factor']),'srt')
                    result['quality']=reference_quality(aligned,ref_doc)
                    if not result['quality']['accepted']:result['sync_was_successful']=False
        else:result=run(make_parser().parse_args(args))
    data={k:result.get(k) for k in ('retval','sync_was_successful','offset_seconds','framerate_scale_factor','analysisComplete','quality')}
    sys.stdout.write(json.dumps({'v':1,**data},allow_nan=False)+'\n');sys.stdout.flush()
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception:
        if sys.stdout:sys.stdout.write('{"v":1,"retval":1,"sync_was_successful":false}\n');sys.stdout.flush()
        # A windowed frozen executable otherwise displays a modal traceback
        # dialog, keeping its Job and temporary files alive until timeout.
        import traceback
        if sys.stderr:traceback.print_exc(file=LimitedLog(sys.stderr));sys.stderr.flush()
        raise SystemExit(1)
