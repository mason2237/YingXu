// YX-02 real UI: purpose variants, replacement and draft reload; generated files only.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import net from 'node:net';
import {spawn} from 'node:child_process';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {CdpClient} from './cdp_client.mjs';

const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const executable=process.argv[2];
const output=path.join(ROOT,`work/test-results/release-model-${Date.now()}`),media=path.join(output,'media');
fs.mkdirSync(media,{recursive:true});
fs.writeFileSync(path.join(media,'The.Movie.2024.S01E01.1080p.WEB-DL-GROUP.mkv'),'generated unchanged video');
for(const tag of ['en','en.forced','en.sdh','chs','cht'])fs.writeFileSync(path.join(media,`The.Movie.2024.S01E01.${tag}.srt`),'1\n00:00:01,000 --> 00:00:02,000\nGenerated dialogue\n');
const alternate='The.Movie.2024.S01E01.AlternateGroup.eng.srt';
fs.writeFileSync(path.join(media,alternate),'1\n00:00:01,000 --> 00:00:02,000\nAlternative generated dialogue\n');
const snapshot=()=>Object.fromEntries(fs.readdirSync(media).map(name=>[name,createHash('sha256').update(fs.readFileSync(path.join(media,name))).digest('hex')]));
const before=snapshot(),sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function until(check){let error;for(let i=0;i<400;i++){try{const v=await check();if(v)return v;}catch(e){error=e;}await sleep(70);}throw Error('Release UI condition timed out '+(error?.message||''));}
let child,page,browser,logs='';const exceptions=[];
try{
  const port=await new Promise(resolve=>{const server=net.createServer();server.listen(0,'127.0.0.1',()=>{const p=server.address().port;server.close(()=>resolve(p));});});
  const env={...process.env,YINGXU_PYTHON:path.join(ROOT,'.venv-core/Scripts/python.exe')};delete env.ELECTRON_RUN_AS_NODE;
  if(executable)delete env.YINGXU_PYTHON;
  child=spawn(executable||path.join(ROOT,'work/tools/electron-45.0.0/electron.exe'),[...(executable?[]:[path.join(ROOT,'desktop/electron')]),'--diagnostics',
    `--profile=${path.join(output,'profile')}`,`--test-folder=${media}`,`--remote-debugging-port=${port}`,'--remote-debugging-address=127.0.0.1'],
    {cwd:ROOT,env,windowsHide:false,stdio:['ignore','pipe','pipe']});
  child.stdout.on('data',v=>logs+=v);child.stderr.on('data',v=>logs+=v);
  const target=await until(async()=>(await fetch(`http://127.0.0.1:${port}/json/list`).then(r=>r.json())).find(v=>v.url==='yingxu://app/workspace.html'));
  page=await CdpClient.open(target.webSocketDebuggerUrl);await page.send('Runtime.enable');
  page.on('Runtime.exceptionThrown',e=>exceptions.push(e));
  const evaluate=async expression=>{const r=await page.send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;};
  await until(()=>evaluate("document.documentElement.dataset.ready==='true'"));
  await evaluate(`(async()=>{window.__ask=(sessionId,action,params={})=>new Promise((resolve,reject)=>{
    const requestId=crypto.randomUUID(),host=yingxuHost.workspace;let stop;
    const timer=setTimeout(()=>{stop?.();reject(Error('Check timeout'));},15000);
    stop=host.onReply(raw=>{const r=JSON.parse(raw);if(r.requestId===requestId){clearTimeout(timer);stop();resolve(r);}});
    host.request(JSON.stringify({v:2,requestId,sessionId,action,params})).catch(reject);
  });window.__sid=(await __ask(null,'app.state')).sessionId;
  window.__call=async(action,params={})=>{const r=await __ask(__sid,action,params);if(!r.ok)throw Error(JSON.stringify(r.error));return r.data;};
  await __call('embedded.configure',{enabled:false,language:'chinese'});document.getElementById('dataset-button').click();return true;})()`);
  await until(()=>evaluate("document.querySelectorAll('.subtitle-detail:not(.embedded-track)').length===5"));
  const text=await evaluate("document.querySelector('#inspector-content').textContent");
  for(const label of ['强制/片段','SDH','名称识别','The Movie','WEB-DL'])assert.ok(text.includes(label),label);
  const languageLabels=await evaluate("[...document.querySelectorAll('#inspector-content .language')].map(n=>n.getAttribute('aria-label'))");
  for(const label of ['简体中文','繁体中文'])assert.ok(languageLabels.includes(label),label);
  await evaluate("[...document.querySelectorAll('#inspector-content button')].find(b=>b.textContent==='选择字幕').click();true");
  const chosen=await until(()=>evaluate(`(()=>{const card=[...document.querySelectorAll('#candidate-list .candidate-card')].find(c=>/\\.(?:en|eng)\\.srt$/.test(c.querySelector('h3')?.textContent)&&!c.querySelector('button')?.disabled);const b=card?.querySelector('button');return b&&{label:b.textContent,name:card.querySelector('h3').textContent};})()`));
  assert.equal(chosen.label,'替换相同语言与用途');
  await evaluate(`(()=>{const card=[...document.querySelectorAll('#candidate-list .candidate-card')].find(c=>c.querySelector('h3')?.textContent===${JSON.stringify(chosen.name)});card.querySelector('button').click();})()`);
  await until(()=>evaluate(`document.querySelectorAll('.subtitle-detail:not(.embedded-track)').length===5&&document.querySelector('#inspector-content').textContent.includes(${JSON.stringify(chosen.name)})`));
  const state=await evaluate("__call('app.state')"),context={scanId:state.summary.scanId,revision:state.summary.revision,rowId:'video-1'};
  const pageOfSubs=await evaluate(`__call('review.detailPage',{...${JSON.stringify(context)},section:'subtitles'})`);
  const subs=pageOfSubs.entries;
  assert.equal(subs.length,5);assert.equal(new Set(subs.map(v=>v.variantKey)).size,5);
  assert.ok(subs.some(s=>s.targetName.endsWith('.en.forced.srt')));assert.ok(subs.some(s=>s.targetName.endsWith('.en.sdh.srt')));
  assert.ok(subs.find(s=>s.name===chosen.name)?.manual);
  await evaluate(`(()=>{const panel=document.getElementById('inspector-content');const item=[...panel.querySelectorAll('.subtitle-detail')].find(n=>n.textContent.includes('强制/片段'));if(item)panel.scrollTop+=item.getBoundingClientRect().top-panel.getBoundingClientRect().top-12;})()`);
  await page.send('Page.enable');const shot=await page.send('Page.captureScreenshot',{format:'png'});
  fs.writeFileSync(path.join(output,'variants.png'),Buffer.from(shot.data,'base64'));
  await page.send('Page.reload');
  await until(()=>evaluate(`document.documentElement.dataset.ready==='true'&&document.querySelectorAll('.subtitle-detail:not(.embedded-track)').length===5&&document.querySelector('#inspector-content').textContent.includes(${JSON.stringify(chosen.name)})`));
  assert.deepEqual(snapshot(),before);assert.equal(exceptions.length,0,JSON.stringify(exceptions));
  const info=await fetch(`http://127.0.0.1:${port}/json/version`).then(r=>r.json());browser=await CdpClient.open(info.webSocketDebuggerUrl);
  await browser.send('Browser.close').catch(()=>{});await until(()=>child.exitCode!==null);assert.equal(child.exitCode,0);
  const report={passed:true,variants:5,purposeLabels:true,advisoryIdentity:true,correctVariantReplaced:true,
    forcedAndSDHRetained:true,reloadDraft:true,mediaUnchanged:true,jsExceptions:0,websiteVisited:false,
    mode:executable?'frozen':'source',executablePackaged:Boolean(executable),exitCode:0,output:path.relative(ROOT,output)};
  fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}catch(error){process.exitCode=1;console.error(error.stack);fs.writeFileSync(path.join(output,'failure.json'),JSON.stringify({error:error.stack,exceptions},null,2));}
finally{page?.close();browser?.close();if(child?.exitCode===null)child.kill();fs.writeFileSync(path.join(output,'runtime.log'),logs);}
