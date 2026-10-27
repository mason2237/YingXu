const {contextBridge,ipcRenderer}=require('electron');
function subscribe(channel,callback){const listener=(_event,value)=>callback(value);ipcRenderer.on(channel,listener);return ()=>ipcRenderer.removeListener(channel,listener);}
contextBridge.exposeInMainWorld('yingxuOnline',{
  request:(action,params)=>ipcRenderer.invoke('yingxu:online:request',action,params),
  appearance:()=>ipcRenderer.invoke('yingxu:online:appearance'),
  onChange:callback=>subscribe('yingxu:online:changed',callback),
  onNotice:callback=>subscribe('yingxu:online:notice',callback),
  onAppearance:callback=>subscribe('yingxu:online:appearance',callback),
});
