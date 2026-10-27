"""Renderer-boundary contracts; no Qt, process host or real network required."""
import json
import unittest

from yingxu.desktop.protocol import MAX_MESSAGE_BYTES, decode_command, encode_error, encode_receipt
from yingxu.domain.models import CommandReceipt, SubtitlePhase, SubtitleTask, WorkflowError


def message(**patch):
    value = {"v": 2, "id": "request-1", "taskId": "task-1", "action": "search",
             "expectedRevision": 0, "workspaceId": "workspace-1", "reviewRevision": 7,
             "params": {"query": "映序", "provider_id": "zimuku"}}
    value.update(patch)
    return json.dumps(value, ensure_ascii=False)


class DesktopProtocolContracts(unittest.TestCase):
    def assert_error(self, raw, code="INVALID_REQUEST"):
        with self.assertRaises(WorkflowError) as caught:
            decode_command(raw)
        self.assertEqual(caught.exception.code, code)

    def test_unicode_command_and_canonical_params(self):
        command = decode_command(message())
        self.assertEqual((command.command_id, command.task_id, command.workspace_id), ("request-1", "task-1", "workspace-1"))
        self.assertEqual(command.review_revision, 7)
        self.assertEqual(command.params, {"query": "映序", "provider_id": "zimuku"})
        self.assertEqual(command.params_json, '{"provider_id":"zimuku","query":"映序"}')
        self.assertIsNone(command.effect_id)
        value = json.loads(message());value.pop("params")
        self.assertEqual(decode_command(json.dumps(value)).params, {})

    def test_utf8_size_limit_is_bytes_not_character_count(self):
        raw = message(params={"query": "影" * 200})
        exact = raw + " " * (MAX_MESSAGE_BYTES - len(raw.encode("utf-8")))
        self.assertLess(len(exact), MAX_MESSAGE_BYTES)
        self.assertEqual(len(exact.encode("utf-8")), MAX_MESSAGE_BYTES)
        self.assertEqual(decode_command(exact).params["query"], "影" * 200)
        self.assert_error(exact + " ")

    def test_old_protocol_is_not_silently_accepted(self):
        self.assert_error(message(v=1), "PROTOCOL_MISMATCH")
        for version in (True, 2.0, "2"):
            self.assert_error(message(v=version), "PROTOCOL_MISMATCH")

    def test_only_public_user_commands_are_decoded(self):
        for action in ("results", "needs_user", "downloaded", "verified", "prepared", "fail", "interrupt",
                       "os.system", "file.rename", "organize.confirmAndStart"):
            with self.subTest(action=action):
                self.assert_error(message(action=action, params={}), "ACTION_UNAVAILABLE")
        for action in ("resume", "cancel", "retry"):
            self.assertEqual(decode_command(message(action=action, params={})).action, action)
        self.assertEqual(decode_command(message(action="select", params={"candidate_id": "candidate-1"})).params["candidate_id"], "candidate-1")
        self.assertFalse(decode_command(message(action="confirm_download", params={"acknowledged": False})).params["acknowledged"])

    def test_renderer_cannot_forge_effects_or_path_arguments(self):
        self.assert_error(message(effectId="effect-1"))
        self.assert_error(message(params={"path": "C:/Windows/example.srt"}))
        self.assert_error(message(action="select", params={"candidate_id": "../file"}))
        self.assert_error(message(action="cancel", params={"command": "anything"}))
        self.assertIsNone(decode_command(message(effectId=None)).effect_id)

    def test_field_shapes_identifiers_and_revisions(self):
        self.assert_error(message(extra="unexpected"))
        value = json.loads(message());value.pop("taskId")
        self.assert_error(json.dumps(value))
        for field in ("id", "taskId", "workspaceId"):
            for invalid in ("", "a" * 65, "含中文", "path/name", 3, None):
                with self.subTest(field=field, invalid=invalid):
                    self.assert_error(message(**{field: invalid}))
        for field in ("expectedRevision", "reviewRevision"):
            for invalid in (True, -1, 1.0, "1", None, 2**31, 2**53):
                with self.subTest(field=field, invalid=invalid):
                    self.assert_error(message(**{field: invalid}))
        for params in (None, [], "query", 1, {"query": " "}, {"query": "x" * 201}, {"provider_id": 1}):
            self.assert_error(message(params=params))
        for params in ({}, {"acknowledged": 1}, {"acknowledged": True, "path": "file"}):
            self.assert_error(message(action="confirm_download", params=params))

    def test_invalid_json_duplicate_fields_nonfinite_and_top_level(self):
        for raw in (None, b"{}", "", "{", "null", "[]", "3", "true", "\ud800"):
            with self.subTest(raw=repr(raw)):
                self.assert_error(raw)
        raw = message()
        self.assert_error(raw[:-1] + ',"v":2}')
        self.assert_error(message(params={"query": "valid"}).replace('"query": "valid"', '"query":"first","query":"second"'))
        for number in ("NaN", "Infinity", "-Infinity", "1e10000"):
            self.assert_error(raw.replace('"expectedRevision": 0', '"expectedRevision": ' + number))
        self.assert_error(raw.replace('"query": "映序"', '"query": "\\ud800"'))

    def test_fixed_reply_schema_and_duplicate_receipt(self):
        task = SubtitleTask(task_id="task-1", workspace_id="workspace-1", review_revision=7,
                            revision=0, phase=SubtitlePhase("queued"))
        receipt = json.loads(encode_receipt("request-1", CommandReceipt(task, duplicate=True)))
        self.assertEqual(set(receipt), {"v", "id", "ok", "data", "error"})
        self.assertEqual(receipt, {"v": 2, "id": "request-1", "ok": True, "error": None,
                                  "data": {"task": {"task_id": "task-1", "workspace_id": "workspace-1",
                                                    "review_revision": 7, "revision": 0, "phase": "queued",
                                                    "active_effect_id": None}, "duplicate": True}})
        error = json.loads(encode_error(None, WorkflowError("NOT_READY", "请先选择字幕。")))
        self.assertEqual(error, {"v": 2, "id": None, "ok": False, "data": None,
                                "error": {"code": "NOT_READY", "message": "请先选择字幕。"}})

    def test_large_persistent_payload_is_not_sent_to_renderer(self):
        payload = json.dumps({"candidates": [{"title": "影" * 100}] * 20, "file_bytes": "x" * 20000}, ensure_ascii=False)
        self.assertGreater(len(payload.encode("utf-8")), MAX_MESSAGE_BYTES)
        task = SubtitleTask(task_id="task-1", workspace_id="workspace-1", review_revision=7,
                            revision=3, phase=SubtitlePhase("candidates_ready"), data_json=payload)
        raw = encode_receipt("request-1", CommandReceipt(task))
        self.assertLess(len(raw.encode("utf-8")), 1024)
        self.assertNotIn("data_json", raw)
        self.assertNotIn("candidates\"", raw)
        self.assertNotIn("file_bytes", raw)
        self.assertEqual(json.loads(raw)["data"]["task"]["phase"], "candidates_ready")

    def test_error_message_is_short_and_every_reply_is_bounded(self):
        raw = encode_error("request-1", WorkflowError("FAILED", "失" * 20000))
        self.assertLessEqual(len(raw.encode("utf-8")), MAX_MESSAGE_BYTES)
        self.assertEqual(json.loads(raw)["error"]["message"], "失" * 200)
        with self.assertRaises(WorkflowError) as caught:
            encode_error("request-1", WorkflowError("x" * MAX_MESSAGE_BYTES, "失败"))
        self.assertEqual(caught.exception.code, "MESSAGE_TOO_LARGE")


if __name__ == "__main__":
    unittest.main()
