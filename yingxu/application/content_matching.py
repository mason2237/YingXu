"""Opt-in, bounded subtitle-only comparison, isolated from name matching decisions."""
from collections import OrderedDict
from ..domain.errors import ProtocolError
from ..domain.content_matching import compare,features
from ..domain.subtitle_quality import analyze
from ..domain.subtitle_variants import variant_of
from ..domain.matching import check_cancelled


class ContentMatching:
    def __init__(self,workspace):self.workspace=workspace;self.cache=OrderedDict()

    def inspect(self,path,stop):
        read=self.workspace.quality.reader.read(path,should_stop=stop)
        if read.text is None:return {'sufficient':False,'windows':[],'samples':[]}
        key=(read.digest,'content-1')
        if key not in self.cache:
            report=analyze(read,should_stop=stop)
            self.cache[key]=features(report.document,stop) if report.document.complete and not report.summary()['errors'] and not any(i.code=='SUSPECT_ENCODING' for i in report.document.issues) else {'sufficient':False,'windows':[],'samples':[]}
            while len(self.cache)>12:self.cache.popitem(last=False)
        self.cache.move_to_end(key);return self.cache[key]

    def dispatch(self,params):
        ws=self.workspace;data=ws.require_review(params);index=data.index(params['rowId']);reference=data.subtitle_ids.get(params['referenceId'])
        if reference is None:raise ProtocolError('NOT_FOUND','请主动选择当前工作区的可信参考字幕。')
        session=ws.session_id
        # At most seven bounded subtitle reads: reference + six name-ranked candidates.
        def work(worker):
            candidates=[path for path,score,owner,language in data.review.candidates(index)
                        if path!=reference and owner in (None,index)][:6]
            ref=self.inspect(reference,worker.stop.is_set);variant=variant_of(reference);rows=[]
            for i,path in enumerate(candidates):
                check_cancelled(worker.stop.is_set);worker.report(i,len(candidates),'只比较所选参考与前六份字幕，不读取视频或联网','content')
                other=variant_of(path);same=bool(variant.languages and variant.languages==other.languages and not variant.ambiguous and not other.ambiguous
                    and (not variant.script or not other.script or variant.script==other.script))
                result=compare(ref,self.inspect(path,worker.stop.is_set),same_language=same)
                rows.append({'subtitleId':data.register(path),'name':path.name,**result})
            rows.sort(key=lambda r:-(r['score'] if r['score'] is not None else -1))
            top=rows[:2];margin=round(top[0]['score']-top[1]['score'],4) if len(top)==2 and all(r['score'] is not None for r in top) else None
            if margin is not None and margin<.1:
                for row in top:row.update(status='ambiguous',reason='前两项文本接近，需要人工核对；不会自动改配。')
            return {'rows':top,'comparedCount':len(candidates),'margin':margin,'videoBytesRead':0,'automaticAssociation':False,
                'scope':'前六份文件名候选及所选参考；同语言、开头/中部/尾部文本；不是作品身份认证。'}
        def complete(value):
            if ws.data is not data or ws.session_id!=session:raise ProtocolError('STALE_REVIEW','页面或审阅已变化，请重新比较。')
            return value
        return ws.launch('content',work,complete,'按需比较本地字幕文本，原关联不变…')
