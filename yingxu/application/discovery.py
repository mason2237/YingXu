"""One authority for browser-assisted search. Views only send commands/facts."""
import json
import time
import random
from uuid import uuid4

from ..domain.errors import ProtocolError
from ..domain.models import ACTIVE_PHASES, SubtitlePhase, WorkflowCommand, WorkflowError, canonical_json
from ..ports.browser_provider import BrowserProvider
from ..ports.workspace import Settings
from ..domain.provider_policy import classify,retry_delay,public_retry
from .subtitles import SubtitleWorkflow


class Discovery:
    def __init__(self, workspace, workflow: SubtitleWorkflow, provider: BrowserProvider, send, settings: Settings, *, clock=time.time, jitter=random.random):
        self.workspace, self.workflow, self.provider, self.send = workspace, workflow, provider, send
        self.entries = {}
        self.active = None
        self.generation = 0
        self.downloads = None
        self.page_pending = None
        self.restore_pending = True
        self.settings = settings
        self.clock,self.jitter=clock,jitter
        self.disabled=set();self.last_sent={}
        if workspace.drafts:
            saved=workspace.drafts.store.load('provider-stops')
            if saved and isinstance(saved.get('providers'),list):
                self.disabled={p for p in saved['providers'] if p in {'zimuku','srtku','subhd','subhd-one'}}
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
            if 'retry' in self.entries[identifier]:self.entries[identifier]['retry'].update(paused=True,nextAttempt=None)
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
            if 'retry' in self.entries[identifier]:self.entries[identifier]['retry'].update(paused=True,nextAttempt=None)
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
            if 'retry' in entry:entry['retry'].update(paused=True,nextAttempt=None)
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
        if params.get('needsId'):self.workspace.needs.require(data,params['needsId'])
        indices = [data.index(params['rowId'])] if 'rowId' in params else self.workspace.needs.missing_indices(data)
        if not indices:
            raise ProtocolError('NOT_FOUND', '没有需要查找字幕的视频。')
        if any(data.review.rows[index].uses_embedded and not self.workspace.needs.has_missing(data,index) for index in indices):
            raise ProtocolError('ALREADY_SATISFIED', '视频内字幕已满足语言要求；请先改为仍需外挂。')
        eligible={data.rows[index]['rowId'] for index in indices}
        if self.entries and (params.get('rowId') and any(entry['rowId']==params['rowId'] for entry in self.entries.values())
                or not params.get('rowId') and {entry['rowId'] for entry in self.entries.values()}<=eligible):
            for identifier in self.entries:self.get(identifier)
            return {'opened':True,'taskCount':len(self.entries),'remaining':0,'restored':True}
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
                           'reason': task.data.get('reason', ''), 'candidateCount': len(entry['candidates']),
                           'selectedCandidateId': task.data.get('selected_candidate_id'),
                           'retry':public_retry(entry.get('retry',{})), 'providerStopped':entry['provider'] in self.disabled})
        return {'tasks': values, 'offset': offset, 'total': len(self.entries), 'downloadAvailable': self.downloads is not None,
                'language': self.language, 'pausedCount':len(self.downloads.paused) if self.downloads else 0,
                'downloadBusy': bool(self.downloads and self.downloads.busy),
                'stoppedProviders':sorted(self.disabled),'capabilities':{'remoteLocalFiles':False,'apiCredentialsRequired':False,'searchConcurrency':1,'automaticRetryLimit':3}}

    def dispatch(self, action, params, request_id):
        if action=='online.provider':
            self.workspace.require_idle()
            if params['enabled']:self.disabled.discard(params['provider'])
            else:
                self.disabled.add(params['provider'])
                for identifier,entry in self.entries.items():
                    if entry['provider']==params['provider']:
                        if 'retry' in entry:entry['retry'].update(paused=True,nextAttempt=None)
                        if self.active and self.active[0]==identifier:
                            task=self.workflow.get_task(identifier);self.command(task,'interrupt',{'reason':'来源已暂停。'},internal=True)
                            self.active=None;self.send({'type':'browser.stop','generation':self.generation})
            if self.workspace.drafts:self.workspace.drafts.store.save('provider-stops',{'v':1,'providers':sorted(self.disabled)})
            self.persist();return {'provider':params['provider'],'enabled':params['enabled']}
        if action == 'online.query':
            return self.query(params.get('offset', 0), params.get('limit', 20))
        if self.downloads and action in {'online.download', 'online.downloads', 'online.retryDownload', 'online.discardDownload', 'online.compactDownload', 'online.import', 'online.resumeQueue',
                'online.qualityFiles','online.quality','online.qualityResult','online.qualityPage'}:
            return self.downloads.dispatch(action, params)
        if action not in {'online.cancel', 'online.candidates'}:
            self.workspace.require_idle()
        if self.downloads and self.downloads.busy and action in {'online.start', 'online.select', 'online.openCandidate', 'online.usePage'}:
            raise ProtocolError('BUSY', '请先完成或取消已确认的下载队列，再更换候选。')
        if action == 'online.configure':
            self.settings.write(params)
            self.language = params['language']
            return {'language': self.language}
        task, entry = self.get(params['taskId'])
        if action == 'online.usePage':
            if self.active or task.phase not in {SubtitlePhase.AWAITING_USER, SubtitlePhase.NO_RESULTS, SubtitlePhase.CANDIDATES_READY, SubtitlePhase.SELECTED}:
                raise ProtocolError('INVALID_TRANSITION', '请先打开并核对网站结果页。')
            download = params.get('acknowledged', False)
            if download and (not self.downloads or entry['provider'] in self.disabled):
                raise ProtocolError('PROVIDER_STOPPED', '请先恢复字幕来源。')
            task = self.command(task, 'capture_page', command_id=request_id)
            self.page_pending = (task.task_id, task.revision, self.generation, download)
            self.send({'type': 'browser.capture', 'taskId': task.task_id, 'effectId': task.active_effect_id, 'generation': self.generation})
            return {'pending': True}
        if action == 'online.candidates':
            offset, limit = params.get('offset', 0), params.get('limit', 6)
            rows = [{key: value for key, value in row.items() if key != 'url'} for row in entry['candidates']]
            return {'rows': rows[offset:offset+limit], 'offset': offset, 'total': len(rows)}
        if action == 'online.start':
            if params['provider'] in self.disabled:raise ProtocolError('PROVIDER_STOPPED','此来源已暂停，请先恢复来源。')
            retry=entry.get('retry',{})
            if retry.get('nextAttempt') and retry['nextAttempt']>self.clock():raise ProtocolError('RATE_LIMITED','来源仍在退避等待，请稍后继续。')
            if self.active:
                raise ProtocolError('BUSY', '请先完成或取消当前网站搜索。')
            query = params['query'].strip()
            if not query:
                raise ProtocolError('INVALID_REQUEST', '请先核对电影或剧集名称。')
            plan = self.provider.plan(query, params['provider'])
            resume = task.phase == SubtitlePhase.AWAITING_USER and query == entry['query'] and params['provider'] == entry['provider']
            if task.phase == SubtitlePhase.CANCELLED:
                previous_id = task.task_id
                task = self.workflow.create_task(task.workspace_id, task.review_revision)
                self.entries = {task.task_id if key == previous_id else key: value for key, value in self.entries.items()}
            task = self.command(task, 'resume' if resume else 'search',
                                None if resume else {'query': query, 'provider_id': params['provider']}, command_id=request_id)
            entry.update(query=query, provider=params['provider'], language=self.language, candidates=[])
            entry['retry']={'attempt':0,'nextAttempt':None,'error':None,'paused':False}
            self.last_sent[params['provider']]=self.clock()
            self.active = (task.task_id, task.active_effect_id)
            self.send({'type': 'browser.search', 'taskId': task.task_id, 'effectId': task.active_effect_id,
                       'generation': self.generation, 'resume': resume, 'plan': plan})
            return {'phase': task.phase.value, 'taskId': task.task_id}
        if action == 'online.cancel':
            if 'retry' in entry:entry['retry'].update(paused=True,nextAttempt=None)
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
        if (not self.page_pending or self.page_pending[:3] != (task.task_id, task.revision, frame['generation'])
                or frame['generation'] != self.generation or frame['effectId'] != task.active_effect_id):
            return False
        download = self.page_pending[3]
        self.page_pending = None
        try:
            url = self.provider.url({'url': frame['url']}, entry['provider'])
        except ProtocolError:
            self.command(task, 'interrupt', {'reason': '请先在右侧打开这个来源的字幕详情或下载页。'}, internal=True)
            self.workspace.emit('online.changed')
            return False
        candidate = {'candidateId': uuid4().hex, 'url': url, 'title': frame['title'][:150] or '手动核对页面',
                     'release': frame['title'][:150], 'language': '需核对', 'score': 0,
                     'reasons': ['你选择了网站当前页面'], 'warnings': ['网站内容尚未验证，版本和语言需人工审阅']}
        # No active external effect is being completed here: this is a separately
        # authorized capture, bound to the task revision and browser generation.
        self.command(task, 'manual_result', {'candidates': [{'candidate_id': candidate['candidateId'],
                     'provider_id': entry['provider'], 'title': candidate['title']}]}, internal=True)
        entry['candidates'] = [candidate]
        if download:
            self.downloads.confirm({'taskIds': [task.task_id], 'acknowledged': True})
        self.workspace.emit('online.changed')
        return True

    def browser_result(self, frame):
        if (frame['generation'] != self.generation or
                self.active != (frame['taskId'], frame['effectId'])):
            return False
        task, entry = self.get(frame['taskId'])
        status = frame['status']
        if status in {'manual', 'failed'}:
            task=self.command(task, 'needs_user' if status == 'manual' else 'fail',
                         {'reason': frame.get('message', '请在网站完成必要验证，再继续搜索。')[:200]}, internal=True)
            self.active = None
            kind='manual' if status=='manual' else classify(frame.get('statusCode'),frame.get('errorClass'))
            retry=entry.setdefault('retry',{'attempt':0})
            delay=retry_delay(kind,retry['attempt'],self.clock(),frame.get('retryAfter'),self.jitter())
            retry.update(error=kind,nextAttempt=self.clock()+delay if delay is not None else None,
                         revision=task.revision,paused=delay is None)
            self.persist()
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

    def tick(self):
        if self.active or self.workspace.busy or self.workspace.session_id is None:return
        if self.downloads and (self.downloads.current or self.downloads.armed or self.downloads.queue or self.downloads.receiving):return
        for identifier,entry in self.entries.items():
            retry=entry.get('retry',{});due=retry.get('nextAttempt')
            if retry.get('paused') or due is None or due>self.clock() or entry['provider'] in self.disabled:continue
            task,_=self.get(identifier)
            if task.phase!=SubtitlePhase.FAILED or task.revision!=retry.get('revision'):
                retry.update(paused=True,nextAttempt=None);continue
            if self.clock()<self.last_sent.get(entry['provider'],0)+2:continue
            plan=self.provider.plan(entry['query'],entry['provider'])
            task=self.command(task,'search',{'query':entry['query'],'provider_id':entry['provider']})
            retry.update(attempt=retry['attempt']+1,nextAttempt=None)
            self.active=(task.task_id,task.active_effect_id);self.last_sent[entry['provider']]=self.clock()
            self.persist()
            self.send({'type':'browser.search','taskId':task.task_id,'effectId':task.active_effect_id,
                       'generation':self.generation,'resume':False,'plan':plan})
            self.workspace.emit('online.changed');return
