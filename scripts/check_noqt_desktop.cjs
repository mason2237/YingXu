// Incremental real-window check through our app's local CDP port. No website visits.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const net=require('node:net');
const {spawn,spawnSync}=require('node:child_process');
const ROOT=path.resolve(__dirname,'..');
const output=path.join(ROOT,'work/test-results',`noqt-desktop-${Date.now()}`);
fs.mkdirSync(output,{recursive:true});
const media=path.join(output,'media');fs.mkdirSync(media);
for(let index=1;index<=300;index++)fs.writeFileSync(path.join(media,`Atlas.S01E${String(index).padStart(3,'0')}.1080p.mkv`),'unchanged video');
for(let index=1;index<=3;index++)fs.writeFileSync(path.join(media,`Atlas.S01E${String(index).padStart(3,'0')}.chs.srt`),'subtitle');
const before=new Map(fs.readdirSync(media).map(name=>[name,fs.readFileSync(path.join(media,name))]));
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
let child,logs='',errors='',cdps=[];

class CDP {
  constructor(url){this.ws=new WebSocket(url);this.pending=new Map();this.id=0;this.errors=[];
    this.open=new Promise((resolve,reject)=>{this.ws.addEventListener('open',resolve,{once:true});this.ws.addEventListener('error',reject,{once:true});});
    this.ws.addEventListener('message',event=>{const value=JSON.parse(event.data);if(value.id){const pending=this.pending.get(value.id);if(pending){this.pending.delete(value.id);clearTimeout(pending.timer);value.error?pending.reject(Error(JSON.stringify(value.error))):pending.resolve(value.result);}}else if(value.method==='Runtime.exceptionThrown')this.errors.push(value.params);});}
  async call(method,params={}){await this.open;const id=++this.id;return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{this.pending.delete(id);reject(Error('CDP timeout '+method));},20000);this.pending.set(id,{resolve,reject,timer});this.ws.send(JSON.stringify({id,method,params}));});}
  async evaluate(expression){let result;try{result=await this.call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});}catch(error){throw Error(error.message+'; expression='+expression.slice(0,160));}if(result.exceptionDetails)throw Error(JSON.stringify(result.exceptionDetails));return result.result.value;}
  close(){this.ws.close();}
}
async function targets(port){return fetch(`http://127.0.0.1:${port}/json/list`).then(response=>response.json());}
async function until(check,timeout=20000){const end=Date.now()+timeout;while(Date.now()<end){const value=await check();if(value)return value;await pause(80);}throw Error('Expected desktop condition did not arrive');}

