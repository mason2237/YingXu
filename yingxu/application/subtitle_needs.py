"""One owner for local needs snapshots, policy changes and upgrade staging."""
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from ..domain.errors import ProtocolError
from ..domain.matching import check_cancelled, clean_token
from ..domain.releases import parse_release
from ..domain.review import path_key
from ..domain.subtitle_policy import (DEFAULT_POLICY, VERSION, Evidence, SubtitlePolicy,
    coverage, embedded_evidence, upgrade_decision)
from ..domain.subtitle_quality import analyze
from ..domain.subtitle_document import MAX_BYTES as MAX_FILE_BYTES
from ..domain.subtitle_variants import variant_of
from .reviewing import ReviewData

MAX_FILES=512
MAX_BYTES=64*1024*1024


def identity_key(path):
    info=parse_release(path.name)
    return (clean_token(info.title),info.year,info.season,info.episodes,info.air_date,info.edition,info.special)


class SubtitleNeeds:
    def __init__(self, workspace, settings=None):
        self.workspace,self.settings=workspace,settings
        try:self.policy=SubtitlePolicy.read(settings.read() if settings else DEFAULT_POLICY)
        except ValueError:self.policy=SubtitlePolicy()
        self.snapshot=None

    def valid(self, data):
        saved=self.snapshot
        return bool(saved and saved['data'] is data and saved['session']==self.workspace.session_id
                    and saved['policy']==self.policy.key)

    def evidence(self, data, index, qualities=None):
        row=data.review.rows[index];result=[]
        if not row.embedded_ignored:result.extend(embedded_evidence(row.embedded))
        for match in row.matches:
            item=(qualities or {}).get(match.source,Evidence(data.register(match.source),variant_of(match.source)))
            result.append(replace(item,accepted=match.confirmed or not match.manual and not match.needs_review,
                                  locked=match.manual or match.confirmed))
        return result

    def missing_indices(self, data):
        if self.valid(data):
            return [row['index'] for row in self.snapshot['rows'] if row['missingCount']]
        return [index for index,row in enumerate(data.review.rows) if not row.skipped
                and any(v['state']=='missing' for v in coverage(self.policy,self.evidence(data,index)))]

    def has_missing(self, data, index):
        if data.review.rows[index].skipped:return False
        if self.valid(data):return bool(self.snapshot['byIndex'].get(index,{}).get('missingCount'))
        return any(v['state']=='missing' for v in coverage(self.policy,self.evidence(data,index)))

    def require(self, data, identifier):
        if not self.valid(data) or self.snapshot['id']!=identifier:
            raise ProtocolError('STALE_NEEDS','字幕需求已变化，请重新检查本地字幕。')
        return self.snapshot

    def inspect(self, data, worker):
        if self.workspace.quality is None:raise ProtocolError('UNAVAILABLE','字幕检查组件未配置。')
        qualities={};budget=0;limited=False
        def read(path):
            nonlocal budget,limited
            if path in qualities:return qualities[path]
            check_cancelled(worker.stop.is_set)
            item=Evidence(data.register(path),variant_of(path))
            if len(qualities)>=MAX_FILES or budget+MAX_FILE_BYTES>MAX_BYTES:
                limited=True;return item
            reserved=budget+MAX_FILE_BYTES
            try:
                read_result=self.workspace.quality.reader.read(path,should_stop=worker.stop.is_set)
                budget+=read_result.bytes_read
                report=analyze(read_result,should_stop=worker.stop.is_set)
                summary=report.summary()
                item=replace(item,quality=summary['status'],digest=summary['digest'],errors=summary['errors'],
                             warnings=summary['warnings'],complete=summary['complete'])
            except (OSError,ValueError,ProtocolError):
                # Reserve a whole bounded read on failure; partial I/O may have occurred.
                budget=reserved;item=replace(item,quality='unavailable')
            qualities[path]=item
            return item
        buckets=defaultdict(list);inventory=defaultdict(dict)
        for path in data.review.subtitles:
            check_cancelled(worker.stop.is_set)
            key,variant=identity_key(path),variant_of(path).key
            buckets[(key,variant)].append(path)
            if data.review.owner(path) is None:inventory[key].setdefault(variant,path)
        rows=[];offers={}
        for index,row in enumerate(data.review.rows):
            check_cancelled(worker.stop.is_set)
            worker.report(index,len(data.review.rows),'检查本地字幕需求；不会联网或改写文件','needs')
            if row.skipped:continue
            for match in row.matches:read(match.source)
            evidence=self.evidence(data,index,qualities)
            # A damaged current match must not hide a usable local alternative
            # of the same variant and trigger another download.
            variants={e.variant.key for e in evidence if not e.errors}
            for key,candidate in inventory.get(identity_key(row.video),{}).items():
                if key in variants:continue
                assessment=data.review.assessment.assess(row.video,candidate)
                if not assessment.conflicts and not assessment.missing:
                    # Available but unassociated files need review, not another download.
                    evidence.append(replace(read(candidate),accepted=False))
            requirements=coverage(self.policy,evidence)
            row_offers=[]
            for match in row.matches:
                current=next(e for e in evidence if e.identifier==data.register(match.source))
                if current.locked or not (current.errors or current.warnings):continue
                candidates=buckets.get((identity_key(row.video),current.variant.key),())
                for candidate in candidates:
                    check_cancelled(worker.stop.is_set)
                    if candidate==match.source or data.review.owner(candidate) is not None:continue
                    # Cheap identity gate precedes content reading and bounds unrelated work.
                    assessment=data.review.assessment.assess(row.video,candidate)
                    if assessment.conflicts or assessment.missing:continue
                    proposed=replace(read(candidate),accepted=True)
                    decision,reason=upgrade_decision(row.video,match.source,candidate,current,proposed)
                    if decision!='suggested':continue
                    identifier=uuid4().hex
                    offers[identifier]=(index,match.source,candidate,current.digest,proposed.digest)
                    row_offers.append({'offerId':identifier,'original':match.source.name,'candidate':candidate.name,'reason':reason,
                        'originalSource':'下载暂存' if path_key(match.source) in data.review.imported else match.source.parent.name,
                        'candidateSource':'下载暂存' if path_key(candidate) in data.review.imported else candidate.parent.name})
                    if len(row_offers)>=2:break
                if len(row_offers)>=2:break
            counts=Counter(r['state'] for r in requirements)
            rows.append({'index':index,'rowId':data.rows[index]['rowId'],'videoName':row.video.name,
                'requirements':requirements,'missingCount':counts['missing'],'reviewCount':counts['review'],
                'state':'missing' if counts['missing'] else 'review' if counts['review'] else 'satisfied','offers':row_offers})
        return {'id':uuid4().hex,'rows':rows,'byIndex':{r['index']:r for r in rows},'offers':offers,'limited':limited,'filesChecked':len(qualities),
                'bytesReadBudget':budget,'data':data,'session':self.workspace.session_id,'policy':self.policy.key}

    def summary(self):
        saved=self.snapshot
        return {'needsId':saved['id'],'total':len(saved['rows']),'missingVideos':sum(bool(r['missingCount']) for r in saved['rows']),
            'reviewVideos':sum(bool(r['reviewCount']) for r in saved['rows']),
            'satisfiedVideos':sum(r['state']=='satisfied' for r in saved['rows']),
            'upgradeCount':len(saved['offers']),'limited':saved['limited'],'filesChecked':saved['filesChecked']}

    def verify_staged(self, data, worker):
        """Staging evidence is not permission to use later, changed file bytes."""
        for row in data.review.rows:
            if row.skipped:continue
            for match in row.matches:
                metadata=data.review.upgrades.get(path_key(match.source))
                if not metadata:continue
                for path,expected in ((match.source,metadata['candidateDigest']),
                                      (Path(metadata['original']),metadata['originalDigest'])):
                    check_cancelled(worker.stop.is_set)
                    if self.workspace.quality.reader.read(path,should_stop=worker.stop.is_set).digest!=expected:
                        raise ProtocolError('FILE_CHANGED','升级候选或原字幕已变化，请重新扫描核对；没有修改原文件。')

    def dispatch(self, action, params):
        ws=self.workspace
        if action=='requirements.policy':return {'version':VERSION,**self.policy.dto()}
        if action=='requirements.configure':
            ws.require_idle();policy=SubtitlePolicy.read(params)
            if policy==self.policy:return {'changed':False,**policy.dto()}
            ws.invalidate_preview();ws.invalidate_online()
            if ws.data:
                data=ws.data
                def work(worker):
                    review=data.review.fork()
                    for row in review.rows:
                        for match in row.matches:match.confirmed=False;match.needs_review=True
                    updated=ReviewData(review,data.register,scan_id=data.scan_id,revision=data.revision+1,warnings=data.scan_warnings,recognition=data.recognition)
                    updated.subtitle_policy=policy.dto()
                    return updated,ws.draft_capture(updated,worker.stop.is_set)
                def complete(value):
                    if self.settings:self.settings.write(policy.dto())
                    self.policy=policy;self.snapshot=None
                    # If checkpoint save fails, live approvals remain revoked; restart
                    # detects the old checkpoint's policy and revokes them again.
                    ws.data=value[0];ws.revision=value[0].revision
                    ws.draft_publish(value[1])
                    return {'changed':True,**policy.dto()}
                return ws.launch('policy',work,complete,'保存字幕需求，保留原关联并撤回旧确认…')
            if self.settings:self.settings.write(policy.dto())
            self.policy=policy;self.snapshot=None
            return {'changed':True,**policy.dto()}
        data=ws.require_review(params)
        if action=='requirements.check':
            session=ws.session_id;policy=self.policy.key
            def complete(value):
                if ws.data is not data or ws.session_id!=session or self.policy.key!=policy:
                    raise ProtocolError('STALE_NEEDS','审阅或页面已变化，请重新检查。')
                self.snapshot=value;return self.summary()
            return ws.launch('needs',lambda worker:self.inspect(data,worker),complete,'检查本地字幕需求，不会联网…')
        saved=self.require(data,params['needsId'])
        if action=='requirements.query':
            offset,limit=params.get('offset',0),params.get('limit',20)
            return {**self.summary(),'offset':offset,'rows':[{k:v for k,v in r.items() if k!='index'} for r in saved['rows'][offset:offset+limit]]}
        if action=='requirements.stage':
            if not params['acknowledged']:raise ProtocolError('CONFIRMATION_REQUIRED','请确认保留原文件并加入新的升级审阅。')
            if params['offerId'] not in saved['offers']:raise ProtocolError('NOT_FOUND','升级建议不属于本次检查。')
            index,original,candidate,old_digest,new_digest=saved['offers'][params['offerId']]
            session=ws.session_id
            ws.invalidate_preview();ws.invalidate_online()
            def work(worker):
                row=data.review.rows[index]
                match=next((m for m in row.matches if m.source==original),None)
                if match is None or match.manual or match.confirmed:raise ProtocolError('PROTECTED_SUBTITLE','已有字幕已变化或由人工锁定。')
                reports=[analyze(ws.quality.reader.read(p,should_stop=worker.stop.is_set),should_stop=worker.stop.is_set).summary() for p in (original,candidate)]
                if [r['digest'] for r in reports]!=[old_digest,new_digest]:raise ProtocolError('FILE_CHANGED','字幕内容已变化，请重新检查；原文件和候选已保留。')
                evidence=[Evidence('',variant_of(p),quality=r['status'],digest=r['digest'],errors=r['errors'],
                    warnings=r['warnings'],complete=r['complete']) for p,r in zip((original,candidate),reports)]
                if upgrade_decision(row.video,original,candidate,*evidence)[0]!='suggested':raise ProtocolError('STALE_NEEDS','升级依据已变化，请重新检查。')
                review=data.review.fork();review.assign(index,candidate,original)
                review.upgrades[path_key(candidate)]={'original':str(original),'originalDigest':old_digest,'candidateDigest':new_digest,
                    'originalOrigin':review.imported.get(path_key(original),{}).get('artifactId','local'),
                    'candidateOrigin':review.imported.get(path_key(candidate),{}).get('artifactId','local'),'policy':VERSION}
                review._replan(worker.stop.is_set)
                updated=ReviewData(review,data.register,scan_id=data.scan_id,revision=data.revision+1,warnings=data.scan_warnings,recognition=data.recognition)
                return updated,ws.draft_capture(updated,worker.stop.is_set)
            def complete(value):
                if ws.data is not data or ws.session_id!=session:raise ProtocolError('STALE_REVIEW','页面已变化，原文件和候选已保留。')
                ws.draft_publish(value[1]);ws.data=value[0];ws.revision=value[0].revision;self.snapshot=None
                return {'rowId':data.rows[index]['rowId'],'revision':value[0].revision,'originalPreserved':True}
            return ws.launch('review',work,complete,'核对升级候选，保留原文件；尚不整理…')
        raise ProtocolError('ACTION_UNAVAILABLE','不支持的字幕需求操作。')
