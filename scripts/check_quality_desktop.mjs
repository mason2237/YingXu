// Generated SRT -> real reader/IPC -> visible quality UI. No sites or media writes.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import net from 'node:net';
import {spawn,spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {CdpClient} from './cdp_client.mjs';

const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const executable=process.argv[2];
const output=path.join(ROOT,`work/test-results/quality-desktop-${Date.now()}`),media=path.join(output,'media');
fs.mkdirSync(media,{recursive:true});
const python=path.join(ROOT,'.venv-core/Scripts/python.exe');
const generate=spawnSync(python,['-S','-c',`from pathlib import Path
import sys
from uuid import uuid4
from dataclasses import asdict
from yingxu.adapters.subtitle_artifacts import LocalSubtitleArtifacts
from yingxu.adapters.legacy_operations import file_mark
root=Path(sys.argv[1])
(root/'Film.2024.S01E01.mkv').write_bytes(b'generated video')
text='\\n'.join(f'{i}\\n00:00:03,000 --> 00:00:01,000\\n<img src=x onerror="window.__qualityXss=true">Generated line {i}\\n' for i in range(1,31))
(root/'Film.2024.S01E01.en.srt').write_text(text,encoding='utf-8')
(root/'Film.2024.S01E01.chs.srt').write_bytes('1\\n00:00:01,000 --> 00:00:03,000\\n生成的中文字幕\\n'.encode('gb18030'))
cache=LocalSubtitleArtifacts(root.parent/'profile/python/subtitles')
record=cache.reserve({'offerId':uuid4().hex,'url':'https://subhd.me/generated.srt','page':'https://subhd.me/a/GENERATED',
    'name':'generated.srt','mime':'text/plain','total':100},{'provider':'subhd','video':str(root/'Film.2024.S01E01.mkv'),'mark':asdict(file_mark(root/'Film.2024.S01E01.mkv'))})
cache.path(record['id']).write_text('1\\n00:00:03,000 --> 00:00:01,000\\nGenerated downloaded text\\n',encoding='utf-8')
cache.prepare(record['id'],lambda:False)
`,media],{cwd:ROOT,encoding:'utf8',windowsHide:true});
assert.equal(generate.status,0,generate.stderr);
const snapshot=()=>Object.fromEntries(fs.readdirSync(media).map(name=>[name,createHash('sha256').update(fs.readFileSync(path.join(media,name))).digest('hex')]));
const before=snapshot(),sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function until(check){let error;for(let i=0;i<450;i++){try{const v=await check();if(v)return v;}catch(e){error=e;}await sleep(60);}throw Error('Quality condition timed out '+(error?.message||''));}
let child,page,onlinePage,browser,logs='';const exceptions=[];
try{
  const port=await new Promise(resolve=>{const server=net.createServer();server.listen(0,'127.0.0.1',()=>{const p=server.address().port;server.close(()=>resolve(p));});});
  const env={...process.env,YINGXU_PYTHON:python};delete env.ELECTRON_RUN_AS_NODE;
  if(executable)delete env.YINGXU_PYTHON;
  child=spawn(executable||path.join(ROOT,'work/tools/electron-45.0.0/electron.exe'),[...(executable?[]:[path.join(ROOT,'desktop/electron')]),'--diagnostics',
    `--profile=${path.join(output,'profile')}`,`--test-folder=${media}`,`--remote-debugging-port=${port}`,'--remote-debugging-address=127.0.0.1'],
    {cwd:ROOT,env,windowsHide:false,stdio:['ignore','pipe','pipe']});
  child.stdout.on('data',v=>logs+=v);child.stderr.on('data',v=>logs+=v);
  const target=await until(async()=>(await fetch(`http://127.0.0.1:${port}/json/list`).then(r=>r.json())).find(t=>t.url==='yingxu://app/workspace.html'));
  page=await CdpClient.open(target.webSocketDebuggerUrl);await page.send('Runtime.enable');
  page.on('Runtime.exceptionThrown',e=>exceptions.push(e));
  const evaluate=async expression=>{const r=await page.send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;};
  await until(()=>evaluate("document.documentElement.dataset.ready==='true'"));
  await evaluate(`(async()=>{window.__wireMax=0;yingxuHost.workspace.onReply(raw=>{__wireMax=Math.max(__wireMax,new TextEncoder().encode(raw).byteLength);});
    window.__ask=(sessionId,action,params={})=>new Promise((resolve,reject)=>{const requestId=crypto.randomUUID(),host=yingxuHost.workspace;let stop;const timer=setTimeout(()=>{stop?.();reject(Error('Check timeout'));},15000);
      stop=host.onReply(raw=>{const r=JSON.parse(raw);if(r.requestId===requestId){clearTimeout(timer);stop();resolve(r);}});host.request(JSON.stringify({v:2,requestId,sessionId,action,params})).catch(reject);});
    window.__sid=(await __ask(null,'app.state')).sessionId;window.__call=async(action,params={})=>{const r=await __ask(__sid,action,params);if(!r.ok)throw Error(JSON.stringify(r.error));return r.data;};
    await __call('embedded.configure',{enabled:false,language:'chinese'});document.getElementById('dataset-button').click();
    window.__qualityCard=ext=>[...document.querySelectorAll('.subtitle-detail:not(.embedded-track)')].find(c=>c.querySelector('p')?.textContent.endsWith(ext+'.srt'));
    return true;})()`);
  await until(()=>evaluate("document.querySelectorAll('.subtitle-detail:not(.embedded-track)').length===2"));
  await until(async()=>!(await evaluate("__call('app.state')")).busy);
  await evaluate("__qualityCard('en').querySelector('.subtitle-quality button').click();true");
  await until(()=>evaluate("__qualityCard('en')?.querySelector('.quality-summary')?.textContent.includes('发现')"));
  assert.equal(await evaluate("Boolean(window.__qualityXss)||Boolean(document.querySelector('.subtitle-quality img'))"),false);
  assert.ok(await evaluate("__qualityCard('en').textContent.includes('<img src=x')"));
  await evaluate("[...__qualityCard('en').querySelectorAll('button')].find(b=>b.textContent==='下一页').click();true");
  await until(()=>evaluate("__qualityCard('en').textContent.includes('11–20')"));
  await evaluate("__qualityCard('chs').querySelector('.subtitle-quality button').click();true");
  await until(()=>evaluate("__qualityCard('chs')?.textContent.includes('请选择编码')"));
  await evaluate("(()=>{const choice=[...__qualityCard('chs').querySelectorAll('details')].find(d=>d.querySelector('summary')?.textContent==='gb18030 预览');choice.open=true;choice.querySelector('button').click();})()");
  await until(()=>evaluate("__qualityCard('chs')?.querySelector('.quality-summary')?.textContent.includes('未发现')"));
  await evaluate("[...__qualityCard('chs').querySelectorAll('button')].find(b=>b.textContent==='查看前五条字幕片段').click();true");
  await until(()=>evaluate("__qualityCard('chs').textContent.includes('生成的中文字幕')"));
  await evaluate("(async()=>{const {LocalAdapter}=await import('./js/local-adapter.js');window.__qualityStart=LocalAdapter.prototype.start;LocalAdapter.prototype.start=function(action,params){if(action==='review.quality')return Promise.reject(Error('测试用检查故障'));return window.__qualityStart.call(this,action,params);};[...__qualityCard('en').querySelectorAll('button')].find(b=>b.textContent==='重新检查字幕').click();})()");
  await until(()=>evaluate("__qualityCard('en').textContent.includes('测试用检查故障')"));
  assert.equal(await evaluate("document.querySelector('#empty-state').hidden&&!document.querySelector('#file-list').hidden&&document.querySelectorAll('#list-items [data-row-id]').length===1"),true);
  await evaluate("(()=>{const panel=document.getElementById('inspector-content'),card=__qualityCard('chs').querySelector('.quality-summary');panel.scrollTop+=card.getBoundingClientRect().top-panel.getBoundingClientRect().top-8;})()");
  await page.send('Page.enable');const screenshot=await page.send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(output,'quality.png'),Buffer.from(screenshot.data,'base64'));
  await evaluate("document.getElementById('subtitle-inbox').click();true");
  const onlineTarget=await until(async()=>(await fetch(`http://127.0.0.1:${port}/json/list`).then(r=>r.json())).find(t=>t.url==='yingxu://app/online.html'));
  onlinePage=await CdpClient.open(onlineTarget.webSocketDebuggerUrl);await onlinePage.send('Runtime.enable');onlinePage.on('Runtime.exceptionThrown',e=>exceptions.push(e));
  const onlineEvaluate=async expression=>{const r=await onlinePage.send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;};
  await until(()=>onlineEvaluate("(()=>{const button=[...document.querySelectorAll('#downloads button')].find(b=>b.textContent==='查看字幕检查结果');if(!button)return false;button.click();return true;})()"));
  await until(()=>onlineEvaluate("(()=>{const button=document.querySelector('#downloads .subtitle-quality button');if(!button||button.disabled)return false;button.click();return true;})()"));
  await until(()=>onlineEvaluate("document.querySelector('#downloads .quality-summary')?.textContent.includes('发现')"));
  assert.ok(await onlineEvaluate("document.querySelector('#downloads').textContent.includes('结束时间早于开始时间')"));
  assert.equal(await onlineEvaluate("(async()=>{try{await yingxuOnline.request('review.quality',{path:'not-a-file'});return false;}catch{return true;}})()"),true);
  await until(()=>onlineEvaluate("(()=>{const sidebar=document.querySelector('aside'),target=document.querySelector('#downloads .quality-summary');if(!target)return false;sidebar.scrollTop+=target.getBoundingClientRect().top-sidebar.getBoundingClientRect().top-8;return true;})()"));
  await onlinePage.send('Page.enable');const downloadShot=await onlinePage.send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(output,'download-quality.png'),Buffer.from(downloadShot.data,'base64'));
  assert.deepEqual(snapshot(),before);assert.equal(exceptions.length,0,JSON.stringify(exceptions));
  const maxReplyBytes=await evaluate('__wireMax');assert.ok(maxReplyBytes<=8192);
  const info=await fetch(`http://127.0.0.1:${port}/json/version`).then(r=>r.json());browser=await CdpClient.open(info.webSocketDebuggerUrl);
  await browser.send('Browser.close').catch(()=>{});await until(()=>child.exitCode!==null);assert.equal(child.exitCode,0);
  const report={passed:true,mode:executable?'frozen':'source',sourceWindow:!executable,executablePackaged:Boolean(executable),reverseTimeLocated:true,paging:true,encodingChoice:true,pureTextPreview:true,
    issueFailureKeepsList:true,downloadQualityUI:true,onlineLocalAPIRestricted:true,mediaUnchanged:true,maxReplyBytes,jsExceptions:0,websiteVisited:false,exitCode:0,output:path.relative(ROOT,output)};
  fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}catch(error){process.exitCode=1;console.error(error.stack);fs.writeFileSync(path.join(output,'failure.json'),JSON.stringify({error:error.stack,exceptions},null,2));}
finally{page?.close();onlinePage?.close();browser?.close();if(child?.exitCode===null)child.kill();fs.writeFileSync(path.join(output,'runtime.log'),logs);}
