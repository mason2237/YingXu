"""Own subtitle task decisions independently of windows, IPC and network I/O.

This prototype records intent and accepts results from trusted application
adapters. It does not itself search, download, validate files or rename media.
Renderer commands must enter through the restricted desktop protocol adapter.
"""
from dataclasses import replace
from uuid import uuid4

from ..domain.models import (ACTIVE_PHASES, CommandReceipt, SubtitlePhase, SubtitleTask,
                             WorkflowCommand, WorkflowError, canonical_json, identifier)
from ..ports.workflow_store import WorkflowStore


PUBLIC_ACTIONS = frozenset({'search', 'resume', 'select', 'capture_page', 'confirm_download', 'resume_download', 'cancel', 'retry'})
INTERNAL_ACTIONS = frozenset({'results', 'manual_result', 'needs_user', 'downloaded', 'verified', 'prepared', 'fail', 'interrupt'})
TERMINAL_PHASES = frozenset({SubtitlePhase.REVIEW_READY, SubtitlePhase.CANCELLED})


def _shape(params: dict, required=(), optional=()):
    if set(required) - params.keys() or params.keys() - set(required) - set(optional):
        raise WorkflowError('INVALID_PARAMS', '操作参数缺失或包含未支持的字段。')


def _text(value, name, limit=500):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise WorkflowError('INVALID_PARAMS', f'{name} 应为非空、长度受限的文本。')
    return value


def _phase(task, *allowed):
    if task.phase not in allowed:
        raise WorkflowError('INVALID_TRANSITION', '当前任务状态不接受此操作。')


def validate_user_params(action: str, params: dict):
    """Shape validation shared by direct callers and the renderer boundary."""
    if action == 'search':
        _shape(params, optional=('query', 'provider_id'))
        if 'query' in params:_text(params['query'], 'query', 200)
        if 'provider_id' in params:identifier(params['provider_id'], 'provider_id')
    elif action == 'select':
        _shape(params, required=('candidate_id',));identifier(params['candidate_id'], 'candidate_id')
    elif action in {'confirm_download', 'resume_download'}:
        _shape(params, required=('acknowledged',))
        if type(params['acknowledged']) is not bool:
            raise WorkflowError('INVALID_PARAMS', '下载确认应为布尔值。')
    elif action in {'resume', 'cancel', 'retry', 'capture_page'}:_shape(params)
    else:raise WorkflowError('ACTION_UNAVAILABLE', '此入口不提供该操作。')


def _candidates(params):
    _shape(params, required=('candidates',))
    values = params['candidates']
    if not isinstance(values, list) or len(values) > 50:
        raise WorkflowError('INVALID_PARAMS', '一次结果最多包含 50 个候选。')
    seen = set()
    for value in values:
        if not isinstance(value, dict):raise WorkflowError('INVALID_PARAMS', '候选必须是对象。')
        _shape(value, required=('candidate_id', 'provider_id', 'title'), optional=('language', 'release'))
        identifier(value['candidate_id'], 'candidate_id');identifier(value['provider_id'], 'provider_id')
        _text(value['title'], 'title')
        for key in ('language', 'release'):
            if key in value and (not isinstance(value[key], str) or len(value[key]) > 200):
                raise WorkflowError('INVALID_PARAMS', '候选描述超出限制。')
        if value['candidate_id'] in seen:raise WorkflowError('INVALID_PARAMS', '候选标识不能重复。')
        seen.add(value['candidate_id'])
    return values


