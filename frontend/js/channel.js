// Appearance and business share exactly one transport per document.
let pending;
export function desktopChannel() {
  if (!pending) pending = new Promise((resolve,reject) => {
    if (!globalThis.qt?.webChannelTransport || !globalThis.QWebChannel) {reject(new Error('本地桌面通信不可用，请通过映序桌面入口打开。'));return;}
    const timer = setTimeout(() => reject(new Error('本地通信初始化超时。')),10000);
    new QWebChannel(qt.webChannelTransport,channel => {clearTimeout(timer);resolve(channel);});
  });
  return pending;
}
