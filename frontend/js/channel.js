// Appearance and business share exactly one transport per document.
let pending;
let hostPending;
export const isDesktopHost = () => Boolean(globalThis.yingxuHost?.kind === 'electron' || globalThis.qt?.webChannelTransport);
const subscribe = (signal, callback) => {signal.connect(callback);return () => signal.disconnect(callback);};

// A transport-independent interface. Electron never installs fake Qt globals.
export function desktopHost() {
  if (!hostPending) hostPending = globalThis.yingxuHost?.kind === 'electron'
    ? Promise.resolve(globalThis.yingxuHost)
    : desktopChannel().then(({objects}) => ({kind:'qt',
      workspace: objects.bridge && {request:raw => objects.bridge.request(raw),
        onReply:callback => subscribe(objects.bridge.reply,callback),onEvent:callback => subscribe(objects.bridge.event,callback)},
      appearance: objects.appearance && {
        getState:() => new Promise(resolve => objects.appearance.getState(raw => resolve(JSON.parse(raw)))),
        update:patch => new Promise(resolve => objects.appearance.update(JSON.stringify(patch),raw => resolve(JSON.parse(raw)))),
        subscribe:callback => subscribe(objects.appearance.changed,raw => callback(JSON.parse(raw)))},
      setOverlayActive:active => objects.compositor?.setOverlayActive(active),
    }));
  return hostPending;
}
export function desktopChannel() {
  if (!pending) pending = new Promise((resolve,reject) => {
    if (!globalThis.qt?.webChannelTransport || !globalThis.QWebChannel) {reject(new Error('本地桌面通信不可用，请通过映序桌面入口打开。'));return;}
    const timer = setTimeout(() => reject(new Error('本地通信初始化超时。')),10000);
    new QWebChannel(qt.webChannelTransport,channel => {clearTimeout(timer);resolve(channel);});
  });
  return pending;
}
