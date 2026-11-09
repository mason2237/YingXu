"""Selected-subtitle transformations -> private candidate -> new review/confirmation."""
from dataclasses import asdict
from pathlib import Path
from ..domain.errors import ProtocolError
from ..domain.review import path_key
from ..domain.subtitle_document import parse_document
from ..domain.subtitle_quality import analyze
from ..domain.sync_models import transform
from ..domain.sync_quality import reference_quality
from .reviewing import ReviewData


class Synchronizing:
    def __init__(self,workspace,artifacts,engine):self.workspace,self.artifacts,self.engine=workspace,artifacts,engine

    def source(self,data,index,identifier):
        path=data.subtitle_ids.get(identifier)
        if path is None or not any(m.source==path for m in data.review.rows[index].matches):raise ProtocolError('NOT_FOUND','请选择当前视频已关联的一份文字字幕。')
        return path

    def preview(self,record):
        meta=record['metadata']
        return {'artifactId':record['id'],'name':record['name'],'status':'succeeded',
            **{k:meta[k] for k in ('engine','offsetMs','scale','before','after','quality')},'originalPreserved':True}

    def dispatch(self,action,params):
        ws=self.workspace
        if action=='sync.capabilities':return {'manual':True,'reference':self.engine.available(),'audio':bool(self.engine.available() and self.engine.audio_tool()),'negativeTime':'reject','engine':'ffsubsync-0.5.1','vad':'webrtc','piecewise':False}
        if action=='sync.clearAnalysis':
            ws.require_idle()
            if not params['acknowledged']:raise ProtocolError('CONFIRMATION_REQUIRED','请确认清理可重建的音频分析缓存。')
            return self.engine.speech_cache.clear()
        data=ws.require_review(params);index=data.index(params['rowId']);row=data.review.rows[index]
        if action=='sync.references':
            values=[{'subtitleId':key,'name':path.name} for key,path in data.subtitle_ids.items()]
            offset,limit=params.get('offset',0),params.get('limit',20)
            return {'rows':values[offset:offset+limit],'total':len(values),'offset':offset}
        if action=='sync.results':
            values=[self.preview(r) for r in self.artifacts.list() if r['metadata'].get('video')==str(row.video)]
            offset,limit=params.get('offset',0),params.get('limit',20)
            return {'rows':values[offset:offset+limit],'total':len(values),'offset':offset}
        if action=='sync.create':
            source=self.source(data,index,params['subtitleId']);mode=params['syncMode'];session=ws.session_id
            if mode not in {'manual','reference','audio'}:raise ProtocolError('UNAVAILABLE','不支持的时间处理方式。')
            reference=data.subtitle_ids.get(params.get('referenceId'))
            if mode=='reference' and (not reference or reference==source):raise ProtocolError('INVALID_REQUEST','请明确选择另一份可信本地参考字幕。')
            def work(worker):
                read=ws.quality.reader.read(source,encoding=params.get('encoding','auto'),should_stop=worker.stop.is_set)
                report=analyze(read,should_stop=worker.stop.is_set)
                if read.text is None or report.summary()['errors'] or not report.document.complete:raise ValueError('原字幕结构或编码尚未通过检查，不能生成时间调整结果。')
                decision={'status':'succeeded','engine':'manual','offsetMs':params.get('offsetMs',0),'scale':1.}
                ref_report=None
                if mode=='reference':
                    reference_read=ws.quality.reader.read(reference,encoding=params.get('referenceEncoding','auto'),should_stop=worker.stop.is_set)
                    ref_report=analyze(reference_read,should_stop=worker.stop.is_set)
                    if reference_read.text is None or ref_report.summary()['errors'] or not ref_report.document.complete:raise ValueError('参考字幕未通过结构或编码检查。')
                    decision=self.engine.align(report.document,ref_report.document,should_stop=worker.stop.is_set)
                elif mode=='audio':
                    if 'audioTrack' not in params:raise ProtocolError('INVALID_REQUEST','请主动选择音轨编号。')
                    decision=self.engine.align(report.document,row.video,mode='audio',track=params['audioTrack'],should_stop=worker.stop.is_set)
                if decision['status']!='succeeded':return decision
                text=transform(read.text,read.format,decision['offsetMs'],decision['scale']);after=parse_document(text,read.format)
                quality=reference_quality(after,ref_report.document) if ref_report else decision.get('quality',{'accepted':True,'reason':'手动时间偏移，尚未证明与视频同步。'})
                if not quality['accepted']:return {'status':'low_quality','reason':quality['reason'],'quality':quality}
                if text==read.text:return {'status':'succeeded','reason':'当前时间无需调整。'}
                meta={'video':str(row.video),'videoMark':asdict(ws.fs.file_mark(row.video)),'source':str(source),'sourceDigest':read.digest,
                    'sourceEncoding':params.get('encoding','auto'),'engine':decision['engine'],'offsetMs':decision['offsetMs'],'scale':decision['scale'],
                    'before':{'cueCount':len(report.document.cues),'firstMs':report.document.cues[0].start,'lastMs':report.document.cues[-1].end},
                    'after':{'cueCount':len(after.cues),'firstMs':after.cues[0].start,'lastMs':after.cues[-1].end},'quality':quality}
                record=self.artifacts.create(source.name,text,meta)
                return self.preview(record)
            def complete(value):
                if ws.data is not data or ws.session_id!=session:raise ProtocolError('STALE_REVIEW','页面或审阅已变化，缓存结果保留但不会自动关联。')
                return value
            return ws.launch('sync',work,complete,'只在私有缓存生成时间调整候选，原字幕保持不变…')
        record=self.artifacts.get(params['artifactId']);meta=record['metadata'];path=self.artifacts.path(record['id'])
        if meta['video']!=str(row.video) or meta['videoMark']!=asdict(ws.fs.file_mark(row.video)):raise ProtocolError('STALE_REVIEW','处理结果不属于当前视频身份。')
        if action=='sync.query':return self.preview(record)
        if action=='sync.discard':
            if not params['acknowledged']:raise ProtocolError('CONFIRMATION_REQUIRED','请确认清除此未引用处理结果。')
            protected=list(data.review.subtitles)
            if ws.execution:protected+=ws.execution.journal.referenced_paths()
            if ws.drafts:
                saved=ws.drafts.store.load('workspace')
                if saved:protected += [item['path'] for item in saved['files']]
            return self.artifacts.discard(record['id'],protected)
        if action=='sync.stage':
            if not params['acknowledged']:raise ProtocolError('CONFIRMATION_REQUIRED','请确认保留原字幕并把候选加入审阅。')
            source=Path(meta['source'])
            if not any(m.source==source for m in row.matches):raise ProtocolError('STALE_REVIEW','原关联已变化，请重新生成处理结果。')
            session=ws.session_id;ws.invalidate_preview();ws.invalidate_online()
            def work(worker):
                original=ws.quality.reader.read(source,encoding=meta['sourceEncoding'],should_stop=worker.stop.is_set)
                candidate=ws.quality.reader.read(path,should_stop=worker.stop.is_set)
                if original.digest!=meta['sourceDigest'] or candidate.digest!=record['digest'] or original.text is None or candidate.text!=transform(original.text,original.format,meta['offsetMs'],meta['scale']):
                    raise ProtocolError('FILE_CHANGED','源字幕或处理缓存已变化；原文件已保留。')
                review=data.review.fork();review.add_imports([(path,{'rowIndex':index,'artifactId':record['id'],'operation':'sync','engine':meta['engine']})])
                if review.owner(path)!=index:review.assign(index,path,source)
                review.upgrades[path_key(path)]={'original':str(source),'originalDigest':original.digest,'candidateDigest':candidate.digest,
                    'originalOrigin':review.imported.get(path_key(source),{}).get('artifactId','local'),'candidateOrigin':record['id'],'policy':'needs-1'}
                review._replan(worker.stop.is_set)
                updated=ReviewData(review,data.register,scan_id=data.scan_id,revision=data.revision+1,warnings=data.scan_warnings,recognition=data.recognition)
                return updated,ws.draft_capture(updated,worker.stop.is_set)
            def complete(value):
                if ws.data is not data or ws.session_id!=session:raise ProtocolError('STALE_REVIEW','页面变化，未关联处理结果。')
                ws.draft_publish(value[1]);ws.data=value[0];ws.revision=value[0].revision
                return {'revision':value[0].revision,'rowId':params['rowId'],'originalPreserved':True}
            return ws.launch('review',work,complete,'核对处理结果后加入待确认审阅…')
        raise ProtocolError('ACTION_UNAVAILABLE','不支持的同步操作。')
