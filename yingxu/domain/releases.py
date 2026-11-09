"""Conservative, bounded filename metadata; advisory until a matching policy uses it."""
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
import re
import unicodedata

from .matching import episode_identity
from .subtitle_variants import split_variant

VERSION='filename-1'
MAX_NAME=2048
SOURCES=(('WEB-DL',r'(?<![a-z])web[ ._-]?dl(?![a-z])'),('WEBRip',r'(?<![a-z])web[ ._-]?rip(?![a-z])'),
         ('BluRay',r'(?<![a-z])(?:blu[ ._-]?ray|bdrip|brrip)(?![a-z])'),
         ('HDTV',r'(?<![a-z])hdtv(?![a-z])'),('DVD',r'(?<![a-z])(?:dvd|dvdrip)(?![a-z])'))
EDITIONS=(('extended',r'\bextended\b'),('directors-cut',r"\bdirector'?s?[ ._-]*cut\b|\bdc\b"),
          ('theatrical',r'\btheatrical\b'),('unrated',r'\bunrated\b'))
MARKER=re.compile(r'(?i)s\d+\s*e\d+|\d+x\d+|(?<![a-z])(?:episode|ep|e)\d+|第[\d一二三四五六七八九十百]+[季集话]|(?<![a-z0-9])sp\d*(?![a-z0-9])')
YEAR=re.compile(r'(?<!\d)((?:19|20)\d{2})(?!\d)')
TECH=re.compile(r'(?i)(?<![a-z0-9])(?:\d{3,4}[pi]|2160p|4k|8k|remux|x26[45]|h[ .]?26[45]|hevc|avc|aac|dts|hdr10?|dv)(?![a-z0-9])')


@dataclass(frozen=True)
class ParsedRelease:
    title: str | None = None
    year: int | None = None
    kind: str = 'unknown'
    season: int | None = None
    # Sorted coverage, never an assertion of playback order or the first episode.
    episodes: tuple[int,...] = ()
    episode_tokens: tuple[str,...] = ()
    numbering: str = 'unknown'
    complete: bool = True
    source: str | None = None
    release_group: str | None = None
    edition: tuple[str,...] = ()
    remux: bool = False
    special: str | None = None
    air_date: str | None = None
    origin: str = 'filename'
    parser: str = 'builtin'
    parser_version: str = VERSION
    warnings: tuple[str,...] = ()


