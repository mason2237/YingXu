import {el,button} from './icons.js';

export function mountSync(host,{request,context,refresh}) {
  const panel=el('details','subtitle-sync'),title=el('summary','','调整字幕时间');panel.append(title,el('p','subtle-text','正偏移表示延后；早于零的时间会被拒绝。只生成新候选，保留原字幕。'));
  const mode=el('select');mode.setAttribute('aria-label','时间调整方式');
  for(const [value,label] of [['manual','手动偏移'],['reference','对齐参考字幕'],['audio','对齐所选音轨']]){const option=el('option','',label);option.value=value;mode.append(option);}
  const offset=el('input');offset.type='number';offset.min=-86400000;offset.max=86400000;offset.step=100;offset.value=0;offset.setAttribute('aria-label','偏移毫秒');
  const ref=el('select');ref.setAttribute('aria-label','可信本地参考字幕');ref.hidden=true;
  const paging=el('div','needs-actions'),previous=button('上一组参考','subtle-button'),next=button('下一组参考','subtle-button');paging.append(previous,next);paging.hidden=true;
  const encoding=el('select');encoding.setAttribute('aria-label','源字幕编码');
  for(const value of ['auto','utf-8','gb18030','big5','shift_jis']){const option=el('option','',value==='auto'?'自动识别编码':value);option.value=value;encoding.append(option);}
  const create=button('生成时间预览','secondary'),results=button('查看保留的处理结果','subtle-button'),body=el('div','sync-result');
  const track=el('input');track.type='number';track.min=0;track.max=31;track.placeholder='主动选择音轨编号，首轨为 0';track.setAttribute('aria-label','音轨编号');track.hidden=true;
  const tool=button('选择本机 FFmpeg','subtle-button');tool.hidden=true;
  const audioNote=el('p','subtle-text','音频模式会读取完整视频核对缓存，再分析指定音轨；不提取字幕轨、不上传。最多分析四小时，证据不足会拒绝采用。');audioNote.hidden=true;
  panel.append(mode,offset,encoding,ref,paging,track,tool,audioNote,create,results,body);host.append(panel);let busy=false,refOffset=0,refTotal=0;
  const run=async fn=>{if(busy)return;busy=true;create.disabled=results.disabled=true;try{await fn();}catch(error){if(panel.isConnected)body.textContent=error.message;}finally{busy=false;create.disabled=results.disabled=false;}};
  const references=async page=>{const list=await request('sync.references',{scanId:context.scanId,revision:context.revision,rowId:context.rowId,offset:page,limit:20});refOffset=page;refTotal=list.total;ref.replaceChildren(el('option','','请选择另一份可信参考字幕'));for(const item of list.rows){if(item.subtitleId===context.subtitleId)continue;const option=el('option','',item.name);option.value=item.subtitleId;ref.append(option);}ref.firstChild.value='';previous.disabled=!page;next.disabled=page+list.rows.length>=refTotal;};
  mode.onchange=()=>run(async()=>{ref.hidden=paging.hidden=mode.value!=='reference';offset.hidden=mode.value!=='manual';track.hidden=tool.hidden=audioNote.hidden=mode.value!=='audio';if(mode.value==='reference')await references(0);if(mode.value==='audio'){const cap=await request('sync.capabilities');if(!cap.audio)body.textContent='请先选择你信任的本机 FFmpeg；此程序不自动下载外部工具。';}});
  tool.onclick=()=>run(async()=>{await request('sync.tool');body.textContent='已核对工具；请主动选择音轨编号再生成预览。';});
  const cleanup=button('清理音频分析缓存','subtle-button');cleanup.onclick=()=>run(async()=>{const value=await request('sync.clearAnalysis',{acknowledged:true});body.textContent=`已清理 ${value.removedFiles} 个可重建的分析缓存文件；字幕候选、恢复与撤销备份保留。`;});panel.append(cleanup);
  const openCache=button('打开处理缓存','subtle-button',()=>request('sync.cache').catch(error=>body.textContent=error.message));panel.append(openCache);
  const compare=button('比较参考字幕的文本','subtle-button');panel.append(compare);
  compare.onclick=()=>run(async()=>{
    if(!ref.value)throw Error('请先切换“对齐参考字幕”，主动选择同语言参考。只读取前六份候选字幕，不读取视频。');
    const value=await request('content.compare',{scanId:context.scanId,revision:context.revision,rowId:context.rowId,referenceId:ref.value});
    body.replaceChildren(el('p','subtle-text',value.scope));
    for(const row of value.rows){body.append(el('strong','',row.name),el('p','subtle-text',`${row.score===null?'证据不足':`文本相似度 ${Math.round(row.score*100)}%`} · ${row.reason}`));for(const excerpt of row.excerpts||[])body.append(el('p','subtle-text',excerpt));}
    if(value.margin!==null)body.append(el('small','subtle-text',`前两项差距 ${value.margin}；分值不表示概率，不会自动改配。`));
  });
  previous.onclick=()=>run(()=>references(Math.max(0,refOffset-20)));next.onclick=()=>run(()=>references(refOffset+20));
  function show(value){
    if(!panel.isConnected)return;body.replaceChildren();
    if(!value.artifactId){body.append(el('p','subtle-text',value.reason||value.status));return;}
    body.append(el('p','',`${value.engine} · ${value.offsetMs>0?'+':''}${value.offsetMs} 毫秒 · 时间比例 ${value.scale.toFixed(6)}`),
      el('small','subtle-text',`${value.before.cueCount} 条字幕，首条 ${value.before.firstMs} → ${value.after.firstMs} 毫秒；${value.quality.reason}`));
    const label=el('label','needs-option'),ack=el('input');ack.type='checkbox';label.append(ack,document.createTextNode('保留原字幕，将新结果加入待确认审阅'));
    const stage=button('加入审阅','secondary');stage.disabled=true;ack.onchange=()=>stage.disabled=!ack.checked;
    stage.onclick=()=>run(async()=>{await request('sync.stage',{scanId:context.scanId,revision:context.revision,rowId:context.rowId,artifactId:value.artifactId,acknowledged:ack.checked});await refresh();});body.append(label,stage);
    const discard=button('清除此未引用结果','subtle-button');discard.onclick=()=>run(async()=>{await request('sync.discard',{scanId:context.scanId,revision:context.revision,rowId:context.rowId,artifactId:value.artifactId,acknowledged:true});body.textContent='已清除未引用的处理缓存。';});body.append(discard);
  }
  create.onclick=()=>run(async()=>{if(mode.value==='audio'&&track.value==='')throw Error('请主动填写音轨编号，第一条音轨为 0。');show(await request('sync.create',{...context,syncMode:mode.value,encoding:encoding.value,...(mode.value==='reference'?{referenceId:ref.value}:mode.value==='audio'?{audioTrack:Number(track.value)}:{offsetMs:Number(offset.value)})}));});
  results.onclick=()=>run(async()=>{const list=await request('sync.results',{scanId:context.scanId,revision:context.revision,rowId:context.rowId,limit:20});body.replaceChildren();if(!list.rows.length)body.textContent='没有保留的处理结果。';for(const item of list.rows){const open=button(`${item.name} · ${item.offsetMs} 毫秒`,'subtle-button',()=>show(item));body.append(open);}});
}
