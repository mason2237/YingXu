// Packaged-window smoke check. Node is a test tool, never a shipped dependency.
// The temporary loopback inspector exists only for this test process.
import assert from 'node:assert/strict';
import {spawn, execFileSync} from 'node:child_process';
import {once} from 'node:events';
import fs from 'node:fs/promises';
import path from 'node:path';
import net from 'node:net';
import {fileURLToPath} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const executable=path.resolve(process.argv[2]);
const results=path.join(root,'work','test-results');
const prefix=process.env.YINGXU_CHECK_PREFIX||'stage8b';
assert.match(prefix,/^[a-z0-9_-]+$/i);
const temporary=await fs.mkdtemp(path.join(results,`${prefix}-exe-`));
const server=net.createServer();server.listen(0,'127.0.0.1');await once(server,'listening');
const port=server.address().port;await new Promise(resolve=>server.close(resolve));
const windows=process.env.SystemRoot||'C:\\Windows';
const environment={...process.env,PATH:`${windows}\\System32;${windows}`,
  QTWEBENGINE_REMOTE_DEBUGGING:`127.0.0.1:${port}`,LOCALAPPDATA:temporary,
  YINGXU_DATA_DIR:temporary,TEMP:temporary,TMP:temporary};
for(const key of ['PYTHONPATH','PYTHONHOME','QT_PLUGIN_PATH','QML2_IMPORT_PATH','QML_IMPORT_PATH','QTWEBENGINE_CHROMIUM_FLAGS','QT_SCALE_FACTOR'])delete environment[key];
const output=await fs.open(path.join(results,`${prefix}_exe.stdout.log`),'w');
const error=await fs.open(path.join(results,`${prefix}_exe.stderr.log`),'w');
const started=performance.now();
const child=spawn(executable,[],{cwd:temporary,env:environment,windowsHide:false,stdio:['ignore',output.fd,error.fd]});
const exceptionMessages=[],consoleMessages=[];
let socket;
const pending=new Map();let sequence=0;
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function until(check,label,timeout=30000){const end=performance.now()+timeout;while(performance.now()<end){if(await check())return;await pause(100);}throw new Error(label);}
async function command(method,params={}){
  const id=++sequence;
  return new Promise((resolve,reject)=>{
    const timeout=setTimeout(()=>{pending.delete(id);reject(new Error(`CDP timeout: ${method}`));},10000);
    pending.set(id,{resolve,reject,timeout});socket.send(JSON.stringify({id,method,params}));
  });
}
async function evaluate(expression){
  const result=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
  if(result.exceptionDetails)throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
try{
  let target;
  await until(async()=>{
    if(child.exitCode!==null)throw new Error(`EXE exited before ready: ${child.exitCode}`);
    try{const targets=await(await fetch(`http://127.0.0.1:${port}/json/list`)).json();target=targets.find(t=>t.url==='yingxu://app/workspace.html');return Boolean(target?.webSocketDebuggerUrl);}catch{return false;}
  },'Packaged inspector/page unavailable');
  socket=new WebSocket(target.webSocketDebuggerUrl);await once(socket,'open');
  socket.addEventListener('message',event=>{
    const message=JSON.parse(event.data);
    if(message.id&&pending.has(message.id)){
      const item=pending.get(message.id);pending.delete(message.id);clearTimeout(item.timeout);
      if(message.error)item.reject(new Error(JSON.stringify(message.error)));else item.resolve(message.result);
    }else if(message.method==='Runtime.exceptionThrown')exceptionMessages.push(message.params.exceptionDetails.text);
    else if(message.method==='Runtime.consoleAPICalled'&&message.params.type==='error')consoleMessages.push(message.params.args.map(a=>a.value||a.description).join(' '));
  });
  await command('Runtime.enable');
  await until(()=>evaluate("document.documentElement?.dataset.ready==='true'&&document.documentElement?.dataset.loading==='false'"),'Packaged workspace/channel did not become ready');
  // Local controls are inserted after channel restoration; glass is mounted
  // on the following animation frame. Wait for that actual lifecycle event.
  await until(()=>evaluate("[...document.querySelectorAll('button')].every(button=>button.classList.contains('liquid-button'))"),'Dynamic button glass did not mount',5000);
  const startupSeconds=(performance.now()-started)/1000;
  const state=await evaluate(`(()=>{const r=document.documentElement;return {title:document.title,mode:r.dataset.workspaceMode,
    width:innerWidth,height:innerHeight,theme:r.dataset.theme,visibility:document.visibilityState,overflow:r.scrollWidth>innerWidth,
    glassButtons:document.querySelectorAll('button.liquid-button').length,buttons:document.querySelectorAll('button').length,
    activeOpticalCanvases:document.querySelectorAll('canvas[data-gpu-state="active"]').length,
    fixtureAPI:typeof globalThis.yingxuPreview,errors:document.querySelector('#scan-notice')?.textContent||'',
    assets:[...document.querySelectorAll('link[rel="stylesheet"],script[src]')].map(e=>e.href||e.src)}})()`);
  assert.equal(state.mode,'local');assert.equal(state.fixtureAPI,'undefined');assert.equal(state.overflow,false);
  assert.equal(state.visibility,'visible');
  assert.equal(state.glassButtons,state.buttons);assert.ok(state.buttons>25);
  assert.ok(state.assets.length>10);
  assert.ok(state.assets.every(url=>url.startsWith('yingxu://app/')));
  assert.ok(!state.assets.some(url=>url.includes('/preview/')||url.endsWith('/effects.html')));
  await evaluate("document.getElementById('appearance-button').click();true");
  await until(()=>evaluate("Boolean(document.querySelector('dialog[open]'))"),'Appearance dialog unavailable');
  assert.equal(await evaluate("document.querySelector('dialog[open]').textContent.includes('玻璃')"),true);
  await evaluate("document.querySelector('dialog[open] [data-close]').click();true");
  await evaluate("document.getElementById('command-button').click();true");
  await until(()=>evaluate("document.getElementById('command-dialog').open"),'Command palette unavailable');
  await evaluate("document.querySelector('#command-dialog [data-close]').click();true");
  await pause(500);
  await command('Page.enable');
  const shot=await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
  await fs.writeFile(path.join(root,'outputs',`${prefix}_packaged_workspace.png`),Buffer.from(shot.data,'base64'));
  assert.deepEqual(exceptionMessages,[]);assert.deepEqual(consoleMessages,[]);
  const processMetrics=execFileSync(path.join(windows,'System32','WindowsPowerShell','v1.0','powershell.exe'),
    ['-NoProfile','-Command',`[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); $ids=@(${child.pid}); $all=Get-CimInstance Win32_Process; for($n=0;$n -lt 5;$n++){ $ids+=@($all | Where-Object {$_.ParentProcessId -in $ids} | ForEach-Object ProcessId); $ids=@($ids | Select-Object -Unique) }; @(Get-Process -Id $ids -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,Responding,MainWindowTitle,WorkingSet64,CPU) | ConvertTo-Json -Compress`],
    {encoding:'utf8',windowsHide:true}).trim();
  const processTree=JSON.parse(processMetrics);
  assert.ok(processTree.some(item=>item.ProcessName==='YingXu'&&item.Responding),'No responsive app process');
  const result={executable,pid:child.pid,startupSeconds:Number(startupSeconds.toFixed(3)),state,processTree,
    exceptionMessages,consoleMessages,nativeTitleVisibleToLauncher:processTree.some(item=>item.MainWindowTitle.includes('映序')),
    testInspector:'temporary 127.0.0.1 only; removed at process exit',
    scope:'Packaged startup, real channel, offline assets, glass controls and dialogs. Media execution covered separately by source E2E.'};
  await fs.writeFile(path.join(results,`${prefix}_packaged.json`),JSON.stringify(result,null,2));
  console.log(JSON.stringify({...result,state:{...state,assets:`${state.assets.length} local resources`}}));
}finally{
  socket?.close();
  if(child.exitCode===null){
    execFileSync(path.join(windows,'System32','WindowsPowerShell','v1.0','powershell.exe'),
      ['-NoProfile','-Command',`$p=Get-Process -Id ${child.pid} -ErrorAction SilentlyContinue; if($p){$null=$p.CloseMainWindow()}`],{windowsHide:true});
    await Promise.race([once(child,'exit'),pause(5000)]);
    if(child.exitCode===null)execFileSync(path.join(windows,'System32','taskkill.exe'),['/PID',String(child.pid),'/T','/F'],{windowsHide:true});
  }
  for(const item of pending.values()){clearTimeout(item.timeout);item.reject(new Error('Test closed'));}
  pending.clear();await output.close();await error.close();
}
