// Disposable presentation state; Python owns the report, context and file reads.
import {el,button} from './icons.js';

const labels={clean:'未发现所检查的格式与时间问题',issues:'发现需要核对的问题',incomplete:'检查未完成，不能据此判定合格',
  encoding_required:'请选择编码并核对预览',unsupported:'此格式暂不支持文字质检',unavailable:'未能完成检查'};
const encodings=['auto','utf-8','utf-8-sig','utf-16-le','utf-16-be','utf-32-le','utf-32-be','gb18030','big5','shift_jis'];
export function validateQualityPage(page,reportId,section,offset){
  if(page.reportId!==reportId||page.qualitySection!==section||page.offset!==offset||
      !Number.isSafeInteger(page.total)||page.total<0||!Array.isArray(page.entries)||
      page.entries.length>page.total-offset||(offset<page.total&&!page.entries.length)||
      page.nextOffset!==(offset+page.entries.length<page.total?offset+page.entries.length:null))throw Error('字幕检查分页已失效，请重新检查。');
  return page;
}
export function validateQualityReport(report){
  if(!report||typeof report.reportId!=='string'||!report.reportId||typeof report.format!=='string'||
      !Object.hasOwn(labels,report.status)||typeof report.encoding!=='string'||
      ['cueCount','issueCount','errors','warnings'].some(key=>!Number.isSafeInteger(report[key])||report[key]<0||report[key]>(key==='cueCount'?50000:500))||
      !Array.isArray(report.encodingCandidates)||report.encodingCandidates.length>5||report.encodingCandidates.some(c=>!encodings.includes(c.encoding)||typeof c.preview!=='string'||c.preview.length>160))throw Error('字幕检查结果格式无效，请重试。');
  return report;
}

