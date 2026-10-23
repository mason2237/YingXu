"""Real backend contracts, with media/history entirely in temporary work folders."""
import json
import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch
from uuid import uuid4

from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QTest

from yingxu.core import collect_media, ScanCancelled
from yingxu.operations import HistoryStore
from yingxu.review import ReviewPlan
from yingxu.web_ui.workspace_bridge import WorkspaceBridge
from yingxu.web_ui.workspace_protocol import decode
from yingxu.web_ui.protocol import ProtocolError

ROOT = Path(__file__).resolve().parents[2]


def wait_for(check):
    for _ in range(1000):
        if check(): return
        QTest.qWait(5)
    raise AssertionError("Background fixture task timed out")


class WorkspaceContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="web-local-",dir=ROOT / "work" / "test-results")
        self.root = Path(self.temp.name);self.media = self.root / "中文 & 字幕 '测'";self.media.mkdir()
        self.bridge = WorkspaceBridge(history=HistoryStore(self.root / "history" / "history.jsonl"))
        self.service = self.bridge.service;self.responses = [];self.events = []
        self.bridge.reply.connect(lambda raw:self.responses.append(json.loads(raw)))
        self.bridge.event.connect(lambda raw:self.events.append(json.loads(raw)))
        self.sid = self.send("app.hello")["data"]["sessionId"]

    def tearDown(self):
        if self.service.worker:
            self.service.worker.stop.set();wait_for(lambda:self.service.worker is None)
        self.temp.cleanup()

    def send(self, action, params=None, *, rid=None, sid=None):
        self.bridge.request(json.dumps({"v":1,"requestId":rid or uuid4().hex,
            "sessionId":None if action == "app.hello" else sid or getattr(self,"sid",None),
            "action":action,"params":params or {}}))
        return self.responses[-1]

    def task(self, action, params=None):
        response = self.send(action,params);self.assertTrue(response["ok"],response)
        wait_for(lambda:self.service.worker is None)
        self.assertEqual(self.service.job["status"],"completed",self.service.job)
        return self.service.job["result"]

    def scan(self, count=2):
        for i in range(1,count+1):
            (self.media / f"剧集.S01E{i:02}.2160p.mkv").write_bytes(b"video-"+bytes([i]))
            (self.media / f"剧集.S01E{i:02}.chs.srt").write_bytes(f"字幕内容{i}".encode())
        self.service.accept_folder(self.media)
        self.task("scan.start",{"folderId":self.service.folder_id,"recursive":True,"move":False})
        return self.service.data

    def context(self, **extra):
        return {"scanId":self.service.data.scan_id,"revision":self.service.data.revision,**extra}

    def preview(self):
        for row in list(self.service.data.rows):
            if row["state"] == "需确认":self.task("review.confirm",self.context(rowId=row["rowId"]))
        return self.task("preview.create",self.context())

    @staticmethod
    def consent(plan):
        return {"scanId":plan["scanId"],"reviewRevision":plan["revision"],"snapshotId":plan["snapshotId"],
            "confirmationToken":plan["confirmationToken"],"acknowledged":True}

    def test_strict_actions_and_no_path_parameters(self):
        cases = [("folder.choose",{"path":str(self.media)}),("file.copyName",{"fileId":3}),
            ("scan.start",{"folderId":"id","recursive":1,"move":False}),
            ("review.query",{"scanId":None,"revision":0,"limit":201}),
            ("os.system",{}),("organize.confirmAndStart",{"acknowledged":True})]
        for action,params in cases:
            response = self.send(action,params);self.assertFalse(response["ok"],response)
        meta = self.bridge.metaObject()
        self.assertEqual({bytes(meta.method(i).methodSignature()).decode() for i in range(meta.methodOffset(),meta.methodCount())},
                         {"request(QString)","reply(QString)","event(QString)"})

    def test_same_existing_plan_and_readonly_preview(self):
        data = self.scan();before = {path.name:path.read_bytes() for path in self.media.iterdir()}
        videos,subtitles = collect_media(self.media);expected = ReviewPlan(videos,subtitles)
        self.assertEqual([[str(m.target) for m in row.matches] for row in expected.rows],
                         [[sub["targetPath"] for sub in row["subtitles"]] for row in data.rows])
        plan = self.preview();page = self.send("preview.query",{"snapshotId":plan["snapshotId"],"limit":1})["data"]
        self.assertEqual(len(page["items"]),1)
        self.assertEqual(before,{path.name:path.read_bytes() for path in self.media.iterdir()})

    def test_ack_required_and_token_bound_to_exact_snapshot(self):
        self.scan();plan = self.preview();params = self.consent(plan)
        for replacement in ({"acknowledged":False},{"snapshotId":"wrong"},{"reviewRevision":999},{"confirmationToken":"wrong"}):
            response = self.send("organize.confirmAndStart",{**params,**replacement});self.assertFalse(response["ok"],response)
        self.assertEqual(len(list(self.media.glob("*.srt"))),2)
        self.assertIsNone(self.service.last_result_id)

    def test_duplicate_and_replayed_execution_never_runs_twice(self):
        self.scan();plan = self.preview();rid = uuid4().hex;params = self.consent(plan)
        first = self.send("organize.confirmAndStart",params,rid=rid)
        self.assertTrue(first["ok"]);self.assertEqual(first,self.send("organize.confirmAndStart",params,rid=rid))
        wait_for(lambda:self.service.worker is None)
        self.assertEqual(self.send("organize.confirmAndStart",params)["error"]["code"],"TOKEN_USED")
        self.assertEqual(len(self.service.history.recent()),1)
        record = self.service.record_page(self.service.last_result_id)
        self.assertEqual(record["success"],2)
        self.assertEqual((self.media / "剧集.S01E01.2160p.chs.srt").read_bytes(),"字幕内容1".encode())

    def test_refresh_revokes_unstarted_consent(self):
        self.scan();plan = self.preview();old = self.sid
        self.bridge.reset_page();self.sid = self.send("app.hello")["data"]["sessionId"]
        self.assertNotEqual(old,self.sid)
        self.assertFalse(self.send("organize.confirmAndStart",self.consent(plan))["ok"])
        self.assertIsNone(self.service.last_result_id)

    def test_refresh_during_apply_keeps_one_job_and_results(self):
        self.scan();plan = self.preview();self.send("organize.confirmAndStart",self.consent(plan))
        self.bridge.reset_page();self.sid = self.send("app.hello")["data"]["sessionId"]
        wait_for(lambda:self.service.worker is None)
        self.assertEqual(len(self.service.history.recent()),1)
        self.assertEqual(self.send("app.state")["data"]["summary"]["lastResultId"],self.service.last_result_id)

    def test_occupied_target_blocks_without_overwrite(self):
        self.scan();plan = self.preview();snapshot = self.service.snapshot
        target = snapshot.changes[0].target;target.write_bytes(b"occupied")
        self.task("organize.confirmAndStart",self.consent(plan))
        self.assertEqual(target.read_bytes(),b"occupied")
        self.assertTrue(all(item.source.exists() for item in snapshot.changes))
        self.assertEqual(self.service.record_page(self.service.last_result_id)["errors"],2)

    def test_mutation_versions_and_failed_assignment_are_atomic(self):
        data = self.scan();plan = self.preview();old_revision = data.revision
        self.task("review.skip",self.context(rowId=data.rows[0]["rowId"],skipped=True))
        self.assertGreater(self.service.data.revision,old_revision)
        self.assertFalse(self.send("organize.confirmAndStart",self.consent(plan))["ok"])
        data = self.service.data
        response = self.send("review.assign",self.context(rowId=data.rows[0]["rowId"],subtitleId="unknown"))
        self.assertTrue(response["ok"]);wait_for(lambda:self.service.worker is None)
        self.assertEqual(self.service.job["status"],"failed")
        self.assertIs(self.service.data,data)

    def test_query_ids_are_optional_and_candidates_are_paged(self):
        self.scan();query = self.send("review.query",self.context(offset=0,limit=1,includeIds=False))["data"]
        self.assertNotIn("ids",query);self.assertEqual(len(query["rows"]),1)
        result = self.task("review.candidates",self.context(rowId=self.service.data.rows[0]["rowId"],offset=0,limit=1))
        self.assertEqual(len(result["rows"]),1);self.assertEqual(result["total"],2)

    def test_late_scan_cancel_does_not_publish_partial_review(self):
        self.service.accept_folder(self.media)
        response = self.send("scan.start",{"folderId":self.service.folder_id,"recursive":True,"move":False})
        self.send("scan.cancel",{"jobId":response["data"]["jobId"]})
        wait_for(lambda:self.service.worker is None)
        self.assertIsNone(self.service.data);self.assertEqual(self.service.job["status"],"cancelled")

    def test_stop_preserves_completed_file_and_marks_remaining_cancelled(self):
        self.scan(3);plan = self.preview();written,release = Event(),Event()
        from yingxu.operations import _move_without_overwrite
        def slow(item):
            _move_without_overwrite(item)
            if not written.is_set():written.set();release.wait(5)
        with patch("yingxu.operations._move_without_overwrite",side_effect=slow):
            reply = self.send("organize.confirmAndStart",self.consent(plan));wait_for(written.is_set)
            self.assertTrue(self.send("job.stop",{"jobId":reply["data"]["jobId"]})["ok"])
            release.set();wait_for(lambda:self.service.worker is None)
        record = self.service.record_page(self.service.last_result_id)
        self.assertEqual((record["success"],record["cancelled"]),(1,2))

    def test_export_is_exclusive_and_history_comes_from_real_records(self):
        self.scan(1);self.task("organize.confirmAndStart",self.consent(self.preview()))
        records = self.task("history.list",{"limit":30});self.assertEqual(len(records),1)
        identifier = records[0]["recordId"];path = self.root / "report.json"
        self.service.export_record(identifier,path);wait_for(lambda:self.service.worker is None)
        original = path.read_bytes();self.service.export_record(identifier,path);wait_for(lambda:self.service.worker is None)
        self.assertEqual(self.service.job["error"]["code"],"TARGET_EXISTS");self.assertEqual(path.read_bytes(),original)

    def test_collector_optional_cancellation_keeps_old_default_contract(self):
        self.scan(1)
        with self.assertRaises(ScanCancelled):collect_media(self.media,should_stop=lambda:True)
        self.assertEqual(len(collect_media(self.media)[0]),1)

    def test_option_changes_revoke_review_and_preview_without_file_changes(self):
        self.scan(1);plan = self.preview();data = self.service.data
        before = {path.name:path.read_bytes() for path in self.media.iterdir()}
        self.assertFalse(self.send("scan.configure",{"recursive":1,"move":False})["ok"])
        self.assertTrue(self.send("scan.configure",{"recursive":True,"move":False})["ok"])
        self.assertIs(self.service.data,data)
        self.assertTrue(self.send("scan.configure",{"recursive":False,"move":True})["ok"])
        self.assertIsNone(self.service.data)
        self.assertIsNone(self.service.snapshot)
        self.assertFalse(self.send("organize.confirmAndStart",self.consent(plan))["ok"])
        self.assertEqual(before,{path.name:path.read_bytes() for path in self.media.iterdir()})


if __name__ == '__main__':unittest.main()
