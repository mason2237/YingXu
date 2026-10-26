"""Shared protocol and production resource boundaries; no user files involved."""
import json
from pathlib import Path
import unittest

from PySide6.QtCore import QUrl

from yingxu.web_ui.protocol import ProtocolError, decode_request, encode_reply
from yingxu.web_ui.resources import ASSETS, LocalOnlyRequests, frontend_root, resource_key


def request(action="app.hello", rid="request-1", sid=None, params=None, **extra):
    return json.dumps({"v": 1, "requestId": rid, "sessionId": sid, "action": action,
                       "params": {} if params is None else params, **extra})


class ProtocolTests(unittest.TestCase):
    def test_rejects_malformed_and_oversized_messages(self):
        for raw in ("[1,2]", "{", "null", "x" * 8193):
            with self.subTest(raw=raw[:15]), self.assertRaises(ProtocolError):
                decode_request(raw)

    def test_rejects_unknown_or_file_mutation_actions(self):
        for action in ("organize.confirmAndStart", "os.system", "file.write", "__dict__", "diagnostics.runSample"):
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
                              ("yingxu://app/js/workspace.js", False)):
            info = Info(url)
            interceptor.interceptRequest(info)
            self.assertEqual(info.blocked, expected)


if __name__ == "__main__":
    unittest.main()