export class SubtitleQuality {
  constructor(request){this.request=request;this.states=new Map();this.views=new Set();}
  mount(host,source){
    const key=JSON.stringify(source);
    if(!this.states.has(key))this.states.set(key,{source,encoding:'auto',maxCps:40,loading:false,error:'',ticket:0});
    const view={host,key};this.views.add(view);this.draw(view);
    while(this.views.size>48)this.views.delete(this.views.values().next().value);
    while(this.states.size>12){const first=this.states.keys().next().value;if(first===key)break;this.states.delete(first);}
  }
  notify(key){for(const view of this.views)if(view.key===key&&view.host.isConnected)this.draw(view);}
  sync(){for(const view of this.views){if(!view.host.isConnected)this.views.delete(view);else this.draw(view);}}
  async run(key){
    const state=this.states.get(key);if(!state||state.loading)return;
    const ticket=++state.ticket;state.loading=true;state.error='';state.report=null;this.notify(key);
    try{
      const {scope,...params}=state.source;
      const report=validateQualityReport(await this.request(scope==='online'?'online.quality':'review.quality',{...params,encoding:state.encoding,maxCps:state.maxCps}));
      if(state.ticket!==ticket||this.states.get(key)!==state)return;
      state.report=report;state.page=null;state.history=[];
      await this.page(key,0,false);
    }catch(error){if(state.ticket===ticket)state.error=error.message;}
    finally{if(state.ticket===ticket){state.loading=false;this.notify(key);}}
  }
  async page(key,offset,push=true,section='issues'){
    const state=this.states.get(key);if(!state?.report)return;
    const ticket=state.ticket,reportId=state.report.reportId,pageTicket=(state.pageTicket||0)+1;state.pageTicket=pageTicket;
    try{
      const {scope,...params}=state.source;
      const page=await this.request(scope==='online'?'online.qualityPage':'review.qualityPage',
        {...params,reportId,qualitySection:section,offset,limit:section==='issues'?10:5});
      validateQualityPage(page,reportId,section,offset);
      if(state.ticket!==ticket||state.pageTicket!==pageTicket||state.report?.reportId!==reportId||this.states.get(key)!==state)return;
      if(push&&state.page&&state.page.qualitySection===section&&state.history.at(-1)!==state.page.offset)state.history.push(state.page.offset);
      state.page=page;state.error='';this.notify(key);
    }catch(error){if(state.ticket===ticket&&state.pageTicket===pageTicket){state.error=error.message;this.notify(key);}}
  }
  draw(view){
    const state=this.states.get(view.key);if(!state)return;
    const host=view.host;host.classList.add('subtitle-quality');host.replaceChildren();
    const run=button(state.loading?'正在只读检查…':state.report?'重新检查字幕':'检查字幕质量','subtle-button',()=>this.run(view.key),'search');
    run.disabled=state.loading;host.append(run);
    if(state.error)host.append(el('p','notice warning',`检查未完成：${state.error}。文件列表和原文件已保留。`));
    if(!state.report)return;
    const report=state.report;
    host.append(el('p','quality-summary',labels[report.status]||'检查状态未知'),
      el('small','subtle-text',`${report.format.toUpperCase()} · ${report.encoding||'编码待确认'} · ${report.cueCount} 条对白 · ${report.errors} 项错误 / ${report.warnings} 项提示`));
    host.append(el('small','subtle-text','只检查这一份本地快照；不证明影视版本或时间同步正确，不自动修复。'));
    const options=el('details','quality-options');options.append(el('summary','','编码与阅读速度'));
    const encoding=el('select');encoding.setAttribute('aria-label','字幕编码');
    for(const code of encodings){const option=el('option','',code==='auto'?'自动（优先 BOM / UTF-8）':code);option.value=code;encoding.append(option);}
    encoding.value=state.encoding;encoding.disabled=state.loading;encoding.onchange=()=>{state.encoding=encoding.value;};
    const speed=el('select');speed.setAttribute('aria-label','阅读速度阈值');
    for(const value of [20,40,60,100]){const option=el('option','',`${value} 字符/秒`);option.value=String(value);speed.append(option);}
    speed.value=String(state.maxCps);speed.disabled=state.loading;speed.onchange=()=>{state.maxCps=Number(speed.value);};
    options.append(encoding,speed);host.append(options);
    for(const candidate of report.encodingCandidates||[]){
      const block=el('details');block.append(el('summary','',`${candidate.encoding} 预览`),el('pre','quality-excerpt',candidate.preview));
      block.append(button('使用此编码重新检查','subtle-button',()=>{state.encoding=candidate.encoding;this.run(view.key);}));host.append(block);
    }
    const page=state.page;
    if(page){
      const entries=el('div','quality-entries');
      for(const entry of page.entries){const item=el('div','quality-entry');
        item.append(el('strong','',entry.message||`字幕片段 ${entry.cue}`),
          el('small','subtle-text',`${entry.line?`第 ${entry.line} 行`:'整体检查'}${entry.cue?` · 条目 ${entry.cue}`:''}${entry.start!=null?` · ${entry.start/1000}–${entry.end/1000} 秒`:''}`));
        const fields=[entry.kind==='comment'?'注释':'',entry.style?`样式 ${entry.style}`:'',entry.layer?`层 ${entry.layer}`:'',entry.settings].filter(Boolean);
        if(fields.length)item.append(el('small','subtle-text',fields.join(' · ')));
        if(entry.excerpt)item.append(el('pre','quality-excerpt',entry.excerpt));entries.append(item);
      }host.append(entries);
      if(page.qualitySection==='issues'&&page.total&&(page.total>page.entries.length||state.history.length)){
        const previous=button('上一页','subtle-button',()=>{const offset=state.history.pop();if(offset!=null)this.page(view.key,offset,false);});previous.disabled=!state.history.length;
        const next=button('下一页','subtle-button',()=>this.page(view.key,page.nextOffset));next.disabled=page.nextOffset==null;
        host.append(previous,el('small','subtle-text',`${page.offset+1}–${page.offset+page.entries.length} / ${page.total}`),next);
      }else if(page.qualitySection==='issues'&&page.total)host.append(el('small','subtle-text',`共 ${page.total} 项检查结果`));
    }
    if(report.cueCount)host.append(button(page?.qualitySection==='cues'?'返回问题列表':'查看前五条字幕片段','subtle-button',()=>{state.history=[];this.page(view.key,0,false,page?.qualitySection==='cues'?'issues':'cues');}));
  }
}
