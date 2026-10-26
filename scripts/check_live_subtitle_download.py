"""Opt-in real website probe, with production Qt/browser/import code and temp media.

Never mocks website responses or changes network policy. Commands in the ignored
test directory allow an operator to inspect each real page before a download click.
No CAPTCHA/login automation; download/import does not confirm a file operation.
"""
import argparse
import faulthandler
from contextlib import ExitStack
import json
from pathlib import Path
import sys
import tempfile
from time import monotonic
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from yingxu.web_ui.resources import register_scheme
register_scheme()
from PySide6.QtCore import QPoint, QSettings, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from scripts.check_subtitle_browser import wait_for, javascript
from scripts.check_subtitle_recommendations import clicked, settled
from yingxu.operations import HistoryStore
from yingxu.web_ui.subtitle_browser import SubtitleBrowser
from yingxu.web_ui.window import WebWindow


PAGE = """JSON.stringify((()=>{
 const safe=u=>{try{const x=new URL(u,location.href);return x.origin+x.pathname}catch{return ''}};
 const visible=e=>e.getClientRects().length&&!e.hidden;
 return {title:document.title,host:location.hostname,path:location.pathname,
  text:document.body?.innerText.slice(0,6500),
  controls:[...document.querySelectorAll('button,a[href],input:not([type=hidden]):not([type=password])')]
    .filter(visible).slice(0,100).map(e=>({tag:e.tagName,id:e.id,cls:e.className,
     text:(e.innerText||e.placeholder||e.getAttribute('aria-label')||'').slice(0,100),
     href:e.href?safe(e.href):'',type:e.type||''}))};
})())"""


