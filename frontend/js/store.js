export class WorkspaceStore extends EventTarget {
  constructor(adapter) {
    super(); this.adapter = adapter; this.filters = {search: '', status: 'all', fileType: '', sortKey: 'name', sortDir: 'asc'};
    this.summary = {scanId:null,revision:0,counts: {all: 0}}; this.view = {total: 0, ids: []}; this.selectedId = null; this.details = null; this.loading = false; this.error = ''; this.ticket = 0;this.selectionTicket = 0;
    adapter.addEventListener('loading', event => this.dispatchEvent(new CustomEvent('loading', {detail: event.detail})));
  }
  get busy() {return this.loading || Boolean(this.adapter.state?.busy);}
  params(extra = {}) {return {scanId: this.summary.scanId, revision: this.summary.revision, ...extra};}
  changed(reset = false) {this.dispatchEvent(new CustomEvent('change',{detail:{reset}}));}
  async load(scenario) {
    if (this.loading) return;
    this.loading = true;this.ticket++;this.selectionTicket++; this.error = '';this.cancelled = false; this.dispatchEvent(new Event('busy'));
    try {
      const summary = await this.adapter.load(scenario);
      this.cancelled = Boolean(summary.cancelled);
      if (!this.cancelled) {this.summary = summary;this.selectedId = null;this.filters.search = '';this.filters.status = 'all';this.filters.fileType = '';}
      await this.refresh(!this.cancelled);
    } catch (error) {
      if (error.code === 'CANCELLED') {this.cancelled = true;await this.refresh(true);}
      else {this.summary = this.adapter.state?.summary || this.summary;this.error = error.message;this.view = {total:0,ids:[]};this.details = null;this.selectedId = null;}
    } finally {this.loading = false;this.changed(!this.cancelled);}
  }
  async refresh(reset = false) {
    const ticket = ++this.ticket;this.selectionTicket++;
    const summary = await this.adapter.request('app.state');
    const view = await this.adapter.request('review.query', {scanId:summary.scanId,revision:summary.revision,...this.filters, offset: 0, limit: 1,includeIds:true});
    if (ticket !== this.ticket) return;
    const selectedId = view.ids.includes(this.selectedId) ? this.selectedId : view.ids[0] || null;
    const details = selectedId ? await this.adapter.request('review.details', {scanId:summary.scanId,revision:summary.revision,rowId:selectedId}) : null;
    if (ticket !== this.ticket) return;
    this.summary = summary;this.view = view;this.selectedId = selectedId;this.details = details;this.changed(reset);
  }
  async select(rowId) {
    if (!this.view.ids.includes(rowId) || this.busy) return;
    const ticket = ++this.selectionTicket;
    try {
      const details = await this.adapter.request('review.details', this.params({rowId}));
      if (ticket !== this.selectionTicket || this.busy) return;
      this.selectedId = rowId;this.details = details;this.dispatchEvent(new Event('selection'));
    } catch (error) {if (ticket === this.selectionTicket && !this.busy) this.dispatchEvent(new CustomEvent('error',{detail:error.message}));}
  }
  async filter(patch) {if (this.busy) return; Object.assign(this.filters, patch); await this.refresh(true);}
  async mutate(action, extra = {}) {
    if (this.busy) throw new Error('请等待当前任务结束。');
    if (!this.selectedId) throw new Error('请先选择一个视频。');
    this.loading = true;this.ticket++;this.selectionTicket++;this.dispatchEvent(new Event('busy'));
    try {await this.adapter.request(action, this.params({rowId: this.selectedId, ...extra}));await this.refresh();}
    finally {this.loading = false;this.changed();}
  }
  async rows(offset, limit) {return (await this.adapter.request('review.query', this.params({...this.filters, offset, limit,includeIds:false}))).rows;}
}
