"""Consent lifetime, IPC validation, and failures after a durable claim."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from tests.operation_fixtures import make_plan, media_snapshot, noop
from yingxu.desktop.host import Host
from yingxu.desktop.workspace_protocol import decode
from yingxu.domain.errors import ProtocolError

ROOT = Path(__file__).resolve().parents[2]


class OperationConsentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='r3-consent-', dir=ROOT / 'work/test-results')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.host = Host(self.root / 'profile', send=lambda value: None)
        self.addCleanup(self.host.close)
        self.execution = self.host.execution
        self.identifier, self.items = make_plan(self.root, self.execution)
        self.workspace = self.host.workspace
        self.workspace.session_id = 'page-1'

    def preview(self):
        self.workspace.snapshot = self.identifier
        info = self.execution.issue(self.identifier, 'page-1', 'resume')
        return {'runId': self.identifier, 'snapshotId': info['snapshotId'],
                'confirmationToken': info['confirmationToken'], 'acknowledged': True}

    def test_refresh_expires_old_consent_without_touching_files(self):
        params = self.preview()
        before = media_snapshot(self.items[0].source.parent, self.items[0].target.parent)
        self.workspace.new_page('page-2')
        with self.assertRaises(ProtocolError) as caught:
            self.workspace.start_operation(params, 'page-1')
        self.assertEqual(caught.exception.code, 'STALE_PLAN')
        self.assertEqual(before, media_snapshot(self.items[0].source.parent, self.items[0].target.parent))

    def test_post_claim_adapter_failure_leaves_a_recoverable_run(self):
        params = self.preview()
        with patch.object(self.workspace, 'invalidate_online', side_effect=RuntimeError('adapter unavailable')):
            with self.assertRaisesRegex(RuntimeError, 'adapter unavailable'):
                self.workspace.start_operation(params, 'page-1')
        self.assertIsNone(self.workspace.worker)
        self.assertEqual(self.execution.journal.run(self.identifier)['phase'], 'interrupted')
        self.assertTrue(self.items[0].source.exists())
        self.assertFalse(self.items[0].target.exists())

    def test_worker_submission_failure_never_replays_consent(self):
        params = self.preview()
        with patch.object(self.workspace.tasks, 'start', side_effect=RuntimeError('cannot start worker')):
            with self.assertRaisesRegex(RuntimeError, 'cannot start worker'):
                self.workspace.start_operation(params, 'page-1')
        self.assertEqual(self.execution.journal.run(self.identifier)['phase'], 'interrupted')
        with self.assertRaises(ProtocolError):
            self.workspace.start_operation(params, 'page-1')
        self.assertTrue(self.items[0].source.exists())

    def test_new_actions_reject_paths_and_non_boolean_confirmation(self):
        import json
        for action, params in [('operation.confirm', {**self.preview(), 'acknowledged': 1}),
                               ('operation.cache', {'path': 'C:\\Windows'}),
                               ('operation.resumePreview', {'runId': self.identifier, 'command': 'del *'}),
                               ('operation.query', {'runId': self.identifier, 'snapshotId': uuid4().hex, 'limit': 201})]:
            with self.subTest(action=action), self.assertRaises(ProtocolError):
                decode(json.dumps({'v': 2, 'requestId': uuid4().hex, 'sessionId': 'page-1', 'action': action, 'params': params}))

    def test_failed_host_initialization_releases_profile_lock(self):
        profile = self.root / 'bad-startup'
        with patch('yingxu.desktop.host.JSONSettings', side_effect=RuntimeError('settings failed')):
            with self.assertRaisesRegex(RuntimeError, 'settings failed'):
                Host(profile)
        second = Host(profile, send=lambda value: None)
        second.close()

    def test_fixed_intent_cannot_be_mutated_and_digest_is_verified(self):
        with self.assertRaises(ProtocolError):
            self.execution.journal.update_item(self.identifier, 0, spec={'target': 'bad'})
        connection = self.execution.journal.connection
        connection.execute('UPDATE items SET spec_hash=? WHERE run_id=?', ('invalid', self.identifier))
        with self.assertRaises(ProtocolError) as caught:
            self.execution.journal.bundle(self.identifier)
        self.assertEqual(caught.exception.code, 'CORRUPT_JOURNAL')

    def test_old_recovery_is_not_hidden_by_newer_history(self):
        journal = self.execution.journal
        info = self.execution.issue(self.identifier, 'page-1', 'execute')
        self.execution.claim(self.identifier, info['snapshotId'], 'page-1', info['confirmationToken'], True, purposes=('execute',))
        journal.interrupt_running()
        # Synthetic metadata records exercise list ordering, not file execution.
        specs = [item['spec'] for item in journal.bundle(self.identifier)[1]]
        for _ in range(31):
            identifier = journal.create(specs, {})
            token = journal.issue_ticket(identifier, 'history-test', 'execute', {})
            journal.claim(identifier, 'history-test', token, acknowledged=True)
            journal.update_run(identifier, phase='completed')
        started = self.workspace.dispatch('history.list', {'limit': 30}, 'page-1')
        while self.workspace.worker:
            self.host.loop.tick()
        records = self.workspace.results[started['jobId']]
        self.assertEqual(len(records), 30)
        self.assertEqual(records[0]['recordId'], self.identifier)
        self.assertTrue(records[0]['needsRecovery'])
        self.assertTrue(self.items[0].source.exists())
        self.assertFalse(self.items[0].target.exists())


if __name__ == '__main__':
    unittest.main()
