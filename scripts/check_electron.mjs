// Real Electron window, synthetic media and isolated settings. No online sites.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawn,execFileSync} from 'node:child_process';
import net from 'node:net';
import assert from 'node:assert/strict';
import {CdpClient} from './cdp_client.mjs';
import {domDriver} from './cdp_dom.mjs';

const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const effects=process.argv.includes('--moderate')?'moderate':'full';
const quick=process.argv.includes('--quick');
const sdr=process.argv.includes('--sdr');
const output=path.join(ROOT,'work/test-results',`electron-a-${effects}${quick?'-capture':''}${sdr?'-sdr':''}`);
const media=path.join(output,'media'),profile=path.join(output,'profile');
fs.mkdirSync(media,{recursive:true});fs.mkdirSync(path.join(profile,'python'),{recursive:true});
for(let index=1;index<=300;index++) {
  const title=`映序测试剧.S01E${String(index).padStart(3,'0')}`;
  fs.writeFileSync(path.join(media,`${title}.2160p.mkv`),'synthetic video');
  fs.writeFileSync(path.join(media,`${title}.chs.srt`),'1\n00:00:01,000 --> 00:00:02,000\n测试字幕\n');
}
const python=path.join(ROOT,'.venv-web/Scripts/python.exe');
const wake=spawn(python,[path.join(ROOT,'scripts/probe_environment.py'),'--keep-awake'],{windowsHide:true,stdio:['pipe','pipe','pipe']});
const environment=await new Promise(resolve=>wake.stdout.once('data',data=>resolve(JSON.parse(data.toString()))));
await new Promise(resolve=>setTimeout(resolve,2000));
execFileSync(python,['-c',"import json,sys;from PySide6.QtCore import QSettings;s=QSettings(sys.argv[1],QSettings.IniFormat);s.setValue('subtitles/embedded/v1',json.dumps({'enabled':False,'language':'chinese'}));s.sync()",path.join(profile,'python/embedded.ini')]);
fs.writeFileSync(path.join(profile,'appearance.json'),JSON.stringify({theme:'dark',nativeHdr:!sdr,mistEnabled:effects==='full',particlesEnabled:effects==='full'}));
const port=await new Promise(resolve=>{const server=net.createServer();server.listen(0,'127.0.0.1',()=>{const {port}=server.address();server.close(()=>resolve(port));});});
const result={passed:false,effects,environment,checks:[],errors:[],physicalPeakMeasured:false};
const env={...process.env,YINGXU_PYTHON:python};delete env.ELECTRON_RUN_AS_NODE;
const start=performance.now();
const child=spawn(path.join(ROOT,'work/tools/electron-45.0.0/electron.exe'),[
  path.join(ROOT,'desktop/electron'),'--preview',`--profile=${profile}`,'--diagnostics',`--test-folder=${media}`,`--effects=${effects}`,
  `--remote-debugging-port=${port}`,'--remote-debugging-address=127.0.0.1',
],{cwd:ROOT,env,windowsHide:false,stdio:['ignore','pipe','pipe']});
const logs=[];child.stdout.on('data',data=>logs.push(data.toString()));child.stderr.on('data',data=>logs.push(data.toString()));
let browser,cdp;
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
try {
  for(let i=0;i<100;i++) {
    if(child.exitCode!==null)throw Error('Electron exited: '+logs.join(''));
    try {const response=await fetch(`http://127.0.0.1:${port}/json/version`);if(response.ok)break;} catch{}
    if(i===99)throw Error('CDP startup timeout');await sleep(150);
  }
  const version=await (await fetch(`http://127.0.0.1:${port}/json/version`)).json();browser=await CdpClient.open(version.webSocketDebuggerUrl);
  let target;
  for(let i=0;i<100;i++) {target=(await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find(item=>item.url.startsWith('yingxu://app/'));if(target)break;await sleep(100);}
  assert(target,'No application page');cdp=await CdpClient.open(target.webSocketDebuggerUrl);const page=domDriver(cdp);
  cdp.on('Runtime.exceptionThrown',event=>result.errors.push(event.exceptionDetails.exception?.description||event.exceptionDetails.text));await cdp.send('Runtime.enable');
  await page.waitForFunction(()=>document.documentElement.dataset.desktopBoot==='ready',{timeout:30000});
  result.startupMs=Math.round(performance.now()-start);
  result.sandbox=await page.evaluate(()=>({node:typeof require,process:typeof process,qt:typeof qt,host:yingxuHost.kind}));
  assert.deepEqual(result.sandbox,{node:'undefined',process:'undefined',qt:'undefined',host:'electron'});
  result.checks.push('isolated_host_no_node_or_fake_qt');
  await page.locator('#dataset-button').click();
  await page.waitForFunction(()=>document.querySelector('#count-all')?.textContent==='300',{timeout:30000});
  await page.waitForFunction(()=>document.querySelector('#file-list')?.getAttribute('aria-busy')==='false');
  result.rows=await page.locator('#file-list').getAttribute('aria-rowcount');assert.equal(result.rows,'300');
  assert(await page.locator('#online-subtitles-button').isDisabled());
  assert(await page.locator('#execute-button').isDisabled());
  result.checks.push('real_scan_300_videos_readonly_controls');
  await page.locator('#search-input').fill('E012');
  await page.waitForFunction(()=>document.querySelector('#list-count').textContent.startsWith('1 /'));
  await page.locator('#search-input').fill('');
  await page.waitForFunction(()=>document.querySelector('#list-count').textContent.startsWith('300 /'));
  result.checks.push('real_search_and_restore');
  await page.locator('#theme-quick').selectOption('light');
  await page.waitForFunction(()=>document.documentElement.dataset.theme==='light');
  await page.locator('#theme-quick').selectOption('dark');
  await page.waitForFunction(()=>document.documentElement.dataset.theme==='dark');
  await page.locator('#preview-button').click();
  await page.waitForFunction(()=>document.querySelector('#preview-dialog').open);
  assert(await page.locator('#preview-items .preview-item').count()>0);
  assert(await page.locator('#preview-ack').isDisabled());assert(await page.locator('#execute-button').isDisabled());
  await page.locator('#preview-dialog [data-close]').first().click();
  await page.waitForFunction(()=>!document.querySelector('#preview-dialog').open);
  await page.reload();await page.waitForFunction(()=>document.documentElement.dataset.desktopBoot==='ready');
  await page.waitForFunction(()=>document.querySelector('#count-all').textContent==='300');
  result.checks.push('theme_real_preview_disabled_execution_reload_reconnect');
  result.hdr=await page.evaluate(async()=>{const {appearance}=await import('./js/appearance.js');for(let i=0;i<50&&appearance.state.nativeHdr&&!appearance.state.displayOutput?.hdrConfigured;i++)await new Promise(resolve=>setTimeout(resolve,100));return appearance.state.displayOutput;});
  for(let i=0;i<(quick?0:20);i++) {
    await page.locator('#appearance-button').click();
    await page.waitForFunction(()=>document.querySelector('#appearance-dialog').open);
    await page.locator('#appearance-dialog [data-close]').click();
    await page.waitForFunction(()=>!document.querySelector('#appearance-dialog').open);
  }
  if(!quick)result.checks.push('20_settings_open_fade_close');
  result.layout=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth,font:document.fonts.check('14px "Noto Sans SC"'),rows:document.querySelectorAll('#list-items [role=row]').length}));
  assert(!result.layout.overflow);
  // Check work stops when interaction ends, and on actual native minimize.
  await page.evaluate(()=>{window.__probeGlDraws=0;for(const name of ['drawArrays','drawElements']){const original=WebGL2RenderingContext.prototype[name];WebGL2RenderingContext.prototype[name]=function(...args){window.__probeGlDraws++;return original.apply(this,args);};}});
  await page.mouse.move(1,1);await sleep(2500);
  const counters=()=>page.evaluate(async()=>({gl:window.__probeGlDraws,hdr:(await import('./js/hdr-layer.js')).hdrLayer?.frames||0}));
  const idleBefore=await counters();await sleep(400);result.idle={before:idleBefore,after:await counters()};
  assert.deepEqual(result.idle.before,result.idle.after);
  const native=logs.join('').split('\n').map(line=>{try{return JSON.parse(line);}catch{return null;}}).find(frame=>frame?.type==='window');
  assert(native,'No native test window identity');
  const control=(action,...args)=>JSON.parse(execFileSync(python,[path.join(ROOT,'scripts/control_probe_window.py'),native.handle,String(native.pid),action,...args.map(String)],{encoding:'utf8'}));
  const bounds=control('restore');
  result.minimize=control('minimize');await sleep(400);
  assert(await page.evaluate(()=>document.hidden));
  const hiddenBefore=await counters();await sleep(300);assert.deepEqual(hiddenBefore,await counters());
  control('restore');await page.waitForFunction(()=>!document.hidden);
  control('resize',1000,760);await sleep(150);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  control('resize',bounds.width,bounds.height);await sleep(150);
  result.checks.push('idle_no_gl_or_hdr_draws_minimize_restore_native_resize');
  await page.screenshot({path:path.join(output,'workspace.png')});
  // Report actual shader configuration separately from measured HDR output.
  if(result.hdr?.hdrConfigured) {
    await page.evaluate(async()=>{const {hdrLayer}=await import('./js/hdr-layer.js');hdrLayer.setCalibration(true);});
    await sleep(150);
    result.hdrCalibrationRect=await page.locator('#electron-hdr-highlights').boundingBox();
    result.deviceScale=await page.evaluate(()=>devicePixelRatio);
    await page.screenshot({path:path.join(output,'calibration-sdr-preview.png')});
    const frame=logs.join('').split('\n').map(line=>{try{return JSON.parse(line);}catch{return null;}}).find(frame=>frame?.type==='window');
    result.nativeWindow=frame;
    if(frame) {
      try {
        result.hdrCapture=JSON.parse(execFileSync(python,['-X','faulthandler',path.join(ROOT,'scripts/capture_hdr.py'),'--debug','--handle',frame.handle,'--rect',JSON.stringify(result.hdrCalibrationRect),'--scale',String(result.deviceScale)],{encoding:'utf8',timeout:15000}));
      } catch(error){result.hdrCapture={verified:false,error:String(error.stderr||error.message),status:error.status,signal:error.signal};}
    }
    await page.evaluate(async()=>{const {hdrLayer}=await import('./js/hdr-layer.js');hdrLayer.setCalibration(false);});
  }
  const windowFrame=logs.join('').split('\n').map(line=>{try{return JSON.parse(line);}catch{return null;}}).find(frame=>frame?.type==='window');
  if(windowFrame)try{execFileSync(python,[path.join(ROOT,'scripts/capture_window_preview.py'),windowFrame.handle,path.join(output,'native-window.png')]);}catch(error){result.nativeScreenshotError=String(error);}
  result.passed=result.errors.length===0;
  await page.close();
} catch(error) {result.failure=error.stack||String(error);process.exitCode=1;}
finally {
  wake.stdin.end();
  try {cdp?.close();browser?.close();}catch{}
  if(child.exitCode===null){await sleep(500);if(child.exitCode===null)child.kill();}
  fs.writeFileSync(path.join(output,'runtime.log'),logs.join(''));
  fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(result,null,2));
  console.log(JSON.stringify(result,null,2));
}
