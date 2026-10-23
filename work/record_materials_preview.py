"""Actual list vapor and original Lens press, no synthetic UI frames/CUA."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
from check_theme_preview import ready,js,data,select,ROOT
from check_web_foundation import wait_for
from PySide6.QtCore import QSettings,QPoint,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from yingxu.web_ui.window import WebWindow

if __name__=='__main__':
    app=QApplication(sys.argv)
    output=ROOT/'outputs/stage63a_motion_frames';output.mkdir(exist_ok=True)
    records=[];images=[]
    with TemporaryDirectory(prefix='yingxu-vapor-record-') as directory:
        settings=QSettings(str(Path(directory)/'appearance.ini'),QSettings.Format.IniFormat)
        settings.setValue('appearance/v1','{"theme":"light"}')
        window=WebWindow(preview=True,appearance_settings=settings);window.show()
        try:
            ready(window)
            wait_for(lambda:js(window,"globalThis.yingxuPreview.stats().effects.mist.mode==='webgl2'"),'Vapor renderer failed')
            QTest.qWait(700);started=perf_counter()
            def grab():
                records.append({'file':f'{len(records):03d}.png','atMs':round((perf_counter()-started)*1000,2)})
                images.append(window.grab())
            def segment(count,delay=28):
                for _ in range(count):grab();QTest.qWait(delay)
            def point(selector,x=.45,y=.5):
                values=data(window,f"(() => {{const r=document.querySelector({json.dumps(selector)}).getBoundingClientRect();return [r.x+r.width*{x},r.y+r.height*{y}];}})()")
                return QPoint(round(values[0]),round(values[1]))
            grab();QTest.qWait(300)
            for selector in ('[data-row-id="video-1"]','[data-row-id="video-3"]'):
                QTest.mouseMove(window.view.focusProxy(),point(selector));segment(9)
            action=point('#preview-button',.65)
            QTest.mouseMove(window.view.focusProxy(),action);segment(3)
            QTest.mousePress(window.view.focusProxy(),Qt.MouseButton.LeftButton,pos=action);segment(5)
            QTest.mouseRelease(window.view.focusProxy(),Qt.MouseButton.LeftButton,pos=action);QTest.qWait(200)
            assert js(window,"document.getElementById('preview-dialog').open")
            QTest.keyClick(window.view.focusProxy(),Qt.Key.Key_Escape);QTest.qWait(180)
            select(window,'#theme-quick','dark');segment(8)
            QTest.mouseMove(window.view.focusProxy(),point('[data-row-id="video-2"]'));segment(12)
            QTest.qWait(350);grab()
            assert not window.page.console_errors,window.page.console_errors
            for record,image in zip(records,images):assert image.save(str(output/record['file']))
            (output/'frames.json').write_text(json.dumps(records),encoding='utf-8')
            print(json.dumps({'frames':len(records),'capturedMs':records[-1]['atMs'],'source':'actual Qt/WebEngine and QTest pointer input'}))
        finally:
            window.close();QTest.qWait(150)
