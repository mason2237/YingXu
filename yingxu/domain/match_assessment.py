"""Explainable approval gates; filename similarity stays a score, not a probability.

Only compact row/group summaries are retained, not a videos × subtitles matrix.
The experimental .85/.08 policy is measured in shadow and never authorizes work.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
import os

from .matching import AUTO_APPLY_THRESHOLD, MATCH_THRESHOLD, check_cancelled, clean_token, similarity
from .releases import parse_release
from .subtitle_variants import split_variant, variant_of

POLICY_VERSION = 'assessment-1'


def release_key(path):
    return (os.path.normcase(os.path.abspath(path.parent)), clean_token(split_variant(path.stem)[0]))


def facts(video, subtitle):
    evidence, conflicts, missing = [], [], []
    if not video.title or not subtitle.title:
        missing.append('作品名称未完整识别')
    elif clean_token(video.title) != clean_token(subtitle.title):
        conflicts.append('作品名称不一致，别名需人工核对')
    else:
        evidence.append('作品名称一致')
    if not video.complete or not subtitle.complete:
        conflicts.append('季集或日期标记不完整')
    for attr, label in (('year','年份'),('season','季数'),('episodes','集数'),('air_date','播出日期'),('special','特别篇')):
        left, right = getattr(video,attr), getattr(subtitle,attr)
        left_present, right_present = left not in (None,(),''), right not in (None,(),'')
        if left_present and right_present:
            (evidence if left==right else conflicts).append(label+('一致' if left==right else '不一致'))
        elif left_present != right_present:
            missing.append(label+'缺少一侧标记')
    if video.episodes and subtitle.episodes and video.numbering != subtitle.numbering:
        conflicts.append('集数编号方式不同，不能自动换算')
    if video.edition != subtitle.edition:
        conflicts.append('剪辑版本不同或未明确')
    elif video.edition:
        evidence.append('剪辑版本一致')
    for attr,label in (('source','片源'),('release_group','发行组')):
        left,right=getattr(video,attr),getattr(subtitle,attr)
        if left and right:
            evidence.append(label+('一致' if left==right else '不同，时间轴需留意'))
        elif left or right:
            evidence.append(label+'仅有一侧标记')
    return tuple(evidence), tuple(conflicts), tuple(missing)


@dataclass(frozen=True)
class Assessment:
    score: float
    evidence: tuple[str,...]
    conflicts: tuple[str,...]
    missing: tuple[str,...]
    why_review: tuple[str,...]
    video_margin: float | None
    subtitle_margin: float | None
    auto_eligible: bool
    shadow_eligible: bool
    policy_version: str = POLICY_VERSION

    def dto(self):
        return {'evidence':self.evidence,'conflicts':self.conflicts,'missing':self.missing,
                'whyReview':self.why_review,'videoMargin':self.video_margin,
                'subtitleMargin':self.subtitle_margin,'autoEligible':self.auto_eligible,
                'shadowEligible':self.shadow_eligible,'policyVersion':self.policy_version}


def top_two(values):
    return sorted(values, key=lambda item:(-item[0],str(item[1]).casefold()))[:2]


class AssessmentIndex:
    def __init__(self, videos, subtitles, should_stop=None):
        self.videos, self.subtitles = tuple(videos), tuple(subtitles)
        self.metadata = {}
        for path in (*self.videos,*self.subtitles):
            check_cancelled(should_stop)
            self.metadata[path]=parse_release(path.name)
        self.groups = {path:release_key(path) for path in self.subtitles}
        self.duplicates = Counter((self.groups[path],variant_of(path).key) for path in self.subtitles)
        buckets=defaultdict(list)
        for sub in self.subtitles:
            check_cancelled(should_stop)
            title=self.metadata[sub].title
            if title:buckets[clean_token(title)].append(sub)
        self.video_summary, self.subtitle_summary = {}, {}
        for video in self.videos:
            check_cancelled(should_stop)
            grouped, exact = {}, set()
            title=self.metadata[video].title
            for sub in buckets.get(clean_token(title) if title else '', ()):
                check_cancelled(should_stop)
                _evidence,conflicts,missing=facts(self.metadata[video],self.metadata[sub])
                if conflicts or missing:continue
                score=similarity(video,sub)
                if score<=MATCH_THRESHOLD:continue
                group=self.groups[sub]
                if group not in grouped or score>grouped[group][0]:grouped[group]=(score,sub)
                is_exact=release_key(video)==group
                if is_exact:exact.add(group)
                summary=self.subtitle_summary.setdefault(sub,{'count':0,'exact':0,'top':[]})
                summary['count']+=1;summary['exact']+=int(is_exact)
                summary['top']=top_two([*summary['top'],(score,video)])
            self.video_summary[video]={'count':len(grouped),'exact':exact,'top':top_two(grouped.values())}

    def assess(self, video, subtitle):
        video_info=self.metadata.get(video) or parse_release(video.name)
        sub_info=self.metadata.get(subtitle) or parse_release(subtitle.name)
        evidence,conflicts,missing=facts(video_info,sub_info)
        score=similarity(video,subtitle)
        reasons=list((*conflicts,*missing))
        variant=variant_of(subtitle)
        if variant.ambiguous:reasons.append('字幕语言或脚本标注存在冲突')
        group=self.groups.get(subtitle,release_key(subtitle))
        row=self.video_summary.get(video,{'count':0,'exact':set(),'top':[]})
        sub=self.subtitle_summary.get(subtitle,{'count':0,'exact':0,'top':[]})
        exact=release_key(video)==group
        if row['count']>1 and not (exact and len(row['exact'])==1):
            reasons.append('存在多份同用途版本候选，请比较前两项')
        if sub['count']>1 and not (exact and sub['exact']==1):
            reasons.append('同一字幕适合多个视频，请确认归属')
        if self.duplicates.get((group,variant.key),0)>1:
            reasons.append('同版同用途有多个文件或格式，请选择一份')
        if score<AUTO_APPLY_THRESHOLD:reasons.append('名称匹配分未达到原有采纳门槛')
        alternatives=[value for value,path in row['top'] if self.groups.get(path)!=group]
        competitors=[value for value,path in sub['top'] if path!=video]
        video_margin=score-max(alternatives) if alternatives else None
        subtitle_margin=score-max(competitors) if competitors else None
        eligible=not reasons
        shadow=eligible and score>=.85 and all(value is None or value>=.08 for value in (video_margin,subtitle_margin))
        return Assessment(score,evidence,conflicts,missing,tuple(dict.fromkeys(reasons)),
                          video_margin,subtitle_margin,eligible,shadow)

    def leaders(self, video, limit=2):
        return [path for _score,path in self.video_summary.get(video,{}).get('top',[])][:limit]
