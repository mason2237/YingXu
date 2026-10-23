"""Stage 5 boundary tests, run explicitly in .venv-web; no user files involved."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QUrl

from yingxu.web_ui.bridge import FoundationBridge
from yingxu.web_ui.protocol import ProtocolError, decode_request, encode_reply
from yingxu.web_ui.resources import ASSETS, LocalOnlyRequests, frontend_root, resource_key
from yingxu.web_ui.workers import inspect_sample


def request(action="app.hello", rid="request-1", sid=None, params=None, **extra):
    return json.dumps({"v": 1, "requestId": rid, "sessionId": sid, "action": action,
                       "params": {} if params is None else params, **extra})


class ProtocolTests(unittest.TestCase):
    def test_rejects_malformed_and_oversized_messages(self):
        for raw in ("[1,2]", "{", "null", "x" * 8193):
            with self.subTest(raw=raw[:15]), self.assertRaises(ProtocolError):
                decode_request(raw)

    def test_rejects_unknown_or_file_mutation_actions(self):
        for action in ("organize.confirmAndStart", "os.system", "file.write", "__dict__"):
            with self.subTest(action=action), self.assertRaises(ProtocolError) as caught:
                decode_request(request(action))
            self.assertEqual(caught.exception.code, "ACTION_UNAVAILABLE")

    def test_requires_strict_version_identifier_and_parameters(self):
        cases = [request(v=True), request(rid="../bad"), request(path="C:/secret"),
                 request(params={"path": "C:/secret"}), request(params=[]),
                 request("app.ping", params={"message": "x" * 513}),
                 request("app.ping", params={"message": 3})]
        for raw in cases:
            with self.subTest(raw=raw[:70]), self.assertRaises(ProtocolError):
                decode_request(raw)

    def test_unicode_and_markup_remain_plain_data(self):
        message = "中文 & <img src=x> 😀"
        parsed = decode_request(request("app.ping", params={"message": message}))
        result = json.loads(encode_reply(parsed.request_id, {"message": parsed.params["message"]}))
        self.assertEqual(result["data"]["message"], message)
        self.assertIsNone(result["error"])


class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.bridge = FoundationBridge()
        self.replies = []
        self.bridge.reply.connect(lambda raw: self.replies.append(json.loads(raw)))

    def send(self, *args, **kwargs):
        self.bridge.request(request(*args, **kwargs))
        return self.replies[-1]

    def hello(self):
        return self.send()["data"]["sessionId"]

    def test_only_request_slot_is_published_on_bridge(self):
        meta = self.bridge.metaObject()
        signatures = [bytes(meta.method(i).methodSignature()).decode()
                      for i in range(meta.methodOffset(), meta.methodCount())]
        self.assertEqual(set(signatures), {"request(QString)", "reply(QString)", "event(QString)"})

    def test_session_is_required_and_reload_invalidates_old_session(self):
        self.assertEqual(self.send("app.state")["error"]["code"], "STALE_SESSION")
        sid = self.hello()
        self.assertTrue(self.send("app.ping", rid="ping", sid=sid, params={"message": "你好"})["ok"])
        self.bridge.reset_page()
        self.assertEqual(self.send("app.state", rid="old", sid=sid)["error"]["code"], "STALE_SESSION")
        self.assertNotEqual(self.hello(), sid)

    def test_duplicate_request_cannot_start_a_second_task(self):
        sid = self.hello()
        with patch.object(self.bridge.service, "start_sample", return_value={"jobId": "job"}) as start:
            first = self.send("diagnostics.runSample", rid="sample", sid=sid)
            second = self.send("diagnostics.runSample", rid="sample", sid=sid)
            self.assertEqual(first, second)
            self.assertEqual(start.call_count, 1)
            conflict = self.send("app.state", rid="sample", sid=sid)
            self.assertEqual(conflict["error"]["code"], "REQUEST_ID_REUSED")

    def test_busy_and_closing_reject_new_work(self):
        sid = self.hello()
        self.bridge.service.worker = object()
        response = self.send("diagnostics.runSample", rid="busy", sid=sid)
        self.assertEqual(response["error"]["code"], "BUSY")
        self.bridge.service.worker = None
        self.bridge.closing = True
        response = self.send("app.ping", rid="closing", sid=sid, params={"message": "test"})
        self.assertEqual(response["error"]["code"], "CLOSING")


class ResourceTests(unittest.TestCase):
    def test_static_allowlist_has_real_files_and_no_filesystem_escape(self):
        for key in ASSETS:
            self.assertEqual(resource_key(QUrl("yingxu://app" + key)), key)
            if not key.startswith("/qt/"):
                self.assertTrue((frontend_root() / key.lstrip("/")).is_file())
        for url in ("https://example.com/", "file:///C:/Windows/win.ini", "yingxu://other/index.html",
                    "yingxu://app:99/index.html", "yingxu://user@app/index.html",
                    "yingxu://app/index.html?path=C:/secret", "yingxu://app/../../secret",
                    "yingxu://app/%252e%252e/secret", "yingxu://app/js/%5csecret"):
            with self.subTest(url=url):
                self.assertIsNone(resource_key(QUrl(url)))

    def test_interceptor_blocks_remote_and_unregistered_resources(self):
        class Info:
            blocked = False
            def __init__(self, url): self.url = QUrl(url)
            def requestUrl(self): return self.url
            def block(self, value): self.blocked = value
        interceptor = LocalOnlyRequests()
        for url, expected in (("https://example.com/script.js", True),
                              ("yingxu://app/operations.py", True),
                              ("yingxu://app/js/app.js", False)):
            info = Info(url)
            interceptor.interceptRequest(info)
            self.assertEqual(info.blocked, expected)


class ExistingCoreTests(unittest.TestCase):
    def test_real_core_sample_reports_three_targets_without_mutation(self):
        phases = []
        result = inspect_sample(lambda phase, text: phases.append(phase))
        self.assertEqual(phases, ["scanning", "matching"])
        self.assertEqual((result["videoCount"], result["subtitleCount"]), (2, 3))
        self.assertEqual(sum(len(row["subtitles"]) for row in result["rows"]), 3)
        self.assertTrue(result["unchanged"])
        self.assertFalse(result["executionAvailable"])
        targets = [sub["targetName"] for row in result["rows"] for sub in row["subtitles"]]
        self.assertIn("示例剧.S01E01.chs.srt", targets)
        self.assertIn("示例剧.S01E01.eng.srt", targets)


if __name__ == "__main__":
    unittest.main()
