"""Incremental review changes preserve old snapshots and do not read other rows."""
from pathlib import Path
import unittest

from yingxu.application.reviewing import ReviewData
from yingxu.domain.review import ReviewPlan


class IncrementalReviewTests(unittest.TestCase):
    def setUp(self):
        self.checked = []
        def exists(path):
            self.checked.append(path)
            return False
        self.videos = [Path(f'video/Atlas.S01E{index:02}.1080p.mkv') for index in (1, 2)]
        self.subtitles = [Path(f'subs/Atlas.S01E{index:02}.chs.srt') for index in (1, 2)]
        self.review = ReviewPlan(self.videos, self.subtitles, exists=exists)
        self.data = ReviewData(self.review, lambda path: str(path).replace('/', '_'))
        self.checked.clear()

    def test_skip_updates_one_row_and_leaves_previous_review_unchanged(self):
        updated = self.data.updated('review.skip', {'rowId': 'video-1', 'skipped': True})
        self.assertFalse(self.data.review.rows[0].skipped)
        self.assertTrue(updated.review.rows[0].skipped)
        self.assertEqual(updated.revision, self.data.revision+1)
        self.assertEqual(self.checked, [self.review.rows[0].matches[0].target])
        self.assertIs(updated.rows[1], self.data.rows[1])

    def test_failed_assignment_does_not_mutate_original_owner_or_targets(self):
        before = [(row.video, tuple((match.source, match.target) for match in row.matches)) for row in self.review.rows]
        subtitle_id = next(key for key, path in self.data.subtitle_ids.items() if path == self.subtitles[1])
        with self.assertRaises(ValueError):
            self.data.updated('review.assign', {'rowId': 'video-1', 'subtitleId': subtitle_id})
        self.assertEqual(before, [(row.video, tuple((match.source, match.target) for match in row.matches)) for row in self.review.rows])
        self.assertEqual(self.review.owner(self.subtitles[1]), 1)


if __name__ == '__main__':
    unittest.main()
