"""Startup marks unknown effects interrupted; it never resumes a website itself."""
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from yingxu.desktop.host import Host
from yingxu.domain.models import SubtitlePhase, WorkflowCommand, WorkflowError
from yingxu.adapters.sqlite_workflow_store import SQLiteWorkflowStore

ROOT = Path(__file__).resolve().parents[2]


class StartupRecoveryTests(unittest.TestCase):
    def test_committed_but_unstarted_effect_is_not_replayed(self):
        with tempfile.TemporaryDirectory(prefix='noqt-restart-', dir=ROOT / 'work/test-results') as directory:
            profile = Path(directory)
            first = Host(profile, send=lambda frame: None)
            task = first.workflow.create_task('workspace', 3)
            task = first.workflow.dispatch(WorkflowCommand(uuid4().hex, task.task_id, 'search', 0, 'workspace', 3)).task
            first.close()
            frames = []
            second = Host(profile, send=frames.append)
            try:
                saved = second.workflow.get_task(task.task_id)
                self.assertEqual(saved.phase, SubtitlePhase.INTERRUPTED)
                self.assertIsNone(saved.active_effect_id)
                self.assertEqual(second.recovered, 1)
                self.assertFalse(any(frame.get('type') == 'browser.search' for frame in frames))
            finally:
                second.close()

    def test_corrupt_storage_has_a_stable_error_and_is_not_rewritten(self):
        with tempfile.TemporaryDirectory(prefix='noqt-corrupt-', dir=ROOT / 'work/test-results') as directory:
            path = Path(directory) / 'tasks.sqlite3'
            payload = b'not a sqlite database'
            path.write_bytes(payload)
            with self.assertRaises(WorkflowError) as caught:
                SQLiteWorkflowStore(path)
            self.assertEqual(caught.exception.code, 'CORRUPT_STORAGE')
            self.assertEqual(path.read_bytes(), payload)


if __name__ == '__main__':
    unittest.main()
