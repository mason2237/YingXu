"""Real Windows no-clobber moves, consent and compensating undo."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.operation_fixtures import approve, make_plan, media_snapshot, noop
from yingxu.adapters.sqlite_operation_journal import SQLiteOperationJournal
from yingxu.adapters.transaction_files import MoveSession
from yingxu.adapters.windows_files import WindowsFile
from yingxu.desktop.operation_runtime import build_execution
from yingxu.domain.errors import ProtocolError
from yingxu.domain.models import WorkflowError

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.name == 'nt', 'Windows handle semantics')
class FileExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='r3-files-', dir=ROOT / 'work/test-results')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.execution = build_execution(self.root / 'profile')
        self.addCleanup(self.execution.journal.close)

    def apply(self, identifier, **options):
        approve(self.execution, identifier)
        return self.execution.execute(identifier, options.get('stop', lambda: False), noop)

    def undo(self, identifier):
        undo = self.execution.prepare_undo(identifier, lambda: False, noop)
        approve(self.execution, undo, purpose='undo')
        self.execution.execute(undo, lambda: False, noop)
        return undo

    def test_preview_confirmation_and_duplicate_protection(self):
        identifier, items = make_plan(self.root, self.execution)
        item = items[0]
        before = media_snapshot(item.source.parent, item.target.parent)
        preview = self.execution.issue(identifier, 'page-1', 'execute')
        for acknowledged, session, code in [(False, 'page-1', 'CONFIRMATION_REQUIRED'), (True, 'page-2', 'STALE_PLAN')]:
            with self.subTest(code=code), self.assertRaises(ProtocolError) as caught:
                self.execution.claim(identifier, preview['snapshotId'], session, preview['confirmationToken'], acknowledged, purposes=('execute',))
            self.assertEqual(caught.exception.code, code)
        self.assertEqual(before, media_snapshot(item.source.parent, item.target.parent))
        self.execution.invalidate()
        with self.assertRaisesRegex(ProtocolError, '失效'):
            self.execution.claim(identifier, preview['snapshotId'], 'page-1', preview['confirmationToken'], True, purposes=('execute',))
        approve(self.execution, identifier)
        with self.assertRaises(ProtocolError) as caught:
            self.execution.claim(identifier, preview['snapshotId'], 'test-session', preview['confirmationToken'], True, purposes=('execute',))
        self.assertEqual(caught.exception.code, 'TOKEN_USED')
        self.execution.execute(identifier, lambda: False, noop)
        with self.assertRaises(ProtocolError):
            self.execution.execute(identifier, lambda: False, noop)
        self.assertEqual(self.execution.journal.run(identifier)['phase'], 'completed')

    def test_same_volume_preserves_identity_time_hardlinks_and_undo(self):
        identifier, items = make_plan(self.root, self.execution, count=2)
        versions = [self.execution.files.inspect(item.source) for item in items]
        link = self.root / 'existing-hard-link.srt'
        os.link(items[0].source, link)
        self.apply(identifier)
        for item, version in zip(items, versions):
            self.assertFalse(item.source.exists())
            self.assertEqual(self.execution.files.inspect(item.target), version)
            self.assertEqual(item.video.read_bytes(), b'video must remain unchanged')
        self.assertEqual(self.execution.files.inspect(link)['identity'], versions[0]['identity'])
        self.assertEqual(self.execution.record_meta(identifier)['success'], 2)
        undo = self.undo(identifier)
        self.assertEqual(self.execution.journal.run(undo)['phase'], 'completed')
        self.assertTrue(self.execution.record_meta(identifier)['undone'])
        for item, version in zip(items, versions):
            self.assertEqual(self.execution.files.inspect(item.source), version)
            self.assertFalse(item.target.exists())

    def test_conflict_after_preview_prevents_any_change(self):
        identifier, items = make_plan(self.root, self.execution, count=2)
        items[1].target.write_bytes(b'never overwrite')
        before = media_snapshot(items[0].source.parent, items[0].target.parent)
        self.apply(identifier)
        self.assertEqual(before, media_snapshot(items[0].source.parent, items[0].target.parent))
        self.assertEqual(self.execution.journal.run(identifier)['phase'], 'partial')

    def test_atomic_commit_race_and_partial_undo(self):
        identifier, items = make_plan(self.root, self.execution, count=3)
        def checkpoint(point, run_id, index):
            if point == 'before_commit' and index == 1:
                items[1].target.write_bytes(b'occupied during commit')
        self.execution.checkpoint = checkpoint
        self.apply(identifier)
        self.assertEqual(items[1].target.read_bytes(), b'occupied during commit')
        self.assertFalse(items[0].source.exists())
        self.assertTrue(items[1].source.exists())
        self.assertTrue(items[2].source.exists())
        self.assertFalse(items[2].target.exists())
        self.assertEqual(self.execution.record_meta(identifier)['success'], 1)
        self.execution.checkpoint = noop
        self.undo(identifier)
        self.assertTrue(items[0].source.exists())
        self.assertEqual(items[1].target.read_bytes(), b'occupied during commit')

    def test_stop_between_files_retains_completed_work_for_undo(self):
        identifier, items = make_plan(self.root, self.execution, count=3)
        stopped = []
        self.execution.checkpoint = lambda point, *args: stopped.append(True) if point == 'applied' else None
        self.apply(identifier, stop=lambda: bool(stopped))
        self.assertEqual(self.execution.journal.run(identifier)['phase'], 'cancelled')
        self.assertEqual(self.execution.record_meta(identifier)['success'], 1)
        self.assertTrue(all(item.source.exists() for item in items[1:]))
        self.execution.checkpoint = noop
        self.undo(identifier)
        self.assertTrue(all(item.source.exists() for item in items))

    def test_edited_target_same_size_and_mtime_blocks_undo(self):
        identifier, items = make_plan(self.root, self.execution)
        self.apply(identifier)
        target = items[0].target
        stamp = target.stat()
        target.write_bytes(b'X' * stamp.st_size)
        os.utime(target, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        undo = self.execution.prepare_undo(identifier, lambda: False, noop)
        self.assertFalse(self.execution.issue(undo, 'page', 'undo')['canExecute'])
        self.assertFalse(items[0].source.exists())
        self.assertEqual(target.read_bytes(), b'X' * stamp.st_size)

    def test_occupied_original_location_blocks_undo(self):
        identifier, items = make_plan(self.root, self.execution)
        self.apply(identifier)
        items[0].source.write_bytes(b'another file')
        undo = self.execution.prepare_undo(identifier, lambda: False, noop)
        self.assertFalse(self.execution.info(undo)['canExecute'])
        self.assertEqual(items[0].source.read_bytes(), b'another file')

    def test_locked_source_and_changed_directory_are_not_modified(self):
        identifier, items = make_plan(self.root, self.execution)
        with WindowsFile(items[0].source, delete=True):
            self.apply(identifier)
        self.assertTrue(items[0].source.exists())
        self.assertFalse(items[0].target.exists())
        original = items[0].target.parent
        original.rename(self.root / 'moved-folder')
        original.mkdir()
        self.execution.prepare_resume(identifier, lambda: False, noop)
        self.assertFalse(self.execution.info(identifier)['canExecute'])

    def test_actual_cross_volume_copy_then_undo(self):
        with tempfile.TemporaryDirectory(prefix='yingxu-r3-cross-') as destination:
            if Path(destination).stat().st_dev == self.root.stat().st_dev:
                self.skipTest('A second local volume is required')
            identifier, items = make_plan(self.root, self.execution, destination=destination, size=2*1024*1024+13)
            source_version = self.execution.files.inspect(items[0].source)
            original = MoveSession.remove_source
            attempts = []
            def check_guard(session):
                with self.assertRaises(PermissionError):
                    items[0].target.write_bytes(b'concurrent edit')
                attempts.append(True)
                original(session)
            with patch.object(MoveSession, 'remove_source', check_guard):
                self.apply(identifier)
            self.assertEqual(attempts, [True])
            self.assertEqual(self.execution.journal.run(identifier)['phase'], 'completed')
            self.assertFalse(items[0].source.exists())
            target_version = self.execution.files.inspect(items[0].target)
            self.assertNotEqual(source_version['volume'], target_version['volume'])
            self.assertEqual(source_version['digest'], target_version['digest'])
            self.assertEqual(source_version['modified'], target_version['modified'])
            self.undo(identifier)
            self.assertEqual(self.execution.files.inspect(items[0].source)['digest'], source_version['digest'])
            self.assertFalse(items[0].target.exists())

    def test_storage_failure_after_commit_is_reconciled_without_replay(self):
        identifier, items = make_plan(self.root, self.execution)
        approve(self.execution, identifier)
        original = self.execution.journal.update_item
        def fail(run_id, index, **changes):
            if changes.get('step') == 'applied':
                raise WorkflowError('STORAGE_FAILED', 'injected failure')
            return original(run_id, index, **changes)
        with patch.object(self.execution.journal, 'update_item', fail), self.assertRaises(WorkflowError):
            self.execution.execute(identifier, lambda: False, noop)
        before = media_snapshot(items[0].source.parent, items[0].target.parent)
        self.execution.journal.interrupt_running()
        self.execution.audit(lambda: False, noop)
        self.assertEqual(before, media_snapshot(items[0].source.parent, items[0].target.parent))
        self.assertEqual(self.execution.journal.run(identifier)['phase'], 'completed')

    def test_profile_lease_and_failed_initialization_release(self):
        with self.assertRaises(ProtocolError) as caught:
            build_execution(self.root / 'profile')
        self.assertEqual(caught.exception.code, 'PROFILE_IN_USE')
        broken = self.root / 'broken'
        broken.mkdir()
        (broken / 'buffers').write_bytes(b'not a directory')
        for _ in range(2):
            with self.assertRaises(WorkflowError) as caught:
                SQLiteOperationJournal(broken)
            self.assertEqual(caught.exception.code, 'STORAGE_FAILED')


if __name__ == '__main__':
    unittest.main()
