import {BridgeClient} from './bridge-client.js';

export class LocalAdapter extends EventTarget {
  constructor() {
    super();this.mode = 'local';this.client = new BridgeClient();this.waiters = new Map();this.poll = 0;this.closed = false;
    this.client.addEventListener('state',event => {
      const message = event.detail;this.receive(message.payload.state);
      if (message.type === 'folder.changed' && message.payload.dropped) this.dispatchEvent(new Event('folderdrop'));
      if (message.type === 'app.error') this.dispatchEvent(new CustomEvent('error',{detail:message.payload.message}));
    });
    window.addEventListener('pagehide',() => {
      this.closed = true;clearTimeout(this.poll);this.client.dispose();
      for (const group of this.waiters.values()) for (const waiter of group) {const error = new Error('页面已关闭');error.code = 'CLOSING';waiter.reject(error);}
      this.waiters.clear();
    },{once:true});
  }
  async init() {if (!this.ready) this.ready = this.client.connect().then(state => {this.receive(state);return state;});return this.ready;}
  receive(state) {
    if (!state || this.closed) return;
    this.state = state;
    if (state.job?.status === 'running') this.dispatchEvent(new CustomEvent('loading',{detail:state.job}));
    this.dispatchEvent(new CustomEvent('backend',{detail:state}));
    const job = state.job;
    if (job && !state.busy && job.status !== 'running' && this.waiters.has(job.jobId)) {
      const group = this.waiters.get(job.jobId);this.waiters.delete(job.jobId);
      for (const waiter of group) {
        if (job.status === 'completed') waiter.resolve(job.result);
        else {const error = new Error(job.error?.message || job.message);error.code = job.error?.code;waiter.reject(error);}
      }
    }
    if (!this.waiters.size) {clearTimeout(this.poll);this.poll = 0;}
  }
  waitJob(jobId) {
    const promise = new Promise((resolve,reject) => {const group = this.waiters.get(jobId) || [];group.push({resolve,reject});this.waiters.set(jobId,group);});
    this.receive(this.state);this.pollState();return promise;
  }
  pollState() {
    if (!this.waiters.size || this.poll || this.closed) return;
    // Read-only resynchronization; no mutation request is ever retried.
    this.poll = setTimeout(async () => {
      this.poll = 0;
      try {this.receive(await this.client.call('app.state'));} catch (error) {this.dispatchEvent(new CustomEvent('error',{detail:error.message}));}
      this.pollState();
    },2000);
  }
  async start(action, params = {}) {
    await this.init();return this.client.call(action,params,{timeout:['folder.choose','result.export'].includes(action) ? 0 : 10000});
  }
  async request(action, params = {}) {
    const response = await this.start(action,params);
    if (action === 'app.state') {this.receive(response);return response.summary;}
    return response?.jobId ? this.waitJob(response.jobId) : response;
  }
  async load(command = 'restore') {
    await this.init();
    if (command === 'choose') {
      const response = await this.request('folder.choose');
      if (response.cancelled) return {cancelled:true};
      await this.request('app.state');command = 'scan';
    }
    if (command === 'scan' || (command === 'restore' && this.state.summary.folderPending && !this.state.busy)) {
      const options = command === 'restore' ? this.state.summary.options : this.readOptions?.() || this.state.summary.options;
      await this.request('scan.start',{folderId:this.state.summary.folderId,...options});
    } else if (this.state.busy && this.state.job) {
      try {await this.waitJob(this.state.job.jobId);} catch (error) {if (!['CANCELLED','STALE_PLAN'].includes(error.code)) throw error;}
    }
    return this.request('app.state');
  }
}
