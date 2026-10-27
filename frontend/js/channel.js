// Presentation depends on a host contract, never on a GUI framework global.
export const isDesktopHost=()=>globalThis.yingxuHost?.kind==='electron';
export function desktopHost(){
  return isDesktopHost()?Promise.resolve(globalThis.yingxuHost):Promise.reject(new Error('请通过映序桌面入口打开。'));
}
