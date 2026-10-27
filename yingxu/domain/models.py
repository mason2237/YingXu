"""Immutable workflow messages and snapshots; JSON is a serialization boundary."""
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from typing import Mapping

IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


class WorkflowError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise WorkflowError('INVALID_PARAMS', f'{name} must be a bounded identifier')
    return value


def revision_number(value: int, name: str) -> int:
    if type(value) is not int or not 0 <= value < 2**31:
        raise WorkflowError('INVALID_PARAMS', f'{name} must be a nonnegative integer')
    return value


def canonical_json(value: dict) -> str:
    if not isinstance(value, dict):
        raise WorkflowError('INVALID_PARAMS', 'JSON payload must be an object')
    try:
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
        if len(raw.encode('utf8')) > 65536:
            raise ValueError('payload exceeds 64 KiB')
        return raw
    except (ValueError, TypeError, RecursionError, UnicodeError) as error:
        raise WorkflowError('INVALID_PARAMS', 'Payload is not bounded JSON') from error


def json_object(raw: str) -> dict:
    if not isinstance(raw, str):
        raise WorkflowError('INVALID_PARAMS', 'JSON payload must be a string')
    try:
        if len(raw.encode('utf8')) > 65536:
            raise ValueError('payload exceeds 64 KiB')
        value = json.loads(raw)
    except (ValueError, RecursionError, UnicodeError) as error:
        raise WorkflowError('INVALID_PARAMS', 'Invalid JSON payload') from error
    canonical_json(value)
    return value


class SubtitlePhase(str, Enum):
    QUEUED = 'queued'
    SEARCHING = 'searching'
    AWAITING_USER = 'awaiting_user'
    CANDIDATES_READY = 'candidates_ready'
    SELECTED = 'selected'
    CAPTURING = 'capturing'
    DOWNLOADING = 'downloading'
    VERIFYING = 'verifying'
    PREPARING = 'preparing'
    REVIEW_READY = 'review_ready'
    NO_RESULTS = 'no_results'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    INTERRUPTED = 'interrupted'


ACTIVE_PHASES = frozenset({
    SubtitlePhase.SEARCHING, SubtitlePhase.CAPTURING, SubtitlePhase.DOWNLOADING,
    SubtitlePhase.VERIFYING, SubtitlePhase.PREPARING,
})


@dataclass(frozen=True)
class SubtitleTask:
    task_id: str
    workspace_id: str
    review_revision: int
    revision: int
    phase: SubtitlePhase
    active_effect_id: str | None = None
    data_json: str = '{}'

    def __post_init__(self):
        identifier(self.task_id, 'task_id');identifier(self.workspace_id, 'workspace_id')
        revision_number(self.review_revision, 'review_revision');revision_number(self.revision, 'revision')
        try:object.__setattr__(self, 'phase', SubtitlePhase(self.phase))
        except (TypeError, ValueError) as error:
            raise WorkflowError('INVALID_PARAMS', 'Unknown subtitle phase') from error
        if self.active_effect_id is not None:
            identifier(self.active_effect_id, 'active_effect_id')
        if (self.phase in ACTIVE_PHASES) != (self.active_effect_id is not None):
            raise WorkflowError('INVALID_PARAMS', 'Active phases require an effect identity; idle phases must clear it')
        object.__setattr__(self, 'data_json', canonical_json(json_object(self.data_json)))

    @property
    def data(self) -> dict:
        """Return a fresh tree; callers cannot mutate the saved snapshot."""
        return json_object(self.data_json)

    def to_dict(self) -> dict:
        return {'task_id': self.task_id, 'workspace_id': self.workspace_id,
                'review_revision': self.review_revision, 'revision': self.revision,
                'phase': self.phase.value, 'active_effect_id': self.active_effect_id,
                'data_json': self.data_json}

    @classmethod
    def from_dict(cls, value: Mapping) -> 'SubtitleTask':
        if not isinstance(value, Mapping):raise WorkflowError('INVALID_PARAMS', 'Snapshot must be an object')
        try:return cls(**dict(value))
        except TypeError as error:raise WorkflowError('INVALID_PARAMS', 'Invalid task snapshot fields') from error


@dataclass(frozen=True)
class WorkflowCommand:
    command_id: str
    task_id: str
    action: str
    expected_revision: int
    workspace_id: str
    review_revision: int
    params_json: str = '{}'
    effect_id: str | None = None

    def __post_init__(self):
        for name in ('command_id', 'task_id', 'workspace_id', 'action'):identifier(getattr(self, name), name)
        revision_number(self.expected_revision, 'expected_revision');revision_number(self.review_revision, 'review_revision')
        if self.effect_id is not None:identifier(self.effect_id, 'effect_id')
        object.__setattr__(self, 'params_json', canonical_json(json_object(self.params_json)))

    @property
    def params(self) -> dict:return json_object(self.params_json)

    def fingerprint(self) -> str:
        value = {name: getattr(self, name) for name in self.__dataclass_fields__}
        return hashlib.sha256(canonical_json(value).encode('utf8')).hexdigest()


@dataclass(frozen=True)
class CommandReceipt:
    task: SubtitleTask
    duplicate: bool = False
