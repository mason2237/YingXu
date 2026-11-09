"""Prevent high filename scores from hiding explicit episode-coverage conflicts."""
from pathlib import Path
import tempfile
import unittest

from yingxu.adapters.subtitle_sites.candidates import rank_candidates
from yingxu.application.reviewing import ReviewData, episode
from yingxu.domain.matching import (AUTO_APPLY_THRESHOLD, episode_conflict,
                                    episode_identity, extract_episode, similarity)
from yingxu.domain.review import ReviewPlan


class EpisodeCoverageTests(unittest.TestCase):
    def test_multi_episode_coverage_conflicts_are_symmetric(self):
        for first, second in (
            ("Show.S01E01E02", "Show.S01E01"),
            ("Show.S01E01-E03", "Show.S01E01"),
            ("Show.S01E01-03", "Show.S01E01E03"),
            ("Show.S01E01E03", "Show.S01E01E02"),
            ("Show.S01E01.S01E02", "Show.S01E01"),
            ("Show.1x01x02", "Show.1x01"),
            ("Show.1x01x02x03", "Show.1x01x02"),
            ("Show.1x01-03", "Show.1x01"),
            ("Show.Ｓ０１Ｅ０１", "Show.S01E02"),
            ("剧名.第１集", "剧名.第2集"),
        ):
            with self.subTest(first=first, second=second):
                for left, right in ((first, second), (second, first)):
                    self.assertTrue(episode_conflict(left, right))
                    self.assertEqual(similarity(Path(left + ".mkv"), Path(right + ".chs.srt")), 0)

    def test_equivalent_episode_sets_keep_matching(self):
        for first, second in (
            ("Show.S01E01-E03", "Show.S01E01E02E03"),
            ("Show.S01E01-03", "Show.S01E01-E03"),
            ("Show.S01E01E02", "Show.1x01x02"),
            ("Show.S01E01-E03", "Show.1x01x02x03"),
            ("Show.S01E01E02E03", "Show.1x01-02x03"),
            ("Show.S01E01E02E03", "Show.1x01-x02x03"),
            ("Show.S01E01.S01E02", "Show.S01E01E02"),
            ("Show.Ｓ０１Ｅ０１", "Show.S01E01"),
            ("Show.S01E01", "Show.E01"),
        ):
            with self.subTest(first=first, second=second):
                self.assertFalse(episode_conflict(first, second))
                self.assertGreaterEqual(similarity(Path(first + ".mkv"), Path(second + ".srt")), .65)

    def test_release_numbers_are_not_episode_ranges(self):
        for stem in ("Show.S01E01-1080p", "Show.S01E01-x265", "Show.S01E01-2024"):
            with self.subTest(stem=stem):
                key = episode_identity(stem)
                self.assertEqual(key.episodes, frozenset({1}))
                self.assertTrue(key.complete)
        self.assertIsNone(episode_identity("Movie.2024.1080p"))

    def test_uncertain_ranges_do_not_get_auto_paired(self):
        for stem in ("Show.S01E03-E01", "Show.S01E01-E999", "Show.S01E01-E9999",
                     "Show.S01E01.S02E02", "Show.1x01.2x02"):
            with self.subTest(stem=stem):
                key = episode_identity(stem)
                self.assertFalse(key.complete)
                self.assertLessEqual(len(key.episodes), 100)
                self.assertEqual(similarity(Path(stem + ".mkv"), Path("Show.S01E01.srt")), 0)
                self.assertEqual(similarity(Path(stem + ".mkv"), Path("Show.srt")), 0)
                self.assertEqual(episode(Path(stem + ".mkv")), "季集范围需核对")

    def test_existing_single_episode_api_and_score_are_preserved(self):
        self.assertEqual(extract_episode("Show.S02E03"), (2, 3, True))
        self.assertEqual(extract_episode("Show.Ｓ０２Ｅ０３"), (2, 3, True))
        self.assertEqual(extract_episode("Show.S01E01E02"), (1, 1, True))
        self.assertEqual(similarity(Path("Show.S01E01.mkv"), Path("Show.S01E01.chs.srt")), 1)
        self.assertLess(similarity(Path("AAAA.S01E01.mkv"), Path("ZZZZ.S01E01.srt")),
                        AUTO_APPLY_THRESHOLD)

    def test_review_explains_full_coverage_and_preserves_manual_choice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video, subtitle = root / "Show.S01E01E02.mkv", root / "Show.S01E01.chs.srt"
            video.write_bytes(b"generated video placeholder")
            subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\nGenerated dialogue\n", encoding="utf-8")
            before = {p: p.read_bytes() for p in (video, subtitle)}
            plan = ReviewPlan([video], [subtitle], exists=Path.exists)
            self.assertEqual(plan.state(0), "未匹配")
            data = ReviewData(plan, lambda path: path.name)
            self.assertEqual(data.rows[0]["episode"], "S01E01E02")
            candidate = data.candidates(0)["rows"][0]
            self.assertIn("集数不一致", candidate["reason"])
            self.assertFalse(candidate["recommended"])
            plan.assign(0, subtitle)
            self.assertEqual(plan.state(0), "需确认")
            plan.confirm(0)
            self.assertEqual(plan.state(0), "待整理")
            self.assertEqual({p: p.read_bytes() for p in (video, subtitle)}, before)

    def test_online_recommendation_warns_about_partial_coverage(self):
        row = {"title": "Show", "release": "Show.S01E01", "metadata": "简体 中文 英语 双语"}
        result = rank_candidates([row], "Show.S01E01E02.mkv")[0]
        self.assertIn("集数不一致", result["warnings"])


if __name__ == "__main__":
    unittest.main()
