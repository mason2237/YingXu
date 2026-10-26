"""Run a frozen Qt baseline against synthetic media for the architecture comparison."""
import argparse
import json
import os
from pathlib import Path
import sys
import threading


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--profile',type=Path,required=True)
    parser.add_argument('--folder',type=Path,required=True)
    parser.add_argument('--port',type=int,required=True)
    parser.add_argument('--effects',choices=['full','moderate'],default='full')
    args=parser.parse_args()
    sys.path.insert(0,str(args.root))
    os.environ['QTWEBENGINE_REMOTE_DEBUGGING']=f'127.0.0.1:{args.port}'
    from PySide6.QtCore import QSettings, QTimer, Qt
    from PySide6.QtWidgets import QApplication
    from yingxu.web_ui.native_window import NativeWindow, configure_graphics
    from yingxu.web_ui.resources import register_scheme
    from yingxu.web_ui.embedded_settings import EmbeddedSettings
    from yingxu.operations import HistoryStore
    configure_graphics();register_scheme();app=QApplication([])
    args.profile.mkdir(parents=True,exist_ok=True)
    settings=QSettings(str(args.profile/'appearance.ini'),QSettings.IniFormat)
    settings.setValue('appearance/v1',json.dumps({'theme':'dark','nativeHdr':True,'strength':'enhanced',
        'mistEnabled':args.effects=='full','particlesEnabled':args.effects=='full'}))
    embedded=QSettings(str(args.profile/'embedded.ini'),QSettings.IniFormat)
    embedded.setValue('subtitles/embedded/v1',json.dumps({'enabled':False,'language':'chinese'}))
    window=NativeWindow(appearance_settings=settings,history=HistoryStore(args.profile/'history.jsonl'))
    window.bridge.service.embedded_settings=EmbeddedSettings(embedded)
    window.bridge.service.accept_folder(args.folder)
    window.setFlags(window.flags()|Qt.WindowType.WindowStaysOnTopHint)
    window.resize(1280,860);window.show();window.requestActivate()
    closing=threading.Event()
    def read():sys.stdin.buffer.read(1);closing.set()
    threading.Thread(target=read,daemon=True).start()
    timer=QTimer();timer.setInterval(50);timer.timeout.connect(lambda:window.close() if closing.is_set() else None);timer.start()
    print(json.dumps({'type':'window','handle':str(int(window.winId()))}),flush=True)
    return app.exec()


if __name__=='__main__':sys.exit(main())
