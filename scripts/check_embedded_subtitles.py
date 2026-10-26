"""Actual desktop/channel checks with generated embedded-subtitle containers.

No external websites, personal media, extraction or physical HDR certification.
"""
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from tests.media_fixtures import mkv, mp4
from yingxu.operations import HistoryStore
from yingxu.web_ui.embedded_settings import EmbeddedSettings
from yingxu.web_ui.native_window import NativeWindow,configure_graphics
from yingxu.web_ui.resources import register_scheme
from scripts.check_subtitle_browser import javascript,wait_for


def main():
    configure_graphics();register_scheme()
    app=QApplication(sys.argv);app.setQuitOnLastWindowClosed(False)
    output=ROOT/'work/test-results/stage18-ui.json';output.parent.mkdir(exist_ok=True)
    result={'passed':False,'checks':[],'physicalFramesVerified':False}
    errors=[];old_hook=sys.excepthook
    sys.excepthook=lambda kind,error,trace:errors.append(f'{kind.__name__}: {error}')
    window=None
    try:
        with tempfile.TemporaryDirectory(prefix='embedded-ui-',dir=output.parent) as folder:
            root=Path(folder);media=root/'视频 中文';media.mkdir()
            chinese=mkv(media/'中文视频.mkv',[('zho','简体中文 <img src=x onerror=alert(1)>',False)])
            english=mp4(media/'English.mp4','eng')
            before={p.name:p.read_bytes() for p in media.iterdir()}
            appearance=QSettings(str(root/'appearance.ini'),QSettings.Format.IniFormat)
            appearance.setValue('appearance/v1',json.dumps({'theme':'dark','nativeHdr':False}))
            window=NativeWindow(appearance_settings=appearance,history=HistoryStore(root/'history.jsonl'))
            service=window.bridge.service
            service.embedded_settings=EmbeddedSettings(QSettings(str(root/'language.ini'),QSettings.Format.IniFormat))
            window.show();window.requestActivate();wait_for(lambda:window._loaded,'Workspace startup')
            service.accept_folder(media,dropped=True)
            wait_for(lambda:service.data is not None and not service.busy,'Embedded scan',12)
            def row(path):return next(item for item in service.data.rows if item['video']['name']==path.name)
            good=row(chinese);bad=row(english)
            assert good['embeddedSatisfied'] and not bad['embeddedSatisfied']
            wait_for(lambda:javascript(window.page,"document.querySelectorAll('.file-row').length===2"),'Actual file rows')
            assert javascript(window.page,f"document.querySelector('[data-row-id=\"{good['rowId']}\"]').textContent.includes('语言符合')")
            result['checks'].append('actual_native_folder_drop_scan_and_language_status')
            javascript(window.page,f"document.querySelector('[data-row-id=\"{good['rowId']}\"]').click();true")
            wait_for(lambda:javascript(window.page,"!!document.querySelector('.embedded-details .embedded-track')"),'Embedded inspector')
            assert javascript(window.page,"document.querySelector('#inspector-actions .detail-actions button').disabled")
            assert javascript(window.page,"document.querySelector('#inspector-actions .online-current').hidden")
            assert javascript(window.page,"document.getElementById('preview-button').disabled")
            assert javascript(window.page,"!document.querySelector('.embedded-details img')")
            result['checks'].append('satisfied_no_external_action_no_extraction_no_markup_execution')
            javascript(window.page,"[...document.querySelectorAll('.embedded-details button')].find(b=>b.textContent.includes('仍需外挂')).click();true")
            wait_for(lambda:not service.busy and not row(chinese)['embeddedSatisfied'],'Manual defer')
            wait_for(lambda:javascript(window.page,"!document.querySelector('#inspector-actions .online-current').hidden"),'External actions restored')
            javascript(window.page,"[...document.querySelectorAll('.embedded-details button')].find(b=>b.textContent.includes('改用已有')).click();true")
            wait_for(lambda:not service.busy and row(chinese)['embeddedSatisfied'],'Manual restore')
            result['checks'].append('real_manual_override_and_restore')
            wait_for(lambda:javascript(window.page,"!document.getElementById('scan-options-button').disabled"),'Review UI settled')
            javascript(window.page,"document.getElementById('scan-options-button').click();true")
            wait_for(lambda:javascript(window.page,"document.getElementById('scan-options-dialog').open"),'Scan options')
            javascript(window.page,"(()=>{const s=document.getElementById('embedded-language');s.value='english';s.dispatchEvent(new Event('change',{bubbles:true}));return true})()")
            wait_for(lambda:service.data is None and service.embedded_settings.options['language']=='english','Saved language preference')
            wait_for(lambda:javascript(window.page,"!document.getElementById('scan-options-start').disabled"),'Language UI settled')
            javascript(window.page,"document.getElementById('scan-options-start').click();true")
            wait_for(lambda:service.data is not None and not service.busy,'Rescan after language change',12)
            assert row(english)['embeddedSatisfied'] and not row(chinese)['embeddedSatisfied']
            assert [task['rowId'] for task in service.subtitle_tasks({'scanId':service.data.scan_id,'revision':service.data.revision})]==[row(chinese)['rowId']]
            result['checks'].append('actual_language_control_changes_policy_and_search_queue')
            assert before=={p.name:p.read_bytes() for p in media.iterdir()}
            assert not window.page.console_errors and not errors
            result['checks'].append('videos_unchanged_no_subtitles_created_no_js_or_python_errors')
            result.update(passed=True,pythonErrors=errors,consoleErrors=list(window.page.console_errors))
    finally:
        if window:
            if window.bridge.service.worker:window.bridge.service.worker.stop.set();wait_for(lambda:not window.bridge.service.busy,'Task shutdown',10)
            window.close();QTest.qWait(100);app.processEvents()
        sys.excepthook=old_hook
        output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
