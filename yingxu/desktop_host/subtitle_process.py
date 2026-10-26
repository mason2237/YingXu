"""Private native subtitle window; remote pages have no channel to this pipe.

Reuses the existing search/download UI and validators in a separate process.
Only the headless workspace service may import candidates or rename media.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import threading

from PySide6.QtCore import QObject, QSettings, Signal, Slot, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from ..web_ui.resources import register_scheme
from ..web_ui.subtitle_browser import SubtitleBrowser
from ..web_ui.typography import ui_font
from .stdio import frames


class Browser(SubtitleBrowser):
    def __init__(self, owner):
        self.owner = owner
        super().__init__(download_root=owner.profile / 'subtitle-inbox',
                         settings=QSettings(str(owner.profile / 'online.ini'), QSettings.IniFormat))
        self.workspace_button.show();self.history_button.show();self.appearance_button.show()
        # Additional videos must enter through the workspace's native scan boundary.
        self.add_button.hide()
        self.download_staged.connect(lambda receipt: owner.send({
            'type': 'staged', 'receipt': receipt, 'inbox': str(self.inbox)}))
        self.import_requested.connect(lambda ids: owner.send({
            'type': 'import', 'ids': ids, 'scanId': self.workspace_context[0],
            'automatic': not self.return_after_import}))
        self.review_requested.connect(lambda: self.open_workspace_dialog(None))
        self.destroyed.connect(lambda _obj=None, ref=self: owner.clear_browser(ref))

    def open_workspace_dialog(self, identifier):
        if identifier not in {None, 'history-button', 'appearance-button'} or self.import_busy:
            return
        self.hide()
        self.owner.send({'type': 'ui', 'identifier': identifier})

    def change_theme(self):
        super().change_theme()
        self.owner.send({'type': 'appearance', 'theme': self._theme_preference})


class Helper(QObject):
    incoming = Signal(object)

    def __init__(self, profile):
        super().__init__()
        self.profile = profile;self.browser = None;self.appearance = {}
        self.incoming.connect(self.receive)

    def send(self, frame):
        try:
            sys.stdout.write(json.dumps(frame, ensure_ascii=True, allow_nan=False) + '\n')
            sys.stdout.flush()
        except (BrokenPipeError, OSError):
            self.receive({'type': 'shutdown'})

    @Slot(object)
    def receive(self, frame):
        if not isinstance(frame, dict):return
        kind = frame.get('type')
        try:
            if kind == 'open':
                context = tuple(frame['context'])
                if self.browser and self.browser.workspace_context[0] != context[0]:
                    if self.browser.busy_downloads() or self.browser.batch_running or self.browser.import_busy:
                        raise ValueError('旧字幕队列仍在处理，请先停止或完成后再打开新扫描。')
                    self.browser.close();self.browser = None
                if not self.browser:
                    self.browser = Browser(self)
                    icon = Path(sys._MEIPASS)/'subtitle_organizer.ico' if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[2]/'assets/subtitle_organizer.ico'
                    if icon.is_file():self.browser.setWindowIcon(QIcon(str(icon)))
                browser = self.browser;browser.workspace_context = context
                tasks = [{**task, 'video': Path(task['video'])} for task in frame['tasks']]
                count = browser.add_workspace_tasks(tasks)
                self.apply_appearance()
                browser.showNormal();browser.raise_();browser.activateWindow()
                self.send({'type': 'opened', 'requestId': frame['requestId'], 'sessionId': frame['sessionId'],
                           'taskCount': len(browser.tasks), 'added': count,
                           'pid': os.getpid(), 'handle': str(int(browser.winId()))})
            elif kind == 'registered' and self.browser:
                entry = next((v for v in self.browser.downloads.values()
                              if v.get('stagingId') == frame['stagingId']), None)
                if entry is not None:
                    entry['registered'] = not bool(frame.get('error'))
                    if frame.get('error'):entry['import_error'] = frame['error']
                    else:
                        entry['item'].setFlags(entry['item'].flags() | Qt.ItemFlag.ItemIsUserCheckable)
                        entry['item'].setCheckState(Qt.CheckState.Checked)
                    self.browser.update_controls();self.browser.schedule_auto_import()
            elif kind == 'import.finished' and self.browser:
                if frame.get('retry'):
                    for entry in self.browser.downloads.values():
                        if entry.get('stagingId') in frame['ids']:entry['auto_attempted'] = False
                if frame.get('context'):self.browser.workspace_context = tuple(frame['context'])
                self.browser.import_finished(frame.get('result'), frame.get('error', ''))
                if frame.get('result', {}).get('imported') and self.browser.return_after_import:
                    self.browser.open_workspace_dialog(None)
            elif kind == 'idle' and self.browser:self.browser.schedule_auto_import()
            elif kind == 'appearance':
                self.appearance = frame['state'];self.apply_appearance()
            elif kind == 'shutdown':
                if self.browser:
                    self.browser.import_busy = False;self.browser.close()
                QApplication.instance().quit()
        except (KeyError, TypeError, ValueError, OSError) as error:
            self.send({'type': 'error', 'requestId': frame.get('requestId'),
                       'sessionId': frame.get('sessionId'), 'message': str(error)})

    def apply_appearance(self):
        if self.browser and self.appearance:
            self.browser._theme_preference = self.appearance['theme']
            self.browser.set_theme(self.appearance['resolvedTheme'], self.appearance['lighting'])

    def clear_browser(self, browser):
        if self.browser is browser:
            self.browser = None
            QApplication.instance().quit()

    def read(self):
        for frame in frames(4 * 1024 * 1024):self.incoming.emit(frame)
        self.incoming.emit({'type': 'shutdown'})


def main():
    parser = argparse.ArgumentParser();parser.add_argument('--profile', type=Path, required=True)
    args = parser.parse_args();args.profile.mkdir(parents=True, exist_ok=True)
    register_scheme()
    app = QApplication([]);app.setQuitOnLastWindowClosed(False)
    app.setApplicationName('映序');app.setStyle('Fusion');app.setFont(ui_font())
    helper = Helper(args.profile.resolve())
    threading.Thread(target=helper.read, daemon=True, name='desktop-parent').start()
    helper.send({'type': 'ready'})
    return app.exec()


if __name__ == '__main__':sys.exit(main())
