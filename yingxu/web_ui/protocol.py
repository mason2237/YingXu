"""Versioned JSON boundary; this module has no Qt or filesystem dependency."""
from dataclasses import dataclass
import json
import re

VERSION = 1
MAX_MESSAGE_BYTES = 8192
ACTIONS = frozenset({"app.hello", "app.state", "app.ping"})
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


class ProtocolError(Exception):
    def __init__(self, code, message, *, request_id=None, retryable=False):
        super().__init__(message)
        self.code, self.message = code, message
        self.request_id, self.retryable = request_id, retryable


@dataclass(frozen=True)
class Request:
    request_id: str
    session_id: str | None
    action: str
    params: dict

    def fingerprint(self):
        return json.dumps([self.action, self.params], sort_keys=True, ensure_ascii=False)


def decode_request(raw, *, actions=ACTIONS, validate_params=None):
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
        raise ProtocolError("INVALID_REQUEST", "请求长度超出限制。")
    try:
        obj = json.loads(raw)
    except (ValueError, RecursionError):
        raise ProtocolError("INVALID_REQUEST", "请求不是有效的 JSON。") from None
    if not isinstance(obj, dict):
        raise ProtocolError("INVALID_REQUEST", "请求必须为对象。")
    rid = obj.get("requestId")
    if not isinstance(rid, str) or not IDENTIFIER.fullmatch(rid):
        raise ProtocolError("INVALID_REQUEST", "请求标识无效。")
    if set(obj) - {"v", "requestId", "sessionId", "action", "params"}:
        raise ProtocolError("INVALID_REQUEST", "请求包含未支持的字段。", request_id=rid)
    if type(obj.get("v")) is not int or obj["v"] != VERSION:
        raise ProtocolError("PROTOCOL_MISMATCH", "通信版本不一致，请重新打开应用。", request_id=rid)
    action, params = obj.get("action"), obj.get("params")
    if not isinstance(action, str) or action not in actions:
        raise ProtocolError("ACTION_UNAVAILABLE", "未提供此操作。", request_id=rid)
    if not isinstance(params, dict):
        raise ProtocolError("INVALID_REQUEST", "操作参数必须为对象。", request_id=rid)
    allowed = {"message"} if action == "app.ping" else set()
    if validate_params is not None:
        try:
            validate_params(action, params)
        except ProtocolError as error:
            error.request_id = rid
            raise
        allowed = set(params)  # Custom schema has already rejected unknown keys.
    if set(params) - allowed:
        raise ProtocolError("INVALID_REQUEST", "操作包含未支持的参数。", request_id=rid)
    if action == "app.ping" and (
        not isinstance(params.get("message"), str) or len(params["message"]) > 512
    ):
        raise ProtocolError("INVALID_REQUEST", "回声内容应为不超过 512 字的文本。", request_id=rid)
    sid = obj.get("sessionId")
    if sid is not None and (not isinstance(sid, str) or not IDENTIFIER.fullmatch(sid)):
        raise ProtocolError("INVALID_REQUEST", "会话标识无效。", request_id=rid)
    return Request(rid, sid, action, params)


def encode_reply(request_id, data=None, error=None):
    return json.dumps({
        "v": VERSION, "requestId": request_id, "ok": error is None,
        "data": data if error is None else None,
        "error": None if error is None else {
            "code": error.code, "message": error.message,
            "retryable": error.retryable, "details": {},
        },
    }, ensure_ascii=True, allow_nan=False)
