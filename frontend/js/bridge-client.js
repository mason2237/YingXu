// One QWebChannel per page. Requests are never retried automatically.
import {desktopChannel} from './channel.js';
export class BridgeClient extends EventTarget {
  constructor() { super(); this.pending = new Map(); this.sessionId = null; this.sequence = 0; }

  async connect() {
    if (!globalThis.qt?.webChannelTransport || !globalThis.QWebChannel) {
      throw new Error('本地桌面通信不可用，请通过映序桌面入口打开。');
    }
    const channel = await desktopChannel();this.bridge = channel.objects.bridge;
    if (!this.bridge) throw new Error('当前入口未提供本地文件功能。');
    this.bridge.reply.connect(raw => this.onReply(raw));this.bridge.event.connect(raw => this.onEvent(raw));
    const hello = await this.call('app.hello');
    this.sessionId = hello.sessionId;
    return hello.state;
  }

  call(action, params = {}, {timeout = 10000} = {}) {
    const requestId = crypto.randomUUID();
    return new Promise((resolve, reject) => {
      const timer = timeout ? setTimeout(() => {
        this.pending.delete(requestId);
        reject(new Error('状态待同步，请重新连接；操作不会自动重试。'));
      }, timeout) : null;
      this.pending.set(requestId, {resolve, reject, timer});
      this.bridge.request(JSON.stringify({v: 1, requestId, sessionId: this.sessionId, action, params}));
    });
  }

  onReply(raw) {
    const reply = JSON.parse(raw);
    const pending = this.pending.get(reply.requestId);
    if (!pending) return;
    clearTimeout(pending.timer); this.pending.delete(reply.requestId);
    if (reply.ok) pending.resolve(reply.data);
    else {const error = new Error(reply.error.message);error.code = reply.error.code;pending.reject(error);}
  }

  onEvent(raw) {
    const event = JSON.parse(raw);
    if (event.sessionId !== this.sessionId || event.sequence <= this.sequence) return;
    this.sequence = event.sequence;
    this.dispatchEvent(new CustomEvent('state', {detail: event}));
  }

  dispose() {for (const pending of this.pending.values()) {clearTimeout(pending.timer);const error = new Error('页面已关闭，操作不会自动重试。');error.code = 'CLOSING';pending.reject(error);}this.pending.clear();}
}
