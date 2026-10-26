"""Workspace-owned lifecycle and native callbacks for the isolated website UI."""
import json
from pathlib import Path
import sys

from PySide6.QtCore import QObject, QProcess, QTimer

from ..operations import StalePlan
from ..subtitle_sources.imports import private_path
from ..web_ui.protocol import ProtocolError


class SubtitleController(QObject):
    def __init__(self, host, profile):
        super().__init__(host)
        self.host = host;self.service = host.bridge.service;self.profile = profile
        self.process = None;self.ready = False;self.queue = [];self.buffer = b''
        self.pending = {};self.import_job = None;self.stopping = False;self.appearance = None
        self.service.idle.connect(self.idle)

    def send(self, frame):
        raw = json.dumps(frame, ensure_ascii=True, allow_nan=False).encode() + b'\n'
        if len(raw) > 4 * 1024 * 1024:raise ValueError('在线队列过大，请分批选择。')
        if self.ready and self.process and self.process.state() != QProcess.NotRunning:
            self.process.write(raw)
        elif not self.stopping:self.queue.append(raw)

    def open(self, params, rid, sid):
        tasks = self.service.subtitle_tasks(params, idle=False)
        if self.process is None:
            process = self.process = QProcess(self);self.buffer = b'';self.stopping = False
            process.setProgram(sys.executable)
            prefix = ['--subtitle-browser'] if getattr(sys, 'frozen', False) else ['-u', '-m', 'yingxu.desktop_host.subtitle_process']
            process.setArguments([*prefix, '--profile', str(self.profile)])
            process.setWorkingDirectory(str(Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[2]))
            process.readyReadStandardOutput.connect(self.read)
            process.readyReadStandardError.connect(lambda: sys.stderr.write(bytes(process.readAllStandardError()).decode('utf-8', errors='replace')))
            process.finished.connect(lambda *_: self.ended(process))
            process.errorOccurred.connect(lambda *_: self.ended(process) if process.state() == QProcess.NotRunning else None)
            process.start()
        self.pending[rid] = sid
        self.send({'type': 'open', 'requestId': rid, 'sessionId': sid,
                   'context': [params['scanId'], params['revision']],
                   'tasks': [{**task, 'video': str(task['video'])} for task in tasks]})
        QTimer.singleShot(15000, lambda: self.timeout(rid, sid))

    def timeout(self, rid, sid):
        if self.pending.get(rid) == sid:
            self.finish_open(rid, sid, error='在线字幕窗口启动超时，请关闭后重试。')

    def finish_open(self, rid, sid, *, data=None, error=None):
        if rid not in self.pending or self.pending[rid] != sid:return
        self.pending.pop(rid)
        if self.host.bridge.session_id == sid:
            self.service.native_busy = False
            self.host.bridge.finish_native(rid, sid, data=data,
                error=ProtocolError('ONLINE_FAILED', error) if error else None)
            self.service.emit('native.idle')

    def read(self):
        if not self.process:return
        self.buffer += bytes(self.process.readAllStandardOutput())
        if len(self.buffer) > 1024 * 1024:
            self.shutdown();return
        while b'\n' in self.buffer:
            raw, self.buffer = self.buffer.split(b'\n', 1)
            try:self.receive(json.loads(raw))
            except (ValueError, TypeError, KeyError):
                sys.stderr.write('Invalid subtitle helper frame\n')

    def receive(self, frame):
        kind = frame.get('type')
        if kind == 'ready':
            self.ready = True
            for raw in self.queue:self.process.write(raw)
            self.queue.clear()
            if self.appearance:self.send({'type': 'appearance', 'state': self.appearance})
        elif kind in {'opened', 'error'}:
            if kind == 'opened':self.host.send({'type': 'online.window', 'pid': frame['pid'], 'handle': frame['handle']})
            self.finish_open(frame.get('requestId'), frame.get('sessionId'),
                data={'opened': True, 'taskCount': frame.get('taskCount', 0), 'added': frame.get('added', 0)},
                error=frame.get('message') if kind == 'error' else None)
        elif kind == 'staged':
            receipt = frame['receipt'];error = None
            try:
                inbox = private_path(Path(frame['inbox']), self.profile / 'subtitle-inbox')
                self.service.register_download(receipt, inbox)
            except (ProtocolError, OSError, ValueError, StalePlan) as caught:
                error = caught.message if isinstance(caught, ProtocolError) else str(caught)
            self.send({'type': 'registered', 'stagingId': receipt['stagingId'], 'error': error})
        elif kind == 'import':self.import_downloads(frame)
        elif kind == 'ui' and frame.get('identifier') in {None, 'history-button', 'appearance-button'}:
            self.host.send({'type': 'online.ui', 'identifier': frame.get('identifier')})
        elif kind == 'appearance' and frame.get('theme') in {'system', 'dark', 'light'}:
            self.host.send({'type': 'online.appearance', 'theme': frame['theme']})

    def import_downloads(self, frame):
        ids = frame['ids'];automatic = frame.get('automatic') is True
        try:
            if not self.service.data or self.service.data.scan_id != frame['scanId']:
                raise ProtocolError('STALE_REVIEW', '扫描已变化，下载保留在缓存；请重新查找。')
            job = self.service.import_downloads(ids, {'scanId': frame['scanId'], 'revision': self.service.revision})
            self.import_job = (job['jobId'], ids)
        except (ProtocolError, OSError, ValueError, StalePlan) as error:
            self.send({'type': 'import.finished', 'ids': ids,
                       'retry': automatic and isinstance(error, ProtocolError) and error.code == 'BUSY',
                       'error': error.message if isinstance(error, ProtocolError) else str(error)})

    def idle(self):
        if self.import_job:
            job_id, ids = self.import_job;job = self.service.job
            if job and job['jobId'] == job_id and job['status'] != 'running':
                self.import_job = None
                self.send({'type': 'import.finished', 'ids': ids,
                    'context': [self.service.data.scan_id, self.service.revision] if self.service.data else None,
                    **({'result': job['result']} if job['status'] == 'completed' else {'error': job['message']})})
        if self.process and not self.stopping:self.send({'type': 'idle'})

    def set_appearance(self, state):
        self.appearance = state
        if self.ready:self.send({'type': 'appearance', 'state': state})

    def ended(self, process):
        if self.process is not process:return
        self.process = None;self.ready = False;self.queue.clear();self.buffer = b''
        for rid, sid in list(self.pending.items()):self.finish_open(rid, sid, error='在线字幕窗口已退出，请重试。')
        process.deleteLater()

    def shutdown(self):
        if self.stopping:return self.process is None
        self.stopping = True;self.queue.clear()
        if self.process:
            self.send({'type': 'shutdown'})
            process = self.process
            # This process only owns website/cache work, never media operations.
            QTimer.singleShot(5000, lambda: process.kill() if self.process is process else None)
        return self.process is None
