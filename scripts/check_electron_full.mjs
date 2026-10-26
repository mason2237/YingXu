// Incremental stage B integration: real window, private synthetic files, no websites.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawn,execFileSync} from 'node:child_process';
import net from 'node:net';
import assert from 'node:assert/strict';
import {CdpClient} from './cdp_client.mjs';
import {domDriver} from './cdp_dom.mjs';

const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const executable=process.argv.find(value=>value.startsWith('--executable='))?.slice('--executable='.length);
const output=path.join(ROOT,'work/test-results',`electron-b-${Date.now()}`),media=path.join(output,'中文 & 视频'),profile=path.join(output,'profile');
const python=path.join(ROOT,process.argv.includes('--pythonw')?'.venv-web/Scripts/pythonw.exe':'.venv-web/Scripts/python.exe');
fs.mkdirSync(media,{recursive:true});fs.mkdirSync(path.join(profile,'python'),{recursive:true});
for(let i=1;i<=3;i++) {
  fs.writeFileSync(path.join(media,`映序.S01E0${i}.2160p.mkv`),`video ${i}`);
  if(i<3)fs.writeFileSync(path.join(media,`映序.S01E0${i}.chs.srt`),'1\n00:00:01,000 --> 00:00:02,000\n测试\n');
}
const initial=Object.fromEntries(fs.readdirSync(media).map(name=>[name,fs.readFileSync(path.join(media,name),'hex')]));
execFileSync(python,['-c',"import json,sys;from PySide6.QtCore import QSettings;s=QSettings(sys.argv[1],QSettings.IniFormat);s.setValue('subtitles/embedded/v1',json.dumps({'enabled':False,'language':'chinese'}));s.sync()",path.join(profile,'python/embedded.ini')]);
fs.writeFileSync(path.join(profile,'appearance.json'),JSON.stringify({theme:'dark'}));
const port=await new Promise(resolve=>{const server=net.createServer();server.listen(0,'127.0.0.1',()=>{const p=server.address().port;server.close(()=>resolve(p));});});
const env={...process.env,YINGXU_PYTHON:python};delete env.ELECTRON_RUN_AS_NODE;
if(executable) {
  env.PATH=[path.join(env.SystemRoot,'System32'),env.SystemRoot].join(path.delimiter);
  for(const key of ['YINGXU_PYTHON','PYTHONPATH','PYTHONHOME','QT_PLUGIN_PATH','QML_IMPORT_PATH','QML2_IMPORT_PATH'])delete env[key];
}
const child=spawn(executable||path.join(ROOT,'work/tools/electron-45.0.0/electron.exe'),[
  ...(executable?[]:[path.join(ROOT,'desktop/electron')]),`--profile=${profile}`,'--diagnostics',`--test-folder=${media}`,
  `--remote-debugging-port=${port}`,'--remote-debugging-address=127.0.0.1',
],{cwd:executable?output:ROOT,env,windowsHide:false,stdio:['ignore','pipe','pipe']});
const logs=[],result={passed:false,checks:[],errors:[],networkSearchRequested:false,pythonRuntime:executable?'frozen':path.basename(python),packaged:Boolean(executable),developerPathsRemoved:Boolean(executable)};
child.stdout.on('data',block=>logs.push(block.toString()));child.stderr.on('data',block=>logs.push(block.toString()));
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));let cdp,page;
try {
  for(let i=0;i<100;i++){try{if((await fetch(`http://127.0.0.1:${port}/json/version`)).ok)break;}catch{}if(child.exitCode!==null)throw Error(logs.join(''));await sleep(100);}
  let target;
  for(let i=0;i<100;i++){target=(await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find(t=>t.url==='yingxu://app/workspace.html');if(target)break;await sleep(100);}
  assert(target);cdp=await CdpClient.open(target.webSocketDebuggerUrl);page=domDriver(cdp);
  cdp.on('Runtime.exceptionThrown',event=>result.errors.push(event.exceptionDetails.exception?.description||event.exceptionDetails.text));await cdp.send('Runtime.enable');
  await page.waitForFunction(()=>document.documentElement.dataset.desktopBoot==='ready');
  assert.deepEqual(await page.evaluate(()=>({prototype:yingxuHost.prototype,node:typeof require,qt:typeof qt})),{prototype:false,node:'undefined',qt:'undefined'});
  await page.evaluate(()=>{window.__events=[];window.__replies=[];yingxuHost.workspace.onEvent(raw=>window.__events.push(JSON.parse(raw)));yingxuHost.workspace.onReply(raw=>window.__replies.push(JSON.parse(raw)));});
  await page.locator('#dataset-button').click();
  await page.waitForFunction(()=>document.querySelector('#count-all').textContent==='3'&&document.querySelector('#file-list').getAttribute('aria-busy')==='false');
  assert(!(await page.locator('#online-subtitles-button').isDisabled()));
  const pathDisplay=await page.evaluate(()=>{const e=document.getElementById('folder-path');const value={text:e.textContent,title:e.title};e.textContent='演示目录（路径已隐去）';e.title='';return value;});
  await page.screenshot({path:path.join(output,'workspace.png')});
  await page.evaluate(value=>{const e=document.getElementById('folder-path');e.textContent=value.text;e.title=value.title;},pathDisplay);
  result.checks.push('full_host_real_scan_and_enabled_capabilities');
  await page.locator('#inspector-actions button:nth-child(2)').click();
  await page.waitForFunction(()=>document.querySelector('#inspector-actions button:nth-child(2)').textContent.includes('恢复审阅'));
  await page.locator('#inspector-actions button:nth-child(2)').click();
  await page.waitForFunction(()=>document.querySelector('#inspector-actions button:nth-child(2)').textContent.includes('跳过'));
  await page.locator('#inspector .subtitle-detail button').click();
  await page.waitForFunction(()=>!document.querySelector('#inspector .subtitle-detail'));
  await page.locator('#inspector-actions button:first-child').click();
  await page.waitForFunction(()=>document.querySelector('#candidate-dialog').open&&document.querySelector('#candidate-list .candidate-card'));
  await page.locator('#candidate-list .candidate-card button').click();
  await page.waitForFunction(()=>!document.querySelector('#candidate-dialog').open&&document.querySelector('#inspector-actions button:first-child').textContent.includes('确认匹配'));
  await page.locator('#inspector-actions button:first-child').click();
  await page.waitForFunction(()=>document.querySelector('#inspector-actions button:first-child').textContent.includes('更换字幕'));
  result.checks.push('skip_restore_candidates_manual_assignment_and_confirmation');
  await page.locator('#preview-button').click();
  await page.waitForFunction(()=>document.querySelector('#preview-dialog').open&&!document.querySelector('#preview-ack').disabled);
  assert(await page.locator('#execute-button').isDisabled());
  assert.deepEqual(Object.fromEntries(fs.readdirSync(media).map(name=>[name,fs.readFileSync(path.join(media,name),'hex')])),initial);
  await page.reload();await page.waitForFunction(()=>document.documentElement.dataset.desktopBoot==='ready');
  await page.locator('#preview-button').click();await page.waitForFunction(()=>document.querySelector('#preview-dialog').open&&!document.querySelector('#preview-ack').disabled);
  await page.locator('#preview-ack').click();await page.waitForFunction(()=>!document.querySelector('#execute-button').disabled);
  await page.evaluate(()=>{document.getElementById('execute-button').click();document.getElementById('execute-button').click();});
  await page.waitForFunction(()=>document.querySelector('#history-dialog').open&&document.querySelector('#history-content').textContent.includes('成功'));
  const history=fs.readFileSync(path.join(profile,'python/history.jsonl'),'utf8').trim().split(/\r?\n/).map(line=>JSON.parse(line));
  assert.equal(history.length,1);assert.equal(history[0].items.filter(i=>i.status==='success').length,2);
  for(let i=1;i<=3;i++)assert.equal(fs.readFileSync(path.join(media,`映序.S01E0${i}.2160p.mkv`),'utf8'),`video ${i}`);
  for(let i=1;i<=2;i++)assert(fs.existsSync(path.join(media,`映序.S01E0${i}.2160p.chs.srt`)));
  result.checks.push('readonly_preview_reload_new_consent_execute_once_and_history_two_success');
  await page.screenshot({path:path.join(output,'result.png')});
  await page.locator('#history-dialog [data-close]').click();await page.waitForFunction(()=>!document.querySelector('#history-dialog').open);
  await page.locator('#scan-button').click();
  await page.waitForFunction(()=>document.querySelector('#count-all').textContent==='3'&&document.querySelector('#file-list').getAttribute('aria-busy')==='false'&&!document.querySelector('#online-subtitles-button').disabled);
  await page.locator('#online-subtitles-button').click();
  await page.waitForFunction(()=>document.querySelector('#toast-message').textContent.includes('已打开在线字幕'));
  const frames=()=>logs.join('').split('\n').map(line=>{try{return JSON.parse(line);}catch{return null;}}).filter(Boolean);
  const online=frames().find(frame=>frame.type==='online.window'),main=frames().find(frame=>frame.type==='window');
  assert(online&&main,'No helper window handshake');assert.notEqual(online.pid,main.pid);
  await sleep(200);
  execFileSync(python,[path.join(ROOT,'scripts/capture_window_preview.py'),online.handle,path.join(output,'online.png'),'--print-window',`--process-id=${online.pid}`],{timeout:5000});
  result.checks.push('separate_native_online_window_opened_for_unmatched_queue_without_search');
  // Close the workspace normally; its backend must close the independent browser too.
  await page.close();
  for(let i=0;i<150&&child.exitCode===null;i++)await sleep(100);
  assert.equal(child.exitCode,0,'Normal safe shutdown timeout');
  assert(!logs.join('').includes('Fatal Python error'), 'Python interpreter shutdown failed');
  result.checks.push('normal_shutdown_waits_for_python_and_online_helper');
  result.passed=result.errors.length===0;
}catch(error){result.failure=error.stack||String(error);process.exitCode=1;
  if(page)try{await page.screenshot({path:path.join(output,'failure.png')});result.diagnostics=await page.evaluate(()=>({inspector:document.getElementById('inspector-content')?.innerText,toast:document.getElementById('toast-message')?.textContent,dialogs:[...document.querySelectorAll('dialog[open]')].map(e=>e.id)}));}catch{}
}
finally {
  try{if(child.exitCode===null&&page)await page.close();}catch{}
  cdp?.close();
  if(child.exitCode===null){await sleep(2000);if(child.exitCode===null)child.kill();}
  fs.writeFileSync(path.join(output,'runtime.log'),logs.join(''));
  fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(result,null,2));
  console.log(JSON.stringify({output,...result},null,2));
}
