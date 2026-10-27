"""Version 2 NDJSON frames. All parent/child messages share the 8 KiB limit."""
from dataclasses import dataclass
import json
import os
import sys

from ..domain.errors import ProtocolError
from .protocol import IDENTIFIER, _check_json, _constant, _finite_number, _object

VERSION = 2
MAX_BYTES = 8192


def dumps(value):
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    if len(raw.encode('utf8')) > MAX_BYTES:
        raise ProtocolError('MESSAGE_TOO_LARGE', '这部分信息暂时无法显示，请重试；已扫描的文件不会被修改。')
    return raw


def loads(raw):
    try:
        if not isinstance(raw, str) or len(raw.encode('utf8')) > MAX_BYTES:
            raise ValueError('Message limit')
        value = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant, parse_float=_finite_number)
        _check_json(value)
        if not isinstance(value, dict):
            raise ValueError('Object required')
        if type(value.get('v')) is not int or value['v'] != VERSION:
            raise ProtocolError('PROTOCOL_MISMATCH', '此入口仅接受版本 2。')
        return value
    except (UnicodeError, ValueError, TypeError, RecursionError):
        raise ProtocolError('INVALID_REQUEST', '消息格式或大小无效。') from None


@dataclass(frozen=True)
class Request:
    request_id: str
    session_id: str | None
    action: str
    params: dict

    def fingerprint(self):
        return json.dumps([self.session_id, self.action, self.params], sort_keys=True,
                          ensure_ascii=False, separators=(',', ':'))


def valid_id(value):
    return isinstance(value, str) and IDENTIFIER.fullmatch(value) is not None


def decode_request(raw, *, actions, validate_params):
    value = loads(raw)
    rid = value.get('requestId')
    if not valid_id(rid):
        raise ProtocolError('INVALID_REQUEST', '请求标识无效。')
    required = {'v', 'type', 'requestId', 'sessionId', 'action', 'params'}
    try:
        if set(value) != required or value['type'] != 'request':
            raise ProtocolError('INVALID_REQUEST', '请求字段无效。')
        if value['sessionId'] is not None and not valid_id(value['sessionId']):
            raise ProtocolError('INVALID_REQUEST', '会话标识无效。')
        if not isinstance(value['action'], str) or value['action'] not in actions:
            raise ProtocolError('ACTION_UNAVAILABLE', '此入口不提供该操作。')
        if not isinstance(value['params'], dict):
            raise ProtocolError('INVALID_REQUEST', '参数必须是对象。')
        validate_params(value['action'], value['params'])
    except ProtocolError as error:
        error.request_id = rid
        raise
    return Request(rid, value['sessionId'], value['action'], value['params'])


def frames():
    buffer = bytearray()
    while True:
        block = os.read(sys.stdin.fileno(), MAX_BYTES)
        if not block:
            return
        buffer.extend(block)
        while b'\n' in buffer:
            line, _, buffer = buffer.partition(b'\n')
            if len(line) > MAX_BYTES:
                return
            try:
                yield loads(line.decode('utf8'))
            except ProtocolError:
                # Malformed transport closes cleanly; never executes a prefix.
                return
        if len(buffer) > MAX_BYTES:
            return


def reply(request_id, session_id, *, data=None, error=None):
    return {'v': VERSION, 'type': 'reply', 'requestId': request_id, 'sessionId': session_id,
            'ok': error is None, 'data': data if error is None else None,
            'error': None if error is None else {'code': error.code, 'message': error.message[:200],
                                                'retryable': error.retryable, 'details': {}}}


def fit_page(frame):
    """Reduce a page with explicit nextOffset. A single oversized item is an error."""
    data = frame.get('data')
    if not isinstance(data, dict):
        dumps(frame)
        return frame
    field = next((name for name in ('rows', 'items', 'entries', 'ids', 'tasks') if isinstance(data.get(name), list)), None)
    if field is None:
        dumps(frame)
        return frame
    data = dict(data)
    frame = {**frame, 'data': data}
    values = list(data[field])
    data[field] = values
    start = data.get('offset', 0)
    total = data.get('total', data.get('itemCount', len(values)))
    while True:
        end = start + len(values)
        data['nextOffset'] = end if end < total else None
        if field == 'rows' and 'ids' in data:
            data['ids'] = data['ids'][:len(values)]
        try:
            dumps(frame)
            return frame
        except ProtocolError:
            if len(values) <= 1:
                raise ProtocolError('ITEM_TOO_LARGE', '单项信息超出通信限制，未截断名称或路径。') from None
            values.pop()
