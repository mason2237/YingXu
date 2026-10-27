// Real Electron download adapter with intercepted HTTPS fixtures; no public website contacted.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),net=require('node:net');
const {spawn}=require('node:child_process');
const ROOT=path.resolve(__dirname,'..');
const output=path.join(ROOT,'work/test-results',`r4-online-${Date.now()}`),profile=path.join(output,'profile'),media=path.join(output,'media');
fs.mkdirSync(media,{recursive:true});fs.writeFileSync(path.join(media,'Atlas.S01E001.mkv'),'generated video unchanged');
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));let child,cdp,online,remote,logs='',errors='';
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

(async()=>{
  const server=net.createServer();await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const port=server.address().port;await new Promise(resolve=>server.close(resolve));
  const executable=process.argv[2]||path.join(ROOT,'work/tools/electron-45.0.0/electron.exe');
  const args=[...(process.argv[2]?[]:[path.join(ROOT,'desktop/electron')]),'--diagnostics',`--profile=${profile}`,`--test-folder=${media}`,`--remote-debugging-port=${port}`,'--remote-debugging-address=127.0.0.1'];
  child=spawn(executable,args,{cwd:ROOT,windowsHide:false,stdio:['ignore','pipe','pipe'],env:{...process.env,YINGXU_PYTHON:path.join(ROOT,'.venv-core/Scripts/python.exe'),ELECTRON_RUN_AS_NODE:undefined}});
  child.stdout.on('data',v=>logs+=v);child.stderr.on('data',v=>errors+=v);
  const targets=()=>fetch(`http://127.0.0.1:${port}/json/list`).then(v=>v.json());
  const target=await until(async()=>{try{return(await targets()).find(v=>v.url==='yingxu://app/workspace.html');}catch{return null;}});
  cdp=new CDP(target.webSocketDebuggerUrl);await cdp.call('Runtime.enable');await until(()=>cdp.evaluate("document.documentElement.dataset.ready==='true'"));await until(()=>enabled('dataset-button'));
  await click('#dataset-button');await until(()=>cdp.evaluate("document.querySelector('#overview strong')?.textContent==='1'"));
  await until(()=>enabled('online-subtitles-button'));await click('#online-subtitles-button');
  const onlineTarget=await until(async()=>(await targets()).find(v=>v.url==='yingxu://app/online.html'));
  online=new CDP(onlineTarget.webSocketDebuggerUrl);await online.call('Runtime.enable');
  const remoteTarget=await until(async()=>(await targets()).find(v=>v.url==='about:blank'));
  remote=new CDP(remoteTarget.webSocketDebuggerUrl);await remote.call('Runtime.enable');
  const page=`<!doctype html><meta charset="utf-8"><title>Atlas 字幕详情 · 测试样本</title><h1>Atlas · 中英双语</h1><p>网站访问认证</p><button id="download">下载生成的测试字幕</button><script>document.querySelector('#download').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob(['1\\n00:00:01,000 --> 00:00:02,000\\n你好 Hello\\n'.replaceAll('\\\\n','\\n')],{type:'text/plain'}));a.download='Atlas.chs.srt';a.click();};<\/script>`;
  remote.ws.addEventListener('message',event=>{const message=JSON.parse(event.data);if(message.method==='Fetch.requestPaused')remote.call('Fetch.fulfillRequest',{requestId:message.params.requestId,responseCode:200,responseHeaders:[{name:'Content-Type',value:'text/html; charset=utf-8'}],body:Buffer.from(page).toString('base64')}).catch(()=>{});});
  await remote.call('Fetch.enable',{patterns:[{urlPattern:'*'}]});
  await until(()=>online.evaluate("document.querySelector('#tasks').options.length===1"));
  await online.evaluate("document.querySelector('#search').click();true");
  await until(()=>online.evaluate("document.querySelector('#phase').textContent.includes('核对')"));
  await remote.call('Page.navigate',{url:'https://zimuku.org/detail/1.html'});
  await until(()=>remote.evaluate("Boolean(document.querySelector('#download'))"));
  assert.equal(await remote.evaluate("typeof yingxuOnline+':'+typeof yingxuHost+':'+typeof require"),'undefined:undefined:undefined');
  await online.evaluate("document.querySelector('#use-page').click();true");
  await until(()=>online.evaluate("document.querySelector('#download-selected').disabled===false"));
  await online.evaluate("document.querySelector('#download-selected').click();true");
  await until(()=>online.evaluate("document.querySelector('#confirmation').open"));
  await online.evaluate("document.querySelector('#confirmation button[value=confirm]').click();true");
  await until(()=>online.evaluate("document.querySelector('#phase').textContent.includes('已确认')"));
  await until(()=>remote.evaluate("Boolean(document.querySelector('#download'))"));
  // Navigate/arm completion is separate from the command acknowledgement.
  await until(()=>online.evaluate("document.querySelector('#notice').textContent.includes('已确认这份')"));
  await remote.evaluate("document.querySelector('#download').click();true");
  await until(()=>online.evaluate("document.querySelector('#import-ready').disabled===false"),25000);
  await online.evaluate("document.querySelector('#downloads').scrollIntoView({block:'center'});true");
  const picture=await online.call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(output,'subtitle-inbox.png'),Buffer.from(picture.data,'base64'));
  assert.equal(fs.readdirSync(media).length,1);
  await online.evaluate("document.querySelector('#import-ready').click();true");
  await online.evaluate("document.querySelector('#confirmation button[value=confirm]').click();true");
  await until(()=>cdp.evaluate("document.body.innerText.includes('Atlas.chs.srt')"));
  assert.equal(fs.readdirSync(media).length,1);await shot('import-review.png');
  assert.equal(online.errors.length,0,JSON.stringify(online.errors));assert.equal(cdp.errors.length,0,JSON.stringify(cdp.errors));
  const browserUrl=(await fetch(`http://127.0.0.1:${port}/json/version`).then(v=>v.json())).webSocketDebuggerUrl;
  const browser=new CDP(browserUrl);await browser.call('Browser.close').catch(()=>{});browser.ws.close();await until(()=>child.exitCode!==null,15000);
  assert.equal(child.exitCode,0);assert.ok(logs.includes('"qtImported":false'));
  const report={passed:true,mode:process.argv[2]?'frozen':'source',realElectronBlobDownload:true,manualPageSelection:true,
    explicitDownloadConfirmation:true,validatedAndImported:true,mediaUnchangedBeforeConfirmation:true,remoteHasNoLocalBridge:true,
    jsExceptions:cdp.errors.length+online.errors.length,publicWebsiteTested:false,exitCode:child.exitCode,output:path.relative(ROOT,output)};
  fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
})().catch(async error=>{console.error(error.stack);process.exitCode=1;
  fs.writeFileSync(path.join(output,'failure.json'),JSON.stringify({error:error.stack,workspace:await cdp?.evaluate('document.body.innerText').catch(()=>null),exceptions:cdp?.errors,online:await online?.evaluate('document.body.innerText').catch(()=>null),remote:await remote?.evaluate('document.body.innerHTML').catch(()=>null)},null,2));
}).finally(()=>{fs.writeFileSync(path.join(output,'stdout.log'),logs);fs.writeFileSync(path.join(output,'stderr.log'),errors);for(const value of [cdp,online,remote])value?.ws.close();if(child&&child.exitCode===null)child.kill();});
