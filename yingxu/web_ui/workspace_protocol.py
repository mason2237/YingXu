"""Strict production actions. Paths, target names and commands are never inputs."""
from ..core import VIDEO_EXTS
from .protocol import IDENTIFIER, ProtocolError, decode_request

CONTEXT = {"scanId", "revision"}
ROW = CONTEXT | {"rowId"}
SCHEMAS = {
    "app.hello": (set(), set()), "app.state": (set(), set()),
    "folder.choose": (set(), set()),
    "scan.start": ({"folderId", "recursive", "move"}, set()),
    "scan.configure": ({"recursive", "move"}, set()),
    "scan.cancel": ({"jobId"}, set()), "job.stop": ({"jobId"}, set()),
    "review.query": (CONTEXT, {"search", "status", "fileType", "sortKey", "sortDir", "offset", "limit", "includeIds"}),
    "review.details": (ROW, set()),
    "review.candidates": (ROW, {"offset", "limit"}),
    "review.assign": (ROW | {"subtitleId"}, {"replaceId"}),
    "review.remove": (ROW | {"subtitleId"}, set()),
    "review.confirm": (ROW, set()), "review.skip": (ROW | {"skipped"}, set()),
    "preview.create": (CONTEXT, set()),
    "preview.query": ({"snapshotId"}, {"offset", "limit"}),
    "preview.discard": (set(), {"snapshotId"}),
    "organize.confirmAndStart": ({"scanId", "reviewRevision", "snapshotId", "confirmationToken", "acknowledged"}, set()),
    "result.get": ({"batchId"}, {"offset", "limit"}),
    "history.list": (set(), {"limit"}),
    "history.get": ({"recordId"}, {"offset", "limit"}),
    "result.export": ({"recordId"}, set()),
    "file.reveal": ({"fileId"}, set()), "file.copyName": ({"fileId"}, set()),
}
ACTIONS = frozenset(SCHEMAS)
ENUMS = {
    "status": {"all", "待整理", "需确认", "未匹配", "存在冲突", "已跳过", "已符合"},
    "fileType": {""} | VIDEO_EXTS, "sortKey": {"name", "score", "state"}, "sortDir": {"asc", "desc"},
}


def validate(action, params):
    required, optional = SCHEMAS[action]
    if required - params.keys() or params.keys() - required - optional:
        raise ProtocolError("INVALID_REQUEST", "操作参数缺失或包含未支持的字段。")
    for key, value in params.items():
        valid = True
        if key in {"recursive", "move", "skipped", "includeIds", "acknowledged"}:
            valid = type(value) is bool
        elif key in {"revision", "reviewRevision", "offset", "limit"}:
            maximum = (30 if action == "history.list" else 200) if key == "limit" else 2**31-1
            valid = type(value) is int and (1 if key == "limit" else 0) <= value <= maximum
        elif key in ENUMS:
            valid = isinstance(value, str) and value in ENUMS[key]
        elif key == "search":
            valid = isinstance(value, str) and len(value) <= 512
        else:
            valid = isinstance(value, str) and IDENTIFIER.fullmatch(value) is not None
            if key == "replaceId" and value is None:
                valid = True
            if key == "scanId" and value is None and action == "review.query":
                valid = True
        if not valid:
            raise ProtocolError("INVALID_REQUEST", f"参数 {key} 的类型或范围无效。")


def decode(raw):
    return decode_request(raw, actions=ACTIONS, validate_params=validate)
