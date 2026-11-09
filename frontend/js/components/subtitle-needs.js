import {el,button} from './icons.js';

const $=id=>document.getElementById(id);
const LANGUAGES=[['chinese','中文'],['bilingual','中英双语'],['simplified','简体中文'],['traditional','繁体中文'],['english','英语'],['japanese','日语'],['korean','韩语']];
const STATES={satisfied:'已满足',review:'待核对',missing:'缺失'};

export function prepareNeedsDialog() {
  const entry=button('字幕需求','subtle-button');entry.id='subtitle-needs-button';entry.disabled=true;
  document.querySelector('.page-heading').append(entry);
  const dialog=el('dialog','needs-dialog');dialog.id='needs-dialog';dialog.setAttribute('aria-labelledby','needs-title');
  const heading=el('div','dialog-heading'),title=el('h2','','字幕需求');title.id='needs-title';title.tabIndex=-1;title.dataset.initialFocus='';
  const close=button('','icon-button',null,'x');close.dataset.close='';close.setAttribute('aria-label','关闭字幕需求');heading.append(title,close);dialog.append(heading);
  dialog.append(el('p','dialog-note','先看本地还缺什么，再查找。检查不会联网、修改或导出字幕。'));
  const field=el('fieldset','needs-languages');field.append(el('legend','','需要哪些完整字幕（最多四种）'));
  for(const [value,label] of LANGUAGES){const row=el('label'),input=el('input');input.type='checkbox';input.value=value;input.name='needs-language';row.append(input,document.createTextNode(label));field.append(row);}
  dialog.append(field);
  for(const [id,label] of [['needs-sdh','允许 SDH 满足普通完整字幕'],['needs-forced','另外补齐所选语言的强制/片段字幕']]){
    const row=el('label','needs-option'),input=el('input');input.type='checkbox';input.id=id;row.append(input,document.createTextNode(label));dialog.append(row);
  }
  const actions=el('div','needs-actions'),save=button('保存需求','secondary'),check=button('检查本地字幕','primary');save.id='needs-save';check.id='needs-check';actions.append(save,check);dialog.append(actions);
  const status=el('p','dialog-note');status.id='needs-status';status.setAttribute('role','status');dialog.append(status);
  const rows=el('div','needs-rows');rows.id='needs-rows';dialog.append(rows);
  const footer=el('div','needs-actions'),previous=button('上一页','secondary'),next=button('下一页','secondary'),search=button('查找缺失字幕','primary');
  previous.id='needs-previous';next.id='needs-next';search.id='needs-search';footer.append(previous,next,search);dialog.append(footer);document.body.append(dialog);
}

