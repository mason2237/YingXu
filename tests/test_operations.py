"""File safety contracts for preview, execution and history."""
import errno
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from yingxu.operations import HistoryStore, export_result, run_batch, snapshot_from_review
from yingxu.review import ReviewPlan


class OperationContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="apply-", dir=Path(__file__).resolve().parents[1] / "work")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.history = HistoryStore(self.root / "records" / "history.jsonl")

    def make(self, name: str) -> Path:
        path = self.root / name
        path.write_bytes(name.encode("utf-8"))
        return path

    def plan(self, count=2):
        videos = [self.make(f"剧集.S01E{number:02d}.mkv") for number in range(1, count + 1)]
        subtitles = [self.make(f"字幕组.S01E{number:02d}.chs.srt") for number in range(1, count + 1)]
        review = ReviewPlan(videos, subtitles)
        for index in range(count):
            review.confirm(index)
        return review

    def test_preview_is_read_only_and_execution_records_exact_targets(self):
        review = self.plan()
        before = {p.name: p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        snapshot = snapshot_from_review(review)
        self.assertEqual(len(snapshot.changes), 2)
        self.assertEqual({p.name: p.read_bytes() for p in self.root.iterdir() if p.is_file()}, before)
        progress = []
        result = run_batch(snapshot, history=self.history,
                           progress=lambda done, total, name: progress.append((done, total, name)))
        self.assertEqual(result.count("success"), 2)
        self.assertEqual([step[0] for step in progress], [1, 2])
        for item in snapshot.changes:
            self.assertFalse(item.source.exists())
            self.assertEqual(item.target.read_bytes(), before[item.source.name])
        records = self.history.recent()
        self.assertEqual(len(records), 1)
        self.assertEqual([item["target"] for item in records[0]["items"]],
                         [str(item.target) for item in snapshot.items])

    def test_target_appears_after_preview_blocks_whole_batch(self):
        snapshot = snapshot_from_review(self.plan())
        occupied = snapshot.changes[1].target
        occupied.write_bytes(b"do not overwrite")
        result = run_batch(snapshot, history=self.history)
        self.assertEqual(result.count("blocked"), 2)
        self.assertTrue(result.issue)
        self.assertEqual(occupied.read_bytes(), b"do not overwrite")
        self.assertTrue(all(item.source.exists() for item in snapshot.changes))

    def test_source_disappears_after_preview_blocks_whole_batch(self):
        snapshot = snapshot_from_review(self.plan())
        snapshot.changes[1].source.unlink()
        result = run_batch(snapshot)
        self.assertEqual(result.count("blocked"), 2)
        self.assertTrue(snapshot.changes[0].source.exists())
        self.assertTrue(all(not item.target.exists() for item in snapshot.changes))

    def test_source_changes_after_preview_blocks_whole_batch(self):
        snapshot = snapshot_from_review(self.plan())
        snapshot.changes[0].source.write_bytes(b"changed")
        result = run_batch(snapshot)
        self.assertEqual(result.count("blocked"), 2)
        self.assertTrue(all(item.source.exists() for item in snapshot.changes))

    def test_permission_error_is_per_file_and_recorded(self):
        snapshot = snapshot_from_review(self.plan())
        original = os.rename

        def fail_first(source, target):
            if source == snapshot.changes[0].source:
                raise PermissionError("permission denied")
            return original(source, target)

        with patch("yingxu.operations.os.rename", side_effect=fail_first):
            result = run_batch(snapshot, history=self.history)
        self.assertEqual([item.status for item in result.items], ["error", "success"])
        self.assertTrue(snapshot.changes[0].source.exists())
        self.assertFalse(snapshot.changes[0].target.exists())
        self.assertFalse(snapshot.changes[1].source.exists())
        self.assertEqual([item["status"] for item in self.history.recent()[0]["items"]],
                         ["error", "success"])

    def test_stop_after_first_completed_item(self):
        snapshot = snapshot_from_review(self.plan(3))
        steps = []
        result = run_batch(snapshot, should_stop=lambda: bool(steps),
                           progress=lambda done, total, name: steps.append(done))
        self.assertEqual([item.status for item in result.items], ["success", "cancelled", "cancelled"])
        self.assertTrue(snapshot.changes[1].source.exists())
        self.assertFalse(snapshot.changes[1].target.exists())

    def test_cross_device_fallback_creates_exclusive_target(self):
        snapshot = snapshot_from_review(self.plan(1))
        source = snapshot.changes[0].source
        payload = source.read_bytes()
        with patch("yingxu.operations.os.rename", side_effect=OSError(errno.EXDEV, "cross device")):
            result = run_batch(snapshot)
        self.assertEqual(result.count("success"), 1)
        self.assertFalse(source.exists())
        self.assertEqual(snapshot.changes[0].target.read_bytes(), payload)

    def test_target_created_during_rename_is_not_overwritten(self):
        snapshot = snapshot_from_review(self.plan(1))
        item = snapshot.changes[0]
        original = os.rename

        def occupy_then_rename(source, target):
            target.write_bytes(b"new arrival")
            return original(source, target)

        with patch("yingxu.operations.os.rename", side_effect=occupy_then_rename):
            result = run_batch(snapshot)
        self.assertEqual(result.count("error"), 1)
        self.assertEqual(item.target.read_bytes(), b"new arrival")
        self.assertTrue(item.source.exists())

    def test_result_export_is_complete_and_exclusive(self):
        result = run_batch(snapshot_from_review(self.plan(1)))
        report = self.root / "report.json"
        export_result(result, report)
        self.assertIn('"success"', report.read_text(encoding="utf-8"))
        with self.assertRaises(FileExistsError):
            export_result(result, report)

    def test_history_failure_is_reported_after_file_change(self):
        snapshot = snapshot_from_review(self.plan(1))
        with patch.object(self.history, "append", side_effect=PermissionError("history denied")):
            result = run_batch(snapshot, history=self.history)
        self.assertEqual(result.count("success"), 1)
        self.assertIn("history denied", result.history_error)

    def test_uncertain_match_requires_confirmation(self):
        video = self.make("影片.S01E01.mkv")
        subtitle = self.make("完全不同.S01E01.srt")
        review = ReviewPlan([video], [subtitle])
        self.assertEqual(review.state(0), "需确认")
        snapshot = snapshot_from_review(review)
        self.assertEqual(snapshot.pending_count, 1)
        result = run_batch(snapshot)
        self.assertEqual(result.count("skipped"), 1)
        self.assertTrue(result.issue)
        self.assertTrue(subtitle.exists())

    def test_skipped_and_unchanged_are_not_modified(self):
        video = self.make("剧集.S01E01.mkv")
        same = self.make("剧集.S01E01.chs.srt")
        review = ReviewPlan([video], [same])
        snap = snapshot_from_review(review)
        self.assertEqual(snap.items[0].action, "unchanged")
        self.assertEqual(run_batch(snap).count("unchanged"), 1)
        review.skip(0)
        snap = snapshot_from_review(review)
        self.assertEqual(run_batch(snap).count("skipped"), 1)
        self.assertEqual(same.read_bytes(), same.name.encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
