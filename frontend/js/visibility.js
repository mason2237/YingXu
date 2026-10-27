// Native minimization and document occlusion are separate visibility signals.
// Remote debugging can keep document.hidden=false even for a minimized window.
export const windowInactive=()=>document.hidden||document.documentElement.dataset.nativeHidden==='true';
export function onWindowVisibility(callback,options={}){
  document.addEventListener('visibilitychange',callback,options);
  document.addEventListener('yingxu:visibilitychange',callback,options);
}
const stop=globalThis.yingxuHost?.lifecycle?.onVisibility(hidden=>{
  document.documentElement.dataset.nativeHidden=String(hidden);
  document.dispatchEvent(new Event('yingxu:visibilitychange'));
});
window.addEventListener('pagehide',()=>stop?.(),{once:true});
