"""Pinned local reads; only same-name NFO and explicitly requested video boundaries."""
from collections import OrderedDict
import hashlib
import os

from ..domain.matching import check_cancelled,episode_identity
from ..domain.media_identity import BLOCK,MAX_NFO,opensubtitles_hash,parse_nfo
from ..domain.errors import ProtocolError
from .subtitle_reader import read_handle


class LocalMediaIdentity:
    def __init__(self):self.cache=OrderedDict()

    def read(self,path,*,include_hash=False,should_stop=None):
        check_cancelled(should_stop)
        result={'ids':[],'conflict':False,'reasons':[],'hashStatus':'not_requested','hash':None,'bytesRead':0}
        nfo=path.with_suffix('.nfo')
        try:
            with read_handle(nfo) as stream:
                if os.fstat(stream.fileno()).st_size>MAX_NFO:raise ValueError('NFO 超过 512 KiB')
                raw=stream.read(MAX_NFO+1)
                result.update(parse_nfo(raw,episode=episode_identity(path.stem) is not None))
                result['nfoDigest']=hashlib.sha256(raw).hexdigest();result['nfoName']=nfo.name
        except FileNotFoundError:pass
        except (OSError,ValueError,ProtocolError) as error:result['reasons'].append(str(error)[:160])
        check_cancelled(should_stop)
        if not include_hash:return result
        with read_handle(path) as stream:
            before=os.fstat(stream.fileno())
            if before.st_size<2*BLOCK:result['hashStatus']='unsupported';return result
            head=stream.read(BLOCK);check_cancelled(should_stop);stream.seek(-BLOCK,os.SEEK_END);tail=stream.read(BLOCK)
            check_cancelled(should_stop);after=os.fstat(stream.fileno())
            if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):
                raise ProtocolError('FILE_CHANGED','读取视频指纹时文件发生变化。')
            key=(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)
            digest=hashlib.sha256(head+tail).hexdigest()
            previous=self.cache.get(key)
            hit=bool(previous and previous[0]==digest)
            value=previous[1] if hit else opensubtitles_hash(before.st_size,head,tail)
            self.cache[key]=(digest,value);self.cache.move_to_end(key)
            while len(self.cache)>64:self.cache.popitem(last=False)
            result.update(hash=value,hashStatus='ready',bytesRead=len(head)+len(tail),cacheHit=hit,
                hashNotice='仅供字幕来源查询的头尾指纹；不是 SHA256，也不能证明整个文件未变化。')
        return result
