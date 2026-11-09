import {el,button} from './icons.js';

export function mountIdentity(host,{request,context,refresh}) {
  const panel=el('details','detail-section'),title=el('summary','','增强识别');panel.append(title);
  panel.append(el('p','subtle-text','读取同名 NFO。可选的视频指纹只读取头尾，不会联网。'));
  const option=el('label','needs-option'),hash=el('input');hash.type='checkbox';option.append(hash,document.createTextNode('同时读取视频头尾各 64 KiB'));panel.append(option);
  const result=el('div','subtitle-quality'),read=button('读取本地识别信息','secondary');
  const manual=el('input');manual.placeholder='当前视频的 IMDb ID，例如 tt1234567';manual.setAttribute('aria-label','当前视频的 IMDb ID');manual.maxLength=12;
  const save=button('保存当前作品标识','subtle-button');panel.append(read,result,manual,save);host.append(panel);
  const run=async(fn)=>{read.disabled=save.disabled=true;try{await fn();}catch(error){if(panel.isConnected)result.textContent=error.message;}finally{read.disabled=save.disabled=false;}};
  read.addEventListener('click',()=>run(async()=>{
    const data=await request('identity.read',{...context,includeHash:hash.checked});if(!panel.isConnected)return;
    result.replaceChildren();for(const item of [...data.ids,...(data.manual?[data.manual]:[])])result.append(el('p','',`${item.kind} · ${item.id} · ${item.source}`));
    for(const reason of data.reasons)result.append(el('p','subtle-text',reason));
    if(data.hash)result.append(el('p','',`视频查询指纹 · ${data.hash}`),el('small','subtle-text',data.hashNotice));
    else if(data.hashStatus==='unsupported')result.append(el('p','','视频不足 128 KiB，无法生成此指纹。'));
    if(!data.ids.length&&!data.manual)result.append(el('p','subtle-text','没有可用的同名 NFO 标识；可手动填写。'));
  }));
  save.addEventListener('click',()=>run(async()=>{await request('identity.set',{...context,imdbId:manual.value.trim()});await refresh();}));
}
