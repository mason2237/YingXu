"""Same-language local text evidence; never an association/rename decision."""
from collections import Counter
from math import sqrt
import re
import unicodedata
from .matching import check_cancelled


def normalize(text):
    text=re.sub(r'\{[^}]*\}|<[^>]*>','',text).replace(r'\N',' ').replace(r'\n',' ')
    text=unicodedata.normalize('NFKC',text).casefold()
    return ''.join(c for c in text if c.isalpha() or c.isspace()).strip()


def features(document,should_stop=None):
    lines=[]
    for cue in document.cues:
        check_cancelled(should_stop)
        if cue.kind!='comment':lines.append(normalize(cue.text))
    counts=Counter(lines);valid=[]
    for index,line in enumerate(lines):
        if len(line)<12 or counts[line]>2 or re.search(r'previously on|subtitles? by|字幕|翻译|校对|片头|作词|作曲|回顾',line):continue
        valid.append((index,line))
    windows=[];samples=[];line_sets=[]
    for part in range(3):
        pieces=[line for index,line in valid if len(lines)*part/3<=index<len(lines)*(part+1)/3]
        text=' '.join(pieces)[:4096];counter=Counter(text[i:i+2] for i in range(max(0,len(text)-1)) if not text[i:i+2].isspace())
        windows.append(counter);samples.append(text[:120])
        line_sets.append(set(pieces[:32]))
    sufficient=len(valid)>=12 and all(sum(w.values())>=100 and len(w)>=35 for w in windows)
    joined=''.join(samples);cjk=sum('\u3400'<=c<='\u9fff' for c in joined)
    return {'sufficient':sufficient,'windows':windows,'samples':samples,'validLines':len(valid),'lineSets':line_sets,
            'script':'cjk' if cjk>len(joined)*.25 else 'latin'}


def cosine(left,right):
    norm=sqrt(sum(n*n for n in left.values())*sum(n*n for n in right.values()))
    return sum(n*right.get(k,0) for k,n in left.items())/norm if norm else 0.


def compare(reference,candidate,same_language=True):
    if not same_language or not reference['sufficient'] or not candidate['sufficient'] or reference.get('script')!=candidate.get('script'):
        return {'status':'insufficient_evidence','score':None,'reason':'语言不同或有效对白不足；片头、重复歌曲和短文本不能作可靠依据。'}
    scores=[cosine(a,b) for a,b in zip(reference['windows'],candidate['windows'])]
    value=sum(scores)/3
    distinctive=all(len(a&b)>=2 for a,b in zip(reference['lineSets'],candidate['lineSets']))
    supports=value>=.8 and min(scores)>=.65 and distinctive
    return {'status':'supporting' if supports else 'ambiguous',
        'score':round(value,4),'windowScores':[round(s,4) for s in scores],
        'reason':'同语言三个文本窗口有共同的独特对白，可作为补充证据，仍需人工核对。' if supports else '文本或独特对白证据不足，不能确认作品或剪辑。',
        'excerpts':candidate['samples']}
