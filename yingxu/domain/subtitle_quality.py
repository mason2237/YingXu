"""Read-only diagnostics. Syntax, quality, identity and synchronization are distinct."""
from collections import Counter
from dataclasses import dataclass
import heapq
import re
import math
import unicodedata

from .subtitle_document import MAX_ISSUES, Cue, Issue, SubtitleDocument, SubtitleRead, parse_document
from .matching import check_cancelled


@dataclass(frozen=True, slots=True)
class QualityReport:
    document: SubtitleDocument
    encoding: str
    digest: str
    candidates: tuple[tuple[str,str],...]
    status: str
    replacements: int = 0

    def summary(self):
        counts=Counter(issue.severity for issue in self.document.issues)
        return {'status':self.status,'format':self.document.format,'encoding':self.encoding,
                'digest':self.digest,'cueCount':sum(c.kind!='comment' for c in self.document.cues),
                'issueCount':len(self.document.issues),'complete':self.document.complete,
                'errors':counts['error'],'warnings':counts['warning'],'info':counts['info'],
                'replacementCharacters':self.replacements,
                'encodingCandidates':[{'encoding':code,'preview':preview} for code,preview in self.candidates]}


def inspect_document(document, *, max_cps=40, should_stop=None):
    issues=list(document.issues);complete=document.complete
    def add(code,severity,message,cue=None):
        nonlocal complete
        if len(issues)>=MAX_ISSUES:complete=False;return
        issues.append(Issue(code,severity,message,cue.line if cue else 0,cue.identifier if cue else '',
            cue.start if cue else None,cue.end if cue else None,cue.text[:160] if cue else ''))
    previous=None;seen=set();valid=0;intervals=[]
    for cue in document.cues:
        check_cancelled(should_stop)
        if cue.kind=='comment':continue
        if cue.start is None or cue.end is None:add('INVALID_TIME','error','时间戳格式无效',cue);continue
        if cue.end<cue.start:add('REVERSED_TIME','error','结束时间早于开始时间',cue)
        elif cue.end==cue.start:add('ZERO_DURATION','warning','字幕持续时间为零',cue)
        else:intervals.append(cue)
        if previous is not None and cue.start<previous:add('OUT_OF_ORDER','warning','字幕开始时间未按顺序排列',cue)
        previous=cue.start
        plain=re.sub(r'\{[^}]*\}|<[^>]*>','',cue.text).replace(r'\N','\n').replace(r'\n','\n').strip()
        if plain and cue.end>cue.start:valid+=1
        if not plain:add('EMPTY_TEXT','warning','字幕正文为空',cue)
        suspicious=len(re.findall(r'Ã[\x80-\xff]|Â[\x80-\xff]|â[€\x80-\xff]|ï¿½',cue.text))>=2
        if '\ufffd' in cue.text or suspicious or any(unicodedata.category(c)=='Cc' and c not in '\r\n\t' for c in cue.text):
            add('SUSPECT_ENCODING','warning','正文含替换字符或异常控制字符，请核对编码',cue)
        identity=(cue.start,cue.end,cue.text)
        if identity in seen:add('DUPLICATE','warning','相同时间和正文重复出现',cue)
        seen.add(identity)
        if cue.end>cue.start and len(plain)/((cue.end-cue.start)/1000)>max_cps:
            add('READING_SPEED','warning',f'阅读速度超过 {max_cps:g} 字符/秒，请人工核对',cue)
    if not valid:add('NO_VALID_CUES','error','没有可用的有效对白字幕')
    active=[]
    for index,cue in enumerate(sorted(intervals,key=lambda c:(c.start,c.end,c.line))):
        check_cancelled(should_stop)
        while active and active[0][0]<=cue.start:heapq.heappop(active)
        if active:add('OVERLAP','info' if document.format in {'ass','ssa'} else 'warning',
            '字幕时间重叠；ASS/SSA 分层或双语可能有意如此' if document.format in {'ass','ssa'} else '与另一条字幕时间重叠',cue)
        heapq.heappush(active,(cue.end,index))
    return SubtitleDocument(document.format,document.cues,document.blocks,tuple(issues),complete)


def analyze(read: SubtitleRead, *, max_cps=40, should_stop=None):
    if type(max_cps) not in {int,float} or not math.isfinite(max_cps) or not 1<=max_cps<=1000:raise ValueError('阅读速度阈值必须在 1–1000 之间')
    if read.text is None:
        status='encoding_required' if read.candidates else 'unavailable'
        issue=Issue('ENCODING_REQUIRED' if read.candidates else 'READ_UNAVAILABLE','warning',read.issue or '此字幕未完成检查')
        return QualityReport(SubtitleDocument(read.format,(),(),(issue,),False),read.encoding,read.digest,read.candidates,status)
    parsed=parse_document(read.text,read.format,should_stop)
    if read.format not in {'srt','ass','ssa','vtt'}:
        return QualityReport(parsed,read.encoding,read.digest,(), 'unsupported')
    document=inspect_document(parsed,max_cps=max_cps,should_stop=should_stop)
    status='incomplete' if not document.complete else 'issues' if document.issues else 'clean'
    return QualityReport(document,read.encoding,read.digest,(),status,read.text.count('\ufffd'))
