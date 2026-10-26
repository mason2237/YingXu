"""New native action stays versioned, ID-only and read-only."""
import json
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from PySide6.QtCore import QCoreApplication
from yingxu.operations import HistoryStore
from yingxu.review import ReviewPlan, ReviewMatch
from yingxu.web_ui.workspace_bridge import WorkspaceBridge
from yingxu.web_ui.workspace_data import ReviewData

ROOT = Path(__file__).resolve().parents[2]


class DiscoveryContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="discovery-", dir=ROOT / "work/test-results")
        root = Path(self.temp.name)
        self.bridge = WorkspaceBridge(history=HistoryStore(root / "history.jsonl"))
        self.service = self.bridge.service
        self.responses, self.native = [], []
        self.bridge.reply.connect(lambda raw: self.responses.append(json.loads(raw)))
        self.service.native_requested.connect(lambda *args: self.native.append(args))
        self.send("app.hello")
        videos = [root / f"Example.S01E{i:02}.mkv" for i in range(1, 4)]
        for video in videos:
            video.write_bytes(b"video")
        sub = root / "Example.S01E01.srt"
        sub.write_text("subtitle")
        review = ReviewPlan(videos, [])
        review.rows[0].matches = [ReviewMatch(sub)]
        review.rows[2].skipped = True
        self.service.data = ReviewData(review, self.service.register, revision=4)
        self.context = {"scanId": self.service.data.scan_id, "revision": 4}

    def tearDown(self):
        self.temp.cleanup()

    def send(self, action, params=None, rid=None):
        self.bridge.request(json.dumps({"v": 1, "requestId": rid or uuid4().hex,
            "sessionId": self.bridge.session_id, "action": action, "params": params or {}}))
        return self.responses[-1] if self.responses else None

    def test_defaults_only_unmatched_not_skipped_and_selected_allows_matched(self):
        tasks = self.service.subtitle_tasks(self.context)
        self.assertEqual([task["rowId"] for task in tasks], ["video-2"])
        task = self.service.subtitle_tasks({**self.context, "rowId": "video-1"})[0]
        self.assertIsInstance(task["video"], Path)
        self.assertEqual(task["revision"], 4)

    def test_untrusted_parameters_rejected_before_native_action(self):
        for params in ({**self.context, "path": "C:/video.mkv"}, {**self.context, "url": "https://example.com"},
                       {**self.context, "rowId": "unknown"}, {**self.context, "revision": 3}):
            self.assertFalse(self.send("subtitle.open", params)["ok"])
        self.assertFalse(self.native)

    def test_duplicate_pending_and_completed_request_only_opens_once(self):
        rid = uuid4().hex
        self.send("subtitle.open", self.context, rid)
        self.send("subtitle.open", self.context, rid)
        self.assertEqual(len(self.native), 1)
        self.service.native_busy = False
        self.bridge.finish_native(rid, self.bridge.session_id, data={"opened": True})
        self.assertTrue(self.send("subtitle.open", self.context, rid)["ok"])
        self.assertEqual(len(self.native), 1)

    def test_busy_and_missing_review_rejected(self):
        self.service.native_busy = True
        self.assertEqual(self.send("subtitle.open", self.context)["error"]["code"], "BUSY")
        self.service.native_busy = False
        self.service.data = None
        self.assertEqual(self.send("subtitle.open", self.context)["error"]["code"], "STALE_REVIEW")

    def test_prepare_preserves_preview_revision_and_file_bytes(self):
        marker = object()
        self.service.snapshot = marker
        root = Path(self.temp.name)
        before = {path.name: path.read_bytes() for path in root.iterdir()}
        self.service.subtitle_tasks(self.context)
        self.assertIs(self.service.snapshot, marker)
        self.assertEqual(self.service.data.revision, 4)
        self.assertEqual(before, {path.name: path.read_bytes() for path in root.iterdir()})


if __name__ == "__main__":
    unittest.main()
