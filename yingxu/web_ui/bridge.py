"""Small allowlist bridge with page sessions and bounded request deduplication."""
from collections import OrderedDict
import json
from uuid import uuid4

from PySide6.QtCore import QObject, Signal, Slot

from .protocol import ACTIONS, VERSION, ProtocolError, decode_request, encode_reply
from .service import FoundationService


class FoundationBridge(QObject):
    reply = Signal(str)
    event = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.session_id = None
        self.sequence = 0
        self._cache = OrderedDict()
        self.service = FoundationService(self)
        # A bound QObject method would become a dynamic Qt slot and be published
        # by QWebChannel. Keep internal callbacks outside the bridge metaobject.
        self.service.changed.connect(lambda kind: self.push(kind))
        self.closing = False

    def reset_page(self):
        self.session_id = None
        self.sequence = 0
        self._cache.clear()

    @Slot(str)
    def request(self, raw):
        rid = None
        try:
            request = decode_request(raw)
            rid = request.request_id
            if self.closing:
                raise ProtocolError("CLOSING", "窗口正在关闭。")
            if request.action != "app.hello" and (
                not self.session_id or request.session_id != self.session_id
            ):
                raise ProtocolError("STALE_SESSION", "页面会话已失效，请重新连接。", retryable=True)
            if request.action == "app.hello" and request.session_id is not None:
                raise ProtocolError("INVALID_REQUEST", "初次握手不应携带会话。")
            fingerprint = request.fingerprint()
            if rid in self._cache:
                previous, response = self._cache[rid]
                if previous != fingerprint:
                    raise ProtocolError("REQUEST_ID_REUSED", "请求标识已用于不同操作。")
                self.reply.emit(response)
                return
            if request.action == "app.hello":
                if self.session_id is not None:
                    raise ProtocolError("ALREADY_CONNECTED", "页面已连接。")
                self.session_id = uuid4().hex
                data = {"sessionId": self.session_id, "capabilities": sorted(ACTIONS),
                        "state": self.service.state()}
            elif request.action == "app.state":
                data = self.service.state()
            elif request.action == "app.ping":
                data = {"message": request.params["message"], "source": "Python"}
            else:
                data = self.service.start_sample()
            response = encode_reply(rid, data)
            self._cache[rid] = (fingerprint, response)
            if len(self._cache) > 128:
                self._cache.popitem(last=False)
            self.reply.emit(response)
        except ProtocolError as error:
            self.reply.emit(encode_reply(error.request_id or rid, error=error))
        except Exception:
            self.reply.emit(encode_reply(rid, error=ProtocolError(
                "INTERNAL_ERROR", "本地通信未完成，请重新连接。")))

    def push(self, kind):
        if self.session_id and not self.closing:
            self.sequence += 1
            self.event.emit(json.dumps({
                "v": VERSION, "sessionId": self.session_id,
                "jobId": self.service.job["jobId"], "sequence": self.sequence,
                "type": kind, "payload": self.service.state(),
            }, ensure_ascii=False, allow_nan=False))
