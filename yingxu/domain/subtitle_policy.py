"""Pure coverage and conservative upgrade decisions, never file operations."""
from dataclasses import dataclass

from .match_assessment import facts
from .releases import parse_release
from .subtitle_variants import SubtitleVariant

VERSION = 'needs-1'
LANGUAGES = {'chinese':'中文', 'bilingual':'中英双语', 'simplified':'简体中文',
             'traditional':'繁体中文', 'english':'英语', 'japanese':'日语', 'korean':'韩语'}
DEFAULT_POLICY = {'languages':['chinese'], 'allowSDH':False, 'includeForced':False}


@dataclass(frozen=True)
class SubtitlePolicy:
    languages: tuple[str, ...] = ('chinese',)
    allow_sdh: bool = False
    include_forced: bool = False

    @classmethod
    def read(cls, value):
        if (not isinstance(value,dict) or set(value)!=set(DEFAULT_POLICY)
                or not isinstance(value['languages'],list) or not 1<=len(value['languages'])<=4
                or any(not isinstance(v,str) or v not in LANGUAGES for v in value['languages'])
                or len(set(value['languages']))!=len(value['languages'])
                or type(value['allowSDH']) is not bool or type(value['includeForced']) is not bool):
            raise ValueError('请选择 1–4 种字幕语言，并确认 SDH 与片段字幕选项。')
        return cls(tuple(sorted(value['languages'])),value['allowSDH'],value['includeForced'])

    def dto(self):
        return {'languages':list(self.languages),'allowSDH':self.allow_sdh,'includeForced':self.include_forced}

    @property
    def key(self):
        return (VERSION,self.languages,self.allow_sdh,self.include_forced)

    @property
    def requirements(self):
        return tuple((language,forced) for language in self.languages
                     for forced in ((False,True) if self.include_forced else (False,)))


@dataclass(frozen=True)
class Evidence:
    identifier: str
    variant: SubtitleVariant
    quality: str = 'unchecked'
    digest: str = ''
    errors: int = 0
    warnings: int = 0
    complete: bool = False
    accepted: bool = True
    locked: bool = False
    origin: str = 'external'


def language_matches(language, variant):
    families=set(variant.languages)
    if variant.ambiguous or not families:return False
    return (language=='chinese' and 'zh' in families
            or language=='bilingual' and {'zh','en'}<=families
            or language=='simplified' and 'zh' in families and variant.script=='Hans'
            or language=='traditional' and 'zh' in families and variant.script=='Hant'
            or language in {'english','japanese','korean'}
               and {'english':'en','japanese':'ja','korean':'ko'}[language] in families)


def coverage(policy, evidence):
    """Unknown evidence is reviewable, never a reason to auto-download again."""
    result=[]
    for language,forced in policy.requirements:
        usable=[];pending=[];reasons=[]
        for item in evidence:
            variant=item.variant
            if not language_matches(language,variant):continue
            if variant.commentary or variant.forced!=forced:
                reasons.append('评论或片段字幕不满足完整字幕要求' if not forced else '缺少对应语言的强制/片段字幕');continue
            if variant.sdh and not policy.allow_sdh:
                reasons.append('SDH 尚未被允许代替普通字幕');continue
            if item.errors:
                reasons.append('已有字幕含格式或时间错误，不能视为已满足');continue
            if not item.accepted or not item.complete or item.quality not in {'clean','metadata'} or item.warnings:
                pending.append(item.identifier);continue
            usable.append(item.identifier)
        state='satisfied' if usable else 'review' if pending else 'missing'
        result.append({'language':language,'forced':forced,'label':LANGUAGES[language]+(' · 强制/片段' if forced else ' · 完整字幕'),
            'state':state,'reason':'已有本地字幕满足要求' if usable else '已有候选，需核对归属、编码或质量' if pending else
                next(iter(reasons),'没有对应语言与用途的本地字幕'), 'evidence':(usable or pending)[:2]})
    return result


def embedded_evidence(info):
    """Track metadata has no content-quality certificate and is never extracted."""
    if info.get('status')!='ok':return []
    result=[]
    for track in info.get('tracks',[]):
        variant=SubtitleVariant(tuple(sorted(track.get('families',[]))),
            {'simplified':'Hans','traditional':'Hant'}.get(track.get('script'),''),
            forced=bool(track.get('forced')),sdh=bool(track.get('sdh')),
            commentary=bool(track.get('commentary')),ambiguous=bool(track.get('ambiguous')),source='metadata')
        result.append(Evidence(track['trackId'],variant,'metadata',complete=True,origin='embedded'))
    return result


def upgrade_decision(video, original, candidate, current, proposed):
    """A suggestion can only stage a separate candidate; it never authorizes writes."""
    if current.locked:return 'protected','人工选择或已确认的字幕受到保护，请使用手动更换入口'
    if current.variant.key!=proposed.variant.key:return 'different_variant','不同语言或用途应分别补齐'
    if not current.digest or not proposed.digest:return 'review','内容摘要不完整，不能比较升级'
    if current.digest==proposed.digest:return 'duplicate','内容相同，无需重复导入'
    for path in (original,candidate):
        _evidence,conflicts,missing=facts(parse_release(video.name),parse_release(path.name))
        if conflicts or missing:return 'review','作品、季集或剪辑信息不充分，不能建议升级'
    old,new=parse_release(original.name),parse_release(candidate.name)
    if any(getattr(old,key) and getattr(new,key) and getattr(old,key)!=getattr(new,key)
           for key in ('source','release_group')):
        return 'review','片源或发行组不同，时间轴需要人工核对'
    if (not proposed.accepted or not proposed.complete or proposed.quality!='clean'
            or proposed.errors or proposed.warnings):return 'review','新候选尚未通过完整的格式与质量核对'
    if current.errors or current.complete and current.warnings:
        return 'suggested','同语言、同用途候选的诊断更少；保留原文件，仍需审阅和最终确认'
    return 'keep','没有足够证据说明新候选更好，保留已有字幕'
