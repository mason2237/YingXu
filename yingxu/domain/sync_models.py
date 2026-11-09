"""Lossless timestamp rewriting over a parsed, selected text subtitle."""
from dataclasses import dataclass
import math
import re
from .subtitle_document import milliseconds,parse_document,MAX_BYTES


@dataclass(frozen=True)
class SyncResult:
    status: str
    offset_ms: int = 0
    scale: float = 1.0
    reason: str = ''
    engine: str = 'manual'


def stamp(value,mode,original):
    value=round(value/10)*10 if mode in {'ass','ssa'} else round(value)
    if value<0:raise ValueError('偏移后出现负时间；本工具会拒绝，不静默裁剪。')
    hours,rest=divmod(value,3600000);minutes,rest=divmod(rest,60000);seconds,ms=divmod(rest,1000)
    if hours>9999:raise ValueError('时间超过支持范围。')
    if mode in {'ass','ssa'}:return f'{hours}:{minutes:02}:{seconds:02}.{ms//10:02}'
    prefix=f'{hours:02}:' if mode=='srt' or original.count(':')==2 or hours else ''
    return f'{prefix}{minutes:02}:{seconds:02}{"," if "," in original else "."}{ms:03}'


def transform(text,format,offset_ms=0,scale=1.):
    if type(offset_ms) is not int or abs(offset_ms)>86400000 or not math.isfinite(scale) or not .9<=scale<=1.1:raise ValueError('时间调整参数超出范围。')
    before=parse_document(text,format)
    if not before.complete or not before.cues or any(i.severity=='error' for i in before.issues):raise ValueError('字幕结构未完整通过，不能调整时间。')
    lines=text.splitlines(keepends=True);events=False;fields=[];changed=0
    pattern=re.compile(r'^(\s*)(\d{1,4}:\d\d(?::\d\d)?[.,]\d{3})(\s*-->\s*)(\d{1,4}:\d\d(?::\d\d)?[.,]\d{3})(.*)$')
    def shifted(value):
        ms=milliseconds(value,format)
        if ms is None:raise ValueError('无效的字幕时间。')
        return stamp(ms*scale+offset_ms,format,value)
    for index,line in enumerate(lines):
        content=line.rstrip('\r\n');ending=line[len(content):]
        if format in {'ass','ssa'}:
            if content.strip().startswith('['):events=content.strip().casefold()=='[events]'
            if not events:continue
            if content.casefold().startswith('format:'):fields=[v.strip().casefold() for v in content.split(':',1)[1].split(',')];continue
            match=re.match(r'^(\s*(?:Dialogue|Comment)\s*:)(.*)$',content,re.I)
            if not match:continue
            if 'start' not in fields or 'end' not in fields:raise ValueError('ASS Events 缺少时间字段。')
            parts=match[2].split(',',len(fields)-1)
            if len(parts)!=len(fields):raise ValueError('ASS 对白字段不完整。')
            for key in ('start','end'):
                position=fields.index(key);old=parts[position];parts[position]=old.replace(old.strip(),shifted(old.strip()),1)
            lines[index]=match[1]+','.join(parts)+ending;changed+=1
        else:
            match=pattern.match(content)
            if match:lines[index]=match[1]+shifted(match[2])+match[3]+shifted(match[4])+match[5]+ending;changed+=1
    result=''.join(lines);after=parse_document(result,format)
    if not changed or len(result.encode('utf8'))>MAX_BYTES or len(before.cues)!=len(after.cues):raise ValueError('调整结果不完整。')
    for old,new in zip(before.cues,after.cues):
        if old.text!=new.text or old.style!=new.style or old.layer!=new.layer or old.settings!=new.settings or old.kind!=new.kind or new.end<=new.start:
            raise ValueError('调整后内容、样式或时间区间不安全。')
    return result


def canonical_srt(document):
    return '\n\n'.join(f'{i}\n{stamp(c.start,"srt","00:00:00,000")} --> {stamp(c.end,"srt","00:00:00,000")}\nText {i}'
                       for i,c in enumerate((c for c in document.cues if c.kind!='comment'),1))+'\n'
