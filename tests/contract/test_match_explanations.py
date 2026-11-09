"""Explainable DTOs and upgraded policies preserve review and consent boundaries."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from yingxu.application.reviewing import ReviewData
from yingxu.application.drafts import Drafts
from yingxu.adapters.local_filesystem import LocalFilesystem
from yingxu.domain.match_assessment import POLICY_VERSION
from yingxu.domain.review import ReviewPlan


class MatchExplanationContracts(unittest.TestCase):
    def test_candidate_conflicts_and_paged_basis_are_explicit(self):
        video=Path('Film.2024.S01E01.mkv')
        subtitles=[Path('Film.2023.S01E01.en.srt'),Path('Film.2024.S01E01.sdh.en.srt')]
        data=ReviewData(ReviewPlan([video],subtitles,exists=lambda p:False),lambda p:p.name)
        rows=data.candidates(0)['rows']
        wrong=next(row for row in rows if '2023' in row['name'])
        self.assertTrue(wrong['conflict']);self.assertFalse(wrong['assessment']['autoEligible'])
        self.assertIn('年份不一致',wrong['assessment']['conflicts'])
        self.assertEqual(data.detail_header(0)['matchPolicy'],POLICY_VERSION)
        self.assertTrue(any('候选 1' in text for text in data.detail_entries(0,'basis')))

    def test_policy_upgrade_keeps_choices_but_invalidates_revision_and_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);video=root/'Film.2024.mkv';sub=root/'Film.2024.en.srt'
            video.write_bytes(b'generated video');sub.write_bytes(b'generated subtitle')
            fs=LocalFilesystem();drafts=Drafts(None,fs)
            plan=ReviewPlan([video],[sub],exists=fs.exists);plan.confirm(0)
            data=ReviewData(plan,lambda p:p.name,revision=4)
            workspace=SimpleNamespace(folder=root,folder_mark=fs.directory_mark(root),options={'move':False,'recursive':True},embedded={'enabled':False,'language':'chinese'})
            value=drafts.capture(workspace,data);value.pop('matchPolicy')
            restored=drafts.restore(value,lambda p:p.name)[2]
            self.assertEqual(restored.revision,5);self.assertEqual(restored.review.state(0),'需确认')
            self.assertEqual(restored.review.rows[0].matches[0].source,sub)
            self.assertFalse(restored.review.rows[0].matches[0].confirmed)


if __name__=='__main__':unittest.main()
