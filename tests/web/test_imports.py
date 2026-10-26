"""Native imports feed the existing reviewed, one-use-confirmation executor."""
import json
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4
import zipfile

from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QTest
from yingxu.operations import HistoryStore
from yingxu.web_ui.workspace_bridge import WorkspaceBridge
from yingxu.web_ui.protocol import ProtocolError

ROOT = Path(__file__).resolve().parents[2]
SRT = b"1\n00:00:01,000 --> 00:00:02,000\nSubtitle\n"


class ImportContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="import-",dir=ROOT/"work/test-results")
        self.root = Path(self.temp.name)
        self.media = self.root/"中文 视频";self.media.mkdir()
        self.video = self.media/"Example.S01E01.1080p.mkv";self.video.write_bytes(b"video")
        self.inbox = self.root/"inbox";self.inbox.mkdir()
        self.bridge = WorkspaceBridge(history=HistoryStore(self.root/"history.jsonl"))
        self.service = self.bridge.service
        self.replies = []
        self.bridge.reply.connect(lambda raw:self.replies.append(json.loads(raw)))
        self.send("app.hello")
        self.service.accept_folder(self.media)
        self.job("scan.start",{"folderId":self.service.folder_id,"recursive":True,"move":False})

    def tearDown(self):
        self.wait()
        self.temp.cleanup()

    def wait(self):
        for _ in range(1200):
            if self.service.worker is None: return
            QTest.qWait(5)
        self.fail("worker timeout")

    def send(self, action, params=None):
        self.bridge.request(json.dumps({"v":1,"requestId":uuid4().hex,"sessionId":self.bridge.session_id,
                                       "action":action,"params":params or {}}))
        return self.replies[-1]

    def context(self, **extra):
        return {"scanId":self.service.data.scan_id,"revision":self.service.revision,**extra}

    def job(self, action, params):
        reply = self.send(action,params);self.assertTrue(reply["ok"],reply)
        self.wait();self.assertEqual(self.service.job["status"],"completed",self.service.job)
        return self.service.job["result"]

    def stage(self, names=("Example.chs.srt",)):
        key = uuid4().hex
        directory = self.inbox/key;directory.mkdir()
        path = directory/(names[0] if len(names) == 1 else "subtitles.zip")
        if len(names) == 1: path.write_bytes(SRT)
        else:
            with zipfile.ZipFile(path,"w") as archive:
                for name in names: archive.writestr(name,SRT)
        self.service.register_download({"stagingId":key,"stagingPath":str(path),"status":"subtitle_candidate",
                                        **self.context(rowId="video-1")},self.inbox)
        return key,path

    def import_files(self, *ids):
        self.service.import_downloads(list(ids),self.context())
        self.wait();self.assertEqual(self.service.job["status"],"completed",self.service.job)
        return self.service.job["result"]

    def confirm_preview(self):
        self.job("review.confirm",self.context(rowId="video-1"))
        return self.job("preview.create",self.context())

    @staticmethod
    def consent(plan):
        return {"scanId":plan["scanId"],"reviewRevision":plan["revision"],"snapshotId":plan["snapshotId"],
                "confirmationToken":plan["confirmationToken"],"acknowledged":True}

    def test_import_requires_review_confirmation_then_moves_copy_beside_video(self):
        key,original = self.stage()
        before = {p.name:p.read_bytes() for p in self.media.iterdir()}
        result = self.import_files(key)
        self.assertEqual(result["assigned"],1)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.media.iterdir()})
        row = self.service.data.rows[0]
        self.assertEqual(row["state"],"需确认")
        self.assertEqual(Path(row["subtitles"][0]["targetPath"]).parent,self.media)
        pending = self.job("preview.create",self.context())
        self.assertFalse(pending["canExecute"])
        plan = self.confirm_preview()
        params = self.consent(plan)
        self.assertFalse(self.send("organize.confirmAndStart",{**params,"acknowledged":False})["ok"])
        self.job("organize.confirmAndStart",params)
        self.assertEqual((self.media/(self.video.stem+".chs.srt")).read_bytes(),SRT)
        self.assertEqual(original.read_bytes(),SRT)
        self.assertEqual(self.video.read_bytes(),b"video")
        self.assertEqual(len(self.service.history.recent()),1)
        self.assertEqual(self.send("organize.confirmAndStart",params)["error"]["code"],"TOKEN_USED")

    def test_multi_file_package_is_inventory_until_manual_choice(self):
        key,_ = self.stage(("Example.eng.srt","Example.chs.srt"))
        result = self.import_files(key)
        self.assertEqual((result["imported"],result["assigned"]),(2,0))
        data = self.service.data
        self.assertFalse(data.review.rows[0].matches)
        choices = data.candidates(0)["rows"]
        self.assertTrue(all(row["imported"] for row in choices))
        self.assertEqual([row["name"] for row in choices],["Example.chs.srt","Example.eng.srt"])
        self.job("review.assign",self.context(rowId="video-1",subtitleId=choices[0]["subtitleId"]))
        self.assertEqual(self.service.data.rows[0]["state"],"需确认")
        self.assertEqual(self.service.data.review.rows[0].matches[0].target.parent,self.media)

    def test_repeat_unknown_ids_stale_scan_and_web_path_actions_rejected(self):
        key,_ = self.stage();self.import_files(key)
        for ids in ([key], ["unknown"], [key,key]):
            with self.assertRaises((ProtocolError,ValueError)):self.service.import_downloads(ids,self.context())
        with self.assertRaises(ProtocolError):
            self.service.import_downloads([key],{**self.context(),"scanId":"old"})
        self.assertFalse(self.send("subtitle.import",{"path":str(self.inbox)})["ok"])

    def test_import_invalidates_old_preview_and_refresh_does_not_repeat(self):
        old = self.job("preview.create",self.context())
        key,_ = self.stage();result = self.import_files(key)
        self.assertIsNone(self.service.snapshot)
        self.assertFalse(self.send("organize.confirmAndStart",self.consent(old))["ok"])
        self.bridge.reset_page();self.send("app.hello")
        self.assertEqual(len(self.service.data.review.imported),result["imported"])
        self.assertEqual(list(self.media.glob("*.srt")),[])

    def test_local_move_false_and_existing_matches_are_preserved(self):
        folder = self.media/"local";folder.mkdir()
        local = folder/"Example.S01E01.chs.srt";local.write_bytes(SRT)
        self.job("scan.start",{"folderId":self.service.folder_id,"recursive":True,"move":False})
        old = self.service.data.review.rows[0].matches[0]
        key,_ = self.stage();result = self.import_files(key)
        self.assertEqual(result["assigned"],0)
        match = self.service.data.review.rows[0].matches[0]
        self.assertEqual((match.source,match.target),(old.source,old.target))
        self.assertEqual(match.target.parent,folder)

    def test_changed_download_is_reported_without_partial_match(self):
        key,path = self.stage();path.write_bytes(SRT+b"changed")
        result = self.import_files(key)
        self.assertEqual(result["imported"],0)
        self.assertTrue(result["outcomes"][0]["error"])
        self.assertFalse(self.service.data.review.rows[0].matches)

    def test_changed_prepared_subtitle_cannot_get_new_preview(self):
        key,_ = self.stage();self.import_files(key)
        self.job("review.confirm",self.context(rowId="video-1"))
        path = self.service.data.review.rows[0].matches[0].source
        path.write_bytes(SRT+b"tampered")
        self.send("preview.create",self.context());self.wait()
        self.assertEqual(self.service.job["error"]["code"],"STALE_PLAN")

    def test_target_conflict_blocks_without_overwrite_and_retains_cache(self):
        key,_ = self.stage();self.import_files(key);plan = self.confirm_preview()
        item = self.service.snapshot.changes[0]
        item.target.write_bytes(b"existing")
        self.job("organize.confirmAndStart",self.consent(plan))
        self.assertEqual(item.target.read_bytes(),b"existing")
        self.assertTrue(item.source.exists())
        self.assertEqual(self.service.record_page(self.service.last_result_id)["errors"],1)


if __name__ == "__main__":unittest.main()
