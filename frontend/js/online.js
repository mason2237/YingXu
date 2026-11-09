import {SubtitleQuality} from './components/subtitle-quality.js';
const api=globalThis.yingxuOnline,$=id=>document.getElementById(id);
const expandedQuality=new Set(),qualityOffsets=new Map();
const qualityPanel=new SubtitleQuality(async(action,params)=>{
  const result=await call(action,params);
  if(action!=='online.quality')return result;
  for(let attempt=0;attempt<100;attempt++){
    await new Promise(resolve=>setTimeout(resolve,250));
    const status=await call('online.qualityResult',{artifactId:params.artifactId,jobId:result.jobId});
    if(status.status==='completed')return status.report;
    if(status.status!=='running')throw Error(status.message||'字幕检查未完成');
  }throw Error('检查超时，请稍后重新检查');
});
const labels={queued:'等待查找',searching:'正在查找…',awaiting_user:'需要在网站核对或完成验证',candidates_ready:'已找到候选，请核对',selected:'已选择候选，等待确认下载',downloading:'已确认下载 · 请在网站完成必要操作',verifying:'正在验证内容',preparing:'正在安全解压',review_ready:'已准备好，可导入待审阅',no_results:'没有找到结果',failed:'本次搜索未完成',cancelled:'已取消',interrupted:'上次任务中断'};
let tasks=[],selected=null,offset=0,total=0,candidateOffset=0,candidateTotal=0,busy=false,refreshing=false,refreshQueued=false,downloadOffset=0,downloadRows=[],downloadTicket=0;
const notice=message=>{$('notice').textContent=message;};
async function call(action,params={}){try{const result=await api.request(action,params);
  const field=Array.isArray(result?.tasks)?'tasks':Array.isArray(result?.rows)?'rows':null;
  if(field){let next=result.nextOffset;const end=(params.offset||0)+(params.limit||20);
    while(next!=null&&next<end){const page=await api.request(action,{...params,offset:next,limit:end-next});result[field].push(...page[field]);if(page.nextOffset!=null&&page.nextOffset<=next)throw Error('分页未能继续');next=page.nextOffset;}}
  return result;}catch(error){notice(error.message);throw error;}}
