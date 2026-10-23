"""A single JSON request slot; internal/native callbacks are never Qt slots."""
from collections import OrderedDict
import json
from uuid import uuid4

from PySide6.QtCore import QObject, Signal, Slot

from .protocol import ProtocolError, encode_reply, VERSION
from .workspace_protocol import ACTIONS, decode
from .workspace_service import WorkspaceService


class WorkspaceBridge(QObject):
    reply = Signal(str)
    event = Signal(str)

    def __init__(self, parent=None, *, history=None):
        super().__init__(parent)
        self.service = WorkspaceService(self,history=history)
        self.service.changed.connect(lambda kind,payload:self._push(kind,payload))
        self.session_id = None;self.sequence = 0;self.closing = False
        self._cache = OrderedDict();self._pending = {}

    def reset_page(self):
        self.session_id = None;self.sequence = 0;self._cache.clear();self._pending.clear()
        self.service.new_page(None)

    def _save(self, rid, fingerprint, *, data=None, error=None):
        raw = encode_reply(rid,data,error)
        self._cache[rid] = (fingerprint,raw)
        if len(self._cache) > 128:self._cache.popitem(last=False)
        self.reply.emit(raw)

    @Slot(str)
    def request(self, raw):
        rid = None; fingerprint = None
        try:
            request = decode(raw);rid = request.request_id;fingerprint = request.fingerprint()
            if self.closing:raise ProtocolError("CLOSING","窗口正在安全关闭。")
            if request.action != "app.hello" and (not self.session_id or request.session_id != self.session_id):
                raise ProtocolError("STALE_SESSION","页面会话已失效，请重新连接。",retryable=True)
            if request.action == "app.hello" and request.session_id is not None:
                raise ProtocolError("INVALID_REQUEST","初次握手不应携带会话。")
            previous = self._cache.get(rid) or self._pending.get(rid)
            if previous:
                if previous[0] != fingerprint:raise ProtocolError("REQUEST_ID_REUSED","请求标识已用于不同操作。")
                if rid in self._cache:self.reply.emit(previous[1])
                return
            if request.action == "app.hello":
                if self.session_id:raise ProtocolError("ALREADY_CONNECTED","页面已连接。")
                self.session_id = uuid4().hex;self.service.new_page(self.session_id)
                data = {"sessionId":self.session_id,"capabilities":sorted(ACTIONS),"state":self.service.state()}
            elif request.action in {"folder.choose","result.export","file.reveal","file.copyName"}:
                self.service.require_idle()
                if request.action.startswith("file."): self.service.registered_path(request.params["fileId"])
                if request.action == "result.export" and request.params["recordId"] not in self.service.records:
                    raise ProtocolError("NOT_FOUND","整理记录不可用。")
                self.service.native_busy = True
                self._pending[rid] = (fingerprint,self.session_id)
                self.service.native_requested.emit(request.action,request.params,rid,self.session_id)
                return
            else:data = self.service.dispatch(request.action,request.params,self.session_id)
            self._save(rid,fingerprint,data=data)
        except ProtocolError as error:
            if rid and fingerprint and rid not in self._cache and rid not in self._pending:
                self._save(rid,fingerprint,error=error)
            else:self.reply.emit(encode_reply(error.request_id or rid,error=error))
        except Exception:
            error = ProtocolError("INTERNAL_ERROR","本地操作未完成，请重新连接或扫描。")
            if rid and fingerprint:self._save(rid,fingerprint,error=error)
            else:self.reply.emit(encode_reply(rid,error=error))

    def finish_native(self, rid, session_id, *, data=None, error=None):
        pending = self._pending.pop(rid,None)
        if not self.closing and pending and self.session_id == session_id:
            self._save(rid,pending[0],data=data,error=error)

    def _push(self, kind, payload):
        if self.session_id and not self.closing:
            self.sequence += 1
            self.event.emit(json.dumps({"v":VERSION,"sessionId":self.session_id,"sequence":self.sequence,
                "jobId":self.service.job["jobId"] if self.service.job else None,"type":kind,
                "payload":{"state":self.service.state(),**payload}},ensure_ascii=True,allow_nan=False))
