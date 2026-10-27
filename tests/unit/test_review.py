"""Review planning contracts: in-memory edits, distinct languages, unique targets."""
import tempfile
import unittest
from pathlib import Path

from yingxu.review import ReviewPlan, language_of, path_key


class ReviewContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def file(self, name):
        path = self.root / name
        path.write_bytes(name.encode())
        return path

    def snapshot(self):
        return {path.name: path.read_bytes() for path in self.root.iterdir() if path.is_file()}

    def test_distinct_languages_and_existing_target(self):
        video = self.file("剧集.S01E01.mkv")
        chinese = self.file("剧集.S01E01.chs.srt")
        english = self.file("剧集.S01E01.eng.srt")
        duplicate_chinese = self.file("剧集.S01E01.zh-cn.srt")
        self.file("剧集.S01E01.en.srt")
        self.file("剧集.S01E01_1.eng.srt")
        before = self.snapshot()
        plan = ReviewPlan([video], [chinese, english, duplicate_chinese], False)
        row = plan.rows[0]
        self.assertEqual({language_of(m.source) for m in row.matches}, {"简体中文", "英语"})
        self.assertEqual(plan.owner(duplicate_chinese), None)
        targets = [path_key(m.target) for m in row.matches]
        self.assertEqual(len(targets), len(set(targets)))
        self.assertEqual(self.snapshot(), before)

    def test_manual_assignment_conflicts_and_review(self):
        first = self.file("剧集.S01E01.mkv")
        second = self.file("剧集.S01E02.mkv")
        first_sub = self.file("剧集.S01E01.chs.srt")
        spare = self.file("完全不同.S09E09.eng.srt")
        before = self.snapshot()
        plan = ReviewPlan([first, second], [first_sub, spare])
        with self.assertRaisesRegex(ValueError, "另一个视频"):
            plan.assign(1, first_sub)
        plan.assign(1, spare)
        self.assertEqual(plan.state(1), "需确认")
        self.assertTrue(plan.rows[1].matches[0].manual)
        self.assertEqual(plan.rows[1].matches[0].score, 0)
        plan.confirm(1)
        self.assertEqual(plan.state(1), "待整理")
        plan.skip(1)
        self.assertEqual(plan.state(1), "已跳过")
        plan.skip(1, False)
        self.assertEqual(plan.state(1), "待整理")
        self.assertEqual(self.snapshot(), before)

    def test_replace_and_remove_release_subtitle(self):
        video = self.file("剧集.S01E01.mkv")
        chinese = self.file("剧集.S01E01.chs.srt")
        alternate = self.file("另一组.S01E01.zh-cn.ass")
        plan = ReviewPlan([video], [chinese, alternate])
        self.assertEqual(len(plan.rows[0].matches), 1)
        plan.assign(0, alternate, replace=chinese)
        self.assertEqual(plan.owner(chinese), None)
        self.assertEqual(plan.owner(alternate), 0)
        self.assertEqual(plan.rows[0].matches[0].target.suffix, ".ass")
        plan.remove(0, alternate)
        self.assertEqual(plan.state(0), "未匹配")
        self.assertEqual(plan.owner(alternate), None)

    def test_duplicate_language_requires_replacement(self):
        video = self.file("剧集.S01E01.mkv")
        chinese = self.file("剧集.S01E01.chs.srt")
        alternate = self.file("另一组.S01E01.zh-cn.ass")
        plan = ReviewPlan([video], [chinese, alternate])
        with self.assertRaisesRegex(ValueError, "同一种语言"):
            plan.assign(0, alternate)

    def test_existing_destination_is_numbered_without_overwrite(self):
        video = self.file("剧集.S01E01.mkv")
        subtitle = self.file("另一组.S01E01.eng.srt")
        occupied = self.file("剧集.S01E01.eng.srt")
        plan = ReviewPlan([video], [subtitle])
        self.assertEqual(plan.rows[0].matches[0].target.name, "剧集.S01E01_1.eng.srt")
        self.assertEqual(occupied.read_bytes(), occupied.name.encode())


if __name__ == "__main__":
    unittest.main()
