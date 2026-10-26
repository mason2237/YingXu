// Public evidence contains summarized measurements, no local paths or sessions.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {gunzipSync} from 'node:zlib';

const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const base=path.join(ROOT,'work/test-results/architecture-a-fixed60');
const range=values=>({min:Math.min(...values),max:Math.max(...values)});
const round=value=>Math.round(value*100)/100;
const median=values=>[...values].sort((a,b)=>a-b)[Math.floor(values.length/2)];
const summary={date:'2026-10-26',stage:'20A',baseline:'228773c95e8ab9c1c786354ad0d8b026f11826f0',
  electron:'45.0.0',protocol:1,viewport:{width:1280,height:860,scale:1},display:{width:2560,height:1440,refreshHz:180,systemHdr:true,sdrWhiteNits:240},
  workload:{videos:300,subtitles:300,inputHz:60,repeats:3,secondsPerRepeat:30,phases:['hover','drag','scroll']},variants:[],
  warnings:['rAF measures page updates, not physical display rate.','Chromium DrawAndSwap measures intermediate composition, not independently verified scanout.',
    'CDP-reported Chromium process footprint excludes a separate Python child in Electron; it is not whole-app memory.',
    'Recorded startup points differ: Qt includes initial fixture scanning; Electron is measured before folder selection. Do not compare them as cold-start speed.',
    'No GPU utilization percentage was measured. PresentMon ETW access was denied.'],
  migrationGate:{passed:false,reason:'Independent Windows presentation-rate cross-check is unavailable: PresentMon ETW access denied. HDR output itself was verified.'},
  mediaModified:false,osPreferencesChanged:false,physicalPeakMeasured:false};
for(const host of ['qt','electron'])for(const effects of ['full','moderate']) {
  const directory=path.join(host==='electron'?path.join(ROOT,'work/test-results/architecture-a-visible'):base,`${host}-${effects}`),record=JSON.parse(fs.readFileSync(path.join(directory,'result.json'),'utf8'));
  if(!record.completed||record.passes.length!==3)throw Error(`Incomplete measurements: ${host}-${effects}`);
  if(host==='electron'&&!record.nativeWindowVisible)throw Error('Refusing hidden-window Electron results');
  const item={host,effects,phases:{},longTasks:record.passes.reduce((sum,pass)=>sum+pass.longTasks.length,0),
    chromiumCpuSecondsPer30s:record.passes.map(pass=>round(pass.chromiumCpuSeconds)),
    chromiumWorkingSetMiB:record.passes.map(pass=>round(pass.processMemory.workingSetBytes/1048576)),
    chromiumPrivateMiB:record.passes.map(pass=>round(pass.processMemory.privateBytes/1048576)),
    observedReadyMs:record.startupMs};
  for(const phase of ['hover','drag','scroll']) {
    const values=record.passes.map(pass=>pass.phases[phase]);
    item.phases[phase]={rafFps:range(values.map(value=>value.raf.fps)),p95MsMax:Math.max(...values.map(value=>value.raf.p95Ms)),
      over25PercentMax:Math.max(...values.map(value=>value.raf.over25Percent)),inputEvents:range(values.map(value=>value.events))};
  }
  const events=JSON.parse(gunzipSync(fs.readFileSync(path.join(directory,'trace.json.gz')))).traceEvents;
  const tracks=new Map();
  for(const event of events)if(event.name==='Display::DrawAndSwap'&&['X','B'].includes(event.ph)) {
    const key=`${event.pid}:${event.tid}`;if(!tracks.has(key))tracks.set(key,[]);tracks.get(key).push(event.ts);
  }
  const times=[...tracks.values()].sort((a,b)=>b.length-a.length)[0]||[];
  times.sort((a,b)=>a-b);const gaps=times.slice(1).map((time,index)=>(time-times[index])/1000).filter(value=>value>0);
  if(gaps.length) {const sorted=[...gaps].sort((a,b)=>a-b);item.chromiumDrawAndSwap={count:times.length,rateHz:round(1000/(gaps.reduce((a,b)=>a+b,0)/gaps.length)),
    p95Ms:round(sorted[Math.floor(sorted.length*.95)]),medianMs:round(median(gaps)),independentPresentationVerified:false};}
  summary.variants.push(item);
}
const capturePath=path.join(ROOT,'work/test-results/electron-a-full-capture/result.json');
if(fs.existsSync(capturePath)) {const capture=JSON.parse(fs.readFileSync(capturePath,'utf8'));summary.hdr={configured:capture.hdr?.hdrConfigured===true,
  actualOutputVerified:capture.hdrCapture?.verified===true,method:capture.hdrCapture?.method,
  samples:capture.hdrCapture?.linearScRgbSamples||[],abovePaperWhiteRatio:capture.hdrCapture?.abovePaperWhiteRatio};}
fs.writeFileSync(path.join(ROOT,'docs/evidence/stage20a-electron.json'),JSON.stringify(summary,null,2)+'\n');
console.log(JSON.stringify({variants:summary.variants.map(item=>({host:item.host,effects:item.effects,scrollHz:item.phases.scroll.rafFps,
  hoverHz:item.phases.hover.rafFps,drawAndSwapHz:item.chromiumDrawAndSwap?.rateHz})),hdr:summary.hdr,migrationGate:summary.migrationGate},null,2));