class SubtitleWorkflow:
    """One authority for each task; storage provides atomic revision/idempotency."""
    def __init__(self, store: WorkflowStore):
        self.store = store

    def create_task(self, workspace_id: str, review_revision: int,
                    task_id: str | None = None) -> SubtitleTask:
        return self.store.create(SubtitleTask(task_id or uuid4().hex, workspace_id,
                                review_revision, 0, SubtitlePhase.QUEUED))

    def dispatch(self, command: WorkflowCommand) -> CommandReceipt:
        if command.action not in PUBLIC_ACTIONS | INTERNAL_ACTIONS:
            raise WorkflowError('ACTION_UNAVAILABLE', '此入口不提供该操作。')
        return self.store.apply(command, lambda task: self._evolve(task, command))

    def get_task(self, task_id: str) -> SubtitleTask:
        return self.store.get(identifier(task_id, 'task_id'))

    def recover_inflight(self, tasks):
        """Mark unknown external effects interrupted; never replay them at startup."""
        count = 0
        for task in tasks:
            if task.phase in ACTIVE_PHASES:
                self.dispatch(WorkflowCommand(uuid4().hex, task.task_id, 'interrupt', task.revision,
                    task.workspace_id, task.review_revision,
                    canonical_json({'reason': '应用上次退出时任务尚未结束；未自动重新执行。'}), task.active_effect_id))
                count += 1
        return count

    @staticmethod
    def _evolve(task: SubtitleTask, command: WorkflowCommand) -> SubtitleTask:
        action, params, data = command.action, command.params, task.data
        if command.expected_revision != task.revision:
            raise WorkflowError('REVISION_CONFLICT', '任务版本已变化。')
        if (command.workspace_id, command.review_revision) != (task.workspace_id, task.review_revision):
            raise WorkflowError('CONTEXT_MISMATCH', '任务不属于此工作区审阅版本。')
        if action in PUBLIC_ACTIONS:
            if command.effect_id is not None:
                raise WorkflowError('INVALID_PARAMS', '用户操作不能伪造适配器结果。')
            validate_user_params(action, params)
        elif not task.active_effect_id or command.effect_id != task.active_effect_id:
            raise WorkflowError('STALE_EFFECT', '结果不属于本次活动操作。')

        def next_state(phase, *, active=False):
            return replace(task, phase=phase, revision=task.revision + 1,
                           # The transition is deterministic. This is correlation,
                           # not an authorization token for untrusted renderers.
                           active_effect_id=command.command_id if active else None,
                           data_json=canonical_json(data))

        if action == 'search':
            _phase(task, SubtitlePhase.QUEUED, SubtitlePhase.NO_RESULTS,
                   SubtitlePhase.FAILED, SubtitlePhase.INTERRUPTED,
                   SubtitlePhase.AWAITING_USER, SubtitlePhase.CANDIDATES_READY, SubtitlePhase.SELECTED)
            # Preserve artifact references until a future explicit retention/GC policy.
            data.pop('candidates', None);data.pop('selected_candidate_id', None)
            data.pop('reason', None);data.pop('interrupted_from', None)
            data.update(params)
            return next_state(SubtitlePhase.SEARCHING, active=True)
        if action == 'resume':
            _phase(task, SubtitlePhase.AWAITING_USER)
            data.pop('reason', None)
            return next_state(SubtitlePhase.SEARCHING, active=True)
        if action == 'results':
            _phase(task, SubtitlePhase.SEARCHING)
            data['candidates'] = _candidates(params)
            return next_state(SubtitlePhase.CANDIDATES_READY if data['candidates'] else SubtitlePhase.NO_RESULTS)
        if action == 'needs_user':
            _phase(task, SubtitlePhase.SEARCHING);_shape(params, required=('reason',))
            data['reason'] = _text(params['reason'], 'reason')
            return next_state(SubtitlePhase.AWAITING_USER)
        if action == 'select':
            _phase(task, SubtitlePhase.CANDIDATES_READY, SubtitlePhase.SELECTED)
            if params['candidate_id'] not in {item['candidate_id'] for item in data.get('candidates', [])}:
                raise WorkflowError('CANDIDATE_NOT_FOUND', '候选不属于本次搜索结果。')
            data['selected_candidate_id'] = params['candidate_id']
            data.pop('reason', None)
            return next_state(SubtitlePhase.SELECTED)
        if action == 'capture_page':
            _phase(task, SubtitlePhase.AWAITING_USER, SubtitlePhase.NO_RESULTS, SubtitlePhase.CANDIDATES_READY, SubtitlePhase.SELECTED)
            return next_state(SubtitlePhase.CAPTURING, active=True)
        if action == 'manual_result':
            _phase(task, SubtitlePhase.CAPTURING)
            candidates = _candidates(params)
            if len(candidates) != 1:
                raise WorkflowError('INVALID_PARAMS', '手动页面必须指定一份候选。')
            data['candidates'] = candidates
            data['selected_candidate_id'] = candidates[0]['candidate_id']
            data.pop('reason', None)
            return next_state(SubtitlePhase.SELECTED)
        if action == 'confirm_download':
            _phase(task, SubtitlePhase.SELECTED)
            if not params['acknowledged']:
                raise WorkflowError('CONFIRMATION_REQUIRED', '确认选择后才能开始下载。')
            return next_state(SubtitlePhase.DOWNLOADING, active=True)
        if action == 'resume_download':
            _phase(task, SubtitlePhase.INTERRUPTED, SubtitlePhase.FAILED, SubtitlePhase.CANCELLED)
            if not params['acknowledged'] or not data.get('selected_candidate_id'):
                raise WorkflowError('CONFIRMATION_REQUIRED', '请先确认已选下载再重试。')
            data.pop('reason', None)
            return next_state(SubtitlePhase.DOWNLOADING, active=True)
        if action == 'downloaded':
            _phase(task, SubtitlePhase.DOWNLOADING);_shape(params, required=('artifact_id',))
            data['artifact_id'] = identifier(params['artifact_id'], 'artifact_id')
            # A completed transfer is not accepted as verified subtitle content.
            return next_state(SubtitlePhase.VERIFYING, active=True)
        if action == 'verified':
            _phase(task, SubtitlePhase.VERIFYING);_shape(params, required=('artifact_id',))
            if params['artifact_id'] != data.get('artifact_id'):
                raise WorkflowError('ARTIFACT_MISMATCH', '校验结果不属于本次下载。')
            return next_state(SubtitlePhase.PREPARING, active=True)
        if action == 'prepared':
            _phase(task, SubtitlePhase.PREPARING);_shape(params, required=('artifact_id',))
            if params['artifact_id'] != data.get('artifact_id'):
                raise WorkflowError('ARTIFACT_MISMATCH', '准备结果不属于本次下载。')
            return next_state(SubtitlePhase.REVIEW_READY)
        if action in {'fail', 'interrupt'}:
            _phase(task, *ACTIVE_PHASES)
            _shape(params, optional=('reason',))
            if 'reason' in params:data['reason'] = _text(params['reason'], 'reason')
            data['interrupted_from'] = task.phase.value
            return next_state(SubtitlePhase.FAILED if action == 'fail' else SubtitlePhase.INTERRUPTED)
        if action == 'cancel':
            if task.phase in TERMINAL_PHASES:
                raise WorkflowError('INVALID_TRANSITION', '此任务已结束。')
            return next_state(SubtitlePhase.CANCELLED)
        if action == 'retry':
            _phase(task, SubtitlePhase.FAILED, SubtitlePhase.NO_RESULTS, SubtitlePhase.INTERRUPTED)
            # Starting again is not HTTP resume. No byte ranges are joined here.
            data.pop('candidates', None);data.pop('selected_candidate_id', None)
            return next_state(SubtitlePhase.QUEUED)
        raise WorkflowError('ACTION_UNAVAILABLE', '此入口不提供该操作。')
