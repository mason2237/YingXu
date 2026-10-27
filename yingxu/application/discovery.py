"""One authority for browser-assisted search. Views only send commands/facts."""
import json
from uuid import uuid4

from ..domain.errors import ProtocolError
from ..domain.models import ACTIVE_PHASES, SubtitlePhase, WorkflowCommand, WorkflowError, canonical_json
from ..ports.browser_provider import BrowserProvider
from ..ports.workspace import Settings
from .subtitles import SubtitleWorkflow


class Discovery:
    def __init__(self, workspace, workflow: SubtitleWorkflow, provider: BrowserProvider, send, settings: Settings):
        self.workspace, self.workflow, self.provider, self.send = workspace, workflow, provider, send
        self.entries = {}
        self.active = None
        self.generation = 0
        self.downloads = None
        self.page_pending = None
        self.restore_pending = True
        self.settings = settings
        self.language = settings.read().get('language', 'bilingual')
        if self.language not in {'bilingual', 'zh-Hans', 'zh-Hant', 'en'}:
            self.language = 'bilingual'

    def command(self, task, action, params=None, *, command_id=None, internal=False):
        try:
            return self.workflow.dispatch(WorkflowCommand(
                command_id or uuid4().hex, task.task_id, action, task.revision,
                task.workspace_id, task.review_revision, canonical_json(params or {}),
                task.active_effect_id if internal else None)).task
        except WorkflowError as error:
            raise ProtocolError(error.code, error.message) from error

    def invalidate(self):
        self.generation += 1
        self.page_pending = None
        if self.downloads:
            self.downloads.invalidate()
        if self.active:
            self.send({'type': 'browser.stop', 'generation': self.generation})
        for identifier in self.entries:
            task = self.workflow.get_task(identifier)
            if task.phase not in {SubtitlePhase.CANCELLED, SubtitlePhase.REVIEW_READY}:
                self.command(task, 'cancel')
        self.entries.clear()
        self.active = None
        self.restore_pending = False
        if self.workspace.drafts: self.workspace.drafts.store.clear('online')

    def persist(self):
        if not self.workspace.drafts or (self.restore_pending and not self.entries): return
        if not self.entries:
            self.workspace.drafts.store.clear('online');return
        downloads = self.downloads
        pending = list(downloads.paused)+list(downloads.queue) if downloads else []
        if downloads and downloads.armed: pending.insert(0,downloads.armed[0])
        if downloads and downloads.current: pending.insert(0,downloads.current[1])
        self.workspace.drafts.store.save('online',{'v':1,'entries':self.entries,'generation':self.generation,
            'pending':list(dict.fromkeys(pending))})

    def suspend(self):
        if self.restore_pending and not self.entries: return
        downloads = self.downloads
        pending = list(downloads.paused)+list(downloads.queue) if downloads else []
        if downloads and downloads.armed: pending.insert(0,downloads.armed[0])
        if downloads and downloads.current: pending.insert(0,downloads.current[1])
        self.generation += 1
        self.active = self.page_pending = None
        self.send({'type':'browser.stop','generation':self.generation})
        if downloads:
            downloads.invalidate()
            downloads.paused = list(dict.fromkeys(pending))
        for identifier in self.entries:
            task = self.workflow.get_task(identifier)
            if task.phase in ACTIVE_PHASES:
                self.command(task,'interrupt',{'reason':'页面或应用已关闭；草稿保留，需要明确继续。'},internal=True)
        self.persist()

    def restore(self):
        if not self.workspace.drafts: return
        saved = self.workspace.drafts.store.load('online')
        self.restore_pending = False
        if not saved: return
        restored = {}
        for identifier,entry in saved['entries'].items():
            task = self.workflow.get_task(identifier)
            data = self.workspace.data
            if (task.workspace_id,task.review_revision)!=(data.scan_id,data.revision): continue
            if len(entry['candidates'])>20: raise ProtocolError('CORRUPT_CHECKPOINT','候选清单超过限制。')
            data.index(entry['rowId'])
            for candidate in entry['candidates']: self.provider.url(candidate,entry['provider'])
            restored[identifier] = entry
        self.entries = restored
        self.generation = max(self.generation,saved['generation'])+1
        if self.downloads:
            pending = [identifier for identifier in saved['pending'] if identifier in restored]
            # A crash between a task commit and queue checkpoint is still visible.
            pending += [identifier for identifier in restored if self.workflow.get_task(identifier).data.get('interrupted_from')=='downloading']
            self.downloads.paused = [identifier for identifier in dict.fromkeys(pending)
                if self.workflow.get_task(identifier).phase not in {SubtitlePhase.REVIEW_READY,SubtitlePhase.CANCELLED}]
        self.persist()

    def open(self, params):
        data = self.workspace.require_review(params)
        if self.entries and (not params.get('rowId') or any(entry['rowId']==params['rowId'] for entry in self.entries.values())):
            for identifier in self.entries: self.get(identifier)
            return {'opened':True,'taskCount':len(self.entries),'remaining':0,'restored':True}
        indices = [data.index(params['rowId'])] if 'rowId' in params else [
            index for index, row in enumerate(data.review.rows)
            if not row.matches and not row.skipped and not row.uses_embedded]
        if not indices:
            raise ProtocolError('NOT_FOUND', '没有需要查找字幕的视频。')
        if any(data.review.rows[index].uses_embedded for index in indices):
            raise ProtocolError('ALREADY_SATISFIED', '视频内字幕已满足语言要求；请先改为仍需外挂。')
        self.invalidate()
        for index in indices[:200]:
            row = data.rows[index]
            task = self.workflow.create_task(data.scan_id, data.revision)
            self.entries[task.task_id] = {'rowId': row['rowId'], 'videoName': row['video']['name'],
                                          'query': '', 'provider': 'zimuku', 'candidates': []}
        return {'opened': True, 'taskCount': len(self.entries), 'remaining': max(0, len(indices)-200)}

    def get(self, identifier):
        if identifier not in self.entries:
            raise ProtocolError('STALE_REVIEW', '搜索任务已失效，请从工作区重新打开。')
        task = self.workflow.get_task(identifier)
        data = self.workspace.data
        if not data or (task.workspace_id, task.review_revision) != (data.scan_id, data.revision):
            raise ProtocolError('STALE_REVIEW', '工作区审阅已变化，搜索结果不再关联。')
        return task, self.entries[identifier]

    def query(self, offset=0, limit=20):
        values = []
        for identifier, entry in list(self.entries.items())[offset:offset+limit]:
            task, _ = self.get(identifier)
            values.append({'taskId': identifier, 'rowId': entry['rowId'], 'videoName': entry['videoName'],
                           'query': entry['query'], 'provider': entry['provider'], 'phase': task.phase.value,
                           'reason': task.data.get('reason', ''), 'candidateCount': len(entry['candidates'])})
        return {'tasks': values, 'offset': offset, 'total': len(self.entries), 'downloadAvailable': self.downloads is not None,
                'language': self.language, 'pausedCount':len(self.downloads.paused) if self.downloads else 0}

    def dispatch(self, action, params, request_id):
        if action == 'online.query':
            return self.query(params.get('offset', 0), params.get('limit', 20))
        if self.downloads and action in {'online.download', 'online.downloads', 'online.retryDownload', 'online.discardDownload', 'online.compactDownload', 'online.import', 'online.resumeQueue'}:
            return self.downloads.dispatch(action, params)
        if action not in {'online.cancel', 'online.candidates'}:
            self.workspace.require_idle()
        if self.downloads and (self.downloads.armed or self.downloads.receiving or self.downloads.current or self.downloads.queue) and action in {'online.start', 'online.select', 'online.openCandidate', 'online.usePage'}:
            raise ProtocolError('BUSY', '请先完成或取消已确认的下载队列，再更换候选。')
        if action == 'online.configure':
            self.settings.write(params)
            self.language = params['language']
            return {'language': self.language}
        task, entry = self.get(params['taskId'])
        if action == 'online.usePage':
            if task.phase not in {SubtitlePhase.AWAITING_USER, SubtitlePhase.NO_RESULTS, SubtitlePhase.CANDIDATES_READY, SubtitlePhase.SELECTED}:
                raise ProtocolError('INVALID_TRANSITION', '请先打开并核对网站结果页。')
            task = self.command(task, 'capture_page', command_id=request_id)
            self.page_pending = (task.task_id, task.revision, self.generation)
            self.send({'type': 'browser.capture', 'taskId': task.task_id, 'effectId': task.active_effect_id, 'generation': self.generation})
            return {'pending': True}
        if action == 'online.candidates':
            offset, limit = params.get('offset', 0), params.get('limit', 6)
            rows = [{key: value for key, value in row.items() if key != 'url'} for row in entry['candidates']]
            return {'rows': rows[offset:offset+limit], 'offset': offset, 'total': len(rows)}
        if action == 'online.start':
            if self.active:
                raise ProtocolError('BUSY', '请先完成或取消当前网站搜索。')
            query = params['query'].strip()
            if not query:
                raise ProtocolError('INVALID_REQUEST', '请先核对电影或剧集名称。')
            plan = self.provider.plan(query, params['provider'])
            resume = task.phase == SubtitlePhase.AWAITING_USER and query == entry['query'] and params['provider'] == entry['provider']
            task = self.command(task, 'resume' if resume else 'search',
                                None if resume else {'query': query, 'provider_id': params['provider']}, command_id=request_id)
            entry.update(query=query, provider=params['provider'], language=self.language, candidates=[])
            self.active = (task.task_id, task.active_effect_id)
            self.send({'type': 'browser.search', 'taskId': task.task_id, 'effectId': task.active_effect_id,
                       'generation': self.generation, 'resume': resume, 'plan': plan})
            return {'phase': task.phase.value}
        if action == 'online.cancel':
            self.command(task, 'cancel', command_id=request_id)
            if self.downloads:
                self.downloads.cancel(task.task_id)
            if self.active and self.active[0] == task.task_id:
                self.active = None
                self.send({'type': 'browser.stop', 'generation': self.generation})
            return {'cancelled': True}
        if action in {'online.select', 'online.openCandidate'}:
            candidate = next((row for row in entry['candidates'] if row['candidateId'] == params['candidateId']), None)
            if not candidate:
                raise ProtocolError('NOT_FOUND', '候选不属于此搜索任务。')
            task = self.command(task, 'select', {'candidate_id': params['candidateId']}, command_id=request_id)
            if action == 'online.openCandidate':
                self.send({'type': 'browser.open', 'url': self.provider.url(candidate, entry['provider']),
                           'provider': entry['provider'], 'generation': self.generation,
                           'hosts': self.provider.plan(entry['query'], entry['provider'])['hosts']})
            return {'phase': task.phase.value}
        raise ProtocolError('ACTION_UNAVAILABLE', '此搜索操作未开放。')

    def page_result(self, frame):
        task, entry = self.get(frame['taskId'])
        if self.page_pending != (task.task_id, task.revision, frame['generation']) or frame['generation'] != self.generation or frame['effectId'] != task.active_effect_id:
            return False
        self.page_pending = None
        url = self.provider.url({'url': frame['url']}, entry['provider'])
        candidate = {'candidateId': uuid4().hex, 'url': url, 'title': frame['title'][:150] or '手动核对页面',
                     'release': frame['title'][:150], 'language': '需核对', 'score': 0,
                     'reasons': ['你选择了网站当前页面'], 'warnings': ['网站内容尚未验证，版本和语言需人工审阅']}
        # No active external effect is being completed here: this is a separately
        # authorized capture, bound to the task revision and browser generation.
        self.command(task, 'manual_result', {'candidates': [{'candidate_id': candidate['candidateId'],
                     'provider_id': entry['provider'], 'title': candidate['title']}]}, internal=True)
        entry['candidates'] = [candidate]
        self.workspace.emit('online.changed')
        return True

    def browser_result(self, frame):
        if (frame['generation'] != self.generation or
                self.active != (frame['taskId'], frame['effectId'])):
            return False
        task, entry = self.get(frame['taskId'])
        status = frame['status']
        if status in {'manual', 'failed'}:
            self.command(task, 'needs_user' if status == 'manual' else 'fail',
                         {'reason': frame.get('message', '请在网站完成必要验证，再继续搜索。')[:200]}, internal=True)
            self.active = None
        else:
            parsed, rows = self.provider.results(frame.get('raw', '{}'), entry['provider'], entry['videoName'], entry.get('language', 'bilingual'))
            for row in rows:
                if len(entry['candidates']) >= 20:
                    break
                if any(old['url'] == row['url'] for old in entry['candidates']):
                    continue
                entry['candidates'].append({**row, 'candidateId': uuid4().hex})
            if frame.get('final'):
                if parsed not in {'ready', 'empty'} and not entry['candidates']:
                    self.command(task, 'needs_user', {'reason': '该页面暂不支持自动候选解析，请在网站浏览核对。'}, internal=True)
                else:
                    values = [{'candidate_id': row['candidateId'], 'provider_id': entry['provider'],
                               'title': row['title'][:150] or row['release'][:150],
                               'language': row['language'][:80], 'release': row['release'][:100]}
                              for row in entry['candidates']]
                    self.command(task, 'results', {'candidates': values}, internal=True)
                self.active = None
        self.workspace.emit('online.changed')
        return True
