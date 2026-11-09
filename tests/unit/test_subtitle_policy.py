"""Coverage and upgrade decisions without filesystem, GUI, or network."""
from dataclasses import replace
from pathlib import Path
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from yingxu.domain.subtitle_policy import (Evidence,SubtitlePolicy,coverage,embedded_evidence,upgrade_decision)
from yingxu.domain.subtitle_variants import SubtitleVariant
from yingxu.domain.matching import ScanCancelled
from yingxu.domain.review import ReviewPlan
from yingxu.application.reviewing import ReviewData
from yingxu.application.subtitle_needs import SubtitleNeeds
from yingxu.domain.subtitle_document import SubtitleRead,MAX_BYTES as MAX_FILE_BYTES


class SubtitlePolicyTests(unittest.TestCase):
    def evidence(self,**values):
        return replace(Evidence('sub',SubtitleVariant(('zh',),'Hans'),'clean','a'*64,complete=True),**values)

    def test_language_script_and_single_bilingual_requirement(self):
        policy=SubtitlePolicy(('simplified','traditional','english','bilingual'))
        result=coverage(policy,[self.evidence(),self.evidence(variant=SubtitleVariant(('en',)))])
        self.assertEqual([r['state'] for r in result],['satisfied','missing','satisfied','missing'])
        self.assertEqual(coverage(SubtitlePolicy(('bilingual',)),[self.evidence(variant=SubtitleVariant(('en','zh')) )])[0]['state'],'satisfied')

    def test_forced_commentary_unknown_and_sdh_cannot_silently_satisfy_full(self):
        for variant in (SubtitleVariant(('zh',),forced=True),SubtitleVariant(('zh',),commentary=True),
                        SubtitleVariant(),SubtitleVariant(('zh',),ambiguous=True),SubtitleVariant(('zh',),sdh=True)):
            with self.subTest(variant=variant):self.assertEqual(coverage(SubtitlePolicy(),[self.evidence(variant=variant)])[0]['state'],'missing')
        self.assertEqual(coverage(SubtitlePolicy(allow_sdh=True),[self.evidence(variant=SubtitleVariant(('zh',),sdh=True))])[0]['state'],'satisfied')
        self.assertEqual([r['state'] for r in coverage(SubtitlePolicy(include_forced=True),[self.evidence()])],['satisfied','missing'])

    def test_damaged_is_missing_unchecked_or_uncertain_is_review(self):
        self.assertEqual(coverage(SubtitlePolicy(),[self.evidence(errors=1,quality='issues')])[0]['state'],'missing')
        for item in (self.evidence(quality='unchecked',complete=False),self.evidence(quality='encoding_required',complete=False),
                     self.evidence(accepted=False),self.evidence(warnings=1),self.evidence(complete=False)):
            with self.subTest(item=item):self.assertEqual(coverage(SubtitlePolicy(),[item])[0]['state'],'review')

    def test_embedded_is_metadata_only_and_respects_purpose(self):
        tracks={'status':'ok','tracks':[{'trackId':'one','families':['zh'],'script':'simplified','forced':False}]}
        evidence=embedded_evidence(tracks)
        self.assertEqual(coverage(SubtitlePolicy(),evidence)[0]['state'],'satisfied')
        tracks['tracks'][0]['forced']=True
        self.assertEqual(coverage(SubtitlePolicy(),embedded_evidence(tracks))[0]['state'],'missing')
        self.assertFalse(embedded_evidence({'status':'error','tracks':tracks['tracks']}))

    def test_policy_is_bounded_and_strict(self):
        for value in ({'languages':['english']*2,'allowSDH':False,'includeForced':False},
                      {'languages':[],'allowSDH':False,'includeForced':False},
                      {'languages':['unknown'],'allowSDH':False,'includeForced':False},
                      {'languages':['english'],'allowSDH':1,'includeForced':False}):
            with self.subTest(value=value),self.assertRaises(ValueError):SubtitlePolicy.read(value)

    def test_upgrade_checks_locks_digest_version_purpose_and_quality(self):
        video=Path('Film.2024.mkv');old=Path('Film.2024.en.srt');new=Path('other/Film.2024.en.srt')
        current=self.evidence(variant=SubtitleVariant(('en',)),errors=1,quality='issues')
        proposed=self.evidence(variant=current.variant,digest='b'*64)
        self.assertEqual(upgrade_decision(video,old,new,current,proposed)[0],'suggested')
        cases=[(replace(current,locked=True),proposed,'protected'),
               (current,replace(proposed,digest=current.digest),'duplicate'),
               (current,replace(proposed,variant=SubtitleVariant(('en',),forced=True)),'different_variant'),
               (current,replace(proposed,warnings=1),'review'),
               (replace(current,errors=0,quality='clean'),proposed,'keep')]
        for left,right,state in cases:
            self.assertEqual(upgrade_decision(video,old,new,left,right)[0],state)
        self.assertEqual(upgrade_decision(video,old,Path('Film.2023.en.srt'),current,proposed)[0],'review')
        self.assertEqual(upgrade_decision(Path('Film.2024.Directors.Cut.mkv'),old,new,current,proposed)[0],'review')

    def test_inspection_limit_and_cancel_do_not_claim_quality_or_read_without_budget(self):
        review=ReviewPlan([Path('Film.2024.mkv')],[Path('Film.2024.chs.srt')],exists=lambda _p:False)
        data=ReviewData(review,lambda p:p.name)
        reader=SimpleNamespace(read=lambda *_a,**_k:self.fail('Reader must not run beyond the budget'))
        workspace=SimpleNamespace(session_id='test',quality=SimpleNamespace(reader=reader),
            fs=SimpleNamespace(file_mark=lambda _p:SimpleNamespace(size=1)))
        service=SubtitleNeeds(workspace);worker=SimpleNamespace(stop=Event(),report=lambda *_a:None)
        with patch('yingxu.application.subtitle_needs.MAX_FILES',0):
            report=service.inspect(data,worker)
        self.assertTrue(report['limited']);self.assertEqual(report['filesChecked'],0)
        self.assertEqual(report['rows'][0]['state'],'review')
        worker.stop.set()
        with self.assertRaises(ScanCancelled):service.inspect(data,worker)

    def test_byte_budget_uses_actual_bounded_reads_and_marks_remaining_unknown(self):
        review=ReviewPlan([Path('Film.2024.mkv')],[Path('Film.2024.chs.srt'),Path('Film.2024.en.srt')],exists=lambda _p:False)
        data=ReviewData(review,lambda p:p.name);calls=[]
        def read(path,**_options):
            calls.append(path)
            return SubtitleRead('srt','1\n00:00:01,000 --> 00:00:02,000\nText\n','utf8','a'*64,bytes_read=MAX_FILE_BYTES)
        workspace=SimpleNamespace(session_id='test',quality=SimpleNamespace(reader=SimpleNamespace(read=read)))
        service=SubtitleNeeds(workspace);worker=SimpleNamespace(stop=Event(),report=lambda *_a:None)
        with patch('yingxu.application.subtitle_needs.MAX_BYTES',MAX_FILE_BYTES):report=service.inspect(data,worker)
        self.assertEqual(len(calls),1);self.assertTrue(report['limited']);self.assertEqual(report['bytesReadBudget'],MAX_FILE_BYTES)


if __name__=='__main__':unittest.main()
