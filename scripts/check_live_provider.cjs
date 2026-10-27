// Live provider check: generated media only, no CAPTCHA solving or media changes.
const fs=require('node:fs'),path=require('node:path'),net=require('node:net');
const {spawn}=require('node:child_process');
const ROOT=path.resolve(__dirname,'..'),output=path.join(ROOT,'work/test-results',`live-provider-${Date.now()}`);
const query=process.argv.find(value=>value.startsWith('--title='))?.slice(8)||'Interstellar';
const provider=process.argv.find(value=>value.startsWith('--provider='))?.slice(11);
const media=path.join(output,'media'),profile=path.join(output,'profile');fs.mkdirSync(media,{recursive:true});
fs.writeFileSync(path.join(media,query.replaceAll(' ','.')+'.2014.1080p.mkv'),'generated placeholder, no real movie');
let child,cdp,online,remote,logs='',errors='';const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
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
 const listener=net.createServer();await new Promise(resolve=>listener.listen(0,'127.0.0.1',resolve));const port=listener.address().port;await new Promise(resolve=>listener.close(resolve));
 child=spawn(path.join(ROOT,'work/tools/electron-45.0.0/electron.exe'),[path.join(ROOT,'desktop/electron'),'--diagnostics',`--profile=${profile}`,`--test-folder=${media}`,`--remote-debugging-port=${port}`,'--remote-debugging-address=127.0.0.1'],{cwd:ROOT,windowsHide:false,stdio:['ignore','pipe','pipe'],env:{...process.env,YINGXU_PYTHON:path.join(ROOT,'.venv-core/Scripts/python.exe'),ELECTRON_RUN_AS_NODE:undefined}});
 child.stdout.on('data',value=>logs+=value);child.stderr.on('data',value=>errors+=value);
 const targets=()=>fetch(`http://127.0.0.1:${port}/json/list`).then(value=>value.json());
 const main=await until(async()=>{try{return(await targets()).find(value=>value.url==='yingxu://app/workspace.html');}catch{return null;}});
 cdp=new CDP(main.webSocketDebuggerUrl);await cdp.call('Runtime.enable');await until(()=>cdp.evaluate("document.documentElement.dataset.ready==='true'"));await click('#dataset-button');
 await until(()=>cdp.evaluate("!document.querySelector('#online-subtitles-button').disabled"));await click('#online-subtitles-button');
 const local=await until(async()=>(await targets()).find(value=>value.url==='yingxu://app/online.html'));online=new CDP(local.webSocketDebuggerUrl);await online.call('Runtime.enable');
 const external=await until(async()=>(await targets()).find(value=>value.url==='about:blank'));remote=new CDP(external.webSocketDebuggerUrl);await remote.call('Runtime.enable');
 const task=await until(()=>online.evaluate("yingxuOnline.request('online.query',{}).then(value=>value.tasks[0]?.taskId)"));
 const report={generatedMedia:true,query,providers:[],captchaSolved:false,downloaded:false,imported:false};
 for(const provider of (process.argv.some(value=>value.startsWith('--provider='))?[process.argv.find(value=>value.startsWith('--provider=')).slice(11)]:['zimuku','srtku','subhd','subhd-one'])){
  await online.evaluate(`yingxuOnline.request('online.start',{taskId:${JSON.stringify(task)},query:${JSON.stringify(query)},provider:${JSON.stringify(provider)}})`);
  const result=await until(()=>online.evaluate("yingxuOnline.request('online.query',{}).then(value=>value.tasks[0]?.phase!=='searching'?value.tasks[0]:null)"),30000);
  const page=await remote.evaluate("({url:location.origin+location.pathname,title:document.title,text:(document.body?.innerText||'').slice(0,3000)})");
  const info={provider,phase:result.phase,candidates:result.candidateCount,page:page.url,title:page.title,reason:result.reason};report.providers.push(info);
  fs.writeFileSync(path.join(output,provider+'-page.json'),JSON.stringify(page,null,2));
  if(result.phase!=='candidates_ready')continue;
  const candidates=await online.evaluate(`yingxuOnline.request('online.candidates',{taskId:${JSON.stringify(task)},limit:6})`);
  const selected=candidates.rows.find(row=>(row.title+' '+row.release).toLowerCase().includes(query.toLowerCase())||/星际穿越/.test(row.title+' '+row.release));
  if(!selected){info.reason='No recognizable matching public-domain sample candidate; no arbitrary download attempted.';continue;}
  await online.evaluate(`yingxuOnline.request('online.select',{taskId:${JSON.stringify(task)},candidateId:${JSON.stringify(selected.candidateId)}})`);
  await online.evaluate(`yingxuOnline.request('online.download',{taskIds:[${JSON.stringify(task)}],acknowledged:true})`);
  const end=Date.now()+25000;
  while(Date.now()<end){
    const state=await online.evaluate("yingxuOnline.request('online.downloads',{})");
    report.downloadStatus=state.rows.map(row=>({status:row.status,message:row.message}));
    if(state.rows.some(row=>row.status==='ready')){report.downloaded=true;break;}
    if(state.rows.some(row=>row.status==='interrupted'))break;
    const verification=await remote.evaluate("({url:location.origin+location.pathname,title:document.title,text:(document.body?.innerText||'').slice(-8000),captcha:[...document.querySelectorAll('iframe[src*=recaptcha],iframe[src*=challenges],input[name=captcha],img[src*=captcha]')].some(node=>node.getClientRects().length>0),buttons:[...document.querySelectorAll('button')].map(node=>node.innerText.slice(0,60))})");
    fs.writeFileSync(path.join(output,'download-page.json'),JSON.stringify(verification,null,2));
    if(verification.captcha||/请.{0,12}(完成验证|输入验证码)|人机验证|安全验证/i.test(verification.text)){info.manualRequired=true;info.reason='Website requires human verification; no bypass attempted.';break;}
    await pause(400);
  }
  info.autoDownloadAttempted=true;
  if(report.downloaded){
   const ids=await online.evaluate("yingxuOnline.request('online.downloads',{}).then(value=>value.rows.filter(row=>row.status==='ready'&&!row.imported).map(row=>row.artifactId))");
   await online.evaluate(`yingxuOnline.request('online.import',{artifactIds:${JSON.stringify(ids)},acknowledged:true})`);
   await until(()=>cdp.evaluate("document.body.innerText.includes('在线导入')||document.body.innerText.includes('在线字幕候选')"));report.imported=true;
  }
  break;
 }
 report.mediaUnchanged=fs.readdirSync(media).length===1;report.jsErrors=cdp.errors.length+online.errors.length;
 const picture=await online.call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(output,'live-provider.png'),Buffer.from(picture.data,'base64'));
 const browserInfo=await fetch(`http://127.0.0.1:${port}/json/version`).then(value=>value.json());const browser=new CDP(browserInfo.webSocketDebuggerUrl);await browser.call('Browser.close').catch(()=>{});browser.ws.close();await until(()=>child.exitCode!==null);
 report.exitCode=child.exitCode;report.output=path.relative(ROOT,output);fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
})().catch(error=>{console.error(error.stack);fs.writeFileSync(path.join(output,'failure.json'),JSON.stringify({error:error.stack}));process.exitCode=1;}).finally(()=>{for(const page of [cdp,online,remote])page?.ws.close();fs.writeFileSync(path.join(output,'runtime.log'),logs+'\n'+errors);if(child&&child.exitCode===null)child.kill();});
