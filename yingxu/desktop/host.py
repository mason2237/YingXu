"""Qt-free composition root. All business state is owned by the application."""
import argparse
from collections import OrderedDict
import io
import json
import os
from pathlib import Path
import sys
from threading import Thread
from uuid import uuid4

from ..adapters.display_status import display_color_status, display_for_screen, screen_device_for_window
from ..adapters.history_reader import JSONLHistoryReader
from ..adapters.json_settings import JSONSettings
from ..adapters.local_filesystem import LocalFilesystem
from ..adapters.media_inspector import LocalMediaInspector
from ..adapters.preview import LocalPreviewer
from ..adapters.sqlite_workflow_store import SQLiteWorkflowStore
from ..adapters.sqlite_checkpoint import SQLiteCheckpoints
from ..adapters.subtitle_sites.browser_provider import BrowserSiteProvider
from ..adapters.subtitle_artifacts import LocalSubtitleArtifacts
from ..adapters.subtitle_sites.zimuku import search_terms
from ..adapters.thread_tasks import ThreadTasks
from ..application.discovery import Discovery
from ..application.drafts import Drafts
from ..application.downloading import Downloads
from ..application.subtitles import SubtitleWorkflow
from ..application.workspace import Workspace
from ..domain.errors import ProtocolError
from ..domain.media import DEFAULT_OPTIONS
from ..domain.models import WorkflowCommand, WorkflowError
from .lifecycle import OwnerLoop
from .messages import MAX_BYTES, VERSION, dumps, fit_page, frames, reply, valid_id
from .workspace_protocol import ACTIONS, decode
from .operation_runtime import build_execution


DISABLED = frozenset()
NATIVE = frozenset({'folder.choose', 'file.copyName', 'file.reveal', 'operation.cache', 'online.cache', 'result.export'})


