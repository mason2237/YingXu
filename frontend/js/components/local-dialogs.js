import {WorkspaceDialogs} from './dialogs.js';
import {el,iconNode,button,language,badge} from './icons.js';

const $ = id => document.getElementById(id);
const PAGE_SIZE = 20, CANDIDATE_SIZE = 6;

// Production dialogs share the established modal, focus and appearance controls.
// Python owns every matching decision, frozen filename and execution token.
export class LocalWorkspaceDialogs extends WorkspaceDialogs {
  constructor(...args) {
    super(...args);this.adapter = this.store.adapter;this.records = [];this.historyPage = 0;
    this.executing = false;this.previewLoading = false;this.historyLoading = false;
    const bind = (id,run) => $(id).addEventListener('click',() => Promise.resolve(run()).catch(error => this.toast(error.message,{tone:'error'})));
    $('preview-ack').addEventListener('change',() => this.syncExecution());
    bind('execute-button',() => this.execute());
    bind('candidate-previous',() => this.candidatePage(this.candidateOffset-CANDIDATE_SIZE));
    bind('candidate-next',() => this.candidatePage(this.candidateOffset+CANDIDATE_SIZE));
    bind('history-previous',() => this.recordPage(this.historyPage-1));
    bind('history-next',() => this.recordPage(this.historyPage+1));
    bind('export-record',() => this.exportRecord());
    $('history-record').addEventListener('change',() => this.recordPage(0,$('history-record').value).catch(error => this.toast(error.message,{tone:'error'})));
    this.syncExecution();
  }
  syncExecution() {
    $('execute-button').disabled = !this.plan?.canExecute || !$('preview-ack').checked || this.store.busy || this.executing || this.previewLoading;
    $('preview-ack').disabled = this.executing || this.previewLoading;
    this.syncRecordControls();
  }
  syncRecordControls() {
    const blocked = this.store.busy || this.historyLoading;
    $('history-record').disabled = blocked || !this.records.length;
    $('export-record').disabled = blocked || !this.record;
    $('history-previous').disabled = blocked || !this.record || !this.historyPage;
    $('history-next').disabled = blocked || !this.record || (this.historyPage+1)*PAGE_SIZE >= this.record.itemCount;
  }
  async candidates() {
    if (this.store.busy || !this.store.details) return;
    this.candidateRow = this.store.details;await this.candidatePage(0);this.modals.candidate.open();
  }
  async candidatePage(offset) {
    if (this.store.busy) return;
    const row = this.candidateRow;if (!row || row.rowId !== this.store.selectedId) throw new Error('选择已变化，请重新打开候选字幕。');
    $('candidate-previous').disabled = $('candidate-next').disabled = true;
    let response;
    try {response = await this.adapter.request('review.candidates',this.store.params({rowId:row.rowId,offset:Math.max(0,offset),limit:CANDIDATE_SIZE}));}
    catch (error) {$('candidate-previous').disabled = !this.candidateOffset;$('candidate-next').disabled = (this.candidateOffset || 0)+CANDIDATE_SIZE >= (this.candidateTotal || 0);throw error;}
    this.candidateOffset = response.offset;this.candidateTotal = response.total;
    $('candidate-video').textContent = row.video.name;$('candidate-list').replaceChildren();
    for (const candidate of response.rows) {
      const card = el('article',`candidate-card${candidate.recommended ? ' recommended' : ''}`);card.dataset.candidateId = candidate.subtitleId;
      const header = el('header');header.append(language(candidate.language),el('span','',candidate.recommended ? '优先核对' : `候选 ${candidate.rank+1}`));
      card.append(header,el('h3','',candidate.name),el('div','candidate-score',`${Math.round(candidate.score*100)}%`),el('p','',candidate.reason),el('p','',`集数标识 · ${candidate.episode}`));
      const path = el('p','subtle-text',candidate.displayPath);path.title = candidate.displayPath;card.append(path);
      if (candidate.conflict) {const warning = el('div','notice warning');warning.append(iconNode('alert'),document.createTextNode('集数不一致，请核对后选择。'));card.append(warning);}
      const assign = button(candidate.disabled ? candidate.reason : row.subtitles.some(sub => sub.language === candidate.language) ? '替换此语言字幕' : '使用这份字幕',candidate.recommended ? 'primary' : 'secondary',async () => {
        if (this.store.busy) return;assign.disabled = true;
        try {
          if (this.store.selectedId !== row.rowId) throw new Error('选择已变化，请重新打开候选字幕。');
          const replace = row.subtitles.find(sub => sub.language === candidate.language);
          await this.mutate('review.assign',{subtitleId:candidate.subtitleId,replaceId:replace?.subtitleId || null});await this.modals.candidate.close();
        } catch (error) {this.toast(error.message,{tone:'error'});assign.disabled = Boolean(candidate.disabled);}
      });
      assign.disabled = candidate.disabled;card.append(assign);$('candidate-list').append(card);
    }
    if (!response.total) $('candidate-list').append(el('p','command-empty','目录中没有可用字幕。检查扫描选项或选择其他目录。'));
    $('candidate-page').textContent = `${response.total} 份候选 · 第 ${Math.floor(response.offset/CANDIDATE_SIZE)+1} / ${Math.max(1,Math.ceil(response.total/CANDIDATE_SIZE))} 页`;
    $('candidate-previous').disabled = !response.offset;$('candidate-next').disabled = response.offset+CANDIDATE_SIZE >= response.total;
  }
  async preview() {
    if (this.store.busy || this.previewLoading) return;
    this.previewLoading = true;this.plan = null;this.syncExecution();
    try {
      this.plan = await this.adapter.request('preview.create',this.store.params());this.page = 0;$('preview-ack').checked = false;
      await this.renderPlan();this.modals.preview.open();this.feedback.workflow(3);
    } finally {this.previewLoading = false;this.syncExecution();}
  }
  async renderPlan() {
    const plan = this.plan;if (!plan) return;
    $('preview-prev').disabled = $('preview-next').disabled = true;
    const response = await this.adapter.request('preview.query',{snapshotId:plan.snapshotId,offset:this.page*PAGE_SIZE,limit:PAGE_SIZE});
    $('preview-summary').textContent = `${plan.changeCount} 份字幕可整理 · ${plan.unmatchedCount} 个视频未匹配 · 核对后才会修改文件`;
    const warning = $('preview-warning');warning.hidden = !plan.pendingCount && !plan.conflictCount;
    warning.textContent = `还有 ${plan.pendingCount} 项匹配待确认、${plan.conflictCount} 项冲突。请返回审阅后重新生成预览。`;
    const labels = {rename:['待整理','待整理'],skipped:['已跳过','已跳过'],unchanged:['已符合','无需变更'],pending:['需确认','待确认'],blocked:['存在冲突','已阻止'],unmatched:['未匹配','未匹配']};
    const fragment = document.createDocumentFragment();
    for (const item of response.items) {
      const row = el('div','preview-item'),source = el('div'),target = el('div','preview-target');
      source.append(el('small','',item.videoName),el('strong','',item.sourceName),el('small','',item.sourcePath));
      target.append(el('strong','',item.targetName),el('small','',item.targetPath));
      const label = labels[item.action] || ['未匹配','未匹配'],status = badge(label[0]);status.lastChild.textContent = label[1];
      row.append(source,iconNode('arrow'),target,status);fragment.append(row);
    }
    $('preview-items').replaceChildren(fragment);$('preview-items').scrollTop = 0;
    const pages = Math.max(1,Math.ceil(plan.itemCount/PAGE_SIZE));
    $('preview-page-label').textContent = `${plan.itemCount} 项 · 第 ${this.page+1} / ${pages} 页`;
    $('preview-prev').disabled = this.page === 0;$('preview-next').disabled = this.page+1 >= pages;
  }
  async execute() {
    if ($('execute-button').disabled || this.executing) return;
    const plan = this.plan;this.executing = true;this.syncExecution();
    try {
      const started = await this.adapter.start('organize.confirmAndStart',{scanId:plan.scanId,reviewRevision:plan.revision,snapshotId:plan.snapshotId,confirmationToken:plan.confirmationToken,acknowledged:$('preview-ack').checked});
      plan.canExecute = false;await this.modals.preview.close();
      const result = await this.adapter.waitJob(started.jobId);await this.store.refresh(true);await this.showResult(result.batchId);
    } catch (error) {
      plan.canExecute = false;this.toast(`${error.message} 请重新核对预览后操作。`,{tone:'error'});
      try {if (!this.store.busy) await this.store.refresh(true);} catch { /* A later explicit scan can restore the view. */ }
    } finally {this.executing = false;this.syncExecution();}
  }
  updateRecords(records) {
    this.records = records;$('history-record').replaceChildren();
    for (const record of records) {const option = el('option','',`${record.title} · ${this.time(record.time)}`);option.value = record.recordId;$('history-record').append(option);}
  }
  time(value) {const date = new Date(value);return Number.isNaN(date.valueOf()) ? value : date.toLocaleString('zh-CN',{hour12:false});}
  async history() {
    if (this.store.busy || this.historyLoading) return;
    this.historyLoading = true;this.syncRecordControls();
    try {this.updateRecords(await this.adapter.request('history.list',{limit:30}));}
    finally {this.historyLoading = false;this.syncRecordControls();}
    if (this.records.length) await this.recordPage(0,this.records[0].recordId);
    else {this.record = null;$('history-content').replaceChildren(el('p','command-empty','还没有整理记录。完成整理后，结果会显示在这里。'));$('history-warning').hidden = true;$('history-page').textContent = '0 条记录';this.syncRecordControls();}
    this.modals.history.open();
  }
  async showResult(batchId) {
    const record = await this.adapter.request('result.get',{batchId,offset:0,limit:PAGE_SIZE});
    this.updateRecords([record]);this.historyPage = 0;this.record = record;this.renderRecord();this.modals.history.open();
  }
  async recordPage(page,identifier = this.record?.recordId) {
    if (this.historyLoading || !identifier) return;
    this.historyLoading = true;this.syncRecordControls();
    try {
      const record = await this.adapter.request('history.get',{recordId:identifier,offset:Math.max(0,page)*PAGE_SIZE,limit:PAGE_SIZE});
      this.record = record;this.historyPage = Math.max(0,page);this.renderRecord();
    } finally {this.historyLoading = false;this.syncRecordControls();}
  }
  renderRecord() {
    const record = this.record,root = $('history-content');root.replaceChildren();$('history-record').value = record.recordId;
    const warning = $('history-warning');warning.hidden = !record.issue && !record.historyError;warning.textContent = [record.issue,record.historyError && `本地历史保存失败：${record.historyError}。请导出本次记录。`].filter(Boolean).join(' ');
    const summary = el('section','history-summary');summary.append(el('h3','',record.title),el('p','',this.time(record.time)));
    const counts = el('div','result-counts');
    for (const [value,label] of [[record.success,'成功'],[record.skipped,'跳过'],[record.errors,'异常']]) {const cell = el('span');cell.append(el('strong','',String(value)),document.createTextNode(label));counts.append(cell);}summary.append(counts);
    summary.append(el('p','history-meta',`无需变更 ${record.unchanged} · 未匹配 ${record.unmatched} · 未执行 ${record.cancelled}`));
    const distribution = el('div','result-distribution');distribution.setAttribute('aria-hidden','true');
    const values = [[record.success,'success'],[record.skipped+record.unchanged+record.unmatched+record.cancelled,'skipped'],[record.errors,'error']],total = values.reduce((sum,[value]) => sum+value,0);
    for (const [value,tone] of values) {const part = el('span');part.dataset.tone = tone;part.style.width = `${total ? value/total*100 : 0}%`;distribution.append(part);}summary.append(distribution);root.append(summary);
    const items = el('ol','history-list');
    for (const item of record.items) {
      const row = el('li','history-item'),names = el('div'),tone = item.status === 'success' ? 'success' : ['error','blocked'].includes(item.status) ? 'error' : 'skipped';row.dataset.tone = tone;
      names.append(el('p','',item.source),el('small','',`→ ${item.target}`));names.title = `${item.sourcePath}\n${item.targetPath}`;
      if (item.error) names.append(el('p','history-error',item.error));
      row.append(iconNode(tone === 'error' ? 'alert' : tone === 'success' ? 'check' : 'minus'),names,el('span','history-state',item.state));items.append(row);
    }
    root.append(items);root.scrollTop = 0;
    $('history-page').textContent = `${record.itemCount} 项 · 第 ${this.historyPage+1} / ${Math.max(1,Math.ceil(record.itemCount/PAGE_SIZE))} 页`;this.syncRecordControls();
  }
  async exportRecord() {
    if (this.store.busy || this.historyLoading || !this.record) return;
    this.historyLoading = true;this.syncRecordControls();
    try {const result = await this.adapter.request('result.export',{recordId:this.record.recordId});if (!result.cancelled) this.toast('完整整理记录已导出',{tone:'success'});}
    finally {this.historyLoading = false;this.syncRecordControls();}
  }
}
