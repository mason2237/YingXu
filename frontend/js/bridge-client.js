// One QWebChannel per page. Requests are never retried automatically.
import {desktopHost} from './channel.js';
export class BridgeClient extends EventTarget {
  constructor() { super(); this.pending = new Map(); this.sessionId = null; this.sequence = 0; }

  async connect() {
    const host = await desktopHost();this.bridge = host.workspace;
    this.version=this.bridge?.protocolVersion||1;
    if (!this.bridge) throw new Error('当前入口未提供本地文件功能。');
    this.unsubscribe = [this.bridge.onReply(raw => this.onReply(raw)),this.bridge.onEvent(raw => this.onEvent(raw))];
    if (this.bridge.onDisconnect) this.unsubscribe.push(this.bridge.onDisconnect(message => {
      this.dispose();this.dispatchEvent(new CustomEvent('disconnect',{detail:message}));
    }));
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
      Promise.resolve(this.bridge.request(JSON.stringify({v: this.version, requestId, sessionId: this.sessionId, action, params}))).catch(error => {
        if (!this.pending.delete(requestId)) return;
        clearTimeout(timer);reject(error);
      });
    });
  }

  onReply(raw) {
    const reply = JSON.parse(raw);
    if(reply.v!==this.version)return;
    const pending = this.pending.get(reply.requestId);
    if (!pending) return;
    clearTimeout(pending.timer); this.pending.delete(reply.requestId);
    if (reply.ok) pending.resolve(reply.data);
    else {const error = new Error(reply.error.message);error.code = reply.error.code;pending.reject(error);}
  }

  onEvent(raw) {
    const event = JSON.parse(raw);
    if(event.v!==this.version)return;
    if(this.version===2)event.type=event.event;
    if (event.sessionId !== this.sessionId || event.sequence <= this.sequence) return;
    this.sequence = event.sequence;
    this.dispatchEvent(new CustomEvent('state', {detail: event}));
  }

  dispose() {for (const stop of this.unsubscribe || []) {try {stop();} catch {}}this.unsubscribe = [];for (const pending of this.pending.values()) {clearTimeout(pending.timer);const error = new Error('连接已关闭，操作不会自动重试。');error.code = 'CLOSING';pending.reject(error);}this.pending.clear();}
}
