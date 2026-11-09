"""Generated held-out filename corpus. Measures synthetic behavior, not real accuracy."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import types

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from yingxu.domain.review import ReviewPlan


def wilson(success,total):
    if not total:return None
    z=1.95996398454;p=success/total;d=1+z*z/total
    center=(p+z*z/(2*total))/d
    delta=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/d
    return [max(0,center-delta),min(1,center+delta)]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split',choices=['heldout'],default='heldout')
    parser.add_argument('--baseline-ref',default='1179086')
    parser.add_argument('--output',type=Path,default=ROOT/'work/test-results/yx03-matching-quality.json')
    args=parser.parse_args()
    source=subprocess.check_output(['git','show',args.baseline_ref+':yingxu/domain/planning.py'],cwd=ROOT,text=True,encoding='utf-8')
    old={'__name__':'baseline_planning','__package__':'yingxu.domain'}
    exec(compile(source,'baseline_planning','exec'),old)
    review_source=subprocess.check_output(['git','show',args.baseline_ref+':yingxu/domain/review.py'],cwd=ROOT,text=True,encoding='utf-8')
    old_review=types.ModuleType('baseline_review');old_review.__package__='yingxu.domain'
    sys.modules[old_review.__name__]=old_review
    exec(compile(review_source,'baseline_review','exec'),old_review.__dict__)
    old_review.build_plan=old['build_plan']
    cases=[]
    for index in range(1200):
        name=f'Heldout.Work{index}.2024.S01E01.1080p.WEB-DL'
        cases.append(([Path(name+'.mkv')],[Path(name+'.en.srt'),Path(name+'.chs.srt')],{(0,0),(0,1)},'positive'))
    for index in range(100):
        name=f'Other.Heldout{index}'
        for video,sub,kind in ((name+'.2024',name+'.2023','year'),
                              (name+'.2024.EXTENDED',name+'.2024','edition'),
                              (name+'A.S01E01',name+'B.S01E01','title')):
            cases.append(([Path(video+'.mkv')],[Path(sub+'.en.srt')],set(),kind))
        name=f'Competing.Work{index}.2024'
        cases.append(([Path(name+'.mkv'),Path(name+'.mp4')],[Path(name+'.en.srt')],set(),'competition'))
    totals={'new':dict(auto=0,correct=0,review_rows=0,unmatched_rows=0),
            'baseline':dict(auto=0,correct=0,review_rows=0,unmatched_rows=0)}
    hard_errors=0;rows=0;possible=0
    for videos,subtitles,expected,kind in cases:
        rows+=len(videos);possible+=len(expected)
        review=ReviewPlan(videos,subtitles,exists=lambda p:False)
        for index,row in enumerate(review.rows):
            state=review.state(index)
            totals['new']['review_rows']+=state=='需确认';totals['new']['unmatched_rows']+=state=='未匹配'
            if state in {'待整理','已符合'}:
                for match in row.matches:
                    valid=(index,subtitles.index(match.source)) in expected
                    totals['new']['auto']+=1;totals['new']['correct']+=valid
                    hard_errors+=not valid
        baseline=old_review.ReviewPlan(videos,subtitles,exists=lambda p:False)
        for index,row in enumerate(baseline.rows):
            state=baseline.state(index);totals['baseline']['review_rows']+=state=='需确认';totals['baseline']['unmatched_rows']+=state=='未匹配'
            if state in {'待整理','已符合'}:
                for match in row.matches:
                    totals['baseline']['auto']+=1
                    totals['baseline']['correct']+=(index,subtitles.index(match.source)) in expected
    for metric in totals.values():
        metric.update(precision=metric['correct']/metric['auto'] if metric['auto'] else None,
            precision_wilson_95=wilson(metric['correct'],metric['auto']),
            wrong_accepts=metric['auto']-metric['correct'],coverage=metric['correct']/possible,
            review_rate=metric['review_rows']/rows,unmatched_rate=metric['unmatched_rows']/rows)
    result={'corpus':'Original generated filenames; disjoint work names from unit fixtures; no real subtitle text',
        'split':args.split,'cases':len(cases),'video_rows':rows,'metrics':totals,
        'hard_conflict_auto_accepts':hard_errors,'thresholds_085_008':'shadow only',
        'accuracy_target_verified':False,'limits':['Synthetic heldout names are not an independently labeled real library.',
            'Wrong accepts include ambiguous ownership that requires review, not proof of wrong subtitle content.'],
        'baseline_commit':args.baseline_ref}
    assert hard_errors==0
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