def chinese_number(value):
    if value.isdecimal(): return int(value)
    digits={'零':0,'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
    if value in digits:return digits[value]
    if value.count('十')==1:
        left,right=value.split('十')
        if (not left or left in digits) and (not right or right in digits):
            return (digits.get(left,1)*10)+digits.get(right,0)
    return None


@lru_cache(maxsize=4096)
def parse_release(name: str) -> ParsedRelease:
    if not isinstance(name,str) or len(name)>MAX_NAME or any(unicodedata.category(c).startswith('C') for c in name):
        return ParsedRelease(complete=False,warnings=('文件名无效或超过识别限制',))
    value=unicodedata.normalize('NFKC',name)
    # Accept a basename only. A provider cannot smuggle parent-directory titles.
    value=re.split(r'[/\\]',value)[-1]
    value=re.sub(r'(?i)\.(?:mkv|mp4|avi|mov|wmv|flv|m4v|ts|webm|srt|ass|ssa|vtt|sup|sub)$','',value)
    value=split_variant(value)[0]
    lowered=value.casefold().replace('_','.')
    key=episode_identity(value)
    season=key.season if key else None
    episodes=tuple(sorted(key.episodes)) if key else ()
    season_match=re.search(r'第([\d一二三四五六七八九十]+)季',value)
    if season is None and season_match:season=chinese_number(season_match[1])
    chinese_episode=re.search(r'第([一二三四五六七八九十]+)[集话]',value)
    if not episodes and chinese_episode:
        number=chinese_number(chinese_episode[1]);episodes=(number,) if number is not None else ()
    numbering='season_episode' if episodes else 'unknown'
    special_match=re.search(r'(?i)(?<![a-z0-9])sp\d{0,3}(?![a-z0-9])',value)
    special=special_match[0].upper() if special_match else None
    date_match=re.search(r'(?<!\d)((?:19|20)\d{2})[. _-](\d{2})[. _-](\d{2})(?!\d)',value)
    air_date=None
    if date_match:
        try:air_date=date(*map(int,date_match.groups())).isoformat()
        except ValueError:pass
    # Absolute anime numbering requires an explicit fansub group and separator.
    absolute=re.search(r'^\[[^\]]{1,64}\].+?\s-\s(\d{1,4})(?:v\d+)?(?=\s|\[|$)',value)
    if not episodes and absolute:
        episodes=(int(absolute[1]),);numbering='absolute'
    years=list(YEAR.finditer(value))
    year_match=years[-1] if years and years[-1].start()>0 and not date_match else None
    year=int(year_match[1]) if year_match else None
    source=None
    for label,pattern in SOURCES:
        match=re.search(pattern,lowered)
        if match:
            source=source or label
    editions=tuple(label for label,pattern in EDITIONS if re.search(pattern,lowered))
    group_match=re.search(r'-([a-z0-9][a-z0-9._]{0,63})$',lowered)
    group=group_match[1] if group_match and (source or TECH.search(value) or key or year) and not re.fullmatch(r'(?:x26[45]|web[._]?dl|dl|rip|\d+p)',group_match[1]) else None
    if group is None:
        front=re.match(r'^\[([^\]]{1,64})\]',value)
        if front:group=front[1]
    title_value=re.sub(r'^\[[^\]]{1,64}\][ ._-]*','',value)
    title_years=list(YEAR.finditer(title_value))
    title_year=title_years[-1] if year_match and title_years else None
    title_date=re.search(r'(?<!\d)(?:19|20)\d{2}[. _-]\d{2}[. _-]\d{2}(?!\d)',title_value) if date_match else None
    boundaries=[m.start() for m in (MARKER.search(title_value),title_year,title_date,TECH.search(title_value)) if m]
    boundaries += [m.start() for _,p in SOURCES for m in [re.search(p,title_value.casefold())] if m]
    boundaries += [m.start() for _,p in EDITIONS for m in [re.search(p,title_value.casefold().replace('_','.'))] if m]
    if absolute:boundaries.append(max(0,title_value.find(' - ')))
    title=title_value[:min(boundaries)] if boundaries else title_value
    if group and group_match and not boundaries:title=title.rsplit('-',1)[0]
    title=re.sub(r'[._]+',' ',title).strip(' ()[]_-')
    warnings=[]
    if date_match and not air_date:warnings.append('日期标记无效，未推断作品年份')
    if len(title)>256: title='';warnings.append('片名过长，未推断作品身份')
    if key and not key.complete:warnings.append('季集范围需人工核对')
    if air_date:numbering='date' if not episodes else numbering
    return ParsedRelease(title or None,year,'episode' if episodes or air_date or special else 'movie' if year else 'unknown',
        season,episodes,tuple(m[0] for m in MARKER.finditer(value))[:100],numbering,
        not bool((key and not key.complete) or (date_match and not air_date)),source,group,editions,'remux' in lowered,special,air_date,
        warnings=tuple(warnings))


def release_lines(info: ParsedRelease):
    """Small advisory strings go through existing version-bound basis pages."""
    lines=[]
    if info.title:lines.append(f'名称识别 · {info.title}'+(f' · {info.year}' if info.year else ''))
    if info.source or info.release_group or info.edition or info.remux:
        lines.append('片源标记 · '+' · '.join(filter(None,(info.source,info.release_group,
            '/'.join(info.edition),'REMUX' if info.remux else ''))))
    if info.air_date:lines.append(f'播出日期标记 · {info.air_date}')
    if info.special:lines.append(f'特别篇标记 · {info.special}')
    if info.numbering=='absolute':lines.append('绝对集号 · '+'、'.join(map(str,info.episodes)))
    lines.extend(info.warnings)
    lines.append(f'识别来源 · 文件名 / {info.parser} {info.parser_version}；仅供核对')
    return lines
