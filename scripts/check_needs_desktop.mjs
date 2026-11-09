// Generated samples only: real source window and real Python, no sites or media writes.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import net from 'node:net';
import {spawn,spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {CdpClient} from './cdp_client.mjs';

const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),executable=process.argv[2];
const output=path.join(ROOT,`work/test-results/needs-desktop-${Date.now()}`),media=path.join(output,'media');
fs.mkdirSync(path.join(media,'candidates'),{recursive:true});
const good='1\n00:00:01,000 --> 00:00:03,000\nGenerated text\n',bad=good.replace('01,000 --> 00:00:03','03,000 --> 00:00:01');
for(const title of ['Film','Good','Other'])fs.writeFileSync(path.join(media,`${title}.2024.mkv`),'generated video');
fs.writeFileSync(path.join(media,'Film.2024.en.srt'),bad);fs.writeFileSync(path.join(media,'candidates/Film.2024.en.srt'),good);
fs.writeFileSync(path.join(media,'Good.2024.en.srt'),good);fs.writeFileSync(path.join(media,'Other.2024.en.forced.srt'),good);
const snapshot=()=>Object.fromEntries(fs.readdirSync(media,{recursive:true}).filter(n=>fs.statSync(path.join(media,n)).isFile()).map(n=>[n,createHash('sha256').update(fs.readFileSync(path.join(media,n))).digest('hex')]));
const before=snapshot(),sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function until(check){let error;for(let i=0;i<450;i++){try{const value=await check();if(value)return value;}catch(e){error=e;}await sleep(60);}throw Error('Needs UI timeout '+(error?.message||''));}
let child,page,browser,logs='';const exceptions=[];
try{
  const port=await new Promise(resolve=>{const server=net.createServer();server.listen(0,'127.0.0.1',()=>{const p=server.address().port;server.close(()=>resolve(p));});});
  const env={...process.env,YINGXU_PYTHON:path.join(ROOT,'.venv-core/Scripts/python.exe')};delete env.ELECTRON_RUN_AS_NODE;if(executable)delete env.YINGXU_PYTHON;
  child=spawn(executable||path.join(ROOT,'work/tools/electron-45.0.0/electron.exe'),[...(executable?[]:[path.join(ROOT,'desktop/electron')]),'--diagnostics',`--profile=${path.join(output,'profile')}`,`--test-folder=${media}`,`--remote-debugging-port=${port}`,'--remote-debugging-address=127.0.0.1'],{cwd:ROOT,env,windowsHide:false,stdio:['ignore','pipe','pipe']});
  child.stdout.on('data',v=>logs+=v);child.stderr.on('data',v=>logs+=v);
  const target=await until(async()=>(await fetch(`http://127.0.0.1:${port}/json/list`).then(r=>r.json())).find(v=>v.url==='yingxu://app/workspace.html'));
  page=await CdpClient.open(target.webSocketDebuggerUrl);await page.send('Runtime.enable');page.on('Runtime.exceptionThrown',e=>exceptions.push(e));
  const evaluate=async expression=>{const r=await page.send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;};
  await until(()=>evaluate("document.documentElement.dataset.ready==='true'"));
  await evaluate(`(async()=>{window.__wireMax=0;yingxuHost.workspace.onReply(raw=>{__wireMax=Math.max(__wireMax,new TextEncoder().encode(raw).byteLength);});
    window.__ask=(sessionId,action,params={})=>new Promise((resolve,reject)=>{const requestId=crypto.randomUUID(),host=yingxuHost.workspace;let stop;const timer=setTimeout(()=>{stop?.();reject(Error('Check timeout'));},15000);
      stop=host.onReply(raw=>{const r=JSON.parse(raw);if(r.requestId===requestId){clearTimeout(timer);stop();resolve(r);}});host.request(JSON.stringify({v:2,requestId,sessionId,action,params})).catch(reject);});
    window.__sid=(await __ask(null,'app.state')).sessionId;window.__call=async(action,params={})=>{const r=await __ask(__sid,action,params);if(!r.ok)throw Error(JSON.stringify(r.error));return r.data;};
    await __call('requirements.configure',{languages:['english'],allowSDH:false,includeForced:false});await __call('embedded.configure',{enabled:false,language:'chinese'});document.getElementById('dataset-button').click();return true;})()`);
  await until(()=>evaluate("document.querySelectorAll('#list-items [data-row-id]').length===3"));
  await until(()=>evaluate("document.getElementById('subtitle-needs-button').disabled===false"));
  await evaluate("document.getElementById('subtitle-needs-button').click();true");
  await until(()=>evaluate("document.getElementById('needs-dialog').open&&!document.getElementById('needs-check').disabled"));
  assert.equal(await evaluate("document.querySelector('[name=needs-language][value=english]').checked"),true);
  await evaluate("document.getElementById('needs-check').click();true");
  await until(()=>evaluate("document.querySelectorAll('#needs-rows .needs-row').length===3&&!document.getElementById('needs-check').disabled"));
  assert.ok(await evaluate("document.getElementById('needs-status').textContent.includes('1 个已满足')"));
  assert.ok(await evaluate("document.getElementById('needs-rows').textContent.includes('片段字幕')"));
  assert.equal(await evaluate("document.querySelector('#needs-rows [data-stage]').disabled"),true);
  assert.equal(await evaluate("document.querySelector('#needs-dialog').scrollWidth<=document.querySelector('#needs-dialog').clientWidth+1"),true);
  const native=JSON.parse(logs.split('\n').find(line=>line.includes('"type":"window"')));
  const resize=(width,height)=>{const result=spawnSync(path.join(ROOT,'.venv-core/Scripts/python.exe'),[path.join(ROOT,'scripts/check_window_bounds.py'),native.handle,String(child.pid),'resize','--width',String(width),'--height',String(height)],{encoding:'utf8',windowsHide:true});assert.equal(result.status,0,result.stderr);};
  resize(1000,760);
  await until(()=>evaluate("innerWidth<=1000"));
  assert.equal(await evaluate("document.querySelector('#needs-dialog').scrollWidth<=document.querySelector('#needs-dialog').clientWidth+1&&document.documentElement.scrollWidth<=innerWidth+1"),true);
  resize(1280,860);
  await until(()=>evaluate("innerWidth>=1200"));
  // Only label the generated fixture's displayed folder; never change business paths.
  await evaluate("document.getElementById('folder-path').textContent='生成的本地测试样本';document.getElementById('needs-dialog').scrollTop=0;");
  await page.send('Page.enable');const shot=await page.send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(output,'needs.png'),Buffer.from(shot.data,'base64'));
  await evaluate("document.querySelector('#needs-rows .needs-upgrade input').click();true");
  await until(()=>evaluate("document.querySelector('#needs-rows [data-stage]').disabled===false"));
  await evaluate("document.querySelector('#needs-rows [data-stage]').click();true");
  await until(()=>evaluate("!document.getElementById('needs-dialog').open&&document.getElementById('inspector-content').textContent.includes('保留原字幕')"));
  assert.ok(await evaluate("document.getElementById('inspector-content').textContent.includes('Film.2024_1.en.srt')"));
  assert.deepEqual(snapshot(),before);
  const reviewShot=await page.send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(output,'upgrade-review.png'),Buffer.from(reviewShot.data,'base64'));
  const maxReplyBytes=await evaluate('__wireMax');assert.ok(maxReplyBytes<=8192);assert.equal(exceptions.length,0,JSON.stringify(exceptions));
  const info=await fetch(`http://127.0.0.1:${port}/json/version`).then(r=>r.json());browser=await CdpClient.open(info.webSocketDebuggerUrl);
  await browser.send('Browser.close').catch(()=>{});await until(()=>child.exitCode!==null);assert.equal(child.exitCode,0);
  const report={passed:true,mode:executable?'frozen':'source',policyPreference:true,missingAndSatisfiedStates:true,forcedIsNotFull:true,
    boundedLayout:true,smallWindow1000x760:true,upgradeRequiresAcknowledgement:true,stagedReviewKeepsOriginal:true,separateTargetName:true,
    mediaUnchanged:true,maxReplyBytes,jsExceptions:0,websiteVisited:false,exitCode:0,output:path.relative(ROOT,output)};
  fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}catch(error){process.exitCode=1;console.error(error.stack);fs.writeFileSync(path.join(output,'failure.json'),JSON.stringify({error:error.stack,exceptions},null,2));}
finally{page?.close();browser?.close();if(child?.exitCode===null)child.kill();fs.writeFileSync(path.join(output,'runtime.log'),logs);}
