"""Workspace use cases. One owner thread; no IPC, GUI or concrete adapter imports."""
from collections import OrderedDict
from pathlib import Path
from threading import RLock
from uuid import uuid4

from ..domain.errors import ProtocolError
from ..domain.matching import ScanCancelled
from ..domain.media import DEFAULT_OPTIONS, LANGUAGES
from ..domain.review import path_key
from ..ports.tasks import TaskRunner
from ..ports.workspace import Filesystem, HistoryReader, MediaInspector, Previewer, Settings
from .scanning import scan
from .executing import Execution


class Workspace:
    def __init__(self, *, filesystem: Filesystem, inspector: MediaInspector,
                 previewer: Previewer, history: HistoryReader, settings: Settings,
                 tasks: TaskRunner, changed, execution: Execution | None = None, drafts=None):
        self.fs, self.inspector, self.previewer = filesystem, inspector, previewer
        self.history, self.settings, self.tasks, self.changed = history, settings, tasks, changed
        self.worker = None
        self.job = None
        self.results = OrderedDict()
        self.native_busy = False
        self.session_id = None
        self.folder = self.folder_id = self.folder_mark = None
        self.folder_pending = False
        self.data = None
        self.revision = 0
        self.options = {'recursive': True, 'move': False}
        self.embedded = settings.read()
        if (set(self.embedded) != {'enabled', 'language'} or type(self.embedded['enabled']) is not bool
                or self.embedded['language'] not in LANGUAGES):
            self.embedded = dict(DEFAULT_OPTIONS)
        self.paths, self.path_ids = {}, {}
        self._path_lock = RLock()
        self.snapshot = None
        self._preview_generation = 0
        self.records = {}
        self.discovery = None
        self.interrupted_count = 0
        self.execution = execution
        self.finished = False
        self.last_result_id = None
        self._startup_checked = False
        self.drafts = drafts
        self.draft_status = {'restored':False,'message':''}

    @property
    def busy(self):
        return self.worker is not None or self.native_busy

    def require_idle(self):
        if self.busy:
            raise ProtocolError('BUSY', '当前任务尚未结束，请稍候。', retryable=True)

    def emit(self, kind, payload=None):
        self.changed(kind, payload or {})

    def invalidate_preview(self):
        self._preview_generation += 1
        if self.execution:
            self.execution.invalidate()
            self.execution.discard(self.snapshot)
        self.snapshot = None

    def invalidate_online(self):
        if self.discovery:
            self.discovery.invalidate()

    def new_page(self, session_id):
        self.session_id = session_id
        self.invalidate_preview()
        if self.discovery:
            self.discovery.suspend()

    def register(self, path):
        with self._path_lock:
            key = path_key(path)
            if key not in self.path_ids:
                identifier = uuid4().hex
                self.path_ids[key] = identifier
                self.paths[identifier] = Path(path)
            return self.path_ids[key]

    def registered_path(self, identifier):
        if identifier not in self.paths:
            raise ProtocolError('NOT_FOUND', '文件不属于当前工作区。')
        return self.paths[identifier]

    def accept_folder(self, folder, *, dropped=False):
        self.require_idle()
        mark = self.fs.directory_mark(folder)
        if self.drafts: self.drafts.store.clear('workspace','online')
        self.draft_status = {'restored':False,'message':''}
        self.invalidate_online()
        with self._path_lock:
            self.paths.clear()
            self.path_ids.clear()
        self.folder, self.folder_mark = folder, mark
        self.folder_id = self.register(folder)
        self.data = None
        self.revision += 1
        self.folder_pending = True
        self.finished = False
        self.invalidate_preview()
        self.emit('folder.changed', {'dropped': dropped})

    def summary(self):
        data = self.data
        return {
            'mode': 'local', 'scanId': data.scan_id if data else None,
            'revision': data.revision if data else self.revision,
            'folderId': self.folder_id, 'folderName': self.folder.name if self.folder else '尚未选择文件夹',
            'displayPath': str(self.folder) if self.folder else '',
            'counts': data.counts if data else {'all': 0},
            'subtitleCount': data.subtitle_count if data else 0,
            'embeddedSatisfiedCount': sum(row.uses_embedded and not row.skipped for row in data.review.rows) if data else 0,
            'embeddedOptions': dict(self.embedded), 'options': dict(self.options),
            'needsScan': bool(self.folder and not data), 'folderPending': self.folder_pending,
            'finished': self.finished, 'lastResultId': self.last_result_id,
            'scanWarnings': [text[:200] for text in data.scan_warnings[:5]] if data else [],
            'scanWarningCount': data.warning_count if data else 0,
        }

    def state(self):
        return {'stage': 'R4' if self.execution else 'R2', 'mode': 'local', 'summary': self.summary(), 'job': self.job,
                'busy': self.busy, 'nativePending': self.native_busy, 'prototype': False,
                'executionAvailable': self.execution is not None, 'downloadAvailable': self.discovery is not None and self.discovery.downloads is not None, 'reviewReadOnly': False,
                'onlineAvailable': True, 'runtime': 'python-stdlib', 'interruptedTasks': self.interrupted_count,
                'recoveryPending': len(self.execution.journal.pending_ids()) if self.execution else 0,
                'draft':dict(self.draft_status)}

    def draft_capture(self, data, stop=lambda:False, *, fresh=False):
        return self.drafts.capture(self,data,stop,fresh=fresh) if self.drafts else None

    def draft_publish(self, value):
        if self.drafts and value is not None: self.drafts.store.save('workspace',value)

    def idle(self):
        if self.discovery and self.discovery.downloads:
            self.discovery.downloads.advance()
            self.discovery.downloads.maintain_idle()

    def require_review(self, params):
        self.require_idle()
        if not self.data or (params.get('scanId'), params.get('revision')) != (self.data.scan_id, self.data.revision):
            raise ProtocolError('STALE_REVIEW', '审阅版本已变化，请刷新或重新扫描。')
        return self.data

    def launch(self, kind, work, complete, message, *, publish_cancelled=False):
        self.require_idle()
        identifier = uuid4().hex
        self.job = {'jobId': identifier, 'kind': kind, 'status': 'running', 'phase': kind,
                    'message': message, 'done': 0, 'total': None, 'stopRequested': False,
                    'result': None, 'error': None}

        def progress(done, total, text, phase):
            if self.worker is None or not self.job or self.job['jobId'] != identifier or self.job['status'] != 'running':
                return
            self.job.update(done=done, total=total, message=text[:200], phase=phase)
            self.emit('job.progress')

        def failed(error):
            self.worker = None
            if kind in {'apply', 'undo'} and self.execution:
                # A storage/worker failure must not leave an apparently live run.
                # The next startup still reconciles it if the journal is unavailable.
                try:
                    self.execution.journal.interrupt_running()
                except Exception:
                    pass
            code = 'CANCELLED' if isinstance(error, ScanCancelled) else getattr(error, 'code',
                   'PERMISSION_DENIED' if isinstance(error, PermissionError) else
                   'NOT_FOUND' if isinstance(error, FileNotFoundError) else
                   'PATH_UNREADABLE' if isinstance(error, OSError) else 'TASK_FAILED')
            text = str(error)[:200]
            self.job.update(status='cancelled' if code == 'CANCELLED' else 'failed', message=text,
                            error={'code': code, 'message': text})
            self.emit('job.failed')
            self.emit('job.idle')
            self.idle()

        def finished(value):
            try:
                if self.worker.stop.is_set() and kind not in {'apply', 'undo'} and not publish_cancelled:
                    raise ScanCancelled('任务已取消，未发布部分结果。')
                result = complete(value)
            except Exception as error:
                failed(error)
                return
            self.results[identifier] = result
            while len(self.results) > 8:
                self.results.popitem(last=False)
            self.worker = None
            self.job.update(status='completed', message='任务已完成', result={'jobResult': True, 'jobId': identifier})
            self.emit('job.completed')
            self.emit('job.idle')
            self.idle()

        self.worker = self.tasks.start(work, progress, finished, failed)
        self.emit('job.started')
        return {'jobId': identifier}

    def start_scan(self, params):
        self.require_idle()
        if not self.folder or params['folderId'] != self.folder_id:
            raise ProtocolError('NOT_FOUND', '请先选择文件夹。')
        if self.fs.directory_mark(self.folder) != self.folder_mark:
            raise ProtocolError('PATH_UNREADABLE', '目录已变化，请重新选择。')
        self.invalidate_preview()
        self.invalidate_online()
        self.folder_pending = False
        self.finished = False
        self.options = {key: params[key] for key in ('recursive', 'move')}
        root, mark, options, embedded = self.folder, self.folder_mark, dict(self.options), dict(self.embedded)
        revision = self.revision + 1
        def complete(value):
            data, draft = value
            self.draft_publish(draft)
            self.data, self.revision = data, data.revision
            self.draft_status = {'restored':False,'message':''}
            return {'scanId': data.scan_id, 'summary': self.summary()}
        def work(worker):
            data = scan(root,mark,options,embedded,revision,self.register,self.fs,self.inspector,worker)
            return data, self.draft_capture(data,worker.stop.is_set,fresh=True)
        return self.launch('scan', work, complete, '正在读取视频与字幕…')

    def preview_info(self):
        if not self.snapshot:
            raise ProtocolError('STALE_PLAN', '预览已失效，请重新生成。')
        if self.execution:
            return self.execution.info(self.snapshot)
        snapshot = self.snapshot
        return {'snapshotId': snapshot.snapshot_id, 'scanId': self.data.scan_id, 'revision': self.data.revision,
                'changeCount': len(snapshot.changes), 'pendingCount': snapshot.pending_count, 'conflictCount': 0,
                'unmatchedCount': sum(item.action == 'unmatched' for item in snapshot.items),
                'itemCount': len(snapshot.items), 'canExecute': False,
                'executionReason': '此版本仅开放审阅和预览，暂不执行文件变更。'}

    def create_preview(self, params, session):
        data = self.require_review(params)
        self.invalidate_preview()
        generation = self._preview_generation
        def complete(snapshot):
            if generation != self._preview_generation or self.data is not data or session != self.session_id:
                if self.execution:
                    self.execution.discard(snapshot)
                raise ProtocolError('STALE_PLAN', '页面或审阅已变化，请重新预览。')
            self.snapshot = snapshot
            if self.execution:
                return self.execution.issue(snapshot, session, 'execute')
            return self.preview_info()
        def freeze(worker):
            snapshot = self.previewer.freeze(data.review)
            if not self.execution:
                return snapshot
            return self.execution.freeze(snapshot, {'scanId': data.scan_id, 'revision': data.revision},
                                         worker.stop.is_set, worker.report)
        return self.launch('preview', freeze, complete, '正在检查变更预览…')

    def start_reconciliation(self):
        if not self._startup_checked:
            self._startup_checked = True
            pending = self.execution.journal.pending_ids() if self.execution else []
            saved = self.drafts.store.load('workspace') if self.drafts else None
            if not pending and saved:
                return self.restore_draft(saved)
            if pending:
                return self.launch('reconcile',lambda worker:self.execution.audit(worker.stop.is_set,worker.report),
                                   lambda value:value,'正在只读核对上次任务，不会自动修改文件…')
            self.idle()

    def restore_draft(self, saved):
        def work(worker):
            try: return self.drafts.restore(saved,self.register,worker.stop.is_set), None
            except (OSError, ValueError, ProtocolError) as error: return None,str(error)[:200]
        def complete(value):
            restored,error = value
            if error:
                self.draft_status = {'restored':False,'message':error}
                return {'restored':False,'message':error}
            self.folder,self.folder_mark,self.data,self.options,self.embedded = restored
            self.folder_id = self.register(self.folder)
            self.revision = self.data.revision
            self.draft_status = {'restored':True,'message':'已恢复上次审阅与字幕队列；新增文件请重新扫描，整理前需重新预览确认。'}
            if self.discovery: self.discovery.restore()
            return {'restored':True}
        return self.launch('restore',work,complete,'正在核对并恢复审阅草稿，不会自动整理或联网…')

    def operation_preview(self, action, params, session):
        self.require_idle()
        self.invalidate_preview()
        generation = self._preview_generation
        undo = action == 'operation.undoPreview'
        def work(worker):
            method = self.execution.prepare_undo if undo else self.execution.prepare_resume
            return method(params['runId'], worker.stop.is_set, worker.report)
        def complete(identifier):
            if generation != self._preview_generation or session != self.session_id:
                if undo:
                    self.execution.discard(identifier)
                raise ProtocolError('STALE_PLAN', '页面已变化，请重新核对恢复或撤销预览。')
            self.snapshot = identifier
            info = self.execution.issue(identifier, session, 'undo' if undo else 'resume')
            info['operation'] = 'undo' if undo else 'resume'
            return info
        return self.launch('undo_preview' if undo else 'recovery', work, complete, '正在核对文件，尚未执行变更…')

    def start_operation(self, params, session, *, original=False):
        self.require_idle()
        if not self.execution or not self.snapshot:
            raise ProtocolError('STALE_PLAN', '请先生成并核对预览。')
        if original:
            self.require_review({'scanId': params['scanId'], 'revision': params['reviewRevision']})
        elif params['runId'] != self.snapshot:
            raise ProtocolError('STALE_PLAN', '恢复或撤销预览已变化。')
        identifier = self.snapshot
        self.execution.claim(identifier, params['snapshotId'], session, params['confirmationToken'],
                             params['acknowledged'], purposes=('execute',) if original else ('undo', 'resume'))
        if self.drafts: self.drafts.store.clear('workspace','online')
        def complete(value):
            self.data = None
            self.revision += 1
            self.finished = True
            self.last_result_id = identifier
            return value
        try:
            self.invalidate_preview()
            self.invalidate_online()
            run = self.execution.journal.run(identifier)
            return self.launch('undo' if run['kind'] == 'undo' else 'apply',
                lambda worker: self.execution.execute(identifier, worker.stop.is_set, worker.report),
                complete, '正在处理已确认的固定文件计划…')
        except Exception:
            try:
                self.execution.journal.update_run(identifier, phase='interrupted', message='任务未能开始，等待恢复核对。')
            except Exception:
                pass  # Preserve the original failure; startup will find the running intent.
            raise

    def dispatch(self, action, params, session):
        if action == 'app.state':
            return self.state()
        if action == 'result.export':
            raise ProtocolError('CAPABILITY_DISABLED', '记录导出尚未开放，完整操作日志保存在本机。')
        if action == 'organize.confirmAndStart':
            return self.start_operation(params, session, original=True)
        if action == 'operation.confirm':
            return self.start_operation(params, session)
        if action in {'operation.resumePreview', 'operation.undoPreview'}:
            return self.operation_preview(action, params, session)
        if action == 'operation.query':
            if self.execution.journal.run(params['runId'])['snapshot_id'] != params['snapshotId']:
                raise ProtocolError('STALE_PLAN', '固定计划已失效。')
            return self.execution.page(params['runId'], params.get('offset', 0), params.get('limit', 20))
        if action == 'operation.archive':
            self.require_idle()
            value = self.execution.archive(params['runId'], params['acknowledged'])
            self.emit('recovery.changed')
            return value
        if action in {'scan.configure', 'embedded.configure'}:
            self.require_idle()
            if self.drafts: self.drafts.store.clear('workspace','online')
            if action == 'embedded.configure':
                self.settings.write(params)
                self.embedded = dict(params)
            else:
                self.options = dict(params)
            self.invalidate_preview()
            self.invalidate_online()
            self.data = None
            self.revision += 1
            self.emit('review.invalidated')
            return self.summary()
        if action == 'scan.start':
            return self.start_scan(params)
        if action in {'scan.cancel', 'job.stop'}:
            if not self.worker or params['jobId'] != self.job['jobId']:
                raise ProtocolError('NOT_FOUND', '没有这个运行中的任务。')
            self.worker.stop.set()
            message = '当前文件完成后停止；已完成的变更和恢复缓存保留。' if self.job['kind'] in {'apply', 'undo'} else '正在停止…'
            self.job.update(stopRequested=True, message=message)
            self.emit('job.progress')
            return {'stopRequested': True}
        if action == 'preview.create':
            return self.create_preview(params, session)
        if action == 'preview.discard':
            if not params.get('snapshotId') or (self.snapshot and params['snapshotId'] == self.preview_info()['snapshotId']):
                self.invalidate_preview()
            return {'discarded': True}
        if action == 'preview.query':
            info = self.preview_info()
            if params['snapshotId'] != info['snapshotId']:
                raise ProtocolError('STALE_PLAN', '预览已失效。')
            if self.execution:
                return self.execution.page(self.snapshot, params.get('offset', 0), params.get('limit', 20))
            start, limit = params.get('offset', 0), params.get('limit', 20)
            return {'items': [{'videoName': item.video.name, 'sourceName': item.source.name if item.source else '未关联字幕',
                'sourcePath': str(item.source or item.video), 'targetName': item.target.name if item.target else '—',
                'targetPath': str(item.target) if item.target else '—', 'action': item.action}
                for item in self.snapshot.items[start:start+limit]], 'itemCount': info['itemCount'], 'offset': start}
        if action == 'review.query' and self.data is None:
            if params['scanId'] is not None or params['revision'] != self.revision:
                raise ProtocolError('STALE_REVIEW', '扫描结果已变化。')
            return {'rows': [], 'ids': [], 'total': 0, 'counts': {'all': 0}, 'revision': self.revision}
        if action.startswith('review.'):
            data = self.require_review(params)
            if action in {'review.query', 'review.ids'}:
                result = data.query({**params, 'includeIds': True})
                if action == 'review.ids':
                    offset, limit = params.get('offset', 0), params.get('limit', 200)
                    return {'ids': result['ids'][offset:offset+limit], 'total': result['total'], 'offset': offset}
                result['ids'] = result['ids'][params.get('offset', 0):params.get('offset', 0)+len(result['rows'])]
                result['idsPaged'] = params.get('includeIds', True)
                result['offset'] = params.get('offset', 0)
                result['rows'] = [list_row(row) for row in result['rows']]
                return result
            index = data.index(params['rowId'])
            if action == 'review.details':
                return data.detail_header(index)
            if action == 'review.detailPage':
                return data.detail_page(index, params['section'], params.get('offset', 0), params.get('limit', 20))
            if action == 'review.candidates':
                return self.launch('candidates', lambda worker: data.candidates(index, params.get('offset', 0), params.get('limit', 6)),
                                   lambda value: value, '正在比较候选…')
            self.invalidate_preview()
            self.invalidate_online()
            def complete(result):
                value,draft = result
                self.draft_publish(draft)
                self.data, self.revision = value, value.revision
                return {'revision': value.revision}
            def work(worker):
                value = data.updated(action,params)
                return value,self.draft_capture(value,worker.stop.is_set)
            return self.launch('review',work,complete,'正在更新匹配…')
        if action == 'job.result':
            if params['jobId'] not in self.results:
                raise ProtocolError('NOT_FOUND', '任务结果已失效，请刷新。')
            value = self.results[params['jobId']]
            offset, limit = params.get('offset', 0), params.get('limit', 20)
            if isinstance(value, list):
                return {'shape': 'list', 'entries': value[offset:offset+limit], 'total': len(value), 'offset': offset}
            if isinstance(value, dict) and 'rows' in value:
                return {'shape': 'rows', 'meta': {k: v for k, v in value.items() if k != 'rows'},
                        'entries': value['rows'][offset:offset+limit], 'total': len(value['rows']), 'offset': offset}
            return {'shape': 'value', 'value': value}
        if action == 'history.list':
            def complete(records):
                legacy, modern = records
                self.records = {record['run_id']: record for record in legacy}
                merged = {value['recordId']: value for value in [*[record_meta(record) for record in legacy], *modern]}
                return sorted(merged.values(), key=lambda value: (value.get('needsRecovery', False), value['time']), reverse=True)[:params.get('limit', 30)]
            return self.launch('history', lambda worker: (self.history.recent(params.get('limit', 30)),
                self.execution.history(params.get('limit', 30)) if self.execution else []), complete, '正在读取记录…')
        if action in {'history.get', 'result.get'}:
            identifier = params.get('recordId') or params['batchId']
            if self.execution and self.execution.contains(identifier):
                return self.execution.record_page(identifier, params.get('offset', 0), params.get('limit', 20))
            if identifier not in self.records:
                raise ProtocolError('NOT_FOUND', '请先读取记录列表。')
            record = self.records[identifier]
            start, limit = params.get('offset', 0), params.get('limit', 20)
            return {**record_meta(record), 'offset': start, 'items': [
                {'source': Path(item.get('source') or item.get('video') or '').name,
                 'target': Path(item.get('target') or '').name, 'status': item.get('status'),
                 'state': item.get('status'), 'error': str(item.get('error', ''))[:200],
                 'sourcePath': item.get('source') or item.get('video'), 'targetPath': item.get('target') or ''}
                for item in record['items'][start:start+limit]]}
        raise ProtocolError('ACTION_UNAVAILABLE', '此入口不提供该操作。')


