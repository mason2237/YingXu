"""Small v2 presentation-command codec, independent of Qt and transport.

Trusted provider/download completion events never enter this decoder. They
are application adapter callbacks, not commands a renderer may manufacture.
"""
from __future__ import annotations

import json
import math
import re

from ..application.subtitles import PUBLIC_ACTIONS, validate_user_params
from ..domain.models import CommandReceipt, WorkflowCommand, WorkflowError

VERSION = 2
MAX_MESSAGE_BYTES = 8192
MAX_REVISION = 2**31 - 1
MAX_JSON_DEPTH = 16
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
REQUIRED_FIELDS = frozenset({"v", "id", "taskId", "action", "expectedRevision", "workspaceId", "reviewRevision"})
OPTIONAL_FIELDS = frozenset({"params", "effectId"})


def _invalid(message: str) -> WorkflowError:
    return WorkflowError("INVALID_REQUEST", message)


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON field")
        value[key] = item
    return value


def _constant(_value):
    raise ValueError("Non-finite JSON number")


def _finite_number(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Non-finite JSON number")
    return number


def _check_json(value, depth=0):
    if depth > MAX_JSON_DEPTH:
        raise ValueError("JSON nesting limit exceeded")
    if isinstance(value, str):
        value.encode("utf-8")  # Reject escaped, unpaired UTF-16 surrogates too.
    elif isinstance(value, dict):
        for key, item in value.items():
            key.encode("utf-8")
            _check_json(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _check_json(item, depth + 1)


def _identifier(value):
    return isinstance(value, str) and IDENTIFIER.fullmatch(value) is not None


def _revision(value):
    return type(value) is int and 0 <= value <= MAX_REVISION


def _params(action, value):
    if not isinstance(value, dict):
        raise _invalid("操作参数必须是对象。")
    try:
        validate_user_params(action, value)
    except WorkflowError as error:
        raise _invalid(error.message) from error


def decode_command(raw: str) -> WorkflowCommand:
    if not isinstance(raw, str):
        raise _invalid("消息必须是 UTF-8 JSON 文本。")
    try:
        if len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
            raise _invalid("消息超过 8 KiB 限制。")
        value = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant, parse_float=_finite_number)
        _check_json(value)
    except (UnicodeError, ValueError, RecursionError):
        raise _invalid("消息不是受支持的 JSON。") from None
    if not isinstance(value, dict):
        raise _invalid("消息顶层必须是对象。")
    if REQUIRED_FIELDS - value.keys() or value.keys() - REQUIRED_FIELDS - OPTIONAL_FIELDS:
        raise _invalid("消息字段缺失或包含未支持的字段。")
    if type(value["v"]) is not int or value["v"] != VERSION:
        raise WorkflowError("PROTOCOL_MISMATCH", "此入口仅接受版本 2 的协议。")
    for name in ("id", "taskId", "workspaceId"):
        if not _identifier(value[name]):
            raise _invalid("消息标识无效。")
    if not _revision(value["expectedRevision"]) or not _revision(value["reviewRevision"]):
        raise _invalid("版本号应为非负有界整数。")
    action = value["action"]
    if not isinstance(action, str) or action not in PUBLIC_ACTIONS:
        raise WorkflowError("ACTION_UNAVAILABLE", "此入口不提供该操作。")
    if value.get("effectId") is not None:
        raise _invalid("展示层不能提交适配器完成事件。")
    params = value.get("params", {})
    _params(action, params)
    return WorkflowCommand(
        command_id=value["id"], task_id=value["taskId"], action=action,
        expected_revision=value["expectedRevision"], workspace_id=value["workspaceId"],
        review_revision=value["reviewRevision"],
        params_json=json.dumps(params, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")),
        effect_id=None,
    )


def _encode(request_id, *, data=None, error=None):
    if request_id is not None and not _identifier(request_id):
        raise _invalid("回复标识无效。")
    try:
        encoded = json.dumps({"v": VERSION, "id": request_id, "ok": error is None,
                              "data": data if error is None else None,
                              "error": None if error is None else {"code": error.code, "message": error.message[:200]}},
                             ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
        size = len(encoded.encode("utf-8"))
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise WorkflowError("INVALID_RESPONSE", "回复无法编码为受支持的 JSON。") from None
    if size > MAX_MESSAGE_BYTES:
        raise WorkflowError("MESSAGE_TOO_LARGE", "回复超过 8 KiB 限制。")
    return encoded


def encode_receipt(request_id: str, receipt: CommandReceipt) -> str:
    if not _identifier(request_id):
        raise _invalid("回复标识无效。")
    task = receipt.task
    projection = {"task_id": task.task_id, "workspace_id": task.workspace_id,
                  "review_revision": task.review_revision, "revision": task.revision,
                  "phase": task.phase.value, "active_effect_id": task.active_effect_id}
    return _encode(request_id, data={"task": projection, "duplicate": receipt.duplicate})


def encode_error(request_id: str | None, error: WorkflowError) -> str:
    return _encode(request_id, error=error)
