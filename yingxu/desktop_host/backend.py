"""Electron's private Python service; preview mode remains independently restricted."""
import argparse
import json
from pathlib import Path
import sys
import threading

from PySide6.QtCore import QCoreApplication, QObject, QSettings, QTimer, Signal, Slot

from ..operations import HistoryStore, StalePlan
from ..web_ui.display_status import display_color_status, display_for_screen, screen_device_for_window
from ..web_ui.protocol import ProtocolError, encode_reply
from ..web_ui.workspace_bridge import WorkspaceBridge
from ..web_ui.workspace_protocol import decode
from ..web_ui.workspace_service import WorkspaceService
from .stdio import frames

ALLOWED = frozenset({
    'app.hello', 'app.state', 'folder.choose', 'scan.start', 'scan.configure',
    'embedded.configure', 'scan.cancel', 'job.stop', 'review.query', 'review.details',
    'review.candidates', 'preview.create', 'preview.query', 'preview.discard',
    'history.list', 'history.get', 'file.copyName', 'file.reveal',
})


class PreviewService(WorkspaceService):
    def state(self):
        return {**super().state(), 'prototype': True, 'executionAvailable': False,
                'downloadAvailable': False, 'reviewReadOnly': True}


class PreviewBridge(WorkspaceBridge):
    def _save(self, rid, fingerprint, *, data=None, error=None):
        if isinstance(data, dict) and 'capabilities' in data:
            data = {**data, 'capabilities': sorted(ALLOWED)}
        super()._save(rid, fingerprint, data=data, error=error)

    @Slot(str)
    def request(self, raw):
        try:
            request = decode(raw)
            if request.action not in ALLOWED:
                raise ProtocolError('PROTOTYPE_ONLY', '对比原型仅开放扫描与预览；文件执行和在线下载尚未启用。',
                                    request_id=request.request_id)
        except ProtocolError as error:
            self.reply.emit(encode_reply(error.request_id, error=error))
            return
        super().request(raw)


class Host(QObject):
    incoming = Signal(object)

    def __init__(self, profile, *, preview=True):
        super().__init__()
        profile.mkdir(parents=True, exist_ok=True)
        settings = QSettings(str(profile / 'embedded.ini'), QSettings.Format.IniFormat)
        self.preview = preview
        bridge_type, service_type = (PreviewBridge, PreviewService) if preview else (WorkspaceBridge, WorkspaceService)
        self.bridge = bridge_type(history=HistoryStore(profile / 'history.jsonl'),
                                  embedded_settings=settings, service_type=service_type)
        self.bridge.reply.connect(lambda raw: self.send({'type': 'reply', 'raw': raw}))
        self.bridge.event.connect(lambda raw: self.send({'type': 'event', 'raw': raw}))
        self.bridge.service.native_requested.connect(self.native)
        self.incoming.connect(self.receive)
        self.online = None
        if not preview:
            from .subtitle_controller import SubtitleController
            self.online = SubtitleController(self, profile)
        self.stopping = False
        self.stop_timer = QTimer(self)
        self.stop_timer.setInterval(25)
        self.stop_timer.timeout.connect(self.stop_when_idle)

    def send(self, frame):
        try:
            sys.stdout.write(json.dumps(frame, ensure_ascii=True, allow_nan=False) + '\n')
            sys.stdout.flush()
        except (BrokenPipeError, OSError):
            self.shutdown()

    def native(self, action, params, rid, sid):
        if action == 'subtitle.open' and self.online:
            try:self.online.open(params, rid, sid)
            except (ProtocolError, OSError, ValueError) as error:
                self.bridge.service.native_busy = False
                self.bridge.finish_native(rid, sid, error=error if isinstance(error, ProtocolError)
                    else ProtocolError('ONLINE_FAILED', str(error)))
            return
        frame = {'type': 'native', 'action': action, 'requestId': rid, 'sessionId': sid}
        if action.startswith('file.'):
            frame['path'] = str(self.bridge.service.registered_path(params['fileId']))
        elif action == 'result.export':frame['recordId'] = params['recordId']
        self.send(frame)

    @Slot(object)
    def receive(self, frame):
        if not isinstance(frame, dict) or self.stopping:
            return
        kind = frame.get('type')
        if kind == 'request' and isinstance(frame.get('raw'), str):
            self.bridge.request(frame['raw'])
        elif kind == 'native.result':
            rid, sid = frame.get('requestId'), frame.get('sessionId')
            pending = self.bridge._pending.get(rid)
            if not pending or pending[1] != sid or sid != self.bridge.session_id:
                return
            if frame.get('action') != json.loads(pending[0])[0]:
                return
            service = self.bridge.service
            service.native_busy = False
            try:
                if frame.get('error'):
                    raise ProtocolError('NATIVE_FAILED', '系统操作未完成，请重试。')
                if frame.get('action') == 'folder.choose' and frame.get('path'):
                    service.accept_folder(frame['path'])
                    data = {'cancelled': False}
                elif frame.get('action') == 'result.export' and frame.get('path'):
                    original = json.loads(pending[0])[1]
                    data = service.export_record(original['recordId'], Path(frame['path']))
                else:
                    data = {'cancelled': bool(frame.get('cancelled')), 'completed': True}
                self.bridge.finish_native(rid, sid, data=data)
                service.emit('app.state')
            except (OSError, ValueError, StalePlan, ProtocolError) as error:
                error = error if isinstance(error, ProtocolError) else ProtocolError('PATH_UNREADABLE', str(error))
                self.bridge.finish_native(rid, sid, error=error)
        elif kind == 'reset':
            self.bridge.service.native_busy = False
            self.bridge.reset_page()
        elif kind == 'folder.drop' and not self.preview:
            try:self.bridge.service.accept_folder(frame['path'], dropped=True)
            except (ProtocolError, OSError, ValueError, StalePlan) as error:
                self.bridge.service.emit('app.error', {'message': error.message if isinstance(error, ProtocolError) else str(error)})
        elif kind == 'appearance' and self.online:
            self.online.set_appearance(frame['state'])
        elif kind == 'display.query':
            status = display_color_status()
            device = screen_device_for_window(int(frame['handle']))
            self.send({'type': 'display', 'status': display_for_screen(status, device),
                       'device': device, 'osSettingsChanged': False})
        elif kind == 'shutdown':
            self.shutdown()

    def shutdown(self):
        self.stopping = True
        self.bridge.closing = True
        if self.bridge.service.worker:
            self.bridge.service.worker.stop.set()
        self.stop_timer.start()
        self.stop_when_idle()

    def stop_when_idle(self):
        if self.bridge.service.worker is None:
            if self.online and not self.online.shutdown():return
            self.stop_timer.stop()
            QCoreApplication.instance().quit()

    def read(self):
        for frame in frames():
            self.incoming.emit(frame)
        self.incoming.emit({'type': 'shutdown'})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--full', action='store_true')
    args = parser.parse_args()
    app = QCoreApplication([])
    host = Host(args.profile.resolve(), preview=not args.full)
    threading.Thread(target=host.read, daemon=True, name='parent-stdio').start()
    host.send({'type': 'ready', 'protocol': 1, 'readOnly': not args.full})
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