def list_row(row):
    embedded = row.get('embedded', {})
    accepted = set(embedded.get('acceptedTrackIds', []))
    shown_tracks = [track for track in embedded.get('tracks', []) if track['trackId'] in accepted][:2]
    return {key: row[key] for key in ('rowId', 'video', 'state', 'matchCount', 'subtitles', 'warnings', 'episode', 'embeddedSatisfied')} | {
        'video': {key: row['video'][key] for key in ('fileId', 'name', 'extension')},
        'subtitles': [{key: sub[key] for key in ('name', 'language', 'score')} for sub in row['subtitles'][:2]],
        'warnings': row['warnings'][:1], 'warningCount': len(row['warnings']),
        'embedded': {'tracks': [{'trackId': track['trackId'], 'language': track['language']} for track in shown_tracks],
                     'acceptedTrackIds': [track['trackId'] for track in shown_tracks],
                     'trackCount': len(embedded.get('tracks', [])), 'acceptedTrackCount': len(accepted)},
    }


def record_meta(record):
    counts = {status: sum(item.get('status') == status for item in record['items'])
              for status in ('success', 'skipped', 'error', 'blocked', 'unchanged', 'unmatched', 'cancelled')}
    source = next((item.get('video') for item in record['items'] if item.get('video')), '')
    return {'recordId': record['run_id'], 'title': Path(source).parent.name[:100], 'time': record.get('finished_at', ''),
            'success': counts['success'], 'skipped': counts['skipped'], 'errors': counts['error']+counts['blocked'],
            'unchanged': counts['unchanged'], 'unmatched': counts['unmatched'], 'cancelled': counts['cancelled'],
            'itemCount': len(record['items']), 'issue': str(record.get('issue', ''))[:200],
            'historyError': str(record.get('history_error', ''))[:200]}
