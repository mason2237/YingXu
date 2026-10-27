// Core release smoke: visible Electron, generated files, no external websites. Optional EXE argument.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const net=require('node:net');
const {spawn,spawnSync}=require('node:child_process');
const ROOT=path.resolve(__dirname,'..');
const output=path.join(ROOT,'work/test-results',`r3-desktop-${Date.now()}`);
const profile=path.join(output,'profile'),media=path.join(output,'media');
fs.mkdirSync(media,{recursive:true});
for(let i=1;i<=3;i++)fs.writeFileSync(path.join(media,`Atlas.S01E${String(i).padStart(3,'0')}.1080p.mkv`),'unchanged video');
fs.writeFileSync(path.join(media,'Atlas.S01E001.chs.srt'),'subtitle');
const snapshot=()=>Object.fromEntries(fs.readdirSync(media).sort().map(name=>[name,fs.readFileSync(path.join(media,name),'hex')]));
const before=snapshot(),pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
let child,cdp,logs='',errors='';
class CDP {
  constructor(url){this.ws=new WebSocket(url);this.pending=new Map();this.id=0;this.errors=[];this.navigation=0;
    this.open=new Promise((resolve,reject)=>{this.ws.addEventListener('open',resolve,{once:true});this.ws.addEventListener('error',reject,{once:true});});
    this.ws.addEventListener('message',event=>{const value=JSON.parse(event.data);if(value.id){const p=this.pending.get(value.id);if(p){this.pending.delete(value.id);clearTimeout(p.timer);value.error?p.reject(Error(JSON.stringify(value.error))):p.resolve(value.result);}}else if(value.method==='Runtime.exceptionThrown')this.errors.push(value.params);else if(value.method==='Page.frameNavigated'&&!value.params.frame.parentId)this.navigation++;});}
  async call(method,params={}){await this.open;const id=++this.id;return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{this.pending.delete(id);reject(Error('CDP timeout '+method));},20000);this.pending.set(id,{resolve,reject,timer});this.ws.send(JSON.stringify({id,method,params}));});}
  async evaluate(expression){const r=await this.call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
}
async function until(check,timeout=20000){const end=Date.now()+timeout;while(Date.now()<end){const v=await check();if(v)return v;await pause(70);}throw Error('Desktop condition timeout');}
const click=selector=>cdp.evaluate(`document.querySelector(${JSON.stringify(selector)}).click();true`);
const visible=id=>cdp.evaluate(`document.querySelector('#${id}')?.open===true`);
const enabled=id=>cdp.evaluate(`document.querySelector('#${id}')?.disabled===false`);
async function shot(name){const value=await cdp.call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(output,name),Buffer.from(value.data,'base64'));}
async function closeHistory(){await click('#history-dialog [data-close]');await until(async()=>!await visible('history-dialog'));}
async function acknowledge(){assert.equal(await enabled('execute-button'),false);assert.equal(await enabled('preview-ack'),true);await click('#preview-ack');await until(()=>enabled('execute-button'));}

