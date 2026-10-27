// Actual multilingual containers -> scanner -> bounded IPC -> visible inspector.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import net from 'node:net';
import {createHash} from 'node:crypto';
import {spawn,spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {CdpClient} from './cdp_client.mjs';

const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const output=path.join(ROOT,`work/test-results/multitrack-${Date.now()}`),media=path.join(output,'media');
fs.mkdirSync(media,{recursive:true});
const python=path.join(ROOT,'.venv-core/Scripts/python.exe');
const generated=spawnSync(python,['-S','-c',`from pathlib import Path
import sys
from tests.media_fixtures import mkv
folder=Path(sys.argv[1])
for index in range(1,11):
 tracks=[('zho',f'简体中文 完整字幕 {n} '+('轨道标题🙂'*40),False) for n in range(1,(32 if index==1 else 64)+1)]
 mkv(folder/f'Sample.Show.S02E{index:02}.1080p.NF.WEB-DL.mkv',tracks)
`,media],{cwd:ROOT,encoding:'utf8',windowsHide:true});
assert.equal(generated.status,0,generated.stderr);
const snapshot=()=>Object.fromEntries(fs.readdirSync(media).map(name=>[name,createHash('sha256').update(fs.readFileSync(path.join(media,name))).digest('hex')]));
const before=snapshot(),sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function until(check,timeout=30000){const end=Date.now()+timeout;let last;while(Date.now()<end){try{const value=await check();if(value)return value;}catch(error){last=error;}await sleep(70);}throw Error('Multitrack condition timeout'+(last?': '+last.message:''));}
let child,page,browser,logs='',errors='';const exceptions=[];
try {
  const port=await new Promise(resolve=>{const server=net.createServer();server.listen(0,'127.0.0.1',()=>{const port=server.address().port;server.close(()=>resolve(port));});});
  const executable=process.argv[2],env={...process.env,YINGXU_PYTHON:python};delete env.ELECTRON_RUN_AS_NODE;
  child=spawn(executable||path.join(ROOT,'work/tools/electron-45.0.0/electron.exe'),[...(executable?[]:[path.join(ROOT,'desktop/electron')]),
    '--diagnostics',`--profile=${path.join(output,'profile')}`,`--test-folder=${media}`,`--remote-debugging-port=${port}`,'--remote-debugging-address=127.0.0.1'],{cwd:ROOT,env,windowsHide:false,stdio:['ignore','pipe','pipe']});
  child.stdout.on('data',v=>{logs+=v;});child.stderr.on('data',v=>{errors+=v;});
  const target=await until(async()=>(await fetch(`http://127.0.0.1:${port}/json/list`).then(r=>r.json())).find(t=>t.url==='yingxu://app/workspace.html'));
  page=await CdpClient.open(target.webSocketDebuggerUrl);
  const evaluate=async expression=>{const r=await page.send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;};
  page.on('Runtime.exceptionThrown',value=>exceptions.push(value));await page.send('Runtime.enable');await page.send('Page.enable');
  await until(()=>evaluate("document.documentElement.dataset.ready==='true'"));
  await evaluate(`window.__detailWire={maximum:0,trackPages:0};yingxuHost.workspace.onReply(raw=>{
    const p=JSON.parse(raw);__detailWire.maximum=Math.max(__detailWire.maximum,new TextEncoder().encode(raw).byteLength);
    if(p.data?.section==='tracks')__detailWire.trackPages++;
  });document.getElementById('dataset-button').click();true`);
  await until(()=>evaluate("document.querySelector('#count-all').textContent==='10'&&document.querySelectorAll('.embedded-track').length===32"));
  assert.equal(await evaluate("document.querySelector('#file-list').hidden||!document.querySelector('#empty-state').hidden"),false);
  assert.equal(await evaluate("document.querySelector('#preview-button').disabled"),true);
  await evaluate(`(async()=>{
    const {LocalAdapter}=await import('./js/local-adapter.js');window.__originalDetailStart=LocalAdapter.prototype.start;
    window.__failDetailRow='video-2';LocalAdapter.prototype.start=function(action,params={}){
      if(action==='review.detailPage'&&params.rowId===window.__failDetailRow)return Promise.reject(Error('测试用的详情读取失败'));
      return window.__originalDetailStart.call(this,action,params);
    };document.querySelector('[data-row-id="video-2"]').click();
  })()`);
  const retry="[...document.querySelectorAll('#inspector-content button')].find(b=>b.textContent.includes('重试详情'))";
  await until(()=>evaluate(`Boolean(${retry})`));
  assert.equal(await evaluate("!document.querySelector('#file-list').hidden&&document.querySelector('#empty-state').hidden&&document.querySelectorAll('#list-items [data-row-id]').length===10"),true);
  assert.equal(await evaluate("document.querySelector('#footer-status').textContent.includes('扫描结果已保留')"),true);
  let shot=await page.send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(output,'detail-retry.png'),Buffer.from(shot.data,'base64'));
  await evaluate("document.querySelector('[data-row-id=\"video-3\"]').click();true");
  await until(()=>evaluate("document.querySelectorAll('.embedded-track').length===64"));
  await evaluate("document.querySelector('[data-row-id=\"video-2\"]').click();true");await until(()=>evaluate(`Boolean(${retry})`));
  await evaluate(`window.__failDetailRow=null;(${retry}).click();true`);
  await until(()=>evaluate("document.querySelectorAll('.embedded-track').length===64"));
  assert.equal(await evaluate("document.documentElement.scrollWidth<=innerWidth+1"),true);
  const wire=await evaluate('window.__detailWire');assert.ok(wire.maximum<=8192);assert.ok(wire.trackPages>4);
  await evaluate("import('./js/local-adapter.js').then(m=>{m.LocalAdapter.prototype.start=window.__originalDetailStart;})");
  shot=await page.send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(output,'multitrack-workspace.png'),Buffer.from(shot.data,'base64'));
  const navigated=new Promise(resolve=>page.once('Page.frameNavigated',resolve));await page.send('Page.reload');await navigated;
  await until(()=>evaluate("document.documentElement.dataset.ready==='true'&&document.querySelectorAll('.embedded-track').length===32&&document.querySelector('#count-all').textContent==='10'"));
  assert.equal(await evaluate("document.querySelector('#overview').textContent.includes('10个内嵌已满足')"),true);
  assert.deepEqual(snapshot(),before);assert.equal(exceptions.length,0,JSON.stringify(exceptions));
  const info=await fetch(`http://127.0.0.1:${port}/json/version`).then(r=>r.json());browser=await CdpClient.open(info.webSocketDebuggerUrl);
  await browser.send('Browser.close').catch(()=>{});await until(()=>child.exitCode!==null);assert.equal(child.exitCode,0);
  const report={passed:true,mode:executable?'frozen':'source',videos:10,actualGeneratedContainers:true,trackCounts:[32,64],
    allTrackCardsRendered:true,detailFailureKeepsList:true,otherVideoSelectable:true,retry:true,reloadDraft:true,
    embeddedLanguageSatisfiedWithoutExport:true,maxReplyBytes:wire.maximum,trackPages:wire.trackPages,
    mediaUnchanged:true,jsExceptions:0,websiteVisited:false,exitCode:0,output:path.relative(ROOT,output)};
  fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
} catch(error){
  process.exitCode=1;console.error(error.stack);fs.writeFileSync(path.join(output,'failure.json'),JSON.stringify({error:error.stack,exceptions},null,2));
} finally {
  fs.writeFileSync(path.join(output,'runtime.log'),logs+'\n'+errors);page?.close();browser?.close();if(child?.exitCode===null)child.kill();
}
