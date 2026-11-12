"""Strict production actions. Paths, target names and commands are never inputs."""
from ..domain.matching import VIDEO_EXTS
from .messages import IDENTIFIER, ProtocolError, decode_request

CONTEXT = {"scanId", "revision"}
ROW = CONTEXT | {"rowId"}
SCHEMAS = {
    "app.hello": (set(), set()), "app.state": (set(), set()),
    "folder.choose": (set(), set()),
    "subtitle.open": (CONTEXT, {"rowId", "needsId"}),
    "scan.start": ({"folderId", "recursive", "move"}, set()),
    "scan.configure": ({"recursive", "move"}, set()),
    "embedded.configure": ({"enabled", "language"}, set()),
    "scan.cancel": ({"jobId"}, set()), "job.stop": ({"jobId"}, set()),
    "review.query": (CONTEXT, {"search", "status", "fileType", "sortKey", "sortDir", "offset", "limit", "includeIds"}),
    "review.details": (ROW, set()),
    "review.detailPage": (ROW | {"section"}, {"offset", "limit"}),
    "review.quality": (ROW | {'subtitleId'}, {'encoding','maxCps'}),
    "review.qualityPage": (ROW | {'subtitleId','reportId'}, {'offset','limit','qualitySection'}),
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
SCHEMAS['online.provider'] = ({'provider','enabled'},set())
SCHEMAS['online.configure'] = ({'language'}, set())
SCHEMAS['online.start'] = ({'taskId', 'query', 'provider'}, set())
SCHEMAS['online.cancel'] = ({'taskId'}, set())
SCHEMAS['online.usePage'] = ({'taskId'}, {'acknowledged'})
SCHEMAS['online.select'] = ({'taskId', 'candidateId'}, set())
SCHEMAS['online.openCandidate'] = ({'taskId', 'candidateId'}, set())
SCHEMAS['online.candidates'] = ({'taskId'}, {'offset', 'limit'})
SCHEMAS['subtitle.inbox'] = (set(), set())
SCHEMAS['online.download'] = ({'taskIds', 'acknowledged'}, {'candidateId'})
SCHEMAS['online.resumeQueue'] = ({'acknowledged'}, set())
SCHEMAS['online.downloads'] = (set(), {'offset', 'limit'})
SCHEMAS['online.qualityFiles'] = ({'artifactId'}, {'offset','limit'})
SCHEMAS['online.quality'] = ({'artifactId','fileIndex'}, {'encoding','maxCps'})
SCHEMAS['online.qualityResult'] = ({'artifactId','jobId'},set())
SCHEMAS['online.qualityPage'] = ({'artifactId','fileIndex','reportId'},{'qualitySection','offset','limit'})
SCHEMAS['online.retryDownload'] = ({'artifactId', 'acknowledged'}, set())
SCHEMAS['online.discardDownload'] = ({'artifactId', 'acknowledged'}, set())
SCHEMAS['online.compactDownload'] = ({'artifactId', 'acknowledged'}, set())
SCHEMAS['online.import'] = ({'artifactIds', 'acknowledged'}, set())
SCHEMAS['online.cache'] = (set(), set())
SCHEMAS['requirements.policy'] = (set(),set())
SCHEMAS['identity.read'] = (ROW,{'includeHash'})
SCHEMAS['identity.set'] = (ROW|{'imdbId'},set())
SCHEMAS['sync.capabilities'] = (set(),set())
SCHEMAS['sync.references'] = (ROW,{'offset','limit'})
SCHEMAS['sync.results'] = (ROW,{'offset','limit'})
SCHEMAS['sync.create'] = (ROW|{'subtitleId','syncMode'},{'offsetMs','referenceId','encoding','referenceEncoding','audioTrack'})
SCHEMAS['sync.tool'] = (set(),set())
SCHEMAS['sync.clearAnalysis'] = ({'acknowledged'},set())
SCHEMAS['sync.discard'] = (ROW|{'artifactId','acknowledged'},set())
SCHEMAS['sync.cache'] = (set(),set())
SCHEMAS['content.compare'] = (ROW|{'referenceId'},set())
SCHEMAS['sync.query'] = (ROW|{'artifactId'},set())
SCHEMAS['sync.stage'] = (ROW|{'artifactId','acknowledged'},set())
SCHEMAS['requirements.configure'] = ({'languages','allowSDH','includeForced'},set())
SCHEMAS['requirements.check'] = (CONTEXT,set())
SCHEMAS['requirements.query'] = (CONTEXT|{'needsId'},{'offset','limit'})
SCHEMAS['requirements.stage'] = (CONTEXT|{'needsId','offerId','acknowledged'},set())
ACTIONS = frozenset(SCHEMAS)
ENUMS = {
    'syncMode':{'manual','reference','audio'},
    'encoding':{'auto','utf-8','utf-8-sig','utf-16-le','utf-16-be','utf-32-le','utf-32-be','gb18030','big5','shift_jis'},
    'qualitySection':{'issues','cues'},
    "section": {"tracks", "subtitles", "warnings", "basis"},
    "status": {"all", "待整理", "需确认", "未匹配", "存在冲突", "已跳过", "已符合"},
    "fileType": {""} | VIDEO_EXTS, "sortKey": {"name", "score", "state"}, "sortDir": {"asc", "desc"},
    "provider": {"zimuku", "srtku", "subhd", "subhd-one"},
    "language": {"chinese", "bilingual", "simplified", "traditional", "english", "japanese", "korean", "any"},
}
ENUMS['referenceEncoding']=ENUMS['encoding']


def validate(action, params):
    required, optional = SCHEMAS[action]
    if required - params.keys() or params.keys() - required - optional:
        raise ProtocolError("INVALID_REQUEST", "操作参数缺失或包含未支持的字段。")
    if action=='requirements.configure':
        from ..domain.subtitle_policy import SubtitlePolicy
        try:SubtitlePolicy.read(params)
        except ValueError as error:raise ProtocolError('INVALID_REQUEST',str(error)) from error
        return
    if action == 'online.configure':
        if not isinstance(params['language'], str) or params['language'] not in {'bilingual', 'zh-Hans', 'zh-Hant', 'en'}:
            raise ProtocolError('INVALID_REQUEST', '在线字幕语言偏好无效。')
        return
    for key, value in params.items():
        valid = True
        if key=='audioTrack':
            valid=type(value) is int and 0<=value<=31
        elif key=='offsetMs':
            valid=type(value) is int and -86400000<=value<=86400000
        elif key=='maxCps':
            valid=type(value) is int and 1<=value<=1000
        elif key=='fileIndex':
            valid=type(value) is int and 0<=value<200
        elif key in {'taskIds', 'artifactIds'}:
            valid = isinstance(value, list) and 1 <= len(value) <= 20 and all(isinstance(item, str) and IDENTIFIER.fullmatch(item) for item in value) and len(set(value)) == len(value)
        elif key in {"recursive", "move", "skipped", "includeIds", "acknowledged", "enabled", "use", "includeHash"}:
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
    if action == 'online.download' and 'candidateId' in params and len(params['taskIds']) != 1:
        raise ProtocolError('INVALID_REQUEST', '下载指定候选时只能选择一个视频。')


def decode(raw):
    return decode_request(raw, actions=ACTIONS, validate_params=validate)