(async()=>{
  // Seed an interrupted/cancelled task without touching the media used by the UI flow.
  const seed=spawnSync(path.join(ROOT,'.venv-core/Scripts/python.exe'),['-S','-c',
    `import json,sys\nfrom pathlib import Path\nfrom tests.operation_fixtures import make_plan,approve,noop\nfrom yingxu.desktop.operation_runtime import build_execution\nr=Path(sys.argv[1]);r.mkdir()\ne=build_execution(Path(sys.argv[2])/'python')\ni,items=make_plan(r,e)\napprove(e,i)\ne.execute(i,lambda:True,noop)\ne.journal.close()\nprint(json.dumps({'runId':i,'source':str(items[0].source),'target':str(items[0].target)}))`,
    path.join(output,'recovery-media'),profile],{cwd:ROOT,encoding:'utf8',windowsHide:true,env:{...process.env,PYTHONUTF8:'1'}});
  assert.equal(seed.status,0,seed.stderr);const recovery=JSON.parse(seed.stdout);
  const server=net.createServer();await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const port=server.address().port;await new Promise(resolve=>server.close(resolve));
  child=spawn(process.argv[2]||path.join(ROOT,'work/tools/electron-45.0.0/electron.exe'),[...(process.argv[2]?[]:[path.join(ROOT,'desktop/electron')]),'--diagnostics',`--profile=${profile}`,`--test-folder=${media}`,`--remote-debugging-port=${port}`,'--remote-debugging-address=127.0.0.1'],
    {cwd:ROOT,windowsHide:false,stdio:['ignore','pipe','pipe'],env:{...process.env,YINGXU_PYTHON:path.join(ROOT,'.venv-core/Scripts/python.exe'),ELECTRON_RUN_AS_NODE:undefined}});
  child.stdout.on('data',v=>{logs+=v;});child.stderr.on('data',v=>{errors+=v;});
  const target=await until(async()=>{try{return (await fetch(`http://127.0.0.1:${port}/json/list`).then(v=>v.json())).find(v=>v.url==='yingxu://app/workspace.html');}catch{return null;}});
  cdp=new CDP(target.webSocketDebuggerUrl);await cdp.call('Runtime.enable');await cdp.call('Page.enable');
  await until(()=>enabled('dataset-button'));
  assert.equal(await cdp.evaluate('typeof qt'),'undefined');
  await until(()=>cdp.evaluate("document.querySelector('#recovery-notice')?.hidden===false"));
  assert.equal(fs.existsSync(recovery.source),true);assert.equal(fs.existsSync(recovery.target),false);
  await until(()=>enabled('recovery-open'));await click('#recovery-open');await until(()=>visible('history-dialog'));await until(()=>enabled('resume-record'));
  await click('#resume-record');await until(()=>visible('preview-dialog'));
  assert.equal(await cdp.evaluate("document.querySelector('#preview-title').textContent"),'恢复预览');
  await shot('recovery-preview.png');await acknowledge();await click('#execute-button');
  await until(()=>visible('history-dialog'));await until(()=>enabled('undo-record'));
  assert.equal(fs.existsSync(recovery.source),false);assert.equal(fs.existsSync(recovery.target),true);
  await until(()=>cdp.evaluate("document.querySelector('#recovery-notice').hidden"));await closeHistory();
  await click('#dataset-button');await until(()=>cdp.evaluate("document.querySelector('#overview strong')?.textContent==='3'"));
  for(let i=0;i<20;i++){await click('#appearance-button');await until(()=>visible('appearance-dialog'));await click('#appearance-dialog [data-close]');await until(async()=>!await visible('appearance-dialog'));assert.equal(await cdp.evaluate("document.querySelectorAll('#list-items [data-row-id]').length>0"),true);}
  await until(()=>enabled('preview-button'));await click('#preview-button');await until(()=>visible('preview-dialog'));
  assert.deepEqual(snapshot(),before);await shot('organize-preview.png');await acknowledge();await click('#execute-button');
  await until(()=>visible('history-dialog'));await until(()=>enabled('undo-record'));
  assert.equal(fs.existsSync(path.join(media,'Atlas.S01E001.chs.srt')),false);
  assert.equal(fs.readFileSync(path.join(media,'Atlas.S01E001.1080p.chs.srt'),'utf8'),'subtitle');
  await shot('organize-result.png');await click('#undo-record');await until(()=>visible('preview-dialog'));
  assert.equal(await cdp.evaluate("document.querySelector('#preview-title').textContent"),'撤销预览');
  await acknowledge();await click('#execute-button');await until(()=>visible('history-dialog'));
  await until(async()=>JSON.stringify(snapshot())===JSON.stringify(before));await shot('undo-result.png');await closeHistory();
  const navigation=cdp.navigation;await cdp.call('Page.reload',{ignoreCache:true});await until(()=>cdp.navigation>navigation);
  await until(()=>cdp.evaluate("document.documentElement.dataset.ready==='true'"));await until(()=>enabled('history-button'));
  await click('#history-button');await until(()=>visible('history-dialog'));
  await until(()=>cdp.evaluate("document.querySelectorAll('#history-record option').length>=3"));
  assert.equal(await cdp.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),true);
  assert.equal(cdp.errors.length,0,JSON.stringify(cdp.errors));assert.deepEqual(snapshot(),before);
  assert.ok(logs.includes('"qtImported":false'));assert.ok(logs.includes('"visible":true'));
  const browserUrl=(await fetch(`http://127.0.0.1:${port}/json/version`).then(v=>v.json())).webSocketDebuggerUrl;
  const browser=new CDP(browserUrl);await browser.call('Browser.close').catch(()=>{});browser.ws.close();await until(()=>child.exitCode!==null,15000);assert.equal(child.exitCode,0);
  const report={passed:true,mode:process.argv[2]?'frozen':'source',settingsCycles:20,protocol:2,qtImported:false,recoveryBanner:true,recoveryExplicitConfirmation:true,
    previewDoesNotModifyMedia:true,executeAndUndo:true,historyAfterReload:true,mediaRestored:true,jsExceptions:cdp.errors.length,
    websiteVisited:false,exitCode:child.exitCode,screenshots:['recovery-preview.png','organize-preview.png','organize-result.png','undo-result.png']};
  fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({...report,output:path.relative(ROOT,output)}));
})().catch(async error=>{console.error(error.stack);process.exitCode=1;if(cdp){await shot('failure.png').catch(()=>{});const state=await cdp.evaluate("({text:document.body.innerText.slice(-12000),dialogs:[...document.querySelectorAll('dialog')].map(v=>[v.id,v.open]),errors:0})").catch(()=>null);fs.writeFileSync(path.join(output,'failure.json'),JSON.stringify({error:error.stack,dom:state,exceptions:cdp.errors},null,2));}}).finally(()=>{
  fs.writeFileSync(path.join(output,'stdout.log'),logs);fs.writeFileSync(path.join(output,'stderr.log'),errors);
  cdp?.ws.close();if(child&&child.exitCode===null)child.kill();
});
