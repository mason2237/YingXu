"""Workflow behavior through a tiny storage double, not SQLite or a GUI."""
import json
import unittest
from uuid import uuid4

from yingxu.application.subtitles import SubtitleWorkflow
from yingxu.domain.models import CommandReceipt, SubtitlePhase as Phase, SubtitleTask, WorkflowCommand, WorkflowError


class MemoryStore:
    def __init__(self):self.tasks = {}
    def create(self, task):self.tasks[task.task_id] = task;return task
    def get(self, task_id):return self.tasks[task_id]
    def apply(self, command, evolve):
        task = evolve(self.get(command.task_id))
        self.tasks[task.task_id] = task
        return CommandReceipt(task)
    def close(self):pass


class SubtitleWorkflowRules(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore();self.workflow = SubtitleWorkflow(self.store)
        self.task = self.workflow.create_task('workspace', 3)

    def command(self, action, params=None, *, internal=False, **patch):
        values = dict(command_id=uuid4().hex, task_id=self.task.task_id, action=action,
                      expected_revision=self.task.revision, workspace_id=self.task.workspace_id,
                      review_revision=self.task.review_revision, params_json=json.dumps(params or {}),
                      effect_id=self.task.active_effect_id if internal else None)
        values.update(patch);return WorkflowCommand(**values)

    def send(self, action, params=None, **options):
        self.task = self.workflow.dispatch(self.command(action, params, **options)).task
        return self.task

    def reject(self, code, action, params=None, **options):
        before = self.task
        with self.assertRaises(WorkflowError) as caught:
            self.workflow.dispatch(self.command(action, params, **options))
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(self.store.get(before.task_id), before)

    def candidates(self):
        self.send('search', {'query': 'Example', 'provider_id': 'fake'})
        self.send('results', {'candidates': [{'candidate_id': 'c1', 'provider_id': 'fake',
                                             'title': 'Example subtitles'}]}, internal=True)

    def downloading(self):
        self.candidates();self.send('select', {'candidate_id': 'c1'})
        self.send('confirm_download', {'acknowledged': True})

    def test_selection_consent_and_validation_are_separate_steps(self):
        self.candidates()
        self.reject('CANDIDATE_NOT_FOUND', 'select', {'candidate_id': 'foreign'})
        self.send('select', {'candidate_id': 'c1'})
        self.reject('CONFIRMATION_REQUIRED', 'confirm_download', {'acknowledged': False})
        self.send('confirm_download', {'acknowledged': True})
        self.assertEqual(self.task.phase, Phase.DOWNLOADING)
        self.send('downloaded', {'artifact_id': 'a1'}, internal=True)
        self.assertEqual(self.task.phase, Phase.VERIFYING)
        self.reject('INVALID_TRANSITION', 'prepared', {'artifact_id': 'a1'}, internal=True)
        self.send('verified', {'artifact_id': 'a1'}, internal=True)
        self.assertEqual(self.task.phase, Phase.PREPARING)
        self.send('prepared', {'artifact_id': 'a1'}, internal=True)
        self.assertEqual(self.task.phase, Phase.REVIEW_READY)
        self.assertIsNone(self.task.active_effect_id)

    def test_manual_verification_resumes_with_a_new_effect_identity(self):
        self.send('search');old_effect = self.task.active_effect_id
        self.send('needs_user', {'reason': 'Complete website verification'}, internal=True)
        self.assertEqual(self.task.phase, Phase.AWAITING_USER)
        self.send('resume')
        self.assertNotEqual(self.task.active_effect_id, old_effect)
        self.assertNotIn('reason', self.task.data)
        self.reject('STALE_EFFECT', 'results', {'candidates': []}, effect_id=old_effect)

    def test_empty_result_failure_and_retry_are_explicit(self):
        self.send('search');self.send('results', {'candidates': []}, internal=True)
        self.assertEqual(self.task.phase, Phase.NO_RESULTS)
        self.send('retry');self.assertEqual(self.task.phase, Phase.QUEUED)
        self.send('search');self.send('fail', {'reason': 'Provider unavailable'}, internal=True)
        self.assertEqual(self.task.phase, Phase.FAILED)
        self.send('retry');self.assertEqual(self.task.phase, Phase.QUEUED)

    def test_cancelled_task_rejects_late_adapter_results(self):
        self.send('search');old_effect = self.task.active_effect_id
        self.send('cancel');self.assertEqual(self.task.phase, Phase.CANCELLED)
        self.reject('STALE_EFFECT', 'results', {'candidates': []}, effect_id=old_effect)
        self.reject('INVALID_TRANSITION', 'search')

    def test_review_context_and_task_revision_are_independent_guards(self):
        self.reject('CONTEXT_MISMATCH', 'search', workspace_id='another')
        self.reject('CONTEXT_MISMATCH', 'search', review_revision=2)
        self.reject('REVISION_CONFLICT', 'search', expected_revision=2)
        self.reject('INVALID_PARAMS', 'search', effect_id='invented')
        self.reject('ACTION_UNAVAILABLE', 'shell')

    def test_validation_cannot_silently_switch_artifact(self):
        self.downloading();self.send('downloaded', {'artifact_id': 'a1'}, internal=True)
        self.reject('ARTIFACT_MISMATCH', 'verified', {'artifact_id': 'another'}, internal=True)

    def test_saved_snapshots_cannot_be_mutated_by_ui_or_caller(self):
        self.candidates()
        value = self.task.data;value['candidates'].clear()
        self.assertEqual(len(self.task.data['candidates']), 1)
        self.send('select', {'candidate_id': 'c1'})
        self.reject('INVALID_PARAMS', 'confirm_download', {'acknowledged': 1})
        with self.assertRaises(WorkflowError):
            self.command('search', {'query': float('nan')})

    def test_active_identity_cannot_be_missing_or_left_on_idle_snapshot(self):
        for phase, effect in ((Phase.SEARCHING, None), (Phase.DOWNLOADING, None),
                              (Phase.VERIFYING, None), (Phase.PREPARING, None),
                              (Phase.QUEUED, 'old-effect'), (Phase.CANCELLED, 'old-effect')):
            with self.subTest(phase=phase), self.assertRaises(WorkflowError):
                SubtitleTask('task', 'workspace', 0, 0, phase, effect)

    def test_transition_has_no_random_effect_or_io_dependency(self):
        command = self.command('search', {'query': 'Example'})
        first = self.workflow._evolve(self.task, command)
        second = self.workflow._evolve(self.task, command)
        self.assertEqual(first, second)
        self.assertEqual(first.active_effect_id, command.command_id)
        self.assertEqual(self.workflow.get_task(self.task.task_id), self.task)


if __name__ == '__main__':unittest.main()
