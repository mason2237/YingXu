"""Bounded subtitle syntax with source locations; never writes or repairs text."""
from dataclasses import dataclass
import io
import re

MAX_BYTES=8*1024*1024
MAX_CUES=50000
MAX_ISSUES=500
MAX_LINES=250000
MAX_LINE=32768
FORMATS=frozenset({'srt','ass','ssa','vtt'})


@dataclass(frozen=True, slots=True)
class Cue:
    identifier: str
    line: int
    start: int | None
    end: int | None
    text: str
    style: str = ''
    layer: str = ''
    settings: str = ''
    kind: str = 'dialogue'
    raw: str = ''


@dataclass(frozen=True, slots=True)
class Issue:
    code: str
    severity: str
    message: str
    line: int = 0
    cue: str = ''
    start: int | None = None
    end: int | None = None
    excerpt: str = ''

    def dto(self):
        return {'code':self.code,'severity':self.severity,'message':self.message,
                'line':self.line,'cue':self.cue,'start':self.start,'end':self.end,'excerpt':self.excerpt[:160]}


@dataclass(frozen=True, slots=True)
class SourceBlock:
    line: int
    kind: str
    raw: str


@dataclass(frozen=True, slots=True)
class SubtitleDocument:
    format: str
    cues: tuple[Cue,...]
    blocks: tuple[SourceBlock,...]
    issues: tuple[Issue,...]
    complete: bool = True


@dataclass(frozen=True, slots=True)
class SubtitleRead:
    format: str
    text: str | None
    encoding: str
    digest: str
    candidates: tuple[tuple[str,str],...] = ()
    issue: str = ''
    bytes_read: int = 0


def milliseconds(value, mode):
    value=value.strip()
    if mode in {'ass','ssa'}:
        match=re.fullmatch(r'(\d{1,4}):([0-5]\d):([0-5]\d)\.(\d{2})',value)
        if not match:return None
        hours,minutes,seconds,centiseconds=map(int,match.groups())
        return ((hours*60+minutes)*60+seconds)*1000+centiseconds*10
    pattern=r'(?:(\d{1,4}):)?([0-5]\d):([0-5]\d)[.,](\d{3})'
    match=re.fullmatch(pattern,value)
    if not match or (mode=='srt' and match[1] is None):return None
    hours,minutes,seconds,millis=(int(part or 0) for part in match.groups())
    return ((hours*60+minutes)*60+seconds)*1000+millis


def parse_document(text, format, should_stop=None):
    from .matching import check_cancelled
    cues,blocks,issues=[],[],[]
    complete=True
    def issue(code,message,line=0,excerpt='',severity='error'):
        nonlocal complete
        if len(issues)<MAX_ISSUES:issues.append(Issue(code,severity,message,line,excerpt=excerpt[:160]))
        else:complete=False
    lines=[]
    for number,line in enumerate(io.StringIO(text),1):
        check_cancelled(should_stop)
        if number>MAX_LINES or len(line)>MAX_LINE:
            complete=False;issue('INPUT_LIMIT','行数或单行长度超过检查限制',number);break
        lines.append(line.rstrip('\r\n'))
    def append(cue):
        nonlocal complete
        if len(cues)>=MAX_CUES:
            complete=False;issue('CUE_LIMIT','字幕条数超过 50000，未完整检查',cue.line);return False
        cues.append(cue);return True
    if format not in FORMATS:
        return SubtitleDocument(format,(),(),(Issue('UNSUPPORTED_FORMAT','info','此格式暂不支持文字质检'),),False)
    if format in {'ass','ssa'}:
        section='';fields=[]
        for number,line in enumerate(lines,1):
            check_cancelled(should_stop)
            stripped=line.strip()
            if stripped.startswith('[') and stripped.endswith(']'):
                section=stripped.casefold();blocks.append(SourceBlock(number,'section',line));continue
            if section!='[events]':
                blocks.append(SourceBlock(number,'metadata',line));continue
            head,sep,tail=line.partition(':');key=head.strip().casefold()
            if key=='format' and sep:
                fields=[part.strip().casefold() for part in tail.split(',')]
                blocks.append(SourceBlock(number,'format',line));continue
            if key not in {'dialogue','comment'} or not sep:
                blocks.append(SourceBlock(number,'event-metadata',line));continue
            if not fields or not {'start','end','text'}<=set(fields) or len(fields)!=len(set(fields)):
                issue('ASS_FORMAT','Events Format 缺少有效字段或字段重复',number,line);continue
            text_index=fields.index('text')
            prefix=tail.lstrip().split(',',text_index)
            values=prefix[:-1]+prefix[-1].rsplit(',',len(fields)-text_index-1)
            if len(values)!=len(fields):issue('ASS_FIELDS','事件列数与 Format 不一致',number,line);continue
            data=dict(zip(fields,values))
            cue=Cue(str(len(cues)+1),number,milliseconds(data['start'],format),milliseconds(data['end'],format),
                    data['text'],data.get('style',''),data.get('layer',data.get('marked','')),kind=key,raw=line)
            if not append(cue):break
    else:
        index=0
        if format=='vtt':
            if not lines or not re.match(r'^\ufeff?WEBVTT(?:\s|$)',lines[0]):issue('VTT_HEADER','缺少 WEBVTT 标识',1)
            while index<len(lines) and lines[index].strip():
                blocks.append(SourceBlock(index+1,'header',lines[index]));index+=1
        while index<len(lines):
            check_cancelled(should_stop)
            if not lines[index].strip():index+=1;continue
            start=index
            while index<len(lines) and lines[index].strip():index+=1
            block=lines[start:index]
            if format=='vtt' and (re.match(r'^NOTE(?:\s|$)',block[0]) or block[0] in {'STYLE','REGION'}):
                blocks.append(SourceBlock(start+1,block[0].split()[0],'\n'.join(block)));continue
            timing=0 if '-->' in block[0] else 1
            if timing>=len(block) or '-->' not in block[timing]:
                issue('CUE_STRUCTURE','没有找到字幕时间行',start+1,block[0]);continue
            left,right=block[timing].split('-->',1)
            values=right.strip().split(None,1)
            end_value=values[0] if values else ''
            settings=values[1] if len(values)>1 else ''
            identifier=block[0] if timing else str(len(cues)+1)
            for body_index,body in enumerate(block[timing+1:],start+timing+2):
                if re.match(r'^\s*\d{1,4}:\d{2}.*-->',body):
                    issue('MISSING_SEPARATOR','疑似字幕之间缺少空行',body_index,body,'warning')
            if not append(Cue(identifier[:64],start+timing+1,milliseconds(left,format),milliseconds(end_value,format),
                '\n'.join(block[timing+1:]),settings=settings,raw='\n'.join(block))):break
    return SubtitleDocument(format,tuple(cues),tuple(blocks),tuple(issues),complete)
