"""SQLite metadata port contracts, using only disposable workspace databases."""
from dataclasses import replace
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
from threading import Barrier, Thread
import unittest
from uuid import uuid4

from yingxu.adapters.sqlite_workflow_store import SQLiteWorkflowStore
from yingxu.domain.models import SubtitlePhase, SubtitleTask, WorkflowCommand, WorkflowError


ROOT = Path(__file__).resolve().parents[2]


class WorkflowStoreContracts(unittest.TestCase):
    def setUp(self):
        output = ROOT / "work/test-results"
        output.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="workflow-store-", dir=output)
        self.path = Path(self.temp.name) / "tasks.sqlite3"
        self.store = SQLiteWorkflowStore(self.path)
        self.task = SubtitleTask(task_id=uuid4().hex, workspace_id=uuid4().hex,
                                 review_revision=7, revision=0, phase=SubtitlePhase.QUEUED)
        self.store.create(self.task)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def command(self, **changes):
        values = dict(command_id=uuid4().hex, task_id=self.task.task_id, action="search",
                      expected_revision=0, workspace_id=self.task.workspace_id, review_revision=7)
        values.update(changes)
        return WorkflowCommand(**values)

    @staticmethod
    def advance(task):
        return replace(task, revision=task.revision + 1)

    def assert_code(self, code, call):
        with self.assertRaises(WorkflowError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def test_create_get_and_reopen(self):
        self.assertEqual(self.store.get(self.task.task_id), self.task)
        self.store.close()
        self.store = SQLiteWorkflowStore(self.path)
        self.assertEqual(self.store.get(self.task.task_id).to_dict(), self.task.to_dict())
        self.assert_code("ALREADY_EXISTS", lambda: self.store.create(self.task))
        self.assert_code("NOT_FOUND", lambda: self.store.get(uuid4().hex))

    def test_locked_storage_reports_busy_without_reinitializing(self):
        other = SQLiteWorkflowStore(self.path)
        other._connection.execute('PRAGMA busy_timeout=10')
        self.store._connection.execute('BEGIN IMMEDIATE')
        try:
            self.assert_code('STORAGE_BUSY', lambda: other.create(replace(self.task, task_id=uuid4().hex)))
        finally:
            self.store._connection.rollback()
            other.close()
        self.assertEqual(self.store.get(self.task.task_id), self.task)

    def test_replay_returns_original_receipt_even_after_later_commands_and_restart(self):
        first = self.command()
        result = self.store.apply(first, self.advance)
        self.assertFalse(result.duplicate)
        self.store.apply(self.command(expected_revision=1), self.advance)
        self.store.close()
        self.store = SQLiteWorkflowStore(self.path)
        def must_not_run(_task):
            self.fail("An idempotent replay must not run the transition again")
        replay = self.store.apply(first, must_not_run)
        self.assertTrue(replay.duplicate)
        self.assertEqual(replay.task.revision, 1)
        self.assertEqual(replay.task, result.task)
        self.assertEqual(self.store.get(self.task.task_id).revision, 2)

    def test_reused_command_id_with_different_content_is_rejected(self):
        command = self.command(params_json='{"query":"Original"}')
        self.store.apply(command, self.advance)
        changed = replace(command, params_json='{"query":"Different"}')
        self.assert_code("COMMAND_ID_REUSED", lambda: self.store.apply(changed, self.advance))
        self.assertEqual(self.store.get(self.task.task_id).revision, 1)

    def test_expected_revision_and_review_context_are_checked(self):
        self.store.apply(self.command(), self.advance)
        self.assert_code("REVISION_CONFLICT", lambda: self.store.apply(self.command(), self.advance))
        wrong = self.command(expected_revision=1, review_revision=8)
        self.assert_code("CONTEXT_MISMATCH", lambda: self.store.apply(wrong, self.advance))
        self.assertEqual(self.store.get(self.task.task_id).revision, 1)

    def test_transition_failure_does_not_persist_task_or_receipt(self):
        command = self.command()
        def reject(_task):
            raise WorkflowError("INVALID_TRANSITION", "Test failure before commit")
        self.assert_code("INVALID_TRANSITION", lambda: self.store.apply(command, reject))
        self.assertEqual(self.store.get(self.task.task_id).revision, 0)
        result = self.store.apply(command, self.advance)
        self.assertFalse(result.duplicate)
        self.assertEqual(result.task.revision, 1)

    def test_adapter_rejects_incorrect_revision_or_identity_from_evolve(self):
        self.assert_code("INVALID_TRANSITION", lambda: self.store.apply(self.command(), lambda task: task))
        self.assert_code("CONTEXT_MISMATCH", lambda: self.store.apply(
            self.command(), lambda task: replace(task, task_id=uuid4().hex, revision=task.revision + 1)))
        self.assertEqual(self.store.get(self.task.task_id).revision, 0)

    def test_independent_connections_compare_and_swap_one_winner(self):
        other = SQLiteWorkflowStore(self.path)
        barrier = Barrier(2)
        results = []
        def writer(store, command):
            try:
                barrier.wait(timeout=5)
                result = store.apply(command, self.advance)
                results.append(("ok", result.task.revision))
            except WorkflowError as error:
                results.append(("error", error.code))
            except BaseException as error:
                results.append(("unexpected", repr(error)))
        threads = [Thread(target=writer, args=(self.store, self.command())),
                   Thread(target=writer, args=(other, self.command()))]
        try:
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)
                self.assertFalse(thread.is_alive(), "Concurrent store operation did not finish")
            self.assertCountEqual(results, [("ok", 1), ("error", "REVISION_CONFLICT")])
            self.assertEqual(self.store.get(self.task.task_id).revision, 1)
            self.assertEqual(other.get(self.task.task_id).revision, 1)
        finally:
            other.close()

    def test_unknown_schema_is_refused_without_rewriting_version(self):
        path = Path(self.temp.name) / "future.sqlite3"
        with closing(sqlite3.connect(path)) as raw:
            raw.execute("PRAGMA user_version=99")
            raw.commit()
        self.assert_code("UNSUPPORTED_SCHEMA", lambda: SQLiteWorkflowStore(path))
        with closing(sqlite3.connect(path)) as raw:
            self.assertEqual(raw.execute("PRAGMA user_version").fetchone()[0], 99)

    def test_unversioned_unrelated_database_is_not_adopted(self):
        path = Path(self.temp.name) / "unrelated.sqlite3"
        with closing(sqlite3.connect(path)) as raw:
            raw.execute("CREATE TABLE unrelated(value TEXT)")
            raw.execute("INSERT INTO unrelated VALUES ('keep')")
            raw.commit()
        self.assert_code("UNSUPPORTED_SCHEMA", lambda: SQLiteWorkflowStore(path))
        with closing(sqlite3.connect(path)) as raw:
            self.assertEqual(raw.execute("SELECT value FROM unrelated").fetchone()[0], "keep")
            self.assertEqual(raw.execute("PRAGMA user_version").fetchone()[0], 0)

    def test_close_is_idempotent_and_prevents_future_operations(self):
        self.store.close()
        self.store.close()
        self.assert_code("STORE_CLOSED", lambda: self.store.get(self.task.task_id))


if __name__ == "__main__":
    unittest.main()
