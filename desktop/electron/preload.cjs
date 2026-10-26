// Sandboxed preload: no Node, IPC object, filesystem or shell reaches the page.
const {contextBridge,ipcRenderer,webUtils}=require('electron');
const raw=process.argv.find(value=>value.startsWith('--yingxu-bootstrap='));
const initial=JSON.parse(decodeURIComponent(raw.slice('--yingxu-bootstrap='.length)));
function subscribe(channel,callback) {
  const listener=(_event,payload)=>callback(payload);ipcRenderer.on(channel,listener);
  return ()=>ipcRenderer.removeListener(channel,listener);
}
contextBridge.exposeInMainWorld('__yingxuAppearance',initial);
contextBridge.exposeInMainWorld('yingxuHost',{
  kind:'electron',prototype:initial.prototype,effectProfile:initial.effectProfile,
  workspace:{request:raw=>ipcRenderer.invoke('yingxu:request',raw),
    onReply:callback=>subscribe('yingxu:reply',callback),onEvent:callback=>subscribe('yingxu:event',callback),
    onDisconnect:callback=>subscribe('yingxu:disconnected',callback),
    onNativeUi:callback=>subscribe('yingxu:native-ui',callback),
    drop:file=>ipcRenderer.invoke('yingxu:drop',webUtils.getPathForFile(file))},
  appearance:{getState:()=>ipcRenderer.invoke('yingxu:appearance:get'),update:patch=>ipcRenderer.invoke('yingxu:appearance:update',patch),
    subscribe:callback=>subscribe('yingxu:appearance',callback)},
  hdr:{report:report=>ipcRenderer.invoke('yingxu:hdr:report',report)},
});
const bootstrap=()=>{
  const root=document.documentElement;if(!root)return false;
  Object.assign(root.dataset,{theme:initial.resolvedTheme,themePreference:initial.theme,reduced:String(initial.reducedMotion),
    lighting:initial.lighting,appearanceBootstrapped:'true',desktopHost:'electron',effectsProfile:initial.effectProfile});
  return true;
};
if(!bootstrap()){const observer=new MutationObserver(()=>{if(bootstrap())observer.disconnect();});observer.observe(document,{childList:true,subtree:true});}