(async()=>{
  const server=net.createServer();await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const port=server.address().port;await new Promise(resolve=>server.close(resolve));
  const started=Date.now();
  child=spawn(process.argv[2]||path.join(ROOT,'work/tools/electron-45.0.0/electron.exe'),[...(process.argv[2]?[]:[path.join(ROOT,'desktop/electron')]),'--diagnostics',`--profile=${path.join(output,'profile')}`,`--test-folder=${media}`,`--remote-debugging-port=${port}`,'--remote-debugging-address=127.0.0.1'],{
    cwd:ROOT,windowsHide:false,stdio:['ignore','pipe','pipe'],env:{...process.env,YINGXU_PYTHON:path.join(ROOT,'.venv-core/Scripts/python.exe'),ELECTRON_RUN_AS_NODE:undefined}});
  child.stdout.on('data',value=>{logs+=value;});child.stderr.on('data',value=>{errors+=value;});
  const target=await until(async()=>{try{return (await targets(port)).find(value=>value.url==='yingxu://app/workspace.html');}catch{return null;}});
  const page=new CDP(target.webSocketDebuggerUrl);cdps.push(page);await page.call('Runtime.enable');
  await until(()=>page.evaluate("document.documentElement.dataset.ready==='true'"));
  const startupMs=Date.now()-started;
  await until(()=>page.evaluate("Boolean(document.querySelector('#dataset-button')&&!document.querySelector('#dataset-button').disabled)"));
  await page.evaluate(`globalThis.testCall=async(action,params={})=>{
    const host=yingxuHost.workspace,id=crypto.randomUUID();
    const session=await new Promise((resolve,reject)=>{let stop;const timer=setTimeout(()=>{stop?.();reject(Error('Session query timeout'));},5000);stop=host.onReply(raw=>{const r=JSON.parse(raw);if(r.requestId===id){clearTimeout(timer);stop();resolve(r);}});host.request(JSON.stringify({v:2,requestId:id,sessionId:null,action:'app.state',params:{}})).catch(reject);});
    return session;
  };true`);
  // Derive the active session from a reply to a deliberately stale read; no new handshake.
  let stale;const sessionId=await until(async()=>{stale=await page.evaluate("testCall('app.state')");assert.equal(stale.error.code,'STALE_SESSION');return stale.sessionId;});
  await page.evaluate(`globalThis.sessionForCheck=${JSON.stringify(sessionId)};globalThis.checkCall=(action,params={})=>new Promise((resolve,reject)=>{
    const id=crypto.randomUUID(),host=yingxuHost.workspace;let stop;const timer=setTimeout(()=>{stop?.();reject(Error('Backend check timeout'));},10000);
    stop=host.onReply(raw=>{const value=JSON.parse(raw);if(value.requestId===id){stop();clearTimeout(timer);value.ok?resolve(value.data):reject(Error(JSON.stringify(value.error)));}});
    host.request(JSON.stringify({v:2,requestId:id,sessionId:sessionForCheck,action,params})).catch(reject);
  });true`);
  await page.evaluate("checkCall('embedded.configure',{enabled:false,language:'chinese'})");
  await page.evaluate("document.querySelector('#dataset-button').click();true");
  await until(()=>page.evaluate("document.querySelector('#overview strong')?.textContent==='300'"),30000);
  await until(()=>page.evaluate("document.querySelectorAll('#list-items [data-row-id]').length>0"));
  await page.evaluate(fs.readFileSync(path.join(ROOT,'tests/frontend/rendering.js'),'utf8'));
  const rendering=await until(()=>page.evaluate('globalThis.__renderTests'));
  assert.equal(rendering.passed,true,JSON.stringify(rendering));
  const state=await page.evaluate("checkCall('app.state')");assert.equal(state.runtime,'python-stdlib');assert.equal(state.summary.counts.all,300);assert.equal(state.executionAvailable,true);
  const browserTarget=(await fetch(`http://127.0.0.1:${port}/json/version`).then(value=>value.json())).webSocketDebuggerUrl;
  const browser=new CDP(browserTarget);cdps.push(browser);
  const native=JSON.parse(logs.split('\n').find(line=>line.includes('"type":"window"')));
  const windowAction=(action,width=1280)=>{const result=spawnSync(path.join(ROOT,'.venv-core/Scripts/python.exe'),[path.join(ROOT,'scripts/check_window_bounds.py'),native.handle,String(child.pid),action,'--width',String(width)],{encoding:'utf8',windowsHide:true});assert.equal(result.status,0,result.stderr);};
  for(const width of [1000,1360]){
    windowAction('resize',width);
    await pause(200);assert.equal(await page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),true);
  }
  const processBefore=(await browser.call('SystemInfo.getProcessInfo')).processInfo;const activeStart=Date.now();
  let maxRows=0;
  for(let index=0;index<80;index++){
    maxRows=Math.max(maxRows,await page.evaluate(`(()=>{const list=document.querySelector('#file-list');list.scrollTop=${index*300};list.dispatchEvent(new Event('scroll'));return document.querySelectorAll('#list-items [data-row-id]').length;})()`));
    await pause(20);
  }
  assert.ok(maxRows<=60);const activeMs=Date.now()-activeStart;
  const processAfter=(await browser.call('SystemInfo.getProcessInfo')).processInfo;
  const cpuSeconds=processAfter.reduce((sum,item)=>sum+Math.max(0,item.cpuTime-(processBefore.find(value=>value.id===item.id)?.cpuTime||item.cpuTime)),0);
  windowAction('minimize');
  await until(()=>page.evaluate("document.documentElement.dataset.nativeHidden==='true'||document.hidden"));
  windowAction('restore');
  await until(()=>page.evaluate("document.documentElement.dataset.nativeHidden!=='true'&&!document.hidden"));
  await page.evaluate("document.querySelector('#file-list').scrollTop=0;true");
  const backendId=JSON.parse(logs.split('\n').find(line=>line.includes('"type":"backend"'))).pid;
  const pids=[...new Set([...processAfter.map(item=>item.id),backendId])];
  const resource=spawnSync('powershell.exe',['-NoProfile','-Command',`Get-Process -Id ${pids.join(',')} -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,WorkingSet64,CPU | ConvertTo-Json -Compress`],{encoding:'utf8',windowsHide:true});
  const processes=JSON.parse(resource.stdout||'[]');
  assert.equal(await page.evaluate("typeof qt"),'undefined');assert.equal(await page.evaluate("yingxuHost.workspace.protocolVersion"),2);
  const visible=await page.evaluate("document.querySelectorAll('#list-items [data-row-id]').length");assert.ok(visible<=60);
  await page.evaluate("document.querySelector('#preview-button').click();true");
  await until(()=>page.evaluate("document.querySelector('#preview-dialog').open"));
  assert.equal(await page.evaluate("document.querySelector('#execute-button').disabled&&!document.querySelector('#preview-ack').disabled"),true);
  await page.evaluate("document.querySelector('#preview-dialog [data-close]').click();true");
  await until(()=>page.evaluate("!document.querySelector('#preview-dialog').open"));
  await page.evaluate("yingxuHost.appearance.update({theme:'light'})");
  await until(()=>page.evaluate("document.documentElement.dataset.theme==='light'"));
  await page.evaluate("yingxuHost.appearance.update({theme:'dark'})");
  await until(()=>page.evaluate("document.documentElement.dataset.theme==='dark'"));
  let hdr=null;
  if(process.argv.includes('--hdr')) {
    await until(()=>page.evaluate("yingxuHost.appearance.getState().then(s=>s.displayOutput.systemHdrEnabled&&s.displayOutput.hdrConfigured)"));
    const sample=await page.evaluate(`(async()=>{
      const {hdrLayer}=await import('./js/hdr-layer.js');hdrLayer.setCalibration(true);
      const r=hdrLayer.canvas.getBoundingClientRect();return {rect:{x:r.x,y:r.y,width:r.width,height:r.height},scale:devicePixelRatio};
    })()`);
    try {
      await pause(350);
      const capture=spawnSync(path.join(ROOT,'.venv-core/Scripts/python.exe'),[path.join(ROOT,'scripts/capture_hdr.py'),'--handle',native.handle,'--rect',JSON.stringify(sample.rect),'--scale',String(sample.scale)],{encoding:'utf8',windowsHide:true,timeout:10000});
      assert.equal(capture.status,0,capture.stderr);hdr=JSON.parse(capture.stdout);assert.equal(hdr.verified,true,JSON.stringify(hdr));
    } finally {await page.evaluate("import('./js/hdr-layer.js').then(m=>m.hdrLayer.setCalibration(false))");}
  }
  let originalFolderLabel;
  if(process.argv.includes('--release-screenshots')) originalFolderLabel=await page.evaluate("(()=>{const n=document.getElementById('folder-path'),text=n.textContent;n.textContent='示例文件夹 · 300 个视频';return text;})()");
  const screenshot=await page.call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(output,'workspace.png'),Buffer.from(screenshot.data,'base64'));
  if(originalFolderLabel!==undefined)await page.evaluate(`document.getElementById('folder-path').textContent=${JSON.stringify(originalFolderLabel)}`);
  await page.evaluate("document.querySelector('#online-subtitles-button').click();true");
  const onlineTarget=await until(async()=>(await targets(port)).find(value=>value.url==='yingxu://app/online.html'));
  const online=new CDP(onlineTarget.webSocketDebuggerUrl);cdps.push(online);await online.call('Runtime.enable');
  await until(()=>online.evaluate("document.querySelectorAll('#tasks option').length>0"));
  assert.equal(await online.evaluate("typeof yingxuHost"),'undefined');assert.equal(await online.evaluate("document.querySelector('#query').value"),'Atlas');
  await online.evaluate("document.querySelector('#language').value='en';document.querySelector('#language').dispatchEvent(new Event('change'));true");
  await until(()=>online.evaluate("yingxuOnline.request('online.query',{}).then(value=>value.language==='en')"));
  assert.equal(await online.evaluate("document.documentElement.scrollWidth<=innerWidth+1"),true);
  await page.evaluate("yingxuHost.appearance.update({theme:'light'})");
  await until(()=>online.evaluate("document.documentElement.dataset.theme==='light'"));
  await page.evaluate("yingxuHost.appearance.update({theme:'dark'})");
  await until(()=>online.evaluate("document.documentElement.dataset.theme==='dark'"));
  const other=(await targets(port)).filter(value=>!value.url.startsWith('yingxu:')&&value.type==='page');
  assert.ok(other.length,'Expected the isolated remote view');
  for(const target of other){const remote=new CDP(target.webSocketDebuggerUrl);cdps.push(remote);assert.deepEqual(await remote.evaluate("[typeof yingxuHost,typeof yingxuOnline,typeof require,typeof process]"),['undefined','undefined','undefined','undefined']);}
  const onlineScreenshot=await online.call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(output,'online.png'),Buffer.from(onlineScreenshot.data,'base64'));
  const errorsBefore=page.errors.length+online.errors.length;
  await page.evaluate("window.location.reload();true");
  await until(()=>page.evaluate("Boolean(document.querySelector('#dataset-button')&&!document.querySelector('#dataset-button').disabled)"));
  await until(()=>page.evaluate("document.querySelector('#overview strong')?.textContent==='300'"));
  assert.equal(errorsBefore+page.errors.length+online.errors.length,0);
  for(const [name,content] of before)assert.deepEqual(fs.readFileSync(path.join(media,name)),content);
  assert.deepEqual(fs.readdirSync(media).sort(),Array.from(before.keys()).sort());
  assert.ok(logs.includes('"qtImported":false'));assert.ok(!logs.includes('"qtImported":true'));
  assert.ok(logs.includes('"visible":true'),'Expected a visible native window');
  await browser.call('Browser.close').catch(()=>{});
  await until(()=>child.exitCode!==null,15000);
  assert.equal(child.exitCode,0);assert.ok(!errors.includes('JS: '),errors);
  const report={passed:true,mode:process.argv[2]?'frozen':'source',startupMs,activeScroll:{milliseconds:activeMs,chromiumCpuSeconds:cpuSeconds,maxRows},processes,resizeWidths:[1000,1360],minimizeRestore:true,protocol:2,runtime:'Electron + Python',qtImported:false,videos:300,maxVisibleRows:visible,
    scanPreview:true,unconfirmedExecutionBlocked:true,themes:true,onlineLocalUI:true,languagePreference:true,remoteHasLocalAPI:false,websiteVisited:false,reload:true,mediaUnchanged:true,rendering,hdr,demonstrationPathLabel:originalFolderLabel!==undefined,exitCode:child.exitCode,
    screenshot:path.relative(ROOT,path.join(output,'workspace.png')),onlineScreenshot:path.relative(ROOT,path.join(output,'online.png'))};
  fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({...report,output:path.relative(ROOT,output)}));
})().catch(async error=>{console.error(error.stack);process.exitCode=1;fs.writeFileSync(path.join(output,'failure.json'),JSON.stringify({error:error.stack,dom:await cdps[0]?.evaluate('document.body.innerText').catch(()=>null),jsErrors:cdps[0]?.errors},null,2));}).finally(()=>{
  fs.writeFileSync(path.join(output,'stdout.log'),logs);fs.writeFileSync(path.join(output,'stderr.log'),errors);
  for(const cdp of cdps)cdp.close();if(child&&child.exitCode===null)child.kill();
});
