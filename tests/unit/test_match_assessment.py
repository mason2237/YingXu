"""Hard identity conflicts and both directions of competition need real review."""
from pathlib import Path
import unittest

from yingxu.domain.match_assessment import AssessmentIndex
from yingxu.domain.review import ReviewPlan
from yingxu.domain.matching import ScanCancelled


class MatchAssessmentTests(unittest.TestCase):
    def assess(self,video,sub):
        video,sub=Path(video),Path(sub)
        return AssessmentIndex([video],[sub]).assess(video,sub)

    def test_same_episode_is_not_evidence_of_same_work(self):
        for left,right in (('Alpha.S01E01.mkv','Zebra.S01E01.en.srt'),
                           ('Very.Long.Movie.2024.mkv','Very.Long.Movie.2023.en.srt'),
                           ('Film.2024.EXTENDED.mkv','Film.2024.en.srt'),
                           ('Show.S01E01E02.mkv','Show.S01E01.en.srt'),
                           ('Show.S00E01.mkv','Show.E01.en.srt')):
            with self.subTest(video=left,sub=right):
                result=self.assess(left,right)
                self.assertFalse(result.auto_eligible)
                self.assertTrue(result.why_review)

    def test_language_and_purpose_are_not_competing_releases(self):
        video=Path('Film.2024.S01E01.mkv')
        subtitles=[Path('Film.2024.S01E01.'+tag+'.srt') for tag in ('en','en.forced','en.sdh','chs','cht')]
        plan=ReviewPlan([video],subtitles,exists=lambda p:False)
        self.assertEqual(len(plan.rows[0].matches),5)
        self.assertEqual(plan.state(0),'已符合')
        self.assertTrue(all(plan.assessment.assess(video,p).auto_eligible for p in subtitles))

    def test_subtitle_competing_for_two_videos_cannot_be_auto_accepted(self):
        videos=[Path('Film.2024.mkv'),Path('Film.2024.mp4')];sub=Path('Film.2024.en.srt')
        plan=ReviewPlan(videos,[sub],exists=lambda p:False)
        self.assertEqual([plan.state(i) for i in range(2)],['需确认','未匹配'])
        result=plan.assessment.assess(videos[0],sub)
        self.assertEqual(result.subtitle_margin,0)
        self.assertTrue(any('多个视频' in reason for reason in result.why_review))

    def test_two_versions_and_same_variant_formats_are_explained(self):
        video=Path('Film.2024.1080p.mkv')
        subs=[Path('Film.2024.720p.en.srt'),Path('Film.2024.2160p.en.srt')]
        index=AssessmentIndex([video],subs)
        self.assertEqual(len(index.leaders(video)),2)
        self.assertTrue(any('多份' in s for s in index.assess(video,subs[0]).why_review))
        duplicate=[Path('Film.2024.1080p.en.srt'),Path('Film.2024.1080p.en.ass')]
        self.assertTrue(any('多个文件' in s for s in AssessmentIndex([video],duplicate).assess(video,duplicate[0]).why_review))

    def test_unique_exact_release_can_win_without_shadow_threshold(self):
        video=Path('Film.2024.1080p.WEB-DL.mkv')
        subs=[Path('Film.2024.1080p.WEB-DL.en.srt'),Path('Film.2024.720p.WEB-DL.en.srt')]
        self.assertTrue(AssessmentIndex([video],subs).assess(video,subs[0]).auto_eligible)
        self.assertFalse(AssessmentIndex([video],subs).assess(video,subs[1]).auto_eligible)

    def test_manual_override_and_cancellation_stay_available(self):
        video=Path('Film.2024.mkv');sub=Path('Film.2023.en.srt')
        plan=ReviewPlan([video],[sub],exists=lambda p:False)
        self.assertEqual(plan.state(0),'需确认')
        plan.confirm(0);self.assertNotEqual(plan.state(0),'需确认')
        with self.assertRaises(ScanCancelled):AssessmentIndex([video],[sub],lambda:True)


if __name__=='__main__':unittest.main()
