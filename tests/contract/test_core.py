"""Behavior contracts. YINGXU_BASELINE_SOURCE optionally tests the old entry."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

baseline = os.environ.get("YINGXU_BASELINE_SOURCE")
if baseline:
    spec = importlib.util.spec_from_file_location("baseline", baseline)
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
else:
    from yingxu import core


class CoreContracts(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="yingxu-core-")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.videos = self.folder / "Videos"
        self.subtitles = self.folder / "Subtitles"
        self.videos.mkdir()
        self.subtitles.mkdir()

    def put(self, folder, name, content="original content"):
        path = folder / name
        path.write_text(content, encoding="utf-8")
        return path

    def snapshot(self):
        return {str(p.relative_to(self.folder)): p.read_bytes()
                for p in self.folder.rglob("*") if p.is_file()}

    def test_unicode_normalization_keeps_chinese(self):
        self.assertEqual(core.clean_token("漫长的季节 ＡＢＣ.１２"), "漫长的季节abc12")

    def test_episode_formats(self):
        for title, expected in (("Show.S02E03", (2, 3, True)),
                                ("Show.2x03", (2, 3, True)),
                                ("Show.EP03", (None, 3, True)),
                                ("剧名第3集", (None, 3, True)),
                                ("旅行2024", None)):
            with self.subTest(title=title):
                self.assertEqual(core.extract_episode(title), expected)

    def test_conflicting_episode_or_season_cannot_match(self):
        for subtitle in ("Show.S01E02.srt", "Show.S02E01.srt"):
            self.assertEqual(core.similarity(Path("Show.S01E01.mp4"), Path(subtitle)), 0)

    def test_same_episode_unrelated_title_requires_review(self):
        plan = core.build_plan([self.videos / "AAAA.S01E01.mp4"],
                               [self.subtitles / "ZZZZ.S01E01.srt"])
        self.assertEqual(plan[0]["status"], "需确认")
        self.assertLess(plan[0]["score"], core.AUTO_APPLY_THRESHOLD)

    def test_exact_chinese_names_match(self):
        plan = core.build_plan([self.videos / "旅行日记.mp4"],
                               [self.subtitles / "旅行日记.chs.srt"])
        self.assertEqual(plan[0]["score"], 1.0)
        self.assertEqual(plan[0]["status"], "已符合")

    def test_recursive_scan_formats_and_order(self):
        video = self.put(self.videos, "剧集.MKV")
        subtitle = self.put(self.subtitles, "剧集.SRT")
        self.put(self.folder, "ignored.txt")
        self.assertEqual(core.collect_media(self.folder), ([video], [subtitle]))

    def test_nonrecursive_scan_and_empty_folder(self):
        self.put(self.videos, "nested.mp4")
        self.assertEqual(core.collect_media(self.folder, False), ([], []))
        root_video = self.put(self.folder, "root.mp4")
        self.assertEqual(core.collect_media(self.folder, False), ([root_video], []))

    def test_no_subtitles_produces_unmatched_rows(self):
        plan = core.build_plan([self.videos / "旅行.mp4"], [])
        self.assertEqual(plan[0]["status"], "未匹配")
        self.assertIsNone(plan[0]["target"])
        self.assertEqual(core.build_plan([], []), [])

    def test_each_subtitle_assigned_at_most_once(self):
        videos = [self.videos / "Show.S01E01.mp4", self.videos / "Show.S01E01.mkv"]
        plan = core.build_plan(videos, [self.subtitles / "Show.S01E01.eng.srt"])
        self.assertEqual(sum(row["subtitle"] is not None for row in plan), 1)
        self.assertEqual(plan[1]["status"], "未匹配")

    def test_equal_candidates_keep_existing_input_order(self):
        video = self.videos / "Show.S01E01.mp4"
        candidates = [self.subtitles / "Show.S01E01.eng.srt",
                      self.subtitles / "Show.S01E01.chs.srt"]
        self.assertEqual(core.build_plan([video], candidates)[0]["subtitle"], candidates[0])

    def test_default_directory_language_and_extension_preserved(self):
        target = core.destination_for(self.videos / "Show.S01E01.mp4",
                                      self.subtitles / "Other.eng.ASS", set())
        self.assertEqual(target, self.subtitles / "Show.S01E01.eng.ASS")

    def test_optional_move_to_video_directory(self):
        target = core.destination_for(self.videos / "Show.mp4",
                                      self.subtitles / "Other.zh-cn.srt", set(), True)
        self.assertEqual(target, self.videos / "Show.zh-cn.srt")

    def test_existing_and_reserved_destinations_get_numbered(self):
        self.put(self.subtitles, "Show.chs.srt", "existing")
        reserved = {os.path.normcase(os.path.abspath(self.subtitles / "Show_1.chs.srt"))}
        before = self.snapshot()
        target = core.destination_for(self.videos / "Show.mp4",
                                      self.subtitles / "Other.chs.srt", reserved)
        self.assertEqual(target.name, "Show_2.chs.srt")
        self.assertEqual(self.snapshot(), before)

    def test_already_named_file_remains_same(self):
        source = self.put(self.subtitles, "Show.chs.srt")
        self.assertEqual(core.destination_for(self.videos / "Show.mp4", source, set()), source)

    def test_scanning_and_planning_never_mutate_files(self):
        self.put(self.videos, "漫长的季节.S01E01.mp4", "video content")
        self.put(self.subtitles, "漫长的季节.S01E01.字幕组.chs.srt", "subtitle content")
        before = self.snapshot()
        videos, subtitles = core.collect_media(self.folder)
        for move in (False, True):
            plan = core.build_plan(videos, subtitles, move)
            self.assertEqual(plan[0]["status"], "待整理")
            self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
