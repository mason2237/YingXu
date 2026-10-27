// Browser adapter contracts using an Electron boundary double; no website access.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const handlers=new Map();
const moduleObject={exports:{}};
const source=fs.readFileSync(path.resolve(__dirname,'../../desktop/electron/online.cjs'),'utf8');
const wrapper=vm.runInNewContext('(function(require,module,exports){'+source+'\n})',{URL,setTimeout,clearTimeout,Buffer,process});
wrapper(name=>name==='electron'?{ipcMain:{handle:(name,handler)=>handlers.set(name,handler)}}:require(name),moduleObject,moduleObject.exports);
const {OnlineWindow,safeHttps}=moduleObject.exports;

(async()=>{
  for(const value of ['http://subhd.me/','file:///C:/example','https://127.0.0.1/','https://[::1]/','https://localhost/','https://device.local/','https://a:b@example.invalid/','https://subhd.me:444/'])assert.equal(safeHttps(value),false,value);
  assert.equal(safeHttps('https://subhd.me/search/Atlas',['subhd.me']),true);
  assert.equal(safeHttps('https://untrusted.example/',['subhd.me']),false);
  const manager=new OnlineWindow({request:async()=>({ok:true}),write:()=>{},appearance:()=>({})});
  const mainFrame={origin:'yingxu://app'},contents={mainFrame};manager.window={webContents:contents};
  const request=handlers.get('yingxu:online:request');
  assert.throws(()=>request({sender:contents,senderFrame:mainFrame},'folder.choose',{}),/UNTRUSTED/);
  assert.throws(()=>request({sender:{},senderFrame:mainFrame},'online.query',{}),/UNTRUSTED/);
  await request({sender:contents,senderFrame:mainFrame},'online.query',{});

  const scripts=[];let navigations=0;
  manager.show=async()=>{};
  manager.view={setVisible:()=>{},webContents:{isDestroyed:()=>false,stop:()=>{},getURL:()=> 'https://subhd.me/',
    loadURL:async()=>{navigations++;},executeJavaScript:async script=>{scripts.push(script);return script==='challenge'?false:script==='candidates'?JSON.stringify({status:'not_results',rows:[]}):{status:'submitted'};}}};
  await manager.search({resume:true,taskId:'task',effectId:'effect',generation:1,
    plan:{home:'https://subhd.me/',hosts:['subhd.me'],challengeScript:'challenge',candidateScript:'candidates',submitScript:'submit'}});
  assert.deepEqual(scripts,['challenge','candidates','submit']);
  assert.equal(manager.ticket.submitted,true);manager.stop();

  let release;
  manager.show=()=>new Promise(resolve=>{release=resolve;});
  const pending=manager.search({resume:false,plan:{home:'https://subhd.me/',hosts:['subhd.me']}});
  manager.stop();release();await pending;
  assert.equal(navigations,0,'A cancelled window startup must not navigate later');
  assert.equal(manager.ticket,null);
  const pendingArm=manager.arm({taskId:'task',effectId:'download',generation:1,url:'https://subhd.me/a/TEST',hosts:['subhd.me']});
  manager.disarm();release();await pendingArm;
  assert.equal(manager.grant,null);assert.equal(navigations,0,'Cancelled download startup must not regain a grant');
  let url='https://subhd.me/a/TEST',clicks=0,notices=0;
  manager.show=async()=>{};manager.notice=()=>notices++;
  Object.assign(manager.view.webContents,{getURL:()=>url,loadURL:async value=>{url=value;},
    executeJavaScript:async()=>{clicks++;return {status:'clicked'};}});
  await manager.arm({taskId:'task',effectId:'download',generation:2,url,hosts:['subhd.me'],downloadScript:'ordinary-button-only'});
  await manager.downloadReady();await manager.downloadReady();assert.equal(clicks,1,'A repeated load must not click twice');
  url='https://subhd.me/down/TEST';await manager.downloadReady();
  url+='?other';await manager.downloadReady();assert.equal(clicks,2,'Only two ordinary page transitions may be automated');
  manager.disarm();
  await manager.arm({taskId:'task',effectId:'download',generation:3,url:'https://subhd.me/a/TEST',hosts:['subhd.me'],downloadScript:'ordinary-button-only'});
  let finishScript;manager.view.webContents.executeJavaScript=()=>new Promise(resolve=>{finishScript=resolve;});
  const late=manager.downloadReady(),noticeCount=notices;manager.disarm();
  finishScript({status:'manual',message:'old result'});await late;
  assert.equal(notices,noticeCount,'A cancelled page callback must not change the current guidance');
  console.log(JSON.stringify({passed:true,checks:['source-policy','IPC-whitelist','resume-after-verification','cancel-during-window-startup','cancel-during-download-startup','bounded-ordinary-download-steps','late-download-guidance-ignored']}));
})().catch(error=>{console.error(error);process.exitCode=1;});
