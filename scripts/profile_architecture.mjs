// Identical CDP input workloads on the frozen Qt baseline and Electron prototype.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawn,execFileSync} from 'node:child_process';
import net from 'node:net';
import {gzipSync} from 'node:zlib';
import {CdpClient} from './cdp_client.mjs';

const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const option=(key,fallback)=>process.argv.find(value=>value.startsWith(`--${key}=`))?.slice(key.length+3)||fallback;
const host=option('host','electron'),effects=option('effects','full');
const duration=Number(option('seconds','30')),repeats=Number(option('repeats','3'));
const presentationRoot=option('presentation-root',null);
const capturePresentMon=process.argv.includes('--presentmon');
if(capturePresentMon&&(!presentationRoot||host!=='electron'))throw Error('PresentMon requires an Electron presentation-root');
if(!['electron','qt'].includes(host)||!['full','moderate'].includes(effects)||!Number.isFinite(duration)||duration<3||duration>120||!Number.isInteger(repeats)||repeats<1||repeats>5)throw Error('Invalid probe options');
const output=presentationRoot?path.resolve(presentationRoot,`${host}-${effects}`):path.join(ROOT,`work/test-results/${host==='electron'?'architecture-a-visible':'architecture-a-fixed60'}/${host}-${effects}`);
const media=path.join(ROOT,'work/test-results/electron-a-full/media');
const profile=path.join(output,'profile'),python=path.join(ROOT,'.venv-web/Scripts/python.exe');
fs.mkdirSync(profile,{recursive:true});
if(!fs.existsSync(media))throw Error('Run check_electron.mjs once to create the shared synthetic fixture');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const wake=spawn(python,[path.join(ROOT,'scripts/probe_environment.py'),'--keep-awake'],{windowsHide:true,stdio:['pipe','pipe','pipe']});
const environment=await new Promise(resolve=>wake.stdout.once('data',data=>resolve(JSON.parse(data.toString()))));
await sleep(2000);
const port=await new Promise(resolve=>{const server=net.createServer();server.listen(0,'127.0.0.1',()=>{const {port}=server.address();server.close(()=>resolve(port));});});
let command,args;
if(host==='qt') {
  const baseline=path.join(ROOT,'work/test-results/architecture-a/qt-baseline-228773c');
  if(!fs.existsSync(path.join(baseline,'run.py'))) {
    const archive=path.join(ROOT,'work/test-results/architecture-a/baseline.zip');
    execFileSync('git',['archive','228773c','--format=zip',`--output=${archive}`],{cwd:ROOT});
    execFileSync(python,['-c','import sys,zipfile;zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])',archive,baseline]);
  }
  command=python;args=[path.join(ROOT,'scripts/launch_qt_probe.py'),'--root',baseline,'--profile',profile,'--folder',media,'--port',String(port),'--effects',effects];
} else {
  fs.mkdirSync(path.join(profile,'python'),{recursive:true});
  execFileSync(python,['-c',"import json,sys;from PySide6.QtCore import QSettings;s=QSettings(sys.argv[1],QSettings.IniFormat);s.setValue('subtitles/embedded/v1',json.dumps({'enabled':False,'language':'chinese'}));s.sync()",path.join(profile,'python/embedded.ini')]);
  fs.writeFileSync(path.join(profile,'appearance.json'),JSON.stringify({theme:'dark',mistEnabled:effects==='full',particlesEnabled:effects==='full'}));
  command=path.join(ROOT,'work/tools/electron-45.0.0/electron.exe');args=[path.join(ROOT,'desktop/electron'),'--preview',`--profile=${profile}`,'--diagnostics',`--test-folder=${media}`,`--effects=${effects}`,`--remote-debugging-port=${port}`,'--remote-debugging-address=127.0.0.1'];
}
const env={...process.env,YINGXU_PYTHON:python};delete env.ELECTRON_RUN_AS_NODE;
const started=performance.now(),child=spawn(command,args,{cwd:ROOT,env,windowsHide:host!=='electron',stdio:['pipe','pipe','pipe']});
const logs=[];child.stdout.on('data',data=>logs.push(data.toString()));child.stderr.on('data',data=>logs.push(data.toString()));
const result={host,effects,environment,baseline:'228773c95e8ab9c1c786354ad0d8b026f11826f0',durationSeconds:duration,repeats,
  comparableVisualPolicy:'same Lens and desktop overlay behavior; HDR host differs',passes:[],presentMon:{available:false,reason:'ETW trace session access denied (requires Windows administrator or Performance Log Users)'},physicalPeakMeasured:false};
