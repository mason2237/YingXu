"""Subtitle download/import orchestration. No browser, network or file API here."""
from dataclasses import asdict
from pathlib import Path

from ..domain.errors import ProtocolError
from ..domain.models import SubtitlePhase
from ..ports.subtitle_artifacts import SubtitleArtifacts
from .reviewing import ReviewData


class Downloads:
    def __init__(self, workspace, discovery, artifacts: SubtitleArtifacts, send):
        self.workspace, self.discovery, self.artifacts, self.send = workspace, discovery, artifacts, send
        self.queue = []
        self.armed = None
        self.receiving = None
        self.current = None
        self.paused = []
        self.maintenance_checked = False

    def protected(self):
        values=self.workspace.execution.journal.referenced_paths()
        if self.workspace.data: values+=list(self.workspace.data.review.subtitles)
        if self.workspace.drafts:
            saved=self.workspace.drafts.store.load('workspace')
            if saved:values += [item['path'] for item in saved['files']]
        return values

    def maintain_idle(self):
        if self.maintenance_checked or self.workspace.busy or self.queue or self.armed or self.current or self.receiving:return
        self.maintenance_checked=True
        if self.artifacts.maintenance_due():
            protected=self.protected()
            self.workspace.launch('cache_cleanup',lambda worker:self.artifacts.maintain(protected,worker.stop.is_set),
                lambda result:result,'正在释放超过 30 天且无引用的导入缓存…')

    def invalidate(self):
        self.queue.clear()
        self.paused.clear()
        self.armed = None
        self.send({'type': 'browser.disarm'})
        if self.receiving:
            self.artifacts.update(self.receiving, status='interrupted', message='页面已关闭或变化；暂存内容未导入。')
            self.receiving = None
        if self.current and self.workspace.worker:
            self.workspace.worker.stop.set()

    def confirm(self, params):
        self.workspace.require_idle()
        if params['acknowledged'] is not True:
            raise ProtocolError('CONFIRMATION_REQUIRED', '请先确认候选再下载。')
        if self.queue or self.armed or self.current or self.receiving:
            raise ProtocolError('BUSY', '请先完成或取消当前下载队列。')
        ids = params.get('taskIds') or [params['taskId']]
        if len(set(ids)) != len(ids) or not 1 <= len(ids) <= 20:
            raise ProtocolError('INVALID_REQUEST', '每批最多确认 20 份不同字幕。')
        tasks = [self.discovery.get(identifier)[0] for identifier in ids]
        if any(task.phase != SubtitlePhase.SELECTED for task in tasks):
            raise ProtocolError('INVALID_TRANSITION', '请为每个视频明确选择候选；未选择项不会下载。')
        for task in tasks:
            self.discovery.command(task, 'confirm_download', {'acknowledged': True})
            self.queue.append(task.task_id)
        self.advance()
        return {'queued': len(ids)}

    def advance(self):
        if self.armed or self.receiving or self.current or self.workspace.busy: return
        while self.queue:
            identifier = self.queue.pop(0)
            try:
                task, entry = self.discovery.get(identifier)
                if task.phase != SubtitlePhase.DOWNLOADING:
                    continue
                retained = next((record for record in self.artifacts.list()
                    if record['association']['taskId']==identifier and not record['imported'] and record['status'] in {'ready','interrupted'}),None)
                if retained and (retained['status']=='ready' or not retained['blob']):
                    self.start(retained['id'],task,ready=retained['status']=='ready')
                    return
                row = next(row for row in entry['candidates'] if row['candidateId'] == task.data['selected_candidate_id'])
                self.armed = (identifier, task.active_effect_id, self.discovery.generation)
                self.discovery.persist()
                self.send({'type': 'browser.arm', 'taskId': identifier, 'effectId': task.active_effect_id,
                           'generation': self.discovery.generation, 'url': self.discovery.provider.url(row, entry['provider']),
                           'hosts': self.discovery.provider.plan(entry['query'], entry['provider'])['hosts'],
                           'downloadScript':self.discovery.provider.download(row,entry['provider'])})
                return
            except (ProtocolError, StopIteration):
                continue
        self.armed = None
        self.discovery.persist()

    def cancel(self, identifier):
        self.queue = [value for value in self.queue if value != identifier]
        self.paused = [value for value in self.paused if value != identifier]
        if self.armed and self.armed[0] == identifier:
            self.armed = None
            self.send({'type': 'browser.disarm'})
            if self.receiving:
                self.artifacts.update(self.receiving, status='interrupted', message='下载已取消；没有导入。')
                self.receiving = None
            self.advance()
        if self.current and self.current[1] == identifier and self.workspace.worker:
            self.workspace.worker.stop.set()

    def browser_failed(self, frame):
        if self.armed != (frame['taskId'], frame['effectId'], frame['generation']):
            return False
        task = self.discovery.workflow.get_task(frame['taskId'])
        self.discovery.command(task, 'interrupt', {'reason': frame['message'][:200]}, internal=True)
        self.armed = None
        if self.receiving:
            self.artifacts.update(self.receiving, status='interrupted', message=frame['message'][:200])
            self.receiving = None
        self.advance()
        self.workspace.emit('online.changed')
        return True

    def offer(self, frame):
        ticket = (frame['taskId'], frame['effectId'], frame['generation'])
        if ticket != self.armed or self.receiving or self.current:
            return False
        self.workspace.require_idle()
        task, entry = self.discovery.get(frame['taskId'])
        if task.phase != SubtitlePhase.DOWNLOADING or task.active_effect_id != frame['effectId']:
            return False
        data = self.workspace.data
        video = data.review.rows[data.index(entry['rowId'])].video
        association = {'taskId': task.task_id, 'provider': entry['provider'], 'video': str(video),
                       'mark': asdict(self.workspace.fs.file_mark(video)), 'language': self.discovery.language}
        record = self.artifacts.reserve(frame, association)
        if record['blob']:
            self.receiving = record['id']
            self.send({'type': 'browser.accept', 'offerId': frame['offerId'], 'artifactId': record['id'],
                       'path': str(self.artifacts.path(record['id']))})
        else:
            self.armed = None
            self.start(record['id'], task, headers=frame.get('headers'))
        self.workspace.emit('online.changed')
        return True

    def blob_result(self, frame):
        identifier = frame['artifactId']
        if identifier != self.receiving or not self.armed:
            return False
        task = self.discovery.workflow.get_task(self.armed[0])
        if task.active_effect_id != self.armed[1] or task.phase != SubtitlePhase.DOWNLOADING:
            return False
        self.receiving, self.armed = None, None
        if frame['status'] != 'completed':
            self.artifacts.update(identifier, status='interrupted', message='网站生成的下载未完成，请重新获取。')
            self.discovery.command(task, 'interrupt', {'reason': '网站生成的下载未完成，不能跨会话续传。'}, internal=True)
            self.advance()
            self.workspace.emit('online.changed')
        else:
            self.start(identifier, task, blob=True)
        return True

    def start(self, identifier, task, *, headers=None, blob=False, ready=False):
        workspace = self.workspace
        self.current = (identifier, task.task_id, task.active_effect_id)
        ticket = self.current
        def work(worker):
            try:
                if ready:
                    return self.artifacts.prepared(identifier),None
                if not blob:
                    self.artifacts.transfer(identifier, worker.stop.is_set, worker.report, headers)
                return self.artifacts.prepare(identifier, worker.stop.is_set), None
            except Exception as error:
                self.artifacts.update(identifier, status='interrupted', message=str(error)[:200])
                return None, str(error)[:200]
        def complete(result):
            self.current = None
            latest = self.discovery.workflow.get_task(task.task_id)
            if latest.phase == SubtitlePhase.DOWNLOADING and latest.active_effect_id == ticket[2]:
                if result[1]:
                    self.discovery.command(latest, 'interrupt', {'reason': result[1]}, internal=True)
                else:
                    for action in ('downloaded', 'verified', 'prepared'):
                        latest = self.discovery.command(latest, action, {'artifact_id': identifier}, internal=True)
            workspace.emit('online.changed')
            # The next browser navigation is safe while the completed worker unwinds.
            return {'artifactId': identifier, 'ready': not result[1], 'message': result[1] or '已准备好，等待导入审阅。'}
        return workspace.launch('download', work, complete, '正在下载并检查字幕内容…', publish_cancelled=True)

    def dispatch(self, action, params):
        if action == 'online.download':
            return self.confirm(params)
        if action == 'online.resumeQueue':
            if params['acknowledged'] is not True:
                raise ProtocolError('CONFIRMATION_REQUIRED','继续队列需要重新确认。')
            ids = list(self.paused)
            if not ids: raise ProtocolError('NOT_FOUND','没有等待继续的下载队列。')
            if self.queue or self.armed or self.current or self.receiving:
                raise ProtocolError('BUSY','已有下载任务。')
            self.workspace.require_idle()
            for identifier in ids:
                task,_entry = self.discovery.get(identifier)
                if task.phase in {SubtitlePhase.INTERRUPTED,SubtitlePhase.FAILED,SubtitlePhase.CANCELLED}:
                    self.discovery.command(task,'resume_download',{'acknowledged':True})
                    self.queue.append(identifier)
                elif task.phase == SubtitlePhase.DOWNLOADING:
                    self.queue.append(identifier)
            self.paused.clear();self.discovery.persist();self.advance()
            return {'queued':len(self.queue)+(1 if self.armed else 0)}
        if action == 'online.downloads':
            rows = self.artifacts.list()
            values = [{'artifactId': row['id'], 'name': row['filename'], 'videoName': Path(row['association']['video']).name,
                       'status': row['status'], 'message': row['message'], 'imported': row['imported'],
                       'canResume': not row['blob'] and row['status'] == 'interrupted',
                       'fileCount': len(row['prepared'])} for row in rows]
            offset, limit = params.get('offset', 0), params.get('limit', 10)
            return {'rows': values[offset:offset+limit], 'total': len(values), 'offset': offset}
        self.workspace.require_idle()
        if params.get('acknowledged') is not True:
            raise ProtocolError('CONFIRMATION_REQUIRED', '此操作需要明确确认。')
        if action == 'online.retryDownload':
            if self.current or self.receiving or self.armed:
                raise ProtocolError('BUSY', '已有下载任务。')
            record = self.artifacts.get(params['artifactId'])
            if record['status'] != 'interrupted' or record['imported']:
                raise ProtocolError('INVALID_TRANSITION', '这份下载不需要重试。')
            if record['blob']:
                return self.reject_blob()
            task = self.discovery.workflow.get_task(record['association']['taskId'])
            task = self.discovery.command(task, 'resume_download', {'acknowledged': True})
            return self.start(record['id'], task, blob=record['blob']) if not record['blob'] else self.reject_blob()
        if action == 'online.discardDownload':
            return self.artifacts.discard(params['artifactId'], self.protected())
        if action == 'online.compactDownload':
            protected=self.protected()
            return self.workspace.launch('cache_cleanup',lambda worker:self.artifacts.compact(params['artifactId'],protected,worker.stop.is_set),
                lambda result:result,'正在释放可回收缓存，保留恢复与撤销所需文件…')
        if action == 'online.import':
            return self.import_ready(params)
        raise ProtocolError('ACTION_UNAVAILABLE', '此下载操作未开放。')

    @staticmethod
    def reject_blob():
        raise ProtocolError('MANUAL_REQUIRED', '网站生成的 blob 不能跨会话恢复，请在网站重新获取。')

    def import_ready(self, params):
        data = self.workspace.data
        if not data:
            raise ProtocolError('STALE_REVIEW', '请先扫描原视频目录，再导入暂存字幕。')
        identifiers = params['artifactIds']
        if not 1 <= len(identifiers) <= 20 or len(set(identifiers)) != len(identifiers):
            raise ProtocolError('INVALID_REQUEST', '每次最多导入 20 份不同下载。')
        generation, session = self.discovery.generation, self.workspace.session_id
        def work(worker):
            entries = []
            for identifier in identifiers:
                record = self.artifacts.get(identifier)
                association = record['association']
                if record['imported']:
                    raise ProtocolError('ALREADY_IMPORTED', '这份下载已导入；如需恢复整理，请使用历史记录。')
                indices = [i for i, row in enumerate(data.review.rows) if str(row.video) == association['video']]
                if len(indices) != 1 or asdict(self.workspace.fs.file_mark(Path(association['video']))) != association['mark']:
                    raise ProtocolError('STALE_REVIEW', '原视频不在本次扫描中或身份已变化，未自动关联。')
                index = indices[0]
                if data.review.rows[index].uses_embedded:
                    raise ProtocolError('ALREADY_SATISFIED', '视频内字幕已满足语言要求，无需导入外挂字幕。')
                for path in self.artifacts.prepared(identifier):
                    entries.append((path, {'rowIndex': index, 'artifactId': identifier}))
            review = data.review.fork()
            assigned = review.add_imports(entries)
            updated = ReviewData(review, data.register, scan_id=data.scan_id, revision=data.revision+1, warnings=data.scan_warnings)
            return updated, assigned, self.workspace.draft_capture(updated,worker.stop.is_set)
        def complete(value):
            if self.workspace.data is not data or generation != self.discovery.generation or session != self.workspace.session_id:
                raise ProtocolError('STALE_REVIEW', '页面或审阅已变化；暂存字幕保留，未关联。')
            self.workspace.draft_publish(value[2])
            for identifier in identifiers:
                self.artifacts.update(identifier, imported=True, message='已导入待审阅；最终整理仍需预览确认。')
            self.workspace.invalidate_preview()
            self.workspace.data, self.workspace.revision = value[0], value[0].revision
            self.discovery.invalidate()
            self.workspace.emit('review.changed')
            return {'imported': len(identifiers), 'assigned': value[1], 'revision': value[0].revision}
        return self.workspace.launch('import', work, complete, '正在核对缓存并导入待审阅候选…')