def main():
    faulthandler.dump_traceback_later(45,repeat=True)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', choices=['subhd','subhd-one'], default='subhd')
    args = parser.parse_args()
    evidence = ROOT/'work/test-results'
    evidence.mkdir(parents=True,exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='stage9e-live-',dir=evidence))
    output = evidence/'stage9e-live-session.json'
    command_file = evidence/'stage9e-live-command.json'
    app = QApplication(sys.argv);app.setQuitOnLastWindowClosed(False);app.setStyle('Fusion')
    errors = []
    sys.excepthook = lambda kind,error,trace:(errors.append(f'{kind.__name__}: {error}'),sys.__excepthook__(kind,error,trace))
    media = root/'media';media.mkdir()
    video = media/'Interstellar.2014.1080p.mkv';video.write_bytes(b'private-test-video')
    preferences = QSettings(str(root/'language.ini'),QSettings.Format.IniFormat)
    result = {'site':args.site,'query':'Interstellar 2014','root':str(root),
              'liveWebsite':True,'websiteMocked':False,'steps':[]}
    # A restarted probe must not replay an earlier download command.
    try: last_command = json.loads(command_file.read_text(encoding='utf-8-sig')).get('id')
    except (OSError,ValueError): last_command = None
    window = online = None
    timer = QTimer();timer.setInterval(250)
    started = monotonic()
    with ExitStack() as patches:
        def create_browser(parent=None):
            return SubtitleBrowser(parent,website=args.site,settings=preferences,download_root=root/'inbox')
        patches.enter_context(patch('yingxu.web_ui.subtitle_browser.SubtitleBrowser',create_browser))
        patches.enter_context(patch('yingxu.web_ui.window.QFileDialog.getExistingDirectory',return_value=str(media)))
        appearance = QSettings(str(root/'appearance.ini'),QSettings.Format.IniFormat)
        window = WebWindow(appearance_settings=appearance,history=HistoryStore(root/'history.jsonl'))
        window.show()
        print('live probe: workspace starting',flush=True)

        def save(phase):
            result.update(phase=phase,pythonErrors=errors,workspaceErrors=window.page.console_errors,
                mediaUnchanged=video.read_bytes()==b'private-test-video',
                noRemoteChannel=online.page.webChannel() is None,
                status=online.status.text(),verificationRequired=online.verification_required,
                page=json.loads(javascript(online.page,PAGE)),
                candidates=[{k:r[k] for k in ('title','release','language','url')} for r in online.recommendations.rows[:5]],
                downloads=[{'name':e['path'].name,'finished':e['finished'],'registered':e.get('registered',False),
                            'imported':e.get('imported',False),'message':e['item'].text()} for e in online.downloads.values()],
                job=window.bridge.service.job)
            output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            online.grab().save(str(evidence/f'stage9e-{phase}.png'))
            print(json.dumps({'phase':phase,'status':result['status'],'candidateCount':len(online.recommendations.rows),
                              'downloads':result['downloads'],'output':str(output)},ensure_ascii=True),flush=True)

        def poll():
            nonlocal last_command
            if monotonic()-started > 900:
                save('timeout');window.close();app.quit();return
            if not command_file.is_file(): return
            try: command = json.loads(command_file.read_text(encoding='utf-8-sig'))
            except (OSError,ValueError): return
            if command.get('id') == last_command: return
            last_command = command.get('id');timer.stop()
            try:
                action = command['action']
                if action == 'candidate':
                    row = online.recommendations.rows[int(command.get('rank',0))]
                    online.open_candidate(row)
                    wait_for(lambda:not online.load_timer.isActive() and bool(javascript(online.page,'document.body?.innerText.length>50')),'Detail load',40)
                elif action == 'click':
                    if online.verification_required: raise ValueError('CAPTCHA requires the user; stopped.')
                    selector = command['selector']
                    rect = json.loads(javascript(online.page,"JSON.stringify((()=>{const e=document.querySelector("+json.dumps(selector)+");if(!e||e.disabled||!e.getClientRects().length)return null;e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})())"))
                    if not rect: raise ValueError('No visible enabled control for this selector.')
                    target = online.view.focusProxy() or online.view
                    QTest.mouseClick(target,Qt.MouseButton.LeftButton,pos=QPoint(int(rect['x']),int(rect['y'])))
                    QTest.qWait(1500)
                    if online.busy_downloads(): wait_for(lambda:not online.busy_downloads(),'Download completion',45)
                    elif online.load_timer.isActive(): wait_for(lambda:not online.load_timer.isActive(),'Page load',35)
                elif action == 'import':
                    if not online.import_selection(): raise ValueError('No registered download to import.')
                    online.request_import()
                    wait_for(lambda:not online.import_busy and not window.bridge.service.busy,'Import completion',45)
                    wait_for(lambda:settled(window),'Workspace refresh after import',15)
                    result['importedReview'] = window.bridge.service.data.rows
                    window.grab().save(str(evidence/'stage9e-imported-workspace.png'))
                elif action == 'finish':
                    save('finished');window.close();QTest.qWait(150);app.quit();return
                elif action != 'inspect': raise ValueError('Unsupported probe command.')
                result['steps'].append({'action':action,'id':last_command,'ok':True})
                save(str(last_command))
            except Exception as error:
                result['steps'].append({'action':command.get('action'),'id':last_command,'ok':False,'error':str(error)})
                save(str(last_command)+'-failed')
            finally:
                timer.start()

        try:
            wait_for(lambda:window._loaded and settled(window),'Workspace startup')
            print('live probe: scanning disposable video',flush=True)
            clicked(window,'#dataset-button')
            wait_for(lambda:window.bridge.service.data is not None and settled(window),'Local scan')
            clicked(window,'#online-subtitles-button')
            wait_for(lambda:window.subtitle_browser is not None and not window.bridge.service.native_busy,'Online entry')
            online = window.subtitle_browser
            def download_diagnostic(request):
                result.setdefault('downloadEvents',[]).append({
                    'scheme':request.url().scheme(),'host':request.url().host(),
                    'samePage':request.page() is online.page,'hasSearchTask':online.active_task is not None,
                    'batchRunning':online.batch_running,'closing':online.closing,
                    'savePage':request.isSavePageDownload(),'fileName':request.suggestedFileName()[:180],
                    'mime':request.mimeType(),'pageHost':online.page.url().host(),
                    'pagePath':online.page.url().path()})
            online.profile.downloadRequested.connect(download_diagnostic)
            print('live probe: real website search',flush=True)
            online.query.setText(result['query']);online.start_search()
            wait_for(lambda:bool(online.results) or online.verification_required or (not online.load_timer.isActive() and not online.search_pending),'Live search',55)
            save('search')
            if not online.recommendations.rows or online.verification_required:
                window.close();QTest.qWait(150);return
            timer.timeout.connect(poll);timer.start()
            # Waiting for the next operator command is intentional, not a hang.
            faulthandler.cancel_dump_traceback_later()
            app.exec()
        finally:
            timer.stop()
            if window is not None: window.close()
            QTest.qWait(150)
            faulthandler.cancel_dump_traceback_later()


if __name__ == '__main__':main()