let browser,page,cdp,rootCdp,tracing=false;
function summarize(values) {
  if(!values.length)return {count:0};
  const sorted=[...values].sort((a,b)=>a-b),average=values.reduce((a,b)=>a+b,0)/values.length;
  return {count:values.length,fps:Math.round(100000/average)/100,p95Ms:Math.round(sorted[Math.min(sorted.length-1,Math.floor(sorted.length*.95))]*100)/100,
    over25Percent:Math.round(values.filter(value=>value>25).length/values.length*10000)/100,maxMs:Math.round(sorted.at(-1)*100)/100};
}
try {
  for(let i=0;i<150;i++){if(child.exitCode!==null)throw Error(logs.join(''));try{if((await fetch(`http://127.0.0.1:${port}/json/version`)).ok)break;}catch{}if(i===149)throw Error('CDP startup timeout');await sleep(100);}
  const version=await (await fetch(`http://127.0.0.1:${port}/json/version`)).json();
  rootCdp=await CdpClient.open(version.webSocketDebuggerUrl);browser=rootCdp;
  let target;
  for(let i=0;i<100;i++){target=(await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find(item=>item.url.startsWith('yingxu://app/'));if(target)break;await sleep(100);}
  if(!target)throw Error('No workspace');
  cdp=await CdpClient.open(target.webSocketDebuggerUrl);
  const evaluate=async(fn,arg)=>{const reply=await cdp.send('Runtime.evaluate',{expression:`(${fn.toString()})(${arg===undefined?'':JSON.stringify(arg)})`,returnByValue:true,awaitPromise:true});if(reply.exceptionDetails)throw Error(reply.exceptionDetails.exception?.description||reply.exceptionDetails.text);return reply.result?.value;};
  page={evaluate,waitForFunction:async fn=>{const deadline=performance.now()+30000;while(performance.now()<deadline){if(await evaluate(fn))return;await sleep(80);}throw Error('Workspace readiness timeout');},
    screenshot:async({path:filename})=>{const shot=await cdp.send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(filename,Buffer.from(shot.data,'base64'));},
    close:()=>cdp.send('Page.close')};
  await page.waitForFunction(()=>document.documentElement?.dataset.desktopBoot==='ready');
  result.startupMs=Math.round(performance.now()-started);
  if(host==='electron')await page.evaluate(()=>document.getElementById('dataset-button').click());
  await page.waitForFunction(()=>document.querySelector('#count-all').textContent==='300'&&document.querySelector('#file-list').getAttribute('aria-busy')==='false');
  result.viewport=await page.evaluate(()=>({width:innerWidth,height:innerHeight,scale:devicePixelRatio,visibility:document.visibilityState}));
  result.output=await page.evaluate(async()=>{const {appearance}=await import('./js/appearance.js');return appearance.state.displayOutput;});
  if(host==='electron') {
    const native=logs.join('').split('\n').map(line=>{try{return JSON.parse(line);}catch{return null;}}).find(frame=>frame?.type==='window');
    if(!native?.visible)throw Error('Native Electron window is hidden; refusing an invalid performance comparison');
    result.nativeWindowVisible=true;
    execFileSync(python,[path.join(ROOT,'scripts/capture_window_preview.py'),native.handle,path.join(output,'native-before.png')]);
  }
  try {result.gpu=(await rootCdp.send('SystemInfo.getInfo')).gpu.devices;}catch(error){result.gpuError=String(error);}
  if(presentationRoot) {
    const before=Number(process.hrtime.bigint())/1e6;
    const counter=JSON.parse(execFileSync(python,['-c',"import ctypes as c,json;k=c.WinDLL('kernel32');v=c.c_longlong();f=c.c_longlong();k.QueryPerformanceCounter(c.byref(v));k.QueryPerformanceFrequency(c.byref(f));print(json.dumps({'qpcMs':v.value*1000/f.value}))"],{encoding:'utf8'}));
    const after=Number(process.hrtime.bigint())/1e6;
    result.clock={qpcOffsetMs:counter.qpcMs-(before+after)/2,uncertaintyMs:(after-before)/2};
    result.processes=(await rootCdp.send('SystemInfo.getProcessInfo')).processInfo.map(({id,type})=>({id,type}));
    result.presentMon={available:null,reason:'External administrator-only capture; CSV must be matched to the recorded process IDs and QPC phase boundaries.'};
  }
  if(capturePresentMon) {
    const gpu=result.processes.find(item=>item.type==='GPU');
    if(!gpu)throw Error('No GPU process for bounded presentation capture');
    const capture=JSON.parse(execFileSync('powershell.exe',['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',
      path.join(ROOT,'scripts/start_presentmon_capture.ps1'),'-OutputDirectory',output,'-Seconds',String(Math.ceil(duration*repeats+45)),
      '-TargetProcessId',String(gpu.id)],{encoding:'utf8'}));
    if(!capture.launched)throw Error('PresentMon did not start');
    result.presentMon={available:null,capture,reason:'Awaiting CSV displayed-time correlation'};
    await cdp.send('Page.bringToFront');await sleep(2000);
  }
  const boxes=await page.evaluate(()=>Object.fromEntries(['scan-options-button','file-list','dataset-button'].map(id=>{const r=document.getElementById(id).getBoundingClientRect();return [id,{x:r.x,y:r.y,w:r.width,h:r.height}];})));
  for(let iteration=0;iteration<repeats;iteration++) {
    const pass={iteration:iteration+1,phases:{}};
    result.currentPass=pass;
    await page.evaluate(()=>{
      const probe=window.__architectureProbe={phase:null,last:0,gaps:{hover:[],drag:[],scroll:[]},longTasks:[],scrollEvents:0};
      probe.frame=time=>{if(probe.phase){if(probe.last)probe.gaps[probe.phase].push(time-probe.last);probe.last=time;}probe.raf=requestAnimationFrame(probe.frame);};
      probe.raf=requestAnimationFrame(probe.frame);
      probe.scroll=()=>probe.scrollEvents++;document.getElementById('file-list').addEventListener('scroll',probe.scroll);
      probe.observer=new PerformanceObserver(list=>probe.longTasks.push(...list.getEntries().map(entry=>({start:entry.startTime,duration:entry.duration,phase:probe.phase}))));
      probe.observer.observe({type:'longtask'});
    });
    if(iteration===0){await rootCdp.send('Tracing.start',{categories:'viz,cc,benchmark,disabled-by-default-devtools.timeline.frame',transferMode:'ReturnAsStream'});tracing=true;}
    let before;
    try{before=(await rootCdp.send('SystemInfo.getProcessInfo')).processInfo;}catch{}
    const phaseDuration=duration*1000/3;
    for(const phase of ['hover','drag','scroll']) {
      result.activeStep={iteration:iteration+1,phase,step:'positioning'};
      console.log(JSON.stringify({activeStep:result.activeStep}));
      await page.evaluate(phase=>{const p=window.__architectureProbe;p.phase=phase;p.last=0;},phase);
      const box=boxes[phase==='scroll'?'file-list':phase==='drag'?'dataset-button':'scan-options-button'];
      const cx=box.x+box.w/2,cy=box.y+box.h/2;
      await cdp.send('Input.dispatchMouseEvent',{type:'mouseMoved',x:cx,y:cy});
      result.activeStep.step='pressing';
      if(phase==='drag')await cdp.send('Input.dispatchMouseEvent',{type:'mousePressed',x:cx,y:cy,button:'left',buttons:1,clickCount:1});
      const begin=performance.now();let events=0;const inFlight=new Set();let inputError;
      const startQpcMs=result.clock?Number(process.hrtime.bigint())/1e6+result.clock.qpcOffsetMs:null;
      const phaseResult=pass.phases[phase]={events:0,...(startQpcMs===null?{}:{startQpcMs}),completed:false};
      result.activeStep.step='input';
      while(performance.now()-begin<phaseDuration) {
        const scheduled=begin+events*1000/60;
        if(scheduled>performance.now())await sleep(scheduled-performance.now());
        if(performance.now()-begin>=phaseDuration)break;
        const t=performance.now()-begin;
        const request=cdp.send('Input.dispatchMouseEvent',phase==='scroll'
          ?{type:'mouseWheel',x:cx,y:cy,deltaX:0,deltaY:Math.floor(t/1200)%2?50:-50}
          :{type:'mouseMoved',x:cx+Math.sin(t/130)*(phase==='drag'?18:box.w*.38),y:cy+Math.cos(t/170)*8,buttons:phase==='drag'?1:0});
        inFlight.add(request);request.then(()=>inFlight.delete(request),error=>{inputError=error;inFlight.delete(request);});
        events++;phaseResult.events=events;if(inFlight.size>20)await Promise.race(inFlight);
      }
      result.activeStep.step='input-acknowledgement';
      await Promise.all(inFlight);if(inputError)throw inputError;
      result.activeStep.step='releasing';
      if(phase==='drag')await cdp.send('Input.dispatchMouseEvent',{type:'mouseReleased',x:cx+18,y:cy,button:'left',buttons:0,clickCount:1});
      pass.phases[phase]={...phaseResult,activeMs:Math.round(performance.now()-begin),...(startQpcMs===null?{}:{endQpcMs:Number(process.hrtime.bigint())/1e6+result.clock.qpcOffsetMs}),completed:true};
    }
    const sampled=await page.evaluate(()=>{const p=window.__architectureProbe;p.phase=null;cancelAnimationFrame(p.raf);p.observer.disconnect();document.getElementById('file-list').removeEventListener('scroll',p.scroll);return {gaps:p.gaps,longTasks:p.longTasks,scrollEvents:p.scrollEvents};});
    for(const phase of ['hover','drag','scroll'])pass.phases[phase]={...pass.phases[phase],raf:summarize(sampled.gaps[phase])};
    pass.longTasks=sampled.longTasks;pass.scrollEvents=sampled.scrollEvents;
    try{const after=(await rootCdp.send('SystemInfo.getProcessInfo')).processInfo;pass.chromiumCpuSeconds=after.reduce((sum,item)=>sum+Math.max(0,item.cpuTime-(before?.find(old=>old.id===item.id)?.cpuTime||item.cpuTime)),0);
      const ids=[...new Set(after.map(item=>item.id).filter(id=>Number.isInteger(id)&&id>0))].join(',');
      if(ids)pass.processMemory=JSON.parse(execFileSync('powershell.exe',['-NoProfile','-NonInteractive','-Command',`$items=@(Get-Process -Id ${ids} -ErrorAction SilentlyContinue);[pscustomobject]@{workingSetBytes=($items|Measure-Object WorkingSet64 -Sum).Sum;privateBytes=($items|Measure-Object PrivateMemorySize64 -Sum).Sum}|ConvertTo-Json -Compress`],{encoding:'utf8'}));
    }catch(error){pass.processMemoryError=String(error);}
    if(tracing) {
      const complete=new Promise(resolve=>rootCdp.once('Tracing.tracingComplete',resolve));await rootCdp.send('Tracing.end');const {stream}=await complete;tracing=false;
      let raw='';for(;;){const chunk=await rootCdp.send('IO.read',{handle:stream});raw+=chunk.base64Encoded?Buffer.from(chunk.data,'base64').toString():chunk.data;if(chunk.eof)break;}
      await rootCdp.send('IO.close',{handle:stream});fs.writeFileSync(path.join(output,'trace.json.gz'),gzipSync(raw));
      const events=JSON.parse(raw).traceEvents,counts={};
      for(const event of events)if(/present|swap|drawframe|pipeline/i.test(event.name))counts[event.name]=(counts[event.name]||0)+1;
      pass.traceEvents=Object.fromEntries(Object.entries(counts).sort((a,b)=>b[1]-a[1]).slice(0,35));
      pass.presentationCandidates=events.filter(event=>/presented|presentationfeedback|framepresent/i.test(event.name)).slice(0,5);
    }
    result.passes.push(pass);fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(result,null,2));
    delete result.currentPass;
    console.log(JSON.stringify({host,effects,iteration:iteration+1,phases:pass.phases,longTasks:pass.longTasks.length,scrollEvents:pass.scrollEvents}));
  }
  result.completed=true;
  delete result.activeStep;
  await page.screenshot({path:path.join(output,'workspace.png')});
  const windowFrame=logs.join('').split('\n').map(line=>{try{return JSON.parse(line);}catch{return null;}}).find(frame=>frame?.type==='window');
  if(windowFrame)try{execFileSync(python,[path.join(ROOT,'scripts/capture_window_preview.py'),windowFrame.handle,path.join(output,'native-window.png')]);}catch(error){result.nativeScreenshotError=String(error);}
} catch(error){result.failure=error.stack||String(error);process.exitCode=1;}
finally {
  wake.stdin.end();
  child.stdin.end();
  try{if(host==='electron'&&page)await page.close();}catch{}
  try{cdp?.close();browser?.close();}catch{}
  if(child.exitCode===null){await sleep(1000);if(child.exitCode===null)child.kill();}
  fs.writeFileSync(path.join(output,'runtime.log'),logs.join(''));
  fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(result,null,2));
  if(result.failure)console.error(result.failure);
}
