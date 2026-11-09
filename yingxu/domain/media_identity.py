"""Local identity hints. An OpenSubtitles hash is not proof of file ownership."""
from dataclasses import dataclass
import re
import struct
import xml.etree.ElementTree as ET

IMDB=re.compile(r'tt[0-9]{7,10}\Z')
BLOCK=65536
MAX_NFO=512*1024


def opensubtitles_hash(size, head, tail):
    if size<2*BLOCK or len(head)!=BLOCK or len(tail)!=BLOCK:raise ValueError('视频不足 128 KiB，无法生成此指纹。')
    value=size
    for block in (head,tail):value+=sum(v[0] for v in struct.iter_unpack('<Q',block))
    return f'{value & ((1<<64)-1):016x}'


def imdb(value):
    if not isinstance(value,str) or not IMDB.fullmatch(value):raise ValueError('IMDb ID 应为 tt 加 7–10 位数字。')
    return value


def parse_nfo(raw, episode=False):
    if len(raw)>MAX_NFO:raise ValueError('NFO 超过 512 KiB，未读取。')
    encoding='utf-32' if raw.startswith((b'\xff\xfe\x00\x00',b'\x00\x00\xfe\xff')) else 'utf-16' if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig'
    text=raw.decode(encoding,errors='strict')
    if re.search(r'<!\s*(?:DOCTYPE|ENTITY)',text,re.I):raise ValueError('NFO 含 XML 实体或 DTD，已拒绝。')
    try:root=ET.fromstring(text)
    except ET.ParseError as error:raise ValueError('NFO XML 格式无效。') from error
    kind={'movie':'movie','episodedetails':'episode','tvshow':'show'}.get(root.tag)
    if not kind:raise ValueError('NFO 不是支持的影视信息格式。')
    ids=[]
    for element in root.iter():
        if element.tag=='uniqueid' and element.get('type','').casefold()=='imdb' or element.tag=='id':
            value=(element.text or '').strip()
            if IMDB.fullmatch(value) and (kind,value) not in ids:ids.append((kind,value))
        if len(ids)>16:raise ValueError('NFO 标识过多，请人工核对。')
    reasons=[]
    if len(ids)>1:reasons.append('NFO 中有多个不同标识')
    if kind!=('episode' if episode else 'movie'):reasons.append('NFO 标识类型与当前视频不一致，剧集不继承剧集总 ID')
    return {'ids':[{'kind':kind,'id':value,'source':'same-name-nfo'} for kind,value in ids],
            'conflict':bool(reasons),'reasons':reasons}
