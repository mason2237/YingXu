"""Content-verified local analysis cache, never pickle or media-directory data."""
import hashlib
import json
import os
from pathlib import Path
from .subtitle_reader import read_handle
from .subtitle_imports import private_path
from ..domain.matching import check_cancelled


def file_digest(path,stop=None):
    digest=hashlib.sha256()
    with read_handle(path) as stream:
        while block:=stream.read(1024*1024):check_cancelled(stop);digest.update(block)
    return digest.hexdigest()


class SpeechCache:
    def __init__(self,root):self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);private_path(self.root,self.root)

    def prepare(self,video,track,tool_digest,stop=None):
        identity=file_digest(video,stop)
        key=hashlib.sha256(json.dumps([identity,track,'ffsubsync-0.5.1','webrtc','16k-100hz-v1',tool_digest]).encode()).hexdigest()
        path=self.root/(key+'.npy');record=self.root/(key+'.json');hit=False;metadata={}
        if path.exists() and record.exists():
            try:
                private_path(path,self.root);private_path(record,self.root)
                if record.stat().st_size>4096 or path.stat().st_size>8*1024*1024:raise ValueError('Cache limit')
                metadata=json.loads(record.read_text(encoding='utf8'));hit=metadata['key']==key and file_digest(path,stop)==metadata['digest']
            except (OSError,ValueError,KeyError):pass
        if not hit:
            entries=list(self.root.glob('*.npy'))
            if len(entries)>=32 or sum(p.stat().st_size for p in entries)>128*1024*1024:raise ValueError('音频分析缓存已满，请清理未使用的分析缓存。')
            # A corrupt object is not an authorised worker input; only its own
            # content-addressed cache slot may be replaced after a complete analysis.
        return {'key':key,'path':path,'hit':hit,'videoDigest':identity,'digest':metadata.get('digest') if hit else None}

    def clear(self):
        private_path(self.root,self.root);count=0
        for path in self.root.iterdir():
            if path.suffix not in {'.npy','.json','.part','.tmp'} or len(path.stem)!=64 or any(c not in '0123456789abcdef' for c in path.stem):continue
            private_path(path,self.root)
            if path.is_file():path.unlink();count+=1
        return {'removedFiles':count}

    def commit(self,record):
        path=record['path']
        if not path.is_file() or path.stat().st_size>8*1024*1024:return
        private_path(path,self.root);target=path.with_suffix('.json');temporary=target.with_suffix('.tmp')
        data={'key':record['key'],'digest':file_digest(path),'engine':'ffsubsync-0.5.1','vad':'webrtc','videoDigest':record['videoDigest']}
        with temporary.open('w',encoding='utf8') as stream:json.dump(data,stream);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,target)
