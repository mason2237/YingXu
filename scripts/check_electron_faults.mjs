// Real native File drop, then a deliberate exit of this probe's idle Python child.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawn} from 'node:child_process';
import net from 'node:net';
import assert from 'node:assert/strict';
import {CdpClient} from './cdp_client.mjs';
import {domDriver} from './cdp_dom.mjs';

const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const executable=process.argv.find(value=>value.startsWith('--executable='))?.slice('--executable='.length);
const output=path.join(ROOT,'work/test-results',`electron-b-faults-${Date.now()}`),media=path.join(output,'拖入文件夹');fs.mkdirSync(media,{recursive:true});
fs.writeFileSync(path.join(media,'视频.mkv'),'unchanged native drop fixture');
const port=await new Promise(resolve=>{const s=net.createServer();s.listen(0,'127.0.0.1',()=>{const p=s.address().port;s.close(()=>resolve(p));});});
const env={...process.env,YINGXU_PYTHON:path.join(ROOT,'.venv-web/Scripts/python.exe')};delete env.ELECTRON_RUN_AS_NODE;
if(executable) {
  env.LOCALAPPDATA=path.join(output,'user-data');env.PATH=[path.join(env.SystemRoot,'System32'),env.SystemRoot].join(path.delimiter);
  for(const key of ['YINGXU_PYTHON','PYTHONPATH','PYTHONHOME','QT_PLUGIN_PATH','QML_IMPORT_PATH','QML2_IMPORT_PATH'])delete env[key];
}
const child=spawn(executable||path.join(ROOT,'work/tools/electron-45.0.0/electron.exe'),[...(executable?[]:[path.join(ROOT,'desktop/electron'),`--profile=${path.join(output,'profile')}`]),'--diagnostics',`--remote-debugging-port=${port}`,'--remote-debugging-address=127.0.0.1'],{cwd:executable?output:ROOT,env,windowsHide:false,stdio:['ignore','pipe','pipe']});
const logs=[],result={passed:false,checks:[],packaged:Boolean(executable),developerPathsRemoved:Boolean(executable)};child.stdout.on('data',b=>logs.push(b.toString()));child.stderr.on('data',b=>logs.push(b.toString()));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));let cdp,page;
try {
  for(let i=0;i<100;i++){try{if((await fetch(`http://127.0.0.1:${port}/json/version`)).ok)break;}catch{}await sleep(100);}
  let target;for(let i=0;i<100;i++){target=(await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find(t=>t.url==='yingxu://app/workspace.html');if(target)break;await sleep(100);}
  cdp=await CdpClient.open(target.webSocketDebuggerUrl);page=domDriver(cdp);await page.waitForFunction(()=>document.documentElement.dataset.desktopBoot==='ready');
  if(executable) {
    await page.locator('#theme-quick').selectOption('light');
    await page.waitForFunction(()=>document.documentElement.dataset.theme==='light');
    assert.equal(JSON.parse(fs.readFileSync(path.join(env.LOCALAPPDATA,'YingXu/Electron/appearance.json'),'utf8')).theme,'light');
    assert(fs.existsSync(path.join(env.LOCALAPPDATA,'YingXu/Electron/python')));
    result.checks.push('default_user_data_directory_and_theme_persistence_without_profile_override');
  }
  const data={items:[],files:[media],dragOperationsMask:1};
  for(const type of ['dragEnter','dragOver','drop'])await cdp.send('Input.dispatchDragEvent',{type,x:400,y:260,data});
  await page.waitForFunction(()=>document.getElementById('count-all').textContent==='1'&&document.getElementById('file-list').getAttribute('aria-busy')==='false');
  assert.equal(fs.readFileSync(path.join(media,'视频.mkv'),'utf8'),'unchanged native drop fixture');
  result.checks.push('native_directory_drop_uses_real_File_path_and_scans_without_modification');
  const backend=logs.join('').split('\n').map(line=>{try{return JSON.parse(line);}catch{return null;}}).find(f=>f?.type==='backend');
  assert(Number.isInteger(backend?.pid)&&backend.pid>0&&backend.pid!==child.pid);
  process.kill(backend.pid); // Only the child PID emitted by this isolated, idle probe.
  await page.waitForFunction(()=>document.getElementById('scan-button').disabled&&document.getElementById('preview-button').disabled&&document.getElementById('toast-message').textContent.includes('Python 服务已退出'));
  assert.equal(fs.readdirSync(media).length,1);
  result.checks.push('backend_exit_disables_actions_clear_message_no_automatic_restart_or_media_change');
  await page.screenshot({path:path.join(output,'disconnected.png')});
  await page.close();for(let i=0;i<50&&child.exitCode===null;i++)await sleep(100);assert.equal(child.exitCode,0);
  result.passed=true;
}catch(error){result.failure=error.stack||String(error);process.exitCode=1;}
finally {
  try{if(child.exitCode===null&&page)await page.close();}catch{}
  cdp?.close();if(child.exitCode===null){await sleep(1000);if(child.exitCode===null)child.kill();}
  fs.writeFileSync(path.join(output,'runtime.log'),logs.join(''));fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify({output,...result},null,2));
}