function sync(){const task=tasks.find(value=>value.taskId===selected);$('query').disabled=!task||busy;$('provider').disabled=!task||busy;$('search').disabled=!task||busy||['searching','downloading','verifying','preparing','review_ready','cancelled'].includes(task.phase);$('cancel').disabled=!task||busy||['cancelled','review_ready'].includes(task.phase);$('phase').textContent=task?(labels[task.phase]||task.phase):'从工作区重新选择需要查找的视频';$('search').textContent=task?.phase==='awaiting_user'?'继续查找':'确认并查找';$('previous').disabled=!offset;$('next').disabled=offset+tasks.length>=total;$('download-selected').disabled=!tasks.some(value=>value.phase==='selected');$('try-backup').hidden=!task||!['failed','awaiting_user','no_results'].includes(task.phase);}
async function candidates(){const result=await call('online.candidates',{taskId:selected,offset:candidateOffset,limit:4});candidateTotal=result.total;$('candidates').replaceChildren();for(const row of result.rows){const card=document.createElement('article');card.className='candidate';const title=document.createElement('p');title.textContent=row.release||row.title;const detail=document.createElement('small');detail.textContent=[row.language,...row.reasons,...row.warnings].join(' · ');const open=document.createElement('button');open.textContent='查看网站详情';open.addEventListener('click',()=>call('online.openCandidate',{taskId:selected,candidateId:row.candidateId}).catch(()=>{}));const select=document.createElement('button');select.textContent='选择此候选';select.addEventListener('click',()=>call('online.select',{taskId:selected,candidateId:row.candidateId}).then(refresh).catch(()=>{}));card.append(title,detail,select,open);$('candidates').append(card);}if(!result.rows.length){const empty=document.createElement('p');empty.className='note';empty.textContent='候选会显示在这里。字幕库验证页或不支持解析的页面可在右侧浏览。';$('candidates').append(empty);}$('candidate-prev').disabled=!candidateOffset;$('candidate-next').disabled=candidateOffset+result.rows.length>=candidateTotal;}
async function refresh(){if(refreshing){refreshQueued=true;return;}refreshing=true;try{const result=await call('online.query',{offset,limit:12});tasks=result.tasks;total=result.total;$('resume-queue').hidden=!result.pausedCount;$('resume-queue').textContent=`继续上次 ${result.pausedCount||0} 项下载队列`;$('language').value=result.language;selected=tasks.some(value=>value.taskId===selected)?selected:tasks[0]?.taskId;$('tasks').replaceChildren();for(const task of tasks){const option=document.createElement('option');option.value=task.taskId;option.textContent=task.videoName;option.title=task.videoName;$('tasks').append(option);}$('tasks').value=selected||'';$('page').textContent=`${total} 个视频 · 第 ${Math.floor(offset/12)+1} 页`;const task=tasks.find(value=>value.taskId===selected);if(task&&!$('query').matches(':focus'))$('query').value=task.query;if(task&&!$('provider').matches(':focus'))$('provider').value=task.provider;if(task?.reason)notice(task.reason);sync();await downloads();if(selected)await candidates();else{$('candidates').replaceChildren();$('query').value='';$('candidate-prev').disabled=$('candidate-next').disabled=true;}}finally{refreshing=false;if(refreshQueued){refreshQueued=false;queueMicrotask(()=>refresh().catch(()=>{}));}}}
$('search').addEventListener('click',async()=>{if(busy||!selected)return;busy=true;sync();notice('正在打开字幕网站；必要验证请在右侧完成。');try{await call('online.start',{taskId:selected,query:$('query').value,provider:$('provider').value});}catch{}finally{busy=false;await refresh();}});
$('cancel').addEventListener('click',async()=>{if(selected)try{await call('online.cancel',{taskId:selected});await refresh();}catch{}});
$('tasks').addEventListener('change',()=>{selected=$('tasks').value;candidateOffset=0;const task=tasks.find(value=>value.taskId===selected);$('query').value=task?.query||'';$('provider').value=task?.provider||'zimuku';sync();candidates().catch(()=>{});});
$('language').addEventListener('change',()=>call('online.configure',{language:$('language').value}).then(()=>notice('语言偏好已保存，下次查找直接使用。')).catch(()=>{}));
$('refresh').addEventListener('click',()=>refresh().catch(()=>{}));
$('previous').addEventListener('click',()=>{offset=Math.max(0,offset-12);candidateOffset=0;refresh().catch(()=>{});});$('next').addEventListener('click',()=>{offset+=12;candidateOffset=0;refresh().catch(()=>{});});
$('candidate-prev').addEventListener('click',()=>{candidateOffset=Math.max(0,candidateOffset-4);candidates().catch(()=>{});});$('candidate-next').addEventListener('click',()=>{candidateOffset+=4;candidates().catch(()=>{});});
const stopChange=api.onChange(()=>refresh().catch(()=>{})),stopNotice=api.onNotice(notice),stopAppearance=api.onAppearance(state=>{document.documentElement.dataset.theme=state.resolvedTheme;});window.addEventListener('pagehide',()=>{stopChange();stopNotice();stopAppearance();},{once:true});
const providerToggle=document.createElement('button');providerToggle.textContent='暂停当前来源';$('provider').after(providerToggle);
providerToggle.addEventListener('click',async()=>{try{const state=await call('online.query',{limit:1});const stopped=state.stoppedProviders.includes($('provider').value);await call('online.provider',{provider:$('provider').value,enabled:stopped});providerToggle.textContent=stopped?'暂停当前来源':'恢复当前来源';await refresh();}catch{}});
try{const appearance=await api.appearance();document.documentElement.dataset.theme=appearance.resolvedTheme;await refresh();}catch{notice('连接未完成，请返回工作区重新打开在线字幕。');}