class Host:
    def __init__(self, profile, *, send=None):
        profile = Path(profile)
        profile.mkdir(parents=True, exist_ok=True)
        self.loop = OwnerLoop()
        self.runner = ThreadTasks(self.loop)
        self.execution = self.store = None
        self.checkpoints = None
        try:
            self.initialize(profile, send)
        except BaseException:
            if self.store is not None:
                self.store.close()
            if self.checkpoints is not None:
                self.checkpoints.close()
            if self.execution is not None:
                self.execution.journal.close()
            self.runner.close()
            raise

    def initialize(self, profile, send):
        self.execution = build_execution(profile)
        self.checkpoints = SQLiteCheckpoints(profile / 'workspace.sqlite3')
        self.store = SQLiteWorkflowStore(profile / 'tasks.sqlite3')
        self.workflow = SubtitleWorkflow(self.store)
        self.recovered = self.workflow.recover_inflight(self.store.active_tasks())
        self.session_id = None
        self.sequence = 0
        self.cache = OrderedDict()
        self.pending = {}
        self.stopping = False
        self.send = send or self.stdout
        filesystem = LocalFilesystem()
        self.workspace = Workspace(filesystem=filesystem, inspector=LocalMediaInspector(),
            previewer=LocalPreviewer(), history=JSONLHistoryReader(profile / 'history.jsonl'),
            settings=JSONSettings(profile / 'embedded.json', DEFAULT_OPTIONS), tasks=self.runner, changed=self.push,
            execution=self.execution, drafts=Drafts(self.checkpoints,filesystem))
        self.workspace.interrupted_count = self.recovered
        self.discovery = Discovery(self.workspace, self.workflow, BrowserSiteProvider(), self.native_send,
                                   JSONSettings(profile / 'online.json', {'language': 'bilingual'}))
        self.workspace.discovery = self.discovery
        self.downloads = Downloads(self.workspace, self.discovery, LocalSubtitleArtifacts(profile / 'subtitles'), self.native_send)
        self.discovery.downloads = self.downloads

    def stdout(self, frame):
        sys.stdout.write(dumps(frame) + '\n')
        sys.stdout.flush()

    def native_send(self, frame):
        self.send({'v': VERSION, **frame})

    def respond(self, rid, fingerprint, *, data=None, error=None):
        frame = reply(rid, self.session_id, data=data, error=error)
        try:
            frame = fit_page(frame)
        except ProtocolError as size_error:
            frame = reply(rid, self.session_id, error=size_error)
        if rid and fingerprint:
            self.cache[rid] = (fingerprint, frame)
            if len(self.cache) > 128:
                self.cache.popitem(last=False)
        self.send(frame)

    def request(self, frame):
        rid = fingerprint = None
        try:
            request = decode(dumps(frame))
            rid, fingerprint = request.request_id, request.fingerprint()
            if self.stopping:
                raise ProtocolError('CLOSING', '应用正在关闭。')
            if request.action != 'app.hello' and (self.session_id is None or request.session_id != self.session_id):
                raise ProtocolError('STALE_SESSION', '页面会话已失效，请重新连接。')
            previous = self.cache.get(rid) or self.pending.get(rid)
            if previous:
                if previous[0] != fingerprint:
                    raise ProtocolError('REQUEST_ID_REUSED', '此请求标识已用于不同内容。')
                if rid in self.cache:
                    self.send(previous[1])
                return
            if request.action == 'app.hello':
                if request.session_id is not None or self.session_id is not None:
                    raise ProtocolError('ALREADY_CONNECTED', '页面已连接或携带了旧会话。')
                self.session_id = uuid4().hex
                self.sequence = 0
                self.workspace.new_page(self.session_id)
                self.workspace.start_reconciliation()
                data = {'sessionId': self.session_id, 'protocol': VERSION, 'capabilities': sorted(ACTIONS - DISABLED),
                        'state': self.workspace.state(), 'interruptedTasks': self.recovered}
            elif request.action in DISABLED:
                raise ProtocolError('CAPABILITY_DISABLED', '记录导出尚未开放；操作日志仍保存在本机。')
            elif request.action in NATIVE:
                self.workspace.require_idle()
                if len(self.pending) >= 8:
                    raise ProtocolError('BUSY', '系统操作队列已满。')
                native = {'v': VERSION, 'type': 'native', 'action': request.action,
                          'requestId': rid, 'sessionId': self.session_id}
                if request.action.startswith('file.'):
                    native['path'] = str(self.workspace.registered_path(request.params['fileId']))
                elif request.action == 'operation.cache':
                    native['path'] = str(self.execution.files.buffer_root)
                elif request.action == 'online.cache':
                    native['path'] = str(self.downloads.artifacts.root)
                elif request.action == 'result.export':
                    identifier = request.params['recordId']
                    if not self.execution.contains(identifier) and identifier not in self.workspace.records:
                        raise ProtocolError('NOT_FOUND', '请先打开需要导出的记录。')
                dumps(native)
                self.workspace.native_busy = True
                self.pending[rid] = (fingerprint, request)
                self.send(native)
                return
            elif request.action == 'subtitle.inbox':
                self.native_send({'type': 'online.show'})
                data = {'opened': True}
            elif request.action == 'subtitle.open':
                data = self.discovery.open(request.params)
                for entry in self.discovery.entries.values():
                    entry['query'] = search_terms(entry['videoName'])
                self.native_send({'type': 'online.show'})
            elif request.action.startswith('online.'):
                data = self.discovery.dispatch(request.action, request.params, rid)
                if request.action not in {'online.query', 'online.candidates', 'online.downloads'}:
                    self.push('online.changed')
            else:
                data = self.workspace.dispatch(request.action, request.params, self.session_id)
            self.respond(rid, fingerprint, data=data)
        except (ProtocolError, WorkflowError, OSError, ValueError) as error:
            stable = as_error(error)
            # A mismatched replay must not replace the original cached receipt.
            self.respond(getattr(error, 'request_id', None) or rid,
                         fingerprint if rid not in self.cache and rid not in self.pending else None, error=stable)
        except Exception:
            self.respond(rid, fingerprint, error=ProtocolError('INTERNAL_ERROR', '本地操作未完成，请重新连接或扫描。'))

    def push(self, kind, payload=None):
        if not self.session_id or self.stopping:
            return
        if kind in {'online.changed','job.started','job.idle'}:
            try: self.discovery.persist()
            except (WorkflowError,ProtocolError,OSError,ValueError):
                self.workspace.draft_status = {'restored':False,'message':'字幕队列检查点保存失败；请保留数据目录，暂勿关闭应用。'}
        self.sequence += 1
        frame = {'v': VERSION, 'type': kind, 'sessionId': self.session_id, 'sequence': self.sequence,
                 'jobId': self.workspace.job['jobId'] if self.workspace.job else None,
                 'payload': {'state': self.workspace.state(), **(payload or {})}}
        # 'event' is the transport kind; business event name stays separate.
        self.send({**frame, 'type': 'event', 'event': kind})

    def receive(self, frame):
        if self.stopping or type(frame.get('v')) is not int or frame['v'] != VERSION:
            return
        kind = frame.get('type')
        if kind == 'request':
            self.request(frame)
        elif kind == 'native.result':
            self.finish_native(frame)
        elif kind == 'browser.closed' and set(frame) == {'v', 'type'}:
            self.discovery.suspend()
        elif kind == 'download.failed':
            if set(frame) != {'v','type','taskId','effectId','generation','message'} or not all(valid_id(frame.get(key)) for key in ('taskId','effectId')):
                return
            if type(frame['generation']) is int and isinstance(frame['message'], str) and len(frame['message']) <= 200:
                self.downloads.browser_failed(frame)
        elif kind == 'download.offer':
            allowed = {'v', 'type', 'taskId', 'effectId', 'generation', 'offerId', 'url', 'page', 'name', 'mime', 'total', 'headers'}
            if set(frame) - allowed or not all(valid_id(frame.get(key)) for key in ('taskId', 'effectId', 'offerId')):
                return
            if type(frame.get('generation')) is not int or type(frame.get('total')) is not int:
                return
            if not all(isinstance(frame.get(key), str) and len(frame[key]) <= 2048 for key in ('url','page','name','mime')):
                return
            try:
                if not self.downloads.offer(frame):
                    raise ProtocolError('STALE_DOWNLOAD', '下载许可已失效，未接收文件。')
            except (OSError, ValueError, ProtocolError) as error:
                self.native_send({'type': 'browser.reject', 'offerId': frame['offerId'], 'message': str(error)[:200]})
                self.downloads.browser_failed({**frame, 'message': str(error)[:200]})
        elif kind == 'browser.page':
            if set(frame) != {'v','type','taskId','effectId','generation','url','title'} or not all(valid_id(frame.get(key)) for key in ('taskId','effectId')):
                return
            if type(frame['generation']) is not int or not all(isinstance(frame[key], str) and len(frame[key]) <= 2048 for key in ('url','title')):
                return
            try:
                self.discovery.page_result(frame)
            except (OSError, ValueError, ProtocolError) as error:
                self.push('app.error', {'message': str(error)[:200]})
        elif kind == 'download.result':
            if set(frame) != {'v', 'type', 'artifactId', 'status'} or not valid_id(frame.get('artifactId')) or frame.get('status') not in {'completed', 'interrupted'}:
                return
            try:
                self.downloads.blob_result(frame)
            except (OSError, ValueError, ProtocolError) as error:
                self.push('app.error', {'message': str(error)[:200]})
        elif kind == 'reset':
            if set(frame) != {'v', 'type'}:
                return
            self.session_id = None
            self.cache.clear()
            self.pending.clear()
            self.workspace.native_busy = False
            self.workspace.new_page(None)
        elif kind == 'folder.drop':
            if set(frame) != {'v', 'type', 'path'} or not isinstance(frame['path'], str):
                return
            try:
                self.workspace.accept_folder(Path(frame['path']).resolve(strict=True), dropped=True)
            except (OSError, ValueError, ProtocolError) as error:
                self.push('app.error', {'message': str(error)[:200]})
        elif kind == 'browser.result':
            allowed = {'v', 'type', 'taskId', 'effectId', 'generation', 'status', 'raw', 'message', 'final'}
            if set(frame) - allowed or not all(valid_id(frame.get(key)) for key in ('taskId', 'effectId')):
                return
            if type(frame.get('generation')) is not int or frame.get('status') not in {'manual', 'failed', 'results'}:
                return
            if type(frame.get('final', False)) is not bool or not isinstance(frame.get('raw', ''), str) or not isinstance(frame.get('message', ''), str):
                return
            try:
                self.discovery.browser_result(frame)
            except (ProtocolError, WorkflowError) as error:
                self.push('app.error', {'message': str(error)[:200]})
        elif kind == 'display.query':
            if set(frame) != {'v', 'type', 'handle'} or not isinstance(frame['handle'], str) or not frame['handle'].isdigit() or len(frame['handle']) > 20:
                return
            value = int(frame['handle'])
            if value >= 2**64:
                return
            status = display_color_status()
            self.native_send({'type': 'display', 'status': display_for_screen(status, screen_device_for_window(value)),
                              'osSettingsChanged': False})
        elif kind == 'shutdown':
            self.shutdown()
        # Appearance is owned by Electron; no second Python appearance state.

    def finish_native(self, frame):
        allowed = {'v', 'type', 'requestId', 'sessionId', 'action', 'path', 'cancelled', 'completed', 'error'}
        if set(frame) - allowed or not valid_id(frame.get('requestId')):
            return
        pending = self.pending.get(frame['requestId'])
        if not pending:
            return
        fingerprint, request = pending
        if frame.get('sessionId') != self.session_id or request.session_id != self.session_id or frame.get('action') != request.action:
            return
        self.pending.pop(request.request_id)
        self.workspace.native_busy = False
        try:
            if frame.get('error'):
                raise ProtocolError('NATIVE_FAILED', '系统操作未完成。')
            if request.action == 'folder.choose' and not frame.get('cancelled'):
                if not isinstance(frame.get('path'), str):
                    raise ProtocolError('INVALID_REQUEST', '系统选择结果无效。')
                self.workspace.accept_folder(Path(frame['path']).resolve(strict=True))
            if request.action == 'result.export' and not frame.get('cancelled'):
                destination = Path(frame.get('path', ''))
                if not destination.is_absolute() or destination.suffix.casefold() != '.json':
                    raise ProtocolError('INVALID_REQUEST', '记录只能保存到系统对话框选择的 JSON 文件。')
                identifier = request.params['recordId']
                def export(worker):
                    if self.execution.contains(identifier):
                        run, items = self.execution.journal.bundle(identifier)
                        run = {key: value for key, value in run.items() if key not in {'ticket', 'approved'}}
                        value = {'format': 'yingxu.operations.v1', 'run': run, 'items': items}
                    else:
                        value = self.workspace.records[identifier]
                    with destination.open('x', encoding='utf8') as stream:
                        json.dump(value, stream, ensure_ascii=False, indent=2)
                        stream.flush(); os.fsync(stream.fileno())
                    return {'exported': True}
                data = self.workspace.launch('export', export, lambda value: value, '正在导出记录…')
                self.respond(request.request_id, fingerprint, data=data)
                return
            self.respond(request.request_id, fingerprint, data={'cancelled': bool(frame.get('cancelled')), 'completed': True})
        except (OSError, ValueError, ProtocolError) as error:
            self.respond(request.request_id, fingerprint, error=as_error(error))
        self.push('native.idle')

    def shutdown(self):
        self.stopping = True
        if self.workspace.worker:
            self.workspace.worker.stop.set()
        self.discovery.suspend()

    def close(self):
        self.runner.close()
        self.loop.stopping.set()
        try:
            self.store.close()
        finally:
            self.checkpoints.close()
            self.execution.journal.close()