export class SubtitleNeedsPanel {
  constructor(options) {
    Object.assign(this,options);this.running=false;this.report=null;this.offset=0;
    const bind=(id,fn)=>$(id).addEventListener('click',()=>this.run(fn));
    bind('subtitle-needs-button',()=>this.open());bind('needs-save',()=>this.save());bind('needs-check',()=>this.check());
    bind('needs-previous',()=>this.page(Math.max(0,this.offset-20)));bind('needs-next',()=>this.page(this.offset+20));
    bind('needs-search',async()=>{
      await this.adapter.request('subtitle.open',{...this.context,needsId:this.report.needsId});
      await this.dialogs.modals.needs.close();this.toast('已打开缺失字幕查找；确认搜索后才会联网');
    });
    this.controls();
  }
  async run(fn) {
    if(this.running)return;this.running=true;this.controls();
    try{await fn();}catch(error){$('needs-status').textContent=error.message;this.toast(error.message,{tone:'error'});}
    finally{this.running=false;this.controls();}
  }
  controls() {
    for(const node of document.querySelectorAll('#needs-dialog input,#needs-dialog button:not([data-close])'))node.disabled=this.running;
    $('needs-previous').disabled=this.running||!this.report||this.offset===0;
    $('needs-next').disabled=this.running||!this.report||this.offset+20>=this.report.total;
    $('needs-search').disabled=this.running||!this.report?.missingVideos;
    for(const node of document.querySelectorAll('#needs-dialog [data-stage]'))node.disabled=this.running||!node.previousElementSibling.querySelector('input').checked;
  }
  async open() {
    const policy=await this.adapter.request('requirements.policy');
    for(const node of document.querySelectorAll('[name=needs-language]'))node.checked=policy.languages.includes(node.value);
    $('needs-sdh').checked=policy.allowSDH;$('needs-forced').checked=policy.includeForced;
    this.context=this.store.params();this.report=null;this.offset=0;$('needs-rows').replaceChildren();
    $('needs-status').textContent='选择需求后保存，再检查当前扫描的本地字幕。编码或归属不确定时会标为待核对。';
    this.dialogs.open('needs',$('subtitle-needs-button'));
  }
  async save() {
    await this.adapter.request('requirements.configure',{languages:[...document.querySelectorAll('[name=needs-language]:checked')].map(n=>n.value),allowSDH:$('needs-sdh').checked,includeForced:$('needs-forced').checked});
    await this.load('restore');this.context=this.store.params();this.report=null;$('needs-rows').replaceChildren();
    $('needs-status').textContent='需求已保存，原关联保留。规则变化后需重新核对匹配；旧预览不能继续执行。';
  }
  async check() {
    // Persist visible preferences before using them; no silently unsaved policy.
    await this.save();$('needs-status').textContent='正在检查本地字幕…';
    this.report=await this.adapter.request('requirements.check',this.context);await this.page(0);
  }
  async page(offset) {
    const page=await this.adapter.request('requirements.query',{...this.context,needsId:this.report.needsId,offset,limit:20});
    const fragment=document.createDocumentFragment();
    for(const row of page.rows){
      const card=el('article','needs-row');card.append(el('h3','',row.videoName));
      for(const requirement of row.requirements){const line=el('p');line.append(el('strong',`needs-${requirement.state}`,`${requirement.label} · ${STATES[requirement.state]}`),el('small','',requirement.reason));card.append(line);}
      const view=button('查看视频','subtle-button');view.addEventListener('click',()=>this.run(async()=>{await this.dialogs.modals.needs.close();await this.store.select(row.rowId);}));card.append(view);
      for(const offer of row.offers){
        const proposal=el('div','needs-upgrade');proposal.append(el('strong','','可核对的升级候选'),el('p','',`当前 · ${offer.originalSource} / ${offer.original}`),el('p','',`候选 · ${offer.candidateSource} / ${offer.candidate}`),el('small','',offer.reason));
        const label=el('label','needs-option'),ack=el('input');ack.type='checkbox';label.append(ack,document.createTextNode('保留原字幕，将新候选加入待确认审阅'));
        const stage=button('加入升级审阅','secondary');stage.dataset.stage='';stage.disabled=true;ack.addEventListener('change',()=>this.controls());
        stage.addEventListener('click',()=>this.run(async()=>{
          await this.adapter.request('requirements.stage',{...this.context,needsId:this.report.needsId,offerId:offer.offerId,acknowledged:ack.checked});
          await this.dialogs.modals.needs.close();await this.load('restore');await this.store.select(row.rowId);
          this.report=null;this.toast('升级候选已加入审阅，原文件已保留；核对后重新预览并确认整理');
        }));proposal.append(label,stage);card.append(proposal);
      }
      fragment.append(card);
    }
    $('needs-rows').replaceChildren(fragment);this.report=page;this.offset=offset;
    $('needs-status').textContent=`${page.satisfiedVideos} 个已满足 · ${page.missingVideos} 个有缺失 · ${page.reviewVideos} 个有待核对项 · ${page.upgradeCount} 个升级候选${page.limited?'。本次达到读取限额，未检查部分保持待核对。':''}（${page.total?offset+1:0}–${Math.min(offset+page.rows.length,page.total)} / ${page.total}）`;
  }
}
