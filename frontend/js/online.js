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
const labels = {
  queued: '等待查找', searching: '正在查找…', awaiting_user: '请在右侧浏览网站结果或完成验证',
  candidates_ready: '选择一条结果下载', selected: '已选择字幕', capturing: '正在读取右侧页面…',
  downloading: '正在下载或等待网站操作…', verifying: '正在检查字幕', preparing: '正在解压字幕',
  review_ready: '下载完成，可加入工作台', no_results: '没有找到结果', failed: '查找未完成',
  cancelled: '已取消，可以重新查找', interrupted: '任务中断，可以重试'
};
const searchPhases = ['searching', 'capturing', 'awaiting_user'];
const downloadPhases = ['downloading', 'verifying', 'preparing'];
let tasks=[],selected=null,offset=0,total=0,candidateOffset=0,candidateTotal=0,busy=false,refreshing=false,refreshQueued=false,downloadOffset=0,downloadRows=[],downloadTicket=0;
let downloadBusy=false, candidateTicket=0;
const currentTask = () => tasks.find(task => task.taskId === selected);
const notice=message=>{$('notice').textContent=message;};
function errorMessage(error) {
  return String(error.message || error).replace(/^Error invoking remote method '[^']+': (?:Error: )?/, '');
}
async function call(action,params={}){try{const result=await api.request(action,params);
  const field=Array.isArray(result?.tasks)?'tasks':Array.isArray(result?.rows)?'rows':null;
  if(field){let next=result.nextOffset;const end=(params.offset||0)+(params.limit||20);
    while(next!=null&&next<end){const page=await api.request(action,{...params,offset:next,limit:end-next});result[field].push(...page[field]);if(page.nextOffset!=null&&page.nextOffset<=next)throw Error('分页未能继续');next=page.nextOffset;}}
  return result;}catch(error){notice(errorMessage(error));throw error;}}
