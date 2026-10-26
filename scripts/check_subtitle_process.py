"""Async native handoff using a generated ZIP; never contacts a subtitle website."""
import json
from pathlib import Path
import sys
import time
from uuid import uuid4
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSettings, QTimer, Qt
from PySide6.QtWidgets import QApplication, QListWidgetItem
from PySide6.QtWebEngineCore import QWebEngineDownloadRequest, QWebEngineSettings

from yingxu.desktop_host.backend import Host
from yingxu.desktop_host.subtitle_process import Helper
from yingxu.web_ui.resources import register_scheme


def wait(check, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if check():return
        time.sleep(.005)
    raise AssertionError('Native handoff timeout')


def main():
    output = ROOT/'work/test-results'/('electron-b-online-'+uuid4().hex)
    output.mkdir(parents=True);media = output/'视频';media.mkdir()
    video = media/'Atlas.S01E01.2160p.WEB-DL.x265.mkv';video.write_bytes(b'private fixture video')
    profile = output/'profile';profile.mkdir()
    settings = QSettings(str(profile/'embedded.ini'), QSettings.IniFormat)
    settings.setValue('subtitles/embedded/v1', json.dumps({'enabled': False, 'language': 'chinese'}));settings.sync()
    register_scheme();app = QApplication([]);app.setQuitOnLastWindowClosed(False)
    host = Host(profile, preview=False);frames = [];host.send = frames.append
    service = host.bridge.service;service.accept_folder(media)
    service.start_scan({'folderId': service.folder_id, 'recursive': True, 'move': False})
    wait(lambda: service.worker is None)
    helper = Helper(profile);controller = host.online
    # Schedule both directions so registration arrives after finish_download returns,
    # exactly as it does over the private child-process pipes.
    controller.send = lambda frame: QTimer.singleShot(0, lambda value=frame: helper.receive(value))
    helper.send = lambda frame: QTimer.singleShot(0, lambda value=frame: controller.receive(value))
    result = {'passed': False, 'networkRequested': False, 'checks': []}
    try:
        params = {'scanId': service.data.scan_id, 'revision': service.revision}
        tasks = [{**task, 'video': str(task['video'])} for task in service.subtitle_tasks(params)]
        helper.receive({'type': 'appearance', 'state': {'theme': 'dark', 'resolvedTheme': 'dark', 'lighting': 'enhanced'}})
        helper.receive({'type': 'open', 'context': [params['scanId'], params['revision']],
                        'requestId': 'native-open', 'sessionId': 'native-session', 'tasks': tasks})
        browser = helper.browser
        assert browser.page.webChannel() is None
        assert not browser.page.settings().testAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls)
        assert browser.page.chooseFiles(None, [], []) == []
        assert browser.tasks[0].query == 'Atlas', browser.tasks[0].query
        assert browser.page.url().toString() in {'', 'about:blank'}
        result['checks'].append('native_queue_title_only_query_remote_has_no_channel_file_access_or_upload')
        directory = browser.inbox/'generated-download';directory.mkdir(parents=True)
        archive = directory/'字幕.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('Atlas.S01E01.chs.srt', '1\n00:00:01,000 --> 00:00:02,000\n你好 / Hello\n')
        class CompletedDownload:
            def state(self):return QWebEngineDownloadRequest.DownloadCompleted
        item = QListWidgetItem('fixture', browser.download_list);item.setData(Qt.UserRole, 42)
        entry = {'request': CompletedDownload(), 'path': archive, 'item': item, 'finished': False,
                 'reason': '', 'received': archive.stat().st_size,
                 'context': {'scanId': params['scanId'], 'rowId': service.data.rows[0]['rowId'],
                             'videoName': video.name, 'query': browser.tasks[0].query}}
        browser.downloads[42] = entry;browser.download_list.setCurrentItem(item)
        browser.auto_import.setChecked(True)
        browser.finish_download(entry)
        assert not entry.get('registered'), 'Fixture did not exercise asynchronous registration'
        wait(lambda: bool(entry.get('registered')))
        assert item.checkState() == Qt.Checked
        wait(lambda: bool(entry.get('imported')) and service.worker is None)
        assert service.job['kind'] == 'import' and service.job['status'] == 'completed', service.job
        assert service.data.rows[0]['state'] == '需确认'
        assert set(p.name for p in media.iterdir()) == {video.name}
        assert video.read_bytes() == b'private fixture video'
        assert archive.exists()
        result['checks'].append('async_registration_checked_auto_unzip_real_import_pending_review_media_unchanged')
        wait(lambda: not browser.import_busy)
        browser.open_workspace_dialog('history-button');wait(lambda: any(f.get('type') == 'online.ui' for f in frames))
        assert frames[-1]['identifier'] == 'history-button'
        result['checks'].append('return_to_electron_fixed_history_action')
        browser.showNormal();wait(lambda: browser.isVisible())
        app.primaryScreen().grabWindow(int(browser.winId())).save(str(output/'online-import.png'))
        result['passed'] = True
    except Exception as error:
        result['failure'] = repr(error)
        raise
    finally:
        if service.worker:service.worker.stop.set();wait(lambda: service.worker is None)
        helper.receive({'type': 'shutdown'});app.processEvents()
        (output/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
        print(json.dumps({'output': str(output), **result}, ensure_ascii=True))
    return 0


if __name__ == '__main__':sys.exit(main())
