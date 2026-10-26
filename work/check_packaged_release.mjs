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
const sourceMode=executable.endsWith('.py');
const startupOnly=process.argv.includes('--startup-only');
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
const child=spawn(sourceMode?path.join(root,'.venv-web','Scripts','python.exe'):executable,sourceMode?[executable]:[],{cwd:temporary,env:environment,windowsHide:false,stdio:['ignore',output.fd,error.fd]});
const exceptionMessages=[],consoleMessages=[];
let socket;
let workflow=null;
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
    }else if(message.method==='Runtime.exceptionThrown')exceptionMessages.push(message.params.exceptionDetails.exception?.description||message.params.exceptionDetails.text);
    else if(message.method==='Runtime.consoleAPICalled'&&message.params.type==='error')consoleMessages.push(message.params.args.map(a=>a.value||a.description).join(' '));
  });
  await command('Runtime.enable');
  await until(()=>evaluate("document.documentElement?.dataset.ready==='true'&&document.documentElement?.dataset.loading==='false'&&document.documentElement?.dataset.desktopBoot==='ready'&&document.fonts.status==='loaded'&&document.fonts.check('15px \"YingXu Sans\"')"),'Packaged workspace/channel/font did not become ready');
  // Local controls are inserted after channel restoration; glass is mounted
  // on the following animation frame. Wait for that actual lifecycle event.
  await until(()=>evaluate("[...document.querySelectorAll('button')].every(button=>button.dataset.glassRole==='structural'||button.classList.contains('liquid-button'))"),'Dynamic button material roles did not mount',5000);
  const startupSeconds=(performance.now()-started)/1000;
  const state=await evaluate(`(()=>{const r=document.documentElement;return {title:document.title,mode:r.dataset.workspaceMode,
    width:innerWidth,height:innerHeight,theme:r.dataset.theme,visibility:document.visibilityState,overflow:r.scrollWidth>innerWidth,
    desktopBoot:r.dataset.desktopBoot,fontLoaded:document.fonts.check('15px "YingXu Sans"'),bodyOpacity:getComputedStyle(document.body).opacity,
    desktopStyles:document.querySelector('link[href="css/desktop-polish.css"]')!==null,
    glassButtons:document.querySelectorAll('button.liquid-button').length,buttons:document.querySelectorAll('button').length,
    structuralButtons:document.querySelectorAll('button[data-glass-role="structural"]').length,
    lighting:r.dataset.lighting,
    activeOpticalCanvases:document.querySelectorAll('canvas[data-gpu-state="active"]').length,
    fixtureAPI:typeof globalThis.yingxuPreview,errors:document.querySelector('#scan-notice')?.textContent||'',
    assets:[...document.querySelectorAll('link[rel="stylesheet"],script[src]')].map(e=>e.href||e.src)}})()`);
  assert.equal(state.mode,'local');assert.equal(state.fixtureAPI,'undefined');assert.equal(state.overflow,false);
  assert.equal(state.visibility,'visible');
  assert.equal(state.desktopBoot,'ready');assert.equal(state.fontLoaded,true);
  assert.equal(state.bodyOpacity,'1');assert.equal(state.desktopStyles,true);
  assert.equal(state.glassButtons+state.structuralButtons,state.buttons);assert.ok(state.buttons>25);
  assert.ok(state.structuralButtons>=4);
  assert.equal(await evaluate("[...document.querySelectorAll('.list-heading button,.inspector-heading button')].every(b=>!b.classList.contains('liquid-button')&&getComputedStyle(b).boxShadow==='none')"),true);
  assert.ok(state.assets.length>10);
  assert.ok(state.assets.every(url=>url.startsWith('yingxu://app/')));
  assert.ok(!state.assets.some(url=>url.includes('/preview/')||url.endsWith('/effects.html')));
  if(/^stage1[3456789]/.test(prefix)){
    state.displayOutput=await evaluate("(async()=>{const {appearance}=await import('yingxu://app/js/appearance.js');return appearance.state.displayOutput})()");
    assert.equal(state.displayOutput.host,'qt-quick');
    assert.equal(state.displayOutput.backend,'D3D11');
    if(state.displayOutput.systemHdrEnabled===true){
      assert.equal(state.displayOutput.swapchain,'HDRExtendedSrgbLinear');
      assert.equal(state.displayOutput.nativeHdrActive,true);
    }
    assert.equal(state.displayOutput.osSettingsChanged,false);
    state.captureScope='SDR web content before native HDR shader; not a physical luminance measurement';
  }
  if(!startupOnly){
  await evaluate("document.getElementById('appearance-button').click();true");
  await until(()=>evaluate("Boolean(document.querySelector('dialog[open]'))"),'Appearance dialog unavailable');
  assert.equal(await evaluate("document.querySelector('dialog[open]').textContent.includes('玻璃')"),true);
  await evaluate("document.querySelector('dialog[open] [data-close]').click();true");
  await until(()=>evaluate("!document.querySelector('dialog[open]')"),'Appearance dialog did not finish closing');
  if((prefix.startsWith('stage16')||prefix.startsWith('stage17')||prefix.startsWith('stage19'))){
    assert.equal(await evaluate("!document.getElementById('command-button')&&!document.getElementById('command-dialog')"),true);
    await command('Input.dispatchKeyEvent',{type:'keyDown',modifiers:2,key:'k',code:'KeyK',windowsVirtualKeyCode:75});
    await command('Input.dispatchKeyEvent',{type:'keyUp',modifiers:2,key:'k',code:'KeyK',windowsVirtualKeyCode:75});
    assert.equal(await evaluate("!document.querySelector('dialog[open]')"),true);
    const reduced=await evaluate("(async()=>{const {appearance}=await import('yingxu://app/js/appearance.js');return appearance.state.reducedMotion||matchMedia('(prefers-reduced-motion: reduce)').matches})()");
    const fadeFrames=[];
    for(let index=0;index<6;index++){
      await evaluate("document.getElementById('appearance-button').click();true");
      await until(()=>evaluate("document.getElementById('appearance-dialog').open"),'Settings unavailable');
      if(index%2)await evaluate("document.getElementById('appearance-dialog').scrollTop=400;true");
      await pause(100);
      if(index===0){
        const settingsShot=await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
        await fs.writeFile(path.join(root,'outputs',`${prefix}_settings.png`),Buffer.from(settingsShot.data,'base64'));
      }
      await evaluate("(()=>{const d=document.getElementById('appearance-dialog');globalThis.__settingsFade=[];const tick=()=>{if(!d.open)return;__settingsFade.push({opacity:Number(getComputedStyle(d).opacity),closing:d.classList.contains('is-closing'),duration:d.getAnimations().map(a=>a.effect.getTiming().duration)});requestAnimationFrame(tick)};requestAnimationFrame(tick);d.querySelector('[data-close]').click();return true})()");
      await until(()=>evaluate("!document.getElementById('appearance-dialog').open"),'Settings fade did not finish');
      const frames=await evaluate('globalThis.__settingsFade.filter(s=>s.closing)');
      if(!reduced){
        assert.ok(frames.some(frame=>frame.opacity>0&&frame.opacity<1),'No visible fade frame');
        assert.ok(frames.some(frame=>frame.duration.includes(140)),'Missing 140ms animation');
      }
      assert.equal(await evaluate("document.activeElement.id==='appearance-button'"),true);
      fadeFrames.push(frames.length);
      await pause(160);
    }
    state.quickActionsAbsent=true;state.settingsClosesVerified=6;state.fadeFrames=fadeFrames;state.reducedMotion=reduced;
  }
  if(prefix.startsWith('stage19')){
    await evaluate(await fs.readFile(path.join(root,'tests/frontend/rendering.js'),'utf8'));
    state.listRendering=await evaluate('globalThis.__renderTests');
    assert.equal(state.listRendering.passed,true,JSON.stringify(state.listRendering));
    await pause(1200);
    state.idleClassMutations=await evaluate(`new Promise(resolve=>{let count=0;
      const observer=new MutationObserver(records=>count+=records.length);
      observer.observe(document.body,{subtree:true,attributes:true,attributeFilter:['class']});
      setTimeout(()=>{observer.disconnect();resolve(count)},1000)})`);
    assert.ok(state.idleClassMutations<8,'Packaged controls still self-invalidate');
  }
  if(prefix.startsWith('stage14')){
    for(let index=0;index<6;index++){
      await evaluate("document.getElementById('appearance-button').click();true");
      await until(()=>evaluate("document.getElementById('appearance-dialog').open"),'Native settings unavailable');
      assert.equal(await evaluate("getComputedStyle(document.querySelector('dialog[open]'),'::backdrop').backdropFilter"),'none');
      assert.equal(await evaluate("document.querySelector('dialog[open]').getAnimations().length"),0);
      await evaluate("document.getElementById('appearance-dialog').scrollTop=400;true");
      await pause(60);
      await evaluate("document.getElementById('appearance-dialog').scrollTop=0;true");
      if(index===5){
        const settingsShot=await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
        await fs.writeFile(path.join(root,'outputs',`${prefix}_settings.png`),Buffer.from(settingsShot.data,'base64'));
      }
      await evaluate("document.querySelector('#appearance-dialog [data-close]').click();true");
      await until(()=>evaluate("!document.querySelector('dialog[open]')"),'Native settings close failed');
      await evaluate("document.getElementById('command-button').click();document.getElementById('command-search').value='外观';document.getElementById('command-search').dispatchEvent(new Event('input',{bubbles:true}));true");
      await until(()=>evaluate("document.querySelectorAll('#command-list .command-option').length===1"),'Command filtering failed');
      if(index===5){
        const commandShot=await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
        await fs.writeFile(path.join(root,'outputs',`${prefix}_commands.png`),Buffer.from(commandShot.data,'base64'));
      }
      await evaluate("document.querySelector('#command-list .command-option').click();true");
      await until(()=>evaluate("document.getElementById('appearance-dialog').open && !document.getElementById('command-dialog').open"),'Command to settings failed');
      await evaluate("document.querySelector('#appearance-dialog [data-close]').click();true");
      await until(()=>evaluate("!document.querySelector('dialog[open]')"),'Workspace did not return');
    }
    assert.equal(await evaluate("(async()=>{const {desktopChannel}=await import('yingxu://app/js/channel.js');const channel=await desktopChannel();return typeof channel.objects.compositor.setOverlayActive==='function'})()"),true);
    state.modalCyclesVerified=6;
    state.dialogBackdrop='none';
  }
  if(prefix.startsWith('stage15')){
    await evaluate("document.getElementById('command-button').click();globalThis.__packagedWheel=[];document.addEventListener('wheel',e=>__packagedWheel.push({trusted:e.isTrusted,prevented:e.defaultPrevented}),{passive:true});true");
    await until(()=>evaluate("document.querySelectorAll('#command-list .command-option').length>10"),'Full command list unavailable');
    assert.equal(await evaluate("[...document.querySelectorAll('#command-list button')].every(e=>getComputedStyle(e).backdropFilter==='none'&&getComputedStyle(e).transform==='none'&&!e.hasAttribute('data-jelly'))"),true);
    const point=await evaluate("(()=>{const b=document.getElementById('command-list').getBoundingClientRect();return {x:b.x+b.width*.5,y:b.y+b.height*.3}})()");
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point});
    const positions=[];
    for(const deltaY of [60,60,60,60,-60,-60,-60,-60,120,-120,120,-120]){
      await command('Input.dispatchMouseEvent',{type:'mouseWheel',...point,deltaX:0,deltaY});
      await pause(24);
      positions.push(await evaluate("document.getElementById('command-list').scrollTop"));
      assert.ok(await evaluate("document.querySelectorAll('#command-list .command-option').length>10"));
    }
    const wheels=await evaluate('globalThis.__packagedWheel');
    assert.equal(wheels.length,12);assert.ok(wheels.every(e=>e.trusted&&e.prevented));
    assert.ok(Math.max(...positions)>0);
    const wheelShot=await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
    await fs.writeFile(path.join(root,'outputs',`${prefix}_wheel_commands.png`),Buffer.from(wheelShot.data,'base64'));
    state.wheelEventsVerified=12;state.maximumCommandScroll=Math.max(...positions);
    await evaluate("document.querySelector('#command-dialog [data-close]').click();true");
  }
  if(prefix.startsWith('stage12')){
    const lightingBackgrounds={};
    for(const mode of ['off','soft','enhanced']){
      await evaluate("document.getElementById('appearance-button').click();true");
      await until(()=>evaluate("document.getElementById('appearance-dialog').open"),'Lighting dialog unavailable');
      await evaluate(`(()=>{const s=document.getElementById('lighting-setting');s.value='${mode}';s.dispatchEvent(new Event('change',{bubbles:true}));return true})()`);
      await until(()=>evaluate(`document.documentElement.dataset.lighting==='${mode}'`),'Lighting setting did not apply');
      lightingBackgrounds[mode]=await evaluate("getComputedStyle(document.body).backgroundImage");
      assert.equal(await evaluate("document.querySelector('.list-heading button').classList.contains('liquid-button')"),false);
      await evaluate("document.querySelector('#appearance-dialog [data-close]').click();true");
      await until(()=>evaluate("!document.querySelector('dialog[open]')"),'Lighting dialog did not close');
      await pause(150);
      const comparison=await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
      await fs.writeFile(path.join(root,'outputs',`${prefix}_lighting_${mode}.png`),Buffer.from(comparison.data,'base64'));
    }
    assert.notEqual(lightingBackgrounds.off,lightingBackgrounds.enhanced);
    assert.notEqual(lightingBackgrounds.soft,lightingBackgrounds.enhanced);
    // Restore the original user preference after the visual comparison.
    if(state.lighting!=='enhanced'){
      await evaluate(`(()=>{const s=document.getElementById('lighting-setting');s.value='${state.lighting}';s.dispatchEvent(new Event('change',{bubbles:true}));return true})()`);
      await until(()=>evaluate(`document.documentElement.dataset.lighting==='${state.lighting}'`),'Original lighting preference did not restore');
    }
    state.lightingModesVerified=Object.keys(lightingBackgrounds);
  }
  if(process.env.YINGXU_CHECK_WORKFLOW==='1'){
    const media=path.join(temporary,"中文 & 视频 '测试'");await fs.mkdir(media);
    const videoNames=['Feature.S01E01.1080p.mkv','Feature.S01E02.1080p.mkv'];
    const subtitle='1\n00:00:01,000 --> 00:00:02,000\nPackaged workflow fixture\n';
    for(const name of videoNames)await fs.writeFile(path.join(media,name),'test-video');
    const original='Feature.S01E01.chs.srt',destination='Feature.S01E01.1080p.chs.srt';
    await fs.writeFile(path.join(media,original),subtitle);
    await evaluate("document.getElementById('dataset-button').click();true");
    // One native directory choice is supplied by the operator/test agent. Do not
    // expose arbitrary filesystem paths through the production web bridge.
    console.log(JSON.stringify({needsNativeFolderChoice:true,pid:child.pid,folder:media}));
    await until(()=>evaluate("document.documentElement.dataset.loading==='false' && document.querySelectorAll('.file-row').length===2"),'Native folder choice/scan did not finish',300000);
    // The recommendation tab does not load a remote page until search starts;
    // no DevTools target is required for its hidden, empty WebEngine view.
    // Observe the real native reply emitted after construction/show instead.
    await evaluate(`(()=>{
      globalThis.__testOnlineReply=null;
      const transport=qt.webChannelTransport, previous=transport.onmessage;
      transport.onmessage=function(event){
        try{
          const packet=JSON.parse(event.data);
          for(const argument of packet.args||[]){
            if(typeof argument!=='string')continue;
            const reply=JSON.parse(argument);
            if(reply.ok&&reply.data?.opened===true&&Number.isInteger(reply.data.taskCount))globalThis.__testOnlineReply=reply.data;
          }
        }catch{}
        return previous.call(this,event);
      };
      return true;
    })()`);
    await evaluate("document.getElementById('online-subtitles-button').click();true");
    await until(()=>evaluate("globalThis.__testOnlineReply?.opened===true"),'Packaged online browser native reply unavailable');
    const nativeOnline=await evaluate("globalThis.__testOnlineReply");
    assert.equal(nativeOnline.taskCount,1);
    const targets=await(await fetch(`http://127.0.0.1:${port}/json/list`)).json();
    assert.ok(targets.every(item=>item.url==='yingxu://app/workspace.html'||item.url===''||item.url==='about:blank'));
    await evaluate("document.querySelector('[data-row-id=\"video-1\"]').click();true");
    await until(()=>evaluate("document.querySelector('.detail-video')?.textContent.includes('S01E01')"),'Packaged selection failed');
    if(await evaluate("document.querySelector('#inspector-actions .detail-actions button')?.textContent.includes('确认匹配')")){
      await evaluate("document.querySelector('#inspector-actions .detail-actions button').click();true");
      await until(()=>evaluate("document.documentElement.dataset.loading==='false' && !document.querySelector('#inspector-actions .detail-actions button').textContent.includes('确认匹配')"),'Packaged match confirmation failed');
    }
    await evaluate("document.getElementById('preview-button').click();true");
    await until(()=>evaluate("document.getElementById('preview-dialog').open"),'Packaged preview unavailable');
    assert.equal(await evaluate("document.getElementById('execute-button').disabled"),true);
    assert.equal(await fs.readFile(path.join(media,original),'utf8'),subtitle);
    assert.equal(await evaluate(`document.getElementById('preview-items').textContent.includes(${JSON.stringify(destination)})`),true);
    await evaluate("document.getElementById('preview-ack').click();true");
    await until(()=>evaluate("!document.getElementById('execute-button').disabled"),'Packaged acknowledgement failed');
    await evaluate("document.getElementById('execute-button').click();document.getElementById('execute-button').click();true");
    await until(()=>evaluate("document.documentElement.dataset.loading==='false' && document.getElementById('history-dialog').open"),'Packaged organize/result failed');
    assert.equal(await fs.readFile(path.join(media,destination),'utf8'),subtitle);
    assert.equal((await fs.readdir(media)).filter(name=>name.endsWith('.srt')).length,1);
    for(const name of videoNames)assert.equal(await fs.readFile(path.join(media,name),'utf8'),'test-video');
    const history=await fs.readFile(path.join(temporary,'YingXu','history.jsonl'),'utf8');
    const records=history.trim().split(/\r?\n/).map(line=>JSON.parse(line));
    assert.equal(records.length,1);assert.equal(records[0].items.filter(item=>item.status==='success').length,1);
    await command('Page.enable');
    const resultShot=await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
    await fs.writeFile(path.join(root,'outputs',`${prefix}_packaged_result.png`),Buffer.from(resultShot.data,'base64'));
    workflow={scanVideos:2,organized:1,unmatched:1,records:1,mediaBytesPreserved:true,
      confirmationRequired:true,doubleClickOnlyOneRun:true,onlineBrowserOpenedOffline:true,
      note:'Online download/import end-to-end is covered by source Qt controlled fixtures; this EXE test does not connect to external sites.'};
    await evaluate("document.querySelector('#history-dialog [data-close]').click();true");
  }
  await pause(500);
  await command('Page.enable');
  const shot=await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
  await fs.writeFile(path.join(root,'outputs',`${prefix}_packaged_workspace.png`),Buffer.from(shot.data,'base64'));
  }
  state.frameValidationPerformed=!startupOnly;
  if(startupOnly)state.quickActionsAbsent=await evaluate("!document.getElementById('command-button')&&!document.getElementById('command-dialog')");
  assert.deepEqual(exceptionMessages,[]);assert.deepEqual(consoleMessages,[]);
  const processMetrics=execFileSync(path.join(windows,'System32','WindowsPowerShell','v1.0','powershell.exe'),
    ['-NoProfile','-Command',`[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); $ids=@(${child.pid}); $all=Get-CimInstance Win32_Process; for($n=0;$n -lt 5;$n++){ $ids+=@($all | Where-Object {$_.ParentProcessId -in $ids} | ForEach-Object ProcessId); $ids=@($ids | Select-Object -Unique) }; @(Get-Process -Id $ids -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,Responding,MainWindowTitle,WorkingSet64,CPU) | ConvertTo-Json -Compress`],
    {encoding:'utf8',windowsHide:true}).trim();
  const processTree=JSON.parse(processMetrics);
  if(/^stage1[56789]/.test(prefix)){
    const ids=processTree.filter(item=>item.ProcessName==='QtWebEngineProcess').map(item=>item.Id);
    assert.ok(ids.length && ids.every(Number.isInteger));
    state.occlusionGuardPassedToChild=JSON.parse(execFileSync(path.join(windows,'System32','WindowsPowerShell','v1.0','powershell.exe'),
      ['-NoProfile','-Command',`$ids=@(${ids.join(',')}); [bool](@(Get-CimInstance Win32_Process | Where-Object {$_.ProcessId -in $ids -and $_.CommandLine -match 'CalculateNativeWinOcclusion'}).Count -gt 0) | ConvertTo-Json -Compress`],
      {encoding:'utf8',windowsHide:true}).trim());
    assert.equal(state.occlusionGuardPassedToChild,true);
  }
  assert.ok(processTree.some(item=>item.ProcessName===(sourceMode?'python':'YingXu')&&item.Responding),'No responsive app process');
  const result={executable,environment:sourceMode?'source Qt window':'Windows EXE',pid:child.pid,startupSeconds:Number(startupSeconds.toFixed(3)),state,processTree,
    exceptionMessages,consoleMessages,workflow,startupOnly,nativeTitleVisibleToLauncher:processTree.some(item=>item.MainWindowTitle.includes('映序')),
    testInspector:'temporary 127.0.0.1 only; removed at process exit',
    scope:startupOnly?'Startup/channel/offline assets/DOM controls and reported output only; no screenshot, animation-frame or media-execution certification.':workflow?'Packaged startup/channel/assets, actual scan/confirmation/organization/record and isolated online window.':`${sourceMode?'Source':'Packaged'} startup, real channel, offline assets, glass action controls and flat headings, lighting modes and dialogs. Media execution covered separately by source E2E.`};
  await fs.writeFile(path.join(results,`${prefix}_packaged.json`),JSON.stringify(result,null,2));
  console.log(JSON.stringify({...result,state:{...state,assets:`${state.assets.length} local resources`}}));
}catch(failure){
  if(socket?.readyState===WebSocket.OPEN){
    const diagnostic=await evaluate("({data:{...document.documentElement.dataset},visibility:document.visibilityState,focus:document.hasFocus(),footer:document.getElementById('footer-status')?.textContent,qt:!!globalThis.qt?.webChannelTransport,channel:typeof QWebChannel,buttons:document.querySelectorAll('button').length,unmounted:[...document.querySelectorAll('button')].filter(b=>b.dataset.glassRole!=='structural'&&!b.classList.contains('liquid-button')).map(b=>({id:b.id,classes:b.className,hidden:b.hidden}))})").catch(error=>({error:String(error)}));
    const moduleFailure=await evaluate("import('yingxu://app/js/workspace.js').then(()=>null,error=>String(error.stack||error))").catch(error=>String(error));
    await fs.writeFile(path.join(results,`${prefix}_failure.json`),JSON.stringify({error:String(failure),diagnostic,moduleFailure,exceptionMessages,consoleMessages},null,2));
    console.error(JSON.stringify({diagnostic,moduleFailure,exceptionMessages,consoleMessages}));
  }
  throw failure;
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
