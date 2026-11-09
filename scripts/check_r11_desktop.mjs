// End-to-end visible feature smoke; optional real packaged EXE. Generated samples only.
import assert from 'node:assert/strict';
import fs from 'node:fs';import path from 'node:path';import net from 'node:net';
import {spawn,spawnSync} from 'node:child_process';import {createHash} from 'node:crypto';import {fileURLToPath} from 'node:url';
import {CdpClient} from './cdp_client.mjs';
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),executable=process.argv[2];
const output=path.join(ROOT,`work/test-results/r11-desktop-${Date.now()}`),media=path.join(output,'media');fs.mkdirSync(media,{recursive:true});
const generate=spawnSync(path.join(ROOT,'.venv-core/Scripts/python.exe'),['-S','-c',`from pathlib import Path
import sys,random
from tests.unit.test_content_matching import document
from yingxu.domain.sync_models import transform,stamp
r=Path(sys.argv[1]);rng=random.Random(44);position=15000;parts=[]
for i,c in enumerate(document().cues):
 position+=rng.randint(2000,7000);duration=rng.randint(2000,3500)
 parts.append(f'{i+1}\\n{stamp(position,"srt","00:00:00,000")} --> {stamp(position+duration,"srt","00:00:00,000")}\\n{c.text}\\n');position+=duration
text='\\n'.join(parts)
(r/'Film.2024.mkv').write_bytes(b'\\0'*(128*1024))
(r/'Film.2024.en.srt').write_text(transform(text,'srt',2500),encoding='utf8')
(r/'Reference.en.srt').write_text(text,encoding='utf8')
(r/'Film.2024.nfo').write_text('<movie><uniqueid type="imdb">tt1234567</uniqueid></movie>',encoding='utf8')
`,media],{cwd:ROOT,encoding:'utf8',windowsHide:true});assert.equal(generate.status,0,generate.stderr);
const snapshot=()=>Object.fromEntries(fs.readdirSync(media).map(n=>[n,createHash('sha256').update(fs.readFileSync(path.join(media,n))).digest('hex')])),before=snapshot();
const sleep=ms=>new Promise(r=>setTimeout(r,ms));async function until(fn){let error;for(let i=0;i<500;i++){try{const value=await fn();if(value)return value;}catch(e){error=e;}await sleep(60);}throw Error('R11 UI timeout '+(error?.message||''));}
let child,page,browser,logs='';const exceptions=[];
try{
 const port=await new Promise(resolve=>{const server=net.createServer();server.listen(0,'127.0.0.1',()=>{const p=server.address().port;server.close(()=>resolve(p));});});
 const env={...process.env,YINGXU_PYTHON:path.join(ROOT,'.venv-core/Scripts/python.exe')};delete env.ELECTRON_RUN_AS_NODE;if(executable)delete env.YINGXU_PYTHON;
 child=spawn(executable||path.join(ROOT,'work/tools/electron-45.0.0/electron.exe'),[...(executable?[]:[path.join(ROOT,'desktop/electron')]),'--diagnostics',`--profile=${path.join(output,'profile')}`,`--test-folder=${media}`,`--remote-debugging-port=${port}`,'--remote-debugging-address=127.0.0.1'],{cwd:ROOT,env,windowsHide:false,stdio:['ignore','pipe','pipe']});
 child.stdout.on('data',v=>logs+=v);child.stderr.on('data',v=>logs+=v);
 const target=await until(async()=>(await fetch(`http://127.0.0.1:${port}/json/list`).then(r=>r.json())).find(t=>t.url==='yingxu://app/workspace.html'));
 page=await CdpClient.open(target.webSocketDebuggerUrl);await page.send('Runtime.enable');page.on('Runtime.exceptionThrown',e=>exceptions.push(e));
 const evaluate=async expression=>{const r=await page.send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;};
 await until(()=>evaluate("document.documentElement.dataset.ready==='true'"));
 await evaluate(`(async()=>{window.__wireMax=0;yingxuHost.workspace.onReply(raw=>{__wireMax=Math.max(__wireMax,new TextEncoder().encode(raw).byteLength);});window.__ask=(sessionId,action,params={})=>new Promise((resolve,reject)=>{const requestId=crypto.randomUUID(),host=yingxuHost.workspace;let stop;const timer=setTimeout(()=>{stop?.();reject(Error('Timeout'));},15000);stop=host.onReply(raw=>{const r=JSON.parse(raw);if(r.requestId===requestId){clearTimeout(timer);stop();resolve(r);}});host.request(JSON.stringify({v:2,requestId,sessionId,action,params})).catch(reject);});window.__sid=(await __ask(null,'app.state')).sessionId;window.__call=async(action,params={})=>{const r=await __ask(__sid,action,params);if(!r.ok)throw Error(JSON.stringify(r.error));return r.data;};await __call('embedded.configure',{enabled:false,language:'chinese'});document.getElementById('dataset-button').click();return true;})()`);
 await until(()=>evaluate("document.querySelectorAll('.subtitle-detail:not(.embedded-track)').length===1"));
 await evaluate("[...document.querySelectorAll('#inspector-content details')].find(d=>d.querySelector('summary')?.textContent==='增强识别').open=true;[...document.querySelectorAll('#inspector-content button')].find(b=>b.textContent==='读取本地识别信息').click();true");
 await until(()=>evaluate("document.getElementById('inspector-content').textContent.includes('tt1234567')"));
 // Quality redraw must leave the separate timing panel intact.
 await evaluate("document.querySelector('.quality-report button').click();true");
 await until(()=>evaluate("document.querySelector('.quality-summary')&&document.querySelector('.subtitle-sync')"));
 await evaluate("document.querySelector('.subtitle-sync').open=true;document.querySelector('.subtitle-sync input[type=number]').value='1500';[...document.querySelectorAll('.subtitle-sync button')].find(b=>b.textContent==='生成时间预览').click();true");
 await until(()=>evaluate("document.querySelector('.sync-result').textContent.includes('+1500 毫秒')"));
 const shot=async name=>{await evaluate("(()=>{document.getElementById('folder-path').textContent='本地生成的测试样本';const container=document.getElementById('inspector-content'),result=document.querySelector('.sync-result');container.scrollTop+=result.getBoundingClientRect().top-container.getBoundingClientRect().top-16;})()");const r=await page.send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(output,name),Buffer.from(r.data,'base64'));};await page.send('Page.enable');
 await evaluate("document.getElementById('folder-path').textContent='本地生成的测试样本';const panel=document.getElementById('inspector-content'),item=document.querySelector('.subtitle-sync');panel.scrollTop+=item.getBoundingClientRect().top-panel.getBoundingClientRect().top-12;");await shot('timing-preview.png');
 await evaluate("(()=>{const select=document.querySelector('.subtitle-sync > select');select.value='reference';select.dispatchEvent(new Event('change'));})()");
 await until(()=>evaluate("document.querySelector('[aria-label=\"可信本地参考字幕\"] option[value]:not([value=\"\"])')&&![...document.querySelectorAll('.subtitle-sync button')].find(b=>b.textContent==='生成时间预览').disabled"));
 await evaluate("(()=>{const select=document.querySelector('[aria-label=\"可信本地参考字幕\"]');select.value=[...select.options].find(o=>o.textContent==='Reference.en.srt').value;[...document.querySelectorAll('.subtitle-sync button')].find(b=>b.textContent==='生成时间预览').click();})()");
 await until(()=>evaluate("document.querySelector('.sync-result').textContent.includes('ffsubsync-0.5.1')"));
 await evaluate("[...document.querySelectorAll('.subtitle-sync button')].find(b=>b.textContent==='比较参考字幕的文本').click();true");
 await until(()=>evaluate("document.querySelector('.sync-result').textContent.includes('文本相似度 100%')"));await shot('content-evidence.png');
 // Recreate a manual candidate and explicitly stage it, without executing.
 await evaluate("(()=>{const select=document.querySelector('.subtitle-sync > select');select.value='manual';select.dispatchEvent(new Event('change'));})()");
 await until(()=>evaluate("!document.querySelector('.subtitle-sync input[type=number]').hidden&&![...document.querySelectorAll('.subtitle-sync button')].find(b=>b.textContent==='生成时间预览').disabled"));
 await evaluate("document.querySelector('.subtitle-sync input[type=number]').value='1500';[...document.querySelectorAll('.subtitle-sync button')].find(b=>b.textContent==='生成时间预览').click();true");
 await until(()=>evaluate("document.querySelector('.sync-result label input')"));
 await evaluate("document.querySelector('.sync-result label input').click();[...document.querySelectorAll('.sync-result button')].find(b=>b.textContent==='加入审阅').click();true");
 await until(()=>evaluate("document.getElementById('inspector-content').textContent.includes('保留原字幕')&&document.getElementById('inspector-content').textContent.includes('人工指定')"));
 assert.deepEqual(snapshot(),before);assert.equal(exceptions.length,0,JSON.stringify(exceptions));const maxReplyBytes=await evaluate('__wireMax');assert.ok(maxReplyBytes<=8192);
 const info=await fetch(`http://127.0.0.1:${port}/json/version`).then(r=>r.json());browser=await CdpClient.open(info.webSocketDebuggerUrl);await browser.send('Browser.close').catch(()=>{});await until(()=>child.exitCode!==null);assert.equal(child.exitCode,0);
 const report={passed:true,mode:executable?'frozen':'source',nfoUI:true,qualityPreservesTimingPanel:true,manualPreview:true,realReferenceEngine:true,contentEvidence:true,explicitStage:true,mediaUnchanged:true,maxReplyBytes,jsExceptions:0,websiteVisited:false,exitCode:0,output:path.relative(ROOT,output)};
 fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}catch(error){process.exitCode=1;console.error(error.stack);fs.writeFileSync(path.join(output,'failure.json'),JSON.stringify({error:error.stack,exceptions},null,2));}
finally{page?.close();browser?.close();if(child?.exitCode===null)child.kill();fs.writeFileSync(path.join(output,'runtime.log'),logs);}