async function confirmAction(title,body){
  const dialog=$('confirmation');if(dialog.open)return false;
  $('confirmation-title').textContent=title;$('confirmation-body').textContent=body;dialog.returnValue='cancel';
  const result=new Promise(resolve=>dialog.addEventListener('close',()=>resolve(dialog.returnValue==='confirm'),{once:true}));
  dialog.showModal();return result;
}
async function downloads(){
  const ticket=++downloadTicket;
  const result=await call('online.downloads',{offset:downloadOffset,limit:5});
  const fragment=document.createDocumentFragment();
  for(const row of result.rows){
    const card=document.createElement('article');card.className='candidate';
    const title=document.createElement('p');title.textContent=row.name;
    const description=document.createElement('small');description.textContent=`${row.videoName} · ${row.message||row.status}`;
    card.append(title,description);
    if(row.status==='ready'&&row.fileCount){
      const show=document.createElement('button');show.textContent=expandedQuality.has(row.artifactId)?'收起字幕检查':'查看字幕检查结果';
      show.onclick=()=>{expandedQuality.has(row.artifactId)?expandedQuality.delete(row.artifactId):expandedQuality.add(row.artifactId);downloads().catch(()=>{});};card.append(show);
      if(expandedQuality.has(row.artifactId)){
        const files=document.createElement('div');card.append(files);
        await qualityFiles(files,row,qualityOffsets.get(row.artifactId)||0);
      }
    }
    if(row.canResume){const retry=document.createElement('button');retry.textContent='重试 / 核对续传';retry.onclick=async()=>{
      if(await confirmAction('重试这份字幕？','服务器支持且对象未变化时续传，否则重新下载。不会自动整理视频目录。'))
        call('online.retryDownload',{artifactId:row.artifactId,acknowledged:true}).then(refresh).catch(()=>{});
    };card.append(retry);}
    if(row.imported){const release=document.createElement('button');release.textContent='释放可回收缓存';release.onclick=async()=>{
      if(await confirmAction('释放这份已导入缓存？','只移除内容未变化且无引用的文件，保留当前草稿、恢复、撤销文件和所需目录。导入超过 30 天的缓存也会自动按此规则回收。'))
        call('online.compactDownload',{artifactId:row.artifactId,acknowledged:true}).then(()=>notice('正在核对并释放可回收文件…')).catch(()=>{});
    };card.append(release);}
    if(!row.imported&&!['receiving','downloading','preparing'].includes(row.status)){
      const clear=document.createElement('button');clear.textContent='清除此缓存';clear.onclick=async()=>{
        if(await confirmAction('清除这份下载缓存？','仅删除这份未导入下载及其解压文件。受恢复或撤销记录保护的文件不会被删除。'))
          call('online.discardDownload',{artifactId:row.artifactId,acknowledged:true}).then(refresh).catch(()=>{});
      };card.append(clear);
    }
    fragment.append(card);
  }
  if(ticket!==downloadTicket)return;
  downloadRows=result.rows;$('downloads').replaceChildren(fragment);qualityPanel.sync();
  $('import-ready').disabled=!downloadRows.some(row=>row.status==='ready'&&!row.imported);
  $('downloads-prev').disabled=!downloadOffset;$('downloads-next').disabled=downloadOffset+result.rows.length>=result.total;
}
async function qualityFiles(host,row,offset){
  try{
    const page=await call('online.qualityFiles',{artifactId:row.artifactId,offset,limit:5});
    host.replaceChildren();
    for(const file of page.entries){const title=document.createElement('p');title.textContent=file.name;
      const summary=document.createElement('small');summary.textContent=file.quality?.status==='clean'?'已完成轻量检查；仍需核对影视版本与时间轴':'存在问题或尚未完整检查，请展开核对';
      const panel=document.createElement('div');host.append(title,summary,panel);
      qualityPanel.mount(panel,{scope:'online',artifactId:row.artifactId,fileIndex:file.fileIndex});
    }
    const previous=document.createElement('button');previous.textContent='上一组文件';previous.disabled=!offset;
    previous.onclick=()=>{const next=Math.max(0,offset-5);qualityOffsets.set(row.artifactId,next);qualityFiles(host,row,next);};
    const next=document.createElement('button');next.textContent='下一组文件';next.disabled=page.nextOffset==null;
    next.onclick=()=>{qualityOffsets.set(row.artifactId,page.nextOffset);qualityFiles(host,row,page.nextOffset);};if(offset||page.nextOffset!=null)host.append(previous,next);
  }catch(error){host.textContent=`检查结果未载入：${error.message}`;}
}
$('download-selected').onclick=async()=>{
  const chosen=tasks.filter(task=>task.phase==='selected');if(!chosen.length)return;
  if(await confirmAction(`确认下载 ${chosen.length} 份已选字幕？`,'按顺序打开候选页面。网站下载按钮或验证码需你操作；下载后自动检查和解压，最终匹配仍需审阅。'))
    call('online.download',{taskIds:chosen.map(task=>task.taskId),acknowledged:true}).then(refresh).catch(()=>{});
};
$('import-ready').onclick=async()=>{
  const ready=downloadRows.filter(row=>row.status==='ready'&&!row.imported);if(!ready.length)return;
  if(await confirmAction(`导入 ${ready.length} 份下载到待审阅？`,'核对原视频身份后添加字幕候选。单一候选可关联但不自动确认，多个候选由你选择；此时不会修改媒体文件。'))
    call('online.import',{artifactIds:ready.map(row=>row.artifactId),acknowledged:true}).then(()=>notice('正在导入，完成后请回到工作区审阅并生成整理预览。')).catch(()=>{});
};
$('open-cache').onclick=()=>call('online.cache').catch(()=>{});
$('downloads-prev').onclick=()=>{downloadOffset=Math.max(0,downloadOffset-5);downloads().catch(()=>{});};
$('downloads-next').onclick=()=>{downloadOffset+=5;downloads().catch(()=>{});};

$('use-page').onclick=()=>{if(selected)call('online.usePage',{taskId:selected}).then(refresh).catch(()=>{});};

$('resume-queue').onclick=async()=>{if(await confirmAction('继续上次下载队列？','重新打开已选候选页面；不会自动修改媒体。中断的下载也可在暂存列表单独续传。'))call('online.resumeQueue',{acknowledged:true}).then(refresh).catch(()=>{});};

$('try-backup').onclick=()=>{const sources=['zimuku','srtku','subhd','subhd-one'];$('provider').value=sources[(sources.indexOf($('provider').value)+1)%sources.length];$('search').click();};
