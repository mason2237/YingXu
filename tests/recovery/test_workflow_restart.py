"""Child-process exits prove metadata commit/rollback only, never media recovery."""
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from uuid import uuid4

from yingxu.adapters.sqlite_workflow_store import SQLiteWorkflowStore
from yingxu.application.subtitles import SubtitleWorkflow
from yingxu.domain.models import SubtitlePhase, WorkflowCommand, WorkflowError


ROOT = Path(__file__).resolve().parents[2]
CHILD = r'''
from dataclasses import replace
import json,os,sys
from yingxu.adapters.sqlite_workflow_store import SQLiteWorkflowStore
from yingxu.domain.models import WorkflowCommand
store=SQLiteWorkflowStore(sys.argv[1])
command=WorkflowCommand(**json.loads(sys.argv[2]))
if sys.argv[3]=='uncommitted':
    store._connection.create_function('exit_before_receipt',0,lambda:os._exit(72))
    store._connection.execute('CREATE TEMP TRIGGER crash_receipt BEFORE INSERT ON workflow_receipts BEGIN SELECT exit_before_receipt(); END')
store.apply(command,lambda task:replace(task,revision=task.revision+1))
os._exit(71)
'''


class WorkflowRestartTests(unittest.TestCase):
    def setUp(self):
        output = ROOT / "work/test-results"
        output.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="workflow-restart-", dir=output)
        self.path = Path(self.temp.name) / "tasks.sqlite3"
        self.store = SQLiteWorkflowStore(self.path)
        self.workflow = SubtitleWorkflow(self.store)
        self.task = self.workflow.create_task(uuid4().hex, 7)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def command(self, task, action="search", **extra):
        values = dict(command_id=uuid4().hex, task_id=task.task_id, action=action,
                      expected_revision=task.revision, workspace_id=task.workspace_id,
                      review_revision=task.review_revision)
        values.update(extra)
        return WorkflowCommand(**values)

    def restart(self):
        self.store.close()
        self.store = SQLiteWorkflowStore(self.path)
        self.workflow = SubtitleWorkflow(self.store)

    def child_exit(self, command, mode):
        self.store.close()
        completed = subprocess.run(
            [sys.executable, "-S", "-c", CHILD, str(self.path), json.dumps(asdict(command)), mode],
            cwd=ROOT, capture_output=True, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.assertEqual(completed.returncode, 72 if mode == "uncommitted" else 71,
                         completed.stderr.decode("utf8", errors="replace"))
        self.restart()

    def test_committed_state_and_receipt_survive_exit_without_close(self):
        command = self.command(self.task)
        self.child_exit(command, "committed")
        current = self.store.get(self.task.task_id)
        self.assertEqual(current.revision, 1)
        def forbidden(_task):
            self.fail("A persisted command must not execute twice after restart")
        receipt = self.store.apply(command, forbidden)
        self.assertTrue(receipt.duplicate)
        self.assertEqual(receipt.task.revision, 1)

    def test_exit_between_task_write_and_receipt_commit_restores_previous_state(self):
        command = self.command(self.task)
        self.child_exit(command, "uncommitted")
        self.assertEqual(self.store.get(self.task.task_id).revision, 0)
        # A rolled-back command is not mistaken for a committed receipt.
        from dataclasses import replace
        receipt = self.store.apply(command, lambda task: replace(task, revision=task.revision + 1))
        self.assertFalse(receipt.duplicate)
        self.assertEqual(receipt.task.revision, 1)

    def test_old_effect_cannot_complete_a_new_search_after_restart(self):
        searching = self.workflow.dispatch(self.command(self.task)).task
        old_effect = searching.active_effect_id
        interrupted = self.workflow.dispatch(self.command(
            searching, "interrupt", effect_id=old_effect)).task
        self.assertEqual(interrupted.phase, SubtitlePhase.INTERRUPTED)
        new_search = self.workflow.dispatch(self.command(interrupted)).task
        self.assertNotEqual(old_effect, new_search.active_effect_id)
        self.restart()
        candidates = {"candidates": [{"candidate_id": uuid4().hex,
                                       "provider_id": "fake", "title": "Synthetic subtitle"}]}
        old_callback = self.command(new_search, "results", params_json=json.dumps(candidates),
                                    effect_id=old_effect)
        with self.assertRaises(WorkflowError) as caught:
            self.workflow.dispatch(old_callback)
        self.assertEqual(caught.exception.code, "STALE_EFFECT")
        self.assertEqual(self.store.get(self.task.task_id), new_search)
        accepted = self.workflow.dispatch(self.command(
            new_search, "results", params_json=json.dumps(candidates),
            effect_id=new_search.active_effect_id)).task
        self.assertEqual(accepted.phase, SubtitlePhase.CANDIDATES_READY)


if __name__ == "__main__":
    unittest.main()