def as_error(error):
    if isinstance(error, ProtocolError):
        return error
    code = (error.code if isinstance(error, WorkflowError) else
            'PERMISSION_DENIED' if isinstance(error, PermissionError) else
            'NOT_FOUND' if isinstance(error, FileNotFoundError) else
            'PATH_UNREADABLE' if isinstance(error, OSError) else 'INVALID_REQUEST')
    return ProtocolError(code, str(error)[:200])


def inherited_streams():
    if os.name != 'nt':
        return
    import ctypes
    import msvcrt
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetStdHandle.argtypes = [ctypes.c_uint32]
    kernel.GetStdHandle.restype = ctypes.c_void_p
    for name, number, flags, mode in [('stdin', -10, os.O_RDONLY, 'rb'),
                                      ('stdout', -11, os.O_WRONLY, 'wb'), ('stderr', -12, os.O_WRONLY, 'wb')]:
        current = getattr(sys, name, None)
        if current is not None:
            if hasattr(current, 'reconfigure'):
                current.reconfigure(encoding='utf8', errors='replace', newline='\n', write_through=True)
            continue
        handle = kernel.GetStdHandle(number & 0xffffffff)
        raw = (os.fdopen(msvcrt.open_osfhandle(handle, flags | os.O_BINARY), mode, buffering=0)
               if handle and handle != ctypes.c_void_p(-1).value else open(os.devnull, mode, buffering=0))
        setattr(sys, name, io.TextIOWrapper(raw, encoding='utf8', errors='replace', newline='\n', write_through=True))


def main():
    inherited_streams()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    args = parser.parse_args()
    try:
        host = Host(args.profile.resolve())
    except (ProtocolError, WorkflowError, OSError) as error:
        stable = as_error(error)
        sys.stdout.write(dumps({'v': VERSION, 'type': 'startup.error',
                               'code': stable.code, 'message': stable.message}) + '\n')
        sys.stdout.flush()
        return 2
    def read():
        try:
            for frame in frames():
                if not host.loop.post(lambda value=frame: host.receive(value)):
                    break
        finally:
            host.loop.post(host.shutdown)
    Thread(target=read, name='desktop-input', daemon=True).start()
    host.native_send({'type': 'ready', 'protocol': VERSION, 'readOnly': False,
                      'runtime': 'python-stdlib', 'qtImported': any(key.startswith('PySide6') for key in sys.modules)})
    try:
        while not host.stopping or host.workspace.worker is not None:
            host.loop.tick()
    finally:
        host.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
