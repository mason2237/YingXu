"""File-operation vocabulary and immutable identity records; no filesystem access."""
from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path

from .errors import ProtocolError


class RunPhase(str, Enum):
    PREVIEW = 'preview'
    INVALIDATED = 'invalidated'
    RUNNING = 'running'
    INTERRUPTED = 'interrupted'
    COMPLETED = 'completed'
    PARTIAL = 'partial'
    CANCELLED = 'cancelled'
    ARCHIVED = 'archived'


class MoveStep(str, Enum):
    PENDING = 'pending'
    BUFFERING = 'buffering'
    BUFFERED = 'buffered'
    STAGING = 'staging'
    STAGED = 'staged'
    COMMITTING = 'committing'
    COMMITTED = 'committed'
    DELETING = 'deleting'
    APPLIED = 'applied'


@dataclass(frozen=True)
class FileVersion:
    identity: str
    volume: str
    size: int
    modified: int
    created: int
    digest: str = ''

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        try:
            result = cls(**value)
            if not result.identity or not result.volume or type(result.size) is not int or result.size < 0:
                raise ValueError('Invalid file identity')
            if any(type(getattr(result, key)) is not int for key in ('modified', 'created')):
                raise ValueError('Invalid file times')
            if result.digest and (len(result.digest) != 64 or any(char not in '0123456789abcdef' for char in result.digest)):
                raise ValueError('Invalid checksum')
            return result
        except (TypeError, ValueError, AttributeError) as error:
            raise ProtocolError('CORRUPT_JOURNAL', '文件日志的身份记录无效，未自动修改文件。') from error


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':'))


def checksum(value):
    return hashlib.sha256(canonical(value).encode('utf8')).hexdigest()


def validate_intent(value):
    required = {'video', 'source', 'target', 'action', 'source_version', 'video_version', 'source_parent', 'target_parent'}
    if not isinstance(value, dict) or set(value) != required or value['action'] not in {'rename', 'skipped', 'unmatched', 'unchanged', 'pending'}:
        raise ProtocolError('CORRUPT_JOURNAL', '文件计划结构无效。')
    for key in ('video', 'source', 'target'):
        if value[key] is not None and (not isinstance(value[key], str) or not Path(value[key]).is_absolute()):
            raise ProtocolError('CORRUPT_JOURNAL', '文件计划路径无效。')
    if value['action'] == 'rename':
        if not value['source'] or not value['target'] or value['source'] == value['target']:
            raise ProtocolError('CORRUPT_JOURNAL', '文件计划缺少独立的源或目标。')
        FileVersion.from_dict(value['source_version'])
        if not value['source_version']['digest']:
            raise ProtocolError('CORRUPT_JOURNAL', '文件计划缺少内容校验。')
        for key in ('source_parent', 'target_parent'):
            if not isinstance(value[key], dict) or set(value[key]) != {'identity', 'volume'}:
                raise ProtocolError('CORRUPT_JOURNAL', '文件计划的目录身份无效。')
    if value['video_version'] is not None:
        FileVersion.from_dict(value['video_version'])
    return value


def status_for(item, phase):
    if item['spec']['action'] != 'rename':
        return 'skipped' if item['spec']['action'] == 'pending' else item['spec']['action']
    if item.get('error'):
        return 'blocked'
    if item['step'] == MoveStep.APPLIED.value:
        return 'success'
    return 'cancelled' if phase in {'cancelled', 'partial', 'interrupted', 'archived'} else 'pending'
