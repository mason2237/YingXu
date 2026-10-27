"""Process-death fault matrix; deliberately not a power-loss certification."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests.operation_fixtures import approve, make_plan, media_snapshot, noop
from yingxu.adapters.transaction_files import MoveSession
from yingxu.desktop.operation_runtime import build_execution
from yingxu.domain.errors import ProtocolError

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.name == 'nt', 'Windows real filesystem recovery')
class FileRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='r3-crash-', dir=ROOT / 'work/test-results')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.executions = []
        self.addCleanup(lambda: [value.journal.close() for value in self.executions])

    def open(self, root):
        execution = build_execution(root / 'profile')
        self.executions.append(execution)
        return execution

    def crash(self, root, identifier, point):
        result = subprocess.run([sys.executable, '-S', '-m', 'tests.operation_worker', str(root / 'profile'), identifier, point],
            cwd=ROOT, capture_output=True, text=True, encoding='utf8', timeout=20,
            env={**os.environ, 'PYTHONUTF8': '1'}, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 97, result.stdout + result.stderr)

    def prepare_crash(self, root, point, *, destination=None):
        root.mkdir()
        execution = self.open(root)
        identifier, items = make_plan(root, execution, destination=destination, size=2*1024*1024+13)
        expected = items[0].source.read_bytes()
        execution.journal.close()
        self.crash(root, identifier, point)
        return identifier, items, expected

    def recover(self, root, identifier, items, expected):
        execution = self.open(root)  # Also proves the OS lease is released by process death.
        self.assertEqual(execution.journal.run(identifier)['phase'], 'interrupted')
        before = media_snapshot(items[0].source.parent, items[0].target.parent)
        execution.audit(lambda: False, noop)
        self.assertEqual(before, media_snapshot(items[0].source.parent, items[0].target.parent))
        if execution.journal.run(identifier)['phase'] != 'completed':
            execution.prepare_resume(identifier, lambda: False, noop)
            self.assertTrue(execution.info(identifier)['canExecute'])
            approve(execution, identifier, purpose='resume', session='fresh-page')
            execution.execute(identifier, lambda: False, noop)
        self.assertEqual(execution.journal.run(identifier)['phase'], 'completed')
        self.assertEqual(items[0].target.read_bytes(), expected)
        self.assertFalse(items[0].source.exists())
        self.assertEqual(items[0].video.read_bytes(), b'video must remain unchanged')
        return execution

    def test_same_volume_crash_matrix(self):
        points = ('confirmed', 'buffer_created', 'buffer_chunk', 'buffer_written', 'buffered', 'before_commit', 'target_committed', 'applied')
        for point in points:
            with self.subTest(point=point):
                root = self.root / point
                identifier, items, expected = self.prepare_crash(root, point)
                self.recover(root, identifier, items, expected).journal.close()

    def test_resume_preview_alone_can_reconcile_an_already_finished_move(self):
        root = self.root / 'finished-without-audit'
        identifier, items, _ = self.prepare_crash(root, 'target_committed')
        execution = self.open(root)
        before = media_snapshot(items[0].source.parent, items[0].target.parent)
        execution.prepare_resume(identifier, lambda: False, noop)
        self.assertEqual(execution.journal.run(identifier)['phase'], 'completed')
        info = execution.issue(identifier, 'new-page', 'resume')
        self.assertEqual(info['remainingCount'], 0)
        self.assertEqual(info['completedCount'], 1)
        self.assertFalse(info['canExecute'])
        self.assertIsNone(info['confirmationToken'])
        self.assertEqual(before, media_snapshot(items[0].source.parent, items[0].target.parent))

    def test_actual_cross_volume_crash_matrix(self):
        with tempfile.TemporaryDirectory(prefix='yingxu-r3-crashes-') as destination:
            if Path(destination).stat().st_dev == self.root.stat().st_dev:
                self.skipTest('A second local volume is required')
            for point in ('buffer_chunk', 'temp_created', 'temp_chunk', 'temp_written', 'staged', 'before_commit',
                          'target_committed', 'committed', 'source_removed', 'applied'):
                with self.subTest(point=point):
                    folder = Path(destination) / point
                    folder.mkdir()
                    root = self.root / point
                    identifier, items, expected = self.prepare_crash(root, point, destination=folder)
                    execution = self.recover(root, identifier, items, expected)
                    # Partial owned staging files remain referenced; no unknown files are removed.
                    item = execution.journal.item(identifier, 0)
                    if point == 'temp_chunk':
                        self.assertTrue(any(Path(ref['path']).exists() for ref in item['retained']))
                    execution.journal.close()

    def test_unknown_same_content_target_is_not_adopted(self):
        root = self.root / 'unknown-target'
        identifier, items, expected = self.prepare_crash(root, 'before_commit')
        items[0].target.write_bytes(expected)
        execution = self.open(root)
        before = media_snapshot(items[0].source.parent, items[0].target.parent)
        execution.audit(lambda: False, noop)
        execution.prepare_resume(identifier, lambda: False, noop)
        self.assertFalse(execution.info(identifier)['canExecute'])
        self.assertEqual(before, media_snapshot(items[0].source.parent, items[0].target.parent))

    def test_cleanup_rechecks_and_holds_target_before_deleting_source(self):
        with tempfile.TemporaryDirectory(prefix='yingxu-r3-cleanup-') as destination:
            if Path(destination).stat().st_dev == self.root.stat().st_dev:
                self.skipTest('A second local volume is required')
            root = self.root / 'cleanup'
            identifier, items, expected = self.prepare_crash(root, 'committed', destination=destination)
            execution = self.open(root)
            execution.prepare_resume(identifier, lambda: False, noop)
            approve(execution, identifier, purpose='resume')
            original = MoveSession.remove_source
            attempts = []
            def check_guard(session):
                with self.assertRaises(PermissionError):
                    items[0].target.write_bytes(b'concurrent edit')
                attempts.append(True)
                original(session)
            with patch.object(MoveSession, 'remove_source', check_guard):
                execution.execute(identifier, lambda: False, noop)
            self.assertEqual(attempts, [True])
            self.assertFalse(items[0].source.exists())
            self.assertEqual(items[0].target.read_bytes(), expected)

    def test_changed_source_or_committed_target_blocks_recovery(self):
        for point, field in [('buffered', 'source'), ('target_committed', 'target')]:
            with self.subTest(point=point):
                root = self.root / point
                identifier, items, _ = self.prepare_crash(root, point)
                path = getattr(items[0], field)
                stamp = path.stat()
                path.write_bytes(b'X' * stamp.st_size)
                os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
                execution = self.open(root)
                before = media_snapshot(items[0].source.parent, items[0].target.parent)
                execution.audit(lambda: False, noop)
                execution.prepare_resume(identifier, lambda: False, noop)
                self.assertFalse(execution.info(identifier)['canExecute'])
                self.assertEqual(before, media_snapshot(items[0].source.parent, items[0].target.parent))
                execution.journal.close()

    def test_buffer_only_restore_requires_a_new_explicit_preview(self):
        root = self.root / 'buffer-only'
        identifier, items, expected = self.prepare_crash(root, 'buffer_written')
        items[0].source.unlink()
        execution = self.open(root)
        execution.audit(lambda: False, noop)
        self.assertFalse(items[0].target.exists())
        execution.prepare_resume(identifier, lambda: False, noop)
        page = execution.page(identifier)
        self.assertIn('备份恢复', page['items'][0]['message'])
        approve(execution, identifier, purpose='resume')
        execution.execute(identifier, lambda: False, noop)
        self.assertEqual(items[0].target.read_bytes(), expected)
        self.assertEqual(execution.journal.run(identifier)['phase'], 'completed')

    def test_missing_source_after_consent_cannot_silently_restore(self):
        root = self.root / 'post-consent-missing'
        identifier, items, _ = self.prepare_crash(root, 'buffered')
        execution = self.open(root)
        execution.prepare_resume(identifier, lambda: False, noop)
        approve(execution, identifier, purpose='resume')
        items[0].source.unlink()
        execution.execute(identifier, lambda: False, noop)
        self.assertFalse(items[0].target.exists())
        self.assertEqual(execution.journal.run(identifier)['phase'], 'partial')

    def test_corrupt_buffer_never_replaces_a_missing_source(self):
        root = self.root / 'bad-buffer'
        identifier, items, _ = self.prepare_crash(root, 'buffered')
        execution = self.open(root)
        buffer = Path(execution.journal.item(identifier, 0)['buffer'])
        buffer.write_bytes(b'bad')
        items[0].source.unlink()
        execution.prepare_resume(identifier, lambda: False, noop)
        self.assertFalse(execution.info(identifier)['canExecute'])
        self.assertFalse(items[0].target.exists())
        self.assertEqual(buffer.read_bytes(), b'bad')

    def test_interrupted_undo_uses_its_own_run_and_does_not_repeat(self):
        root = self.root / 'undo'
        root.mkdir()
        execution = self.open(root)
        identifier, items = make_plan(root, execution)
        expected = items[0].source.read_bytes()
        approve(execution, identifier)
        execution.execute(identifier, lambda: False, noop)
        undo = execution.prepare_undo(identifier, lambda: False, noop)
        execution.journal.close()
        self.crash(root, undo, 'target_committed')
        execution = self.open(root)
        before = media_snapshot(items[0].source.parent, items[0].target.parent)
        execution.audit(lambda: False, noop)
        self.assertEqual(before, media_snapshot(items[0].source.parent, items[0].target.parent))
        self.assertEqual(execution.journal.run(undo)['phase'], 'completed')
        self.assertEqual(items[0].source.read_bytes(), expected)
        self.assertFalse(items[0].target.exists())
        self.assertTrue(execution.record_meta(identifier)['undone'])
        with self.assertRaises(ProtocolError):
            execution.prepare_undo(identifier, lambda: False, noop)


if __name__ == '__main__':
    unittest.main()
