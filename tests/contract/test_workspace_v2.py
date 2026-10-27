"""Transport contracts, without Qt, Electron, network or media mutation."""
import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from yingxu.desktop.host import Host
from yingxu.desktop.messages import MAX_BYTES, dumps, fit_page, loads
from yingxu.domain.errors import ProtocolError

ROOT = Path(__file__).resolve().parents[2]


class WorkspaceV2Contracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='workspace-v2-', dir=ROOT / 'work/test-results')
        self.root = Path(self.temp.name)
        self.frames = []
        self.host = Host(self.root / 'profile', send=self.frames.append)
        self.sid = self.call('app.hello')['data']['sessionId']

    def tearDown(self):
        self.host.shutdown()
        while self.host.workspace.worker:
            self.host.loop.tick()
        self.host.close()
        self.temp.cleanup()

    def send(self, action, params=None, *, rid=None, sid=None):
        frame = {'v': 2, 'type': 'request', 'requestId': rid or uuid4().hex,
                 'sessionId': None if action == 'app.hello' else sid or self.sid,
                 'action': action, 'params': params or {}}
        self.host.receive(frame)
        return frame['requestId']

    def call(self, action, params=None, **options):
        rid = self.send(action, params, **options)
        return next(value for value in reversed(self.frames) if value.get('type') == 'reply' and value.get('requestId') == rid)

    def test_small_versioned_messages_reject_malformed_json(self):
        for raw in ('{"v":2,"v":2}', '{"v":2,"x":NaN}', '{"v":1}', '[]', 'x' * (MAX_BYTES+1)):
            with self.subTest(raw=raw[:50]), self.assertRaises(ProtocolError):
                loads(raw)
        state = self.call('app.state')
        self.assertEqual(state['v'], 2)
        self.assertTrue(state['data']['executionAvailable'])
        self.assertTrue(state['data']['downloadAvailable'])

    def test_duplicate_request_replays_without_consuming_new_state(self):
        rid = uuid4().hex
        first = self.call('scan.configure', {'recursive': False, 'move': False}, rid=rid)
        revision = self.host.workspace.revision
        self.assertEqual(self.call('scan.configure', {'recursive': False, 'move': False}, rid=rid), first)
        self.assertEqual(self.host.workspace.revision, revision)
        other = self.call('scan.configure', {'recursive': True, 'move': False}, rid=rid)
        self.assertEqual(other['error']['code'], 'REQUEST_ID_REUSED')
        self.assertEqual(self.call('scan.configure', {'recursive': False, 'move': False}, rid=rid), first)

    def test_refresh_and_late_native_callback_cannot_clear_new_pending_dialog(self):
        old_sid = self.sid
        old = self.send('folder.choose')
        self.host.receive({'v': 2, 'type': 'reset'})
        self.sid = self.call('app.hello')['data']['sessionId']
        current = self.send('folder.choose')
        self.host.receive({'v': 2, 'type': 'native.result', 'requestId': old,
                           'sessionId': old_sid, 'action': 'folder.choose', 'path': str(self.root)})
        self.assertTrue(self.host.workspace.native_busy)
        self.assertIn(current, self.host.pending)
        self.assertIsNone(self.host.workspace.folder)

    def test_no_raw_paths_commands_or_forged_completion_from_renderer(self):
        for action, params in [('folder.choose', {'path': str(self.root)}), ('os.system', {}),
                               ('browser.result', {}), ('online.start', {'taskId': 'x', 'query': 'x', 'provider': 'unknown'})]:
            with self.subTest(action=action):
                self.assertFalse(self.call(action, params)['ok'])
        denied = self.call('organize.confirmAndStart', {'scanId': 's', 'reviewRevision': 1,
            'snapshotId': 'snapshot', 'confirmationToken': 'token', 'acknowledged': True})
        self.assertEqual(denied['error']['code'], 'STALE_PLAN')

    def test_read_only_online_query_does_not_generate_a_refresh_feedback_loop(self):
        before = len([frame for frame in self.frames if frame.get('type') == 'event'])
        for _ in range(3):
            self.assertEqual(self.call('online.query')['data']['total'], 0)
        self.assertEqual(len([frame for frame in self.frames if frame.get('type') == 'event']), before)

    def test_online_language_preference_is_validated_and_persisted(self):
        self.assertTrue(self.call('online.configure', {'language': 'en'})['ok'])
        self.assertFalse(self.call('online.configure', {'language': 'unrecognized'})['ok'])
        self.assertEqual(self.call('online.query')['data']['language'], 'en')
        with self.assertRaises(ProtocolError) as caught:
            Host(self.root / 'profile', send=lambda frame: None)
        self.assertEqual(caught.exception.code, 'PROFILE_IN_USE')
        self.host.close()
        second = Host(self.root / 'profile', send=lambda frame: None)
        try:
            self.assertEqual(second.discovery.language, 'en')
        finally:
            second.close()

    def test_page_reduction_is_explicit_and_never_truncates_an_item(self):
        frame = {'v': 2, 'type': 'reply', 'data': {'rows': [{'name': '中文' * 150} for _ in range(30)],
                 'total': 30, 'offset': 0}, 'ok': True}
        page = fit_page(frame)
        self.assertLessEqual(len(dumps(page).encode('utf8')), MAX_BYTES)
        self.assertLess(len(page['data']['rows']), 30)
        self.assertEqual(page['data']['nextOffset'], len(page['data']['rows']))
        self.assertEqual(page['data']['rows'][0]['name'], '中文' * 150)
        frame['data']['rows'] = [{'name': '中' * MAX_BYTES}]
        with self.assertRaises(ProtocolError) as error:
            fit_page(frame)
        self.assertEqual(error.exception.code, 'ITEM_TOO_LARGE')

    def test_cancellation_keeps_partial_scan_out_of_the_workspace(self):
        (self.root / 'Example.mkv').write_bytes(b'unchanged')
        self.host.workspace.accept_folder(self.root)
        summary = self.host.workspace.summary()
        response = self.call('scan.start', {'folderId': summary['folderId'], 'recursive': False, 'move': False})
        self.call('scan.cancel', {'jobId': response['data']['jobId']})
        while self.host.workspace.worker:
            self.host.loop.tick()
        self.assertEqual(self.host.workspace.job['status'], 'cancelled')
        self.assertIsNone(self.host.workspace.data)
        self.assertEqual((self.root / 'Example.mkv').read_bytes(), b'unchanged')


if __name__ == '__main__':
    unittest.main()