function sync() {
  const task = currentTask();
  const phase = task?.phase;
  const searching = ['searching', 'capturing'].includes(phase);
  const downloading = downloadPhases.includes(phase);
  const blocked = busy || downloadBusy || searching;
  $('query').disabled = $('provider').disabled = !task || blocked;
  $('search').disabled = !task || blocked || phase === 'review_ready';
  $('search').textContent = phase === 'awaiting_user' ? '继续查找' : '查找字幕';
  $('cancel').hidden = !task || (!downloading && !searchPhases.includes(phase));
  $('cancel').disabled = busy;
  $('cancel').textContent = downloading ? '取消下载' : '取消查找';
  $('phase').textContent = task ? labels[phase] || phase : '请从工作台选择视频';
  $('use-page').hidden = !['awaiting_user', 'no_results', 'candidates_ready', 'selected'].includes(phase);
  $('use-page').disabled = blocked;
  $('try-backup').hidden = !['failed', 'awaiting_user', 'no_results', 'interrupted'].includes(phase);
  $('try-backup').disabled = blocked;
  $('previous').disabled = !offset;
  $('next').disabled = offset + tasks.length >= total;
  $('download-selected').hidden = total < 2 || !tasks.some(value => value.phase === 'selected');
  $('download-selected').disabled = blocked;
  $('resume-queue').disabled = blocked;
  for (const button of $('candidates').querySelectorAll('article button')) {
    button.disabled = blocked || phase === 'review_ready' || (phase === 'cancelled' && !button.dataset.retry);
  }
}
async function run(action, params, message) {
  if (busy) return;
  busy = true;
  sync();
  if (message) notice(message);
  try {
    const result = await call(action, params);
    if (action === 'online.start' && result.taskId) selected = result.taskId;
    await refresh();
  } catch {} finally {
    busy = false;
    sync();
  }
}
async function candidates() {
  const taskId = selected;
  if (!taskId) return;
  const ticket = ++candidateTicket;
  const result = await call('online.candidates', {taskId, offset:candidateOffset, limit:4});
  if (ticket !== candidateTicket || taskId !== selected) return;
  candidateTotal = result.total;
  $('candidates').replaceChildren();
  for (const row of result.rows) {
    const card = document.createElement('article');
    card.className = 'candidate';
    const title = document.createElement('p');
    title.textContent = row.release || row.title;
    const detail = document.createElement('small');
    detail.textContent = [row.language, ...row.reasons, ...row.warnings].join(' · ');
    const download = document.createElement('button');
    download.className = 'primary';
    const retry = ['interrupted', 'cancelled'].includes(currentTask()?.phase) && currentTask()?.selectedCandidateId === row.candidateId;
    download.textContent = retry ? '重新下载' : '下载字幕';
    if (retry) download.dataset.retry = 'true';
    download.onclick = () => run('online.download', {taskIds:[taskId], candidateId:row.candidateId, acknowledged:true}, '正在准备下载…');
    const open = document.createElement('button');
    open.textContent = '网站详情';
    open.onclick = () => run('online.openCandidate', {taskId, candidateId:row.candidateId});
    card.append(title, detail, download, open);
    if (total > 1) {
      const select = document.createElement('button');
      select.textContent = currentTask()?.selectedCandidateId === row.candidateId ? '已选' : '选入批量';
      select.onclick = () => run('online.select', {taskId, candidateId:row.candidateId});
      card.append(select);
    }
    $('candidates').append(card);
  }
  if (!result.rows.length && currentTask()?.phase === 'awaiting_user') {
    const hint = document.createElement('p');
    hint.className = 'note';
    hint.textContent = '在右侧打开想要的字幕详情或下载页，再点击下方按钮。';
    $('candidates').append(hint);
  }
  $('candidate-prev').disabled = !candidateOffset;
  $('candidate-next').disabled = candidateOffset + result.rows.length >= candidateTotal;
  $('candidate-prev').parentElement.hidden = !candidateOffset && candidateTotal <= 4;
  sync();
}
async function refresh(){if(refreshing){refreshQueued=true;return;}refreshing=true;try{const result=await call('online.query',{offset,limit:12});tasks=result.tasks;total=result.total;downloadBusy=result.downloadBusy;$('resume-queue').hidden=!result.pausedCount;$('resume-queue').textContent=`继续上次 ${result.pausedCount||0} 项下载队列`;$('language').value=result.language;selected=tasks.some(value=>value.taskId===selected)?selected:tasks[0]?.taskId;$('tasks').replaceChildren();for(const task of tasks){const option=document.createElement('option');option.value=task.taskId;option.textContent=task.videoName;option.title=task.videoName;$('tasks').append(option);}$('tasks').value=selected||'';$('page').textContent=`${total} 个视频 · 第 ${Math.floor(offset/12)+1} 页`;const task=tasks.find(value=>value.taskId===selected);if(task&&!$('query').matches(':focus'))$('query').value=task.query;if(task&&!$('provider').matches(':focus'))$('provider').value=task.provider;if(task?.reason&&['failed','interrupted','awaiting_user'].includes(task.phase))notice(task.reason);sync();await downloads();if(selected)await candidates();else{$('candidates').replaceChildren();$('query').value='';$('candidate-prev').disabled=$('candidate-next').disabled=true;}}finally{refreshing=false;if(refreshQueued){refreshQueued=false;queueMicrotask(()=>refresh().catch(()=>{}));}}}
$('search').onclick = () => {
  if (selected) run('online.start', {taskId:selected, query:$('query').value, provider:$('provider').value}, '正在打开字幕网站…');
};
$('query').addEventListener('keydown', event => {
  if (event.key === 'Enter') $('search').click();
});
$('cancel').onclick = () => {
  if (selected) run('online.cancel', {taskId:selected}, $('cancel').textContent === '取消下载' ? '已取消下载。' : '已取消查找。');
};
$('tasks').addEventListener('change',()=>{selected=$('tasks').value;candidateOffset=0;const task=tasks.find(value=>value.taskId===selected);$('query').value=task?.query||'';$('provider').value=task?.provider||'zimuku';sync();candidates().catch(()=>{});});
$('language').addEventListener('change',()=>call('online.configure',{language:$('language').value}).then(()=>notice('语言偏好已保存，下次查找直接使用。')).catch(()=>{}));
$('refresh').addEventListener('click',()=>refresh().catch(()=>{}));
$('previous').addEventListener('click',()=>{offset=Math.max(0,offset-12);candidateOffset=0;refresh().catch(()=>{});});$('next').addEventListener('click',()=>{offset+=12;candidateOffset=0;refresh().catch(()=>{});});
$('candidate-prev').addEventListener('click',()=>{candidateOffset=Math.max(0,candidateOffset-4);candidates().catch(()=>{});});$('candidate-next').addEventListener('click',()=>{candidateOffset+=4;candidates().catch(()=>{});});
const stopChange=api.onChange(()=>refresh().catch(()=>{})),stopNotice=api.onNotice(notice),stopAppearance=api.onAppearance(state=>{document.documentElement.dataset.theme=state.resolvedTheme;});window.addEventListener('pagehide',()=>{stopChange();stopNotice();stopAppearance();},{once:true});
const providerToggle=document.createElement('button');providerToggle.textContent='暂停来源';$('provider').after(providerToggle);
providerToggle.addEventListener('click',async()=>{try{const state=await call('online.query',{limit:1});const stopped=state.stoppedProviders.includes($('provider').value);await call('online.provider',{provider:$('provider').value,enabled:stopped});providerToggle.textContent=stopped?'暂停来源':'恢复来源';await refresh();}catch{}});
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
    const description=document.createElement('small');const state = {receiving:'正在下载…',downloading:'正在下载…',preparing:'正在检查和解压…',ready:'下载完成',interrupted:'下载中断',compacted:'已释放缓存'};
    description.textContent = [row.videoName, row.imported ? '已加入工作台' : state[row.status], row.status === 'interrupted' ? row.message : ''].filter(Boolean).join(' · ');
    card.append(title,description);
    if(row.status==='ready'&&row.fileCount){
      if (!row.imported) {
        const add = document.createElement('button');
        add.className = 'primary';
        add.textContent = '加入工作台';
        add.onclick = () => importDownloads([row.artifactId]);
        card.append(add);
      }
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
  $('import-ready').hidden=downloadRows.filter(row=>row.status==='ready'&&!row.imported).length < 2;
  $('downloads-prev').parentElement.hidden = !downloadOffset && result.total <= 5;
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
$('download-selected').onclick = () => {
  const taskIds = tasks.filter(task => task.phase === 'selected').map(task => task.taskId);
  if (taskIds.length) run('online.download', {taskIds, acknowledged:true}, '正在准备批量下载…');
};
function importDownloads(artifactIds) {
  return run('online.import', {artifactIds, acknowledged:true}, '正在将字幕加入工作台，请回到工作台核对匹配。');
}
$('import-ready').onclick = () => {
  const artifactIds = downloadRows.filter(row => row.status === 'ready' && !row.imported).map(row => row.artifactId);
  if (artifactIds.length) importDownloads(artifactIds);
};
$('open-cache').onclick=()=>call('online.cache').catch(()=>{});
$('downloads-prev').onclick=()=>{downloadOffset=Math.max(0,downloadOffset-5);downloads().catch(()=>{});};
$('downloads-next').onclick=()=>{downloadOffset+=5;downloads().catch(()=>{});};

$('use-page').onclick = () => {
  if (selected) run('online.usePage', {taskId:selected, acknowledged:true}, '正在读取右侧字幕页面…');
};

$('resume-queue').onclick=async()=>{if(await confirmAction('继续上次下载队列？','重新打开已选候选页面；不会自动修改媒体。中断的下载也可在暂存列表单独续传。'))call('online.resumeQueue',{acknowledged:true}).then(refresh).catch(()=>{});};

$('try-backup').onclick=()=>{const sources=['zimuku','srtku','subhd','subhd-one'];$('provider').value=sources[(sources.indexOf($('provider').value)+1)%sources.length];$('search').click();};
