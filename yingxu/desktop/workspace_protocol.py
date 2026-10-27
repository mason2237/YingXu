"""Strict production actions. Paths, target names and commands are never inputs."""
from ..domain.matching import VIDEO_EXTS
from .messages import IDENTIFIER, ProtocolError, decode_request

CONTEXT = {"scanId", "revision"}
ROW = CONTEXT | {"rowId"}
SCHEMAS = {
    "app.hello": (set(), set()), "app.state": (set(), set()),
    "folder.choose": (set(), set()),
    "subtitle.open": (CONTEXT, {"rowId"}),
    "scan.start": ({"folderId", "recursive", "move"}, set()),
    "scan.configure": ({"recursive", "move"}, set()),
    "embedded.configure": ({"enabled", "language"}, set()),
    "scan.cancel": ({"jobId"}, set()), "job.stop": ({"jobId"}, set()),
    "review.query": (CONTEXT, {"search", "status", "fileType", "sortKey", "sortDir", "offset", "limit", "includeIds"}),
    "review.details": (ROW, set()),
    "review.candidates": (ROW, {"offset", "limit"}),
    "review.assign": (ROW | {"subtitleId"}, {"replaceId"}),
    "review.remove": (ROW | {"subtitleId"}, set()),
    "review.confirm": (ROW, set()), "review.skip": (ROW | {"skipped"}, set()),
    "review.embedded": (ROW | {"use"}, set()),
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
SCHEMAS['review.ids'] = SCHEMAS['review.query']
SCHEMAS['job.result'] = ({'jobId'}, {'offset', 'limit'})
SCHEMAS['operation.resumePreview'] = ({'runId'}, set())
SCHEMAS['operation.undoPreview'] = ({'runId'}, set())
SCHEMAS['operation.query'] = ({'runId', 'snapshotId'}, {'offset', 'limit'})
SCHEMAS['operation.confirm'] = ({'runId', 'snapshotId', 'confirmationToken', 'acknowledged'}, set())
SCHEMAS['operation.archive'] = ({'runId', 'acknowledged'}, set())
SCHEMAS['operation.cache'] = (set(), set())
SCHEMAS['online.query'] = (set(), {'offset', 'limit'})
SCHEMAS['online.configure'] = ({'language'}, set())
SCHEMAS['online.start'] = ({'taskId', 'query', 'provider'}, set())
SCHEMAS['online.cancel'] = ({'taskId'}, set())
SCHEMAS['online.usePage'] = ({'taskId'}, set())
SCHEMAS['online.select'] = ({'taskId', 'candidateId'}, set())
SCHEMAS['online.openCandidate'] = ({'taskId', 'candidateId'}, set())
SCHEMAS['online.candidates'] = ({'taskId'}, {'offset', 'limit'})
SCHEMAS['subtitle.inbox'] = (set(), set())
SCHEMAS['online.download'] = ({'taskIds', 'acknowledged'}, set())
SCHEMAS['online.resumeQueue'] = ({'acknowledged'}, set())
SCHEMAS['online.downloads'] = (set(), {'offset', 'limit'})
SCHEMAS['online.retryDownload'] = ({'artifactId', 'acknowledged'}, set())
SCHEMAS['online.discardDownload'] = ({'artifactId', 'acknowledged'}, set())
SCHEMAS['online.compactDownload'] = ({'artifactId', 'acknowledged'}, set())
SCHEMAS['online.import'] = ({'artifactIds', 'acknowledged'}, set())
SCHEMAS['online.cache'] = (set(), set())
ACTIONS = frozenset(SCHEMAS)
ENUMS = {
    "status": {"all", "待整理", "需确认", "未匹配", "存在冲突", "已跳过", "已符合"},
    "fileType": {""} | VIDEO_EXTS, "sortKey": {"name", "score", "state"}, "sortDir": {"asc", "desc"},
    "provider": {"zimuku", "srtku", "subhd", "subhd-one"},
    "language": {"chinese", "bilingual", "simplified", "traditional", "english", "japanese", "korean", "any"},
}


def validate(action, params):
    required, optional = SCHEMAS[action]
    if required - params.keys() or params.keys() - required - optional:
        raise ProtocolError("INVALID_REQUEST", "操作参数缺失或包含未支持的字段。")
    if action == 'online.configure':
        if not isinstance(params['language'], str) or params['language'] not in {'bilingual', 'zh-Hans', 'zh-Hant', 'en'}:
            raise ProtocolError('INVALID_REQUEST', '在线字幕语言偏好无效。')
        return
    for key, value in params.items():
        valid = True
        if key in {'taskIds', 'artifactIds'}:
            valid = isinstance(value, list) and 1 <= len(value) <= 20 and all(isinstance(item, str) and IDENTIFIER.fullmatch(item) for item in value) and len(set(value)) == len(value)
        elif key in {"recursive", "move", "skipped", "includeIds", "acknowledged", "enabled", "use"}:
            valid = type(value) is bool
        elif key in {"revision", "reviewRevision", "offset", "limit"}:
            maximum = (30 if action == "history.list" else 200) if key == "limit" else 2**31-1
            valid = type(value) is int and (1 if key == "limit" else 0) <= value <= maximum
        elif key in ENUMS:
            valid = isinstance(value, str) and value in ENUMS[key]
        elif key in {"search", "query"}:
            valid = isinstance(value, str) and len(value) <= (200 if key == "query" else 512)
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
