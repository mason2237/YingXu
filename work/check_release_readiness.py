"""Focused resize/DPI and real scan metrics; no external media or OS changes."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

from check_local_workspace import ROOT, js, wait_for, click, ready, settled, files
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from yingxu.operations import HistoryStore
from yingxu.web_ui.window import WebWindow


def metrics(window):
    return json.loads(js(window, """JSON.stringify((()=>{
      const list=document.getElementById('file-list'),r=list.getBoundingClientRect();
      return {width:innerWidth,height:innerHeight,dpr:devicePixelRatio,
        overflow:document.documentElement.scrollWidth>innerWidth,
        listHeight:r.height,listBottom:r.bottom,renderedRows:document.querySelectorAll('#list-items .file-row').length,
        rows:Number(list.getAttribute('aria-rowcount')),buttons:document.querySelectorAll('button').length,
        glassButtons:document.querySelectorAll('button.liquid-button').length,
        webglCanvases:document.querySelectorAll('canvas[data-gpu-state]').length,
        fixtureAPI:typeof globalThis.yingxuPreview,heartbeat:globalThis.__checkHeartbeat||0};
    })())"""))


if __name__ == '__main__':
    started = time.monotonic()
    app = QApplication(sys.argv)
    scale = os.environ.get('QT_SCALE_FACTOR', '1')
    count = 1000 if scale == '1' else 12
    with tempfile.TemporaryDirectory(prefix='stage8b-',dir=ROOT/'work'/'test-results') as temporary:
        root = Path(temporary);media = root/'中文 剧集';media.mkdir()
        # Real files. One subtitle exercises matching against all 1000 videos
        # without conflating million-pair scoring with list rendering.
        for number in range(1,count+1):
            (media/f'测试长文件名.映序.S01E{number:04}.2160p.WEB-DL.H265.mkv').write_bytes(b'video')
        (media/'映序.S01E0001.chs.srt').write_bytes(b'subtitle')
        before=files(media)
        settings=QSettings(str(root/'appearance.ini'),QSettings.Format.IniFormat)
        window=WebWindow(workspace=True,appearance_settings=settings,history=HistoryStore(root/'history.jsonl'))
        window.show()
        try:
            wait_for(lambda:window._loaded and ready(window),'Initial workspace startup')
            startup=time.monotonic()-started
            js(window,"globalThis.__checkHeartbeat=0;globalThis.__checkTimer=setInterval(()=>globalThis.__checkHeartbeat++,50);true")
            with patch('yingxu.web_ui.window.QFileDialog.getExistingDirectory',return_value=str(media)):
                scan_start=time.monotonic();click(window,'dataset-button')
                wait_for(lambda:window.bridge.service.data is not None and settled(window),'Real scan timed out',90)
            scan=time.monotonic()-scan_start
            wait_for(lambda:metrics(window)['renderedRows']>0,'Rows not rendered')
            info={'scaleFactor':scale,'startupSeconds':round(startup,3),'scanSeconds':round(scan,3),
                  'videoFiles':count,'subtitleFiles':1,'initial':metrics(window)}
            assert info['initial']['rows']==count,info
            assert info['initial']['renderedRows']<=30 and info['initial']['fixtureAPI']=='undefined',info
            assert not info['initial']['overflow'] and info['initial']['listHeight']>100,info
            assert info['initial']['buttons']==info['initial']['glassButtons'],info
            info['screen']={'availableWidth':window.screen().availableGeometry().width(),
                            'availableHeight':window.screen().availableGeometry().height()}
            assert window.height()+40<=info['screen']['availableHeight'],info
            # Reach last real row via the actual keyboard handler and scroll.
            js(window,"document.getElementById('file-list').focus();true")
            QTest.keyClick(window.view.focusProxy(),Qt.Key.Key_End)
            wait_for(lambda:js(window,f"Number(document.querySelector('#list-items .file-row:last-child')?.getAttribute('aria-rowindex'))==={count}"),'Last row inaccessible')
            info['end']=metrics(window)
            for theme in ('dark','light'):
                js(window,f"(()=>{{const t=document.getElementById('theme-quick');t.value='{theme}';t.dispatchEvent(new Event('change',{{bubbles:true}}));return true}})()")
                wait_for(lambda:js(window,f"document.documentElement.dataset.theme==='{theme}'"),'Theme did not apply')
                QTest.qWait(280)
            window.resize(window.minimumWidth(),window.minimumHeight());QTest.qWait(320)
            info['minimum']=metrics(window)
            assert not info['minimum']['overflow'] and info['minimum']['listHeight']>80,info
            click(window,'appearance-button');QTest.qWait(250)
            assert js(window,"[...document.querySelectorAll('dialog[open]')].every(d=>{const r=d.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight+1&&r.right<=innerWidth+1})"),'Modal does not fit'
            js(window,"document.querySelector('dialog[open] [data-close]').click();true");QTest.qWait(180)
            if scale=='1':
                window.showMaximized();QTest.qWait(180);info['maximized']=metrics(window)
                assert not info['maximized']['overflow']
                window.showMinimized();QTest.qWait(160);window.showNormal();QTest.qWait(200)
            assert files(media)==before,'Read-only scan changed media'
            assert window.page.console_errors==[],window.page.console_errors
            assert window.grab().save(str(ROOT/'outputs'/f'stage8b_dpi_{scale}.png'))
            info['consoleErrors']=window.page.console_errors
            info['mediaUnchanged']=True
            target=ROOT/'work'/'test-results'/f'stage8b_dpi_{scale}.json'
            target.write_text(json.dumps(info,indent=2,ensure_ascii=False),encoding='utf-8')
            print(json.dumps(info,ensure_ascii=False),flush=True)
        finally:
            window.close();QTest.qWait(200)
