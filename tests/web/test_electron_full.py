"""Full stdio host retains the original one-use consent and import boundaries."""
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from uuid import uuid4
import zipfile

from PySide6.QtCore import QCoreApplication, QSettings
from PySide6.QtTest import QTest

from yingxu.desktop_host.backend import Host

ROOT = Path(__file__).resolve().parents[2]


class FullHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'work/test-results', prefix='electron-full-')
        self.root = Path(self.temp.name);self.media = self.root/'中文 视频';self.media.mkdir()
        profile = self.root/'profile';profile.mkdir()
        settings = QSettings(str(profile/'embedded.ini'), QSettings.IniFormat)
        settings.setValue('subtitles/embedded/v1', json.dumps({'enabled': False, 'language': 'chinese'}));settings.sync()
        self.host = Host(profile, preview=False);self.frames = [];self.host.send = self.frames.append
        self.service = self.host.bridge.service
        self.sid = self.send('app.hello')['data']['sessionId']

    def tearDown(self):
        self.idle();self.host.online.shutdown();self.temp.cleanup()

    def send(self, action, params=None, rid=None):
        self.host.receive({'type': 'request', 'raw': json.dumps({'v': 1, 'requestId': rid or uuid4().hex,
            'sessionId': None if action == 'app.hello' else self.sid, 'action': action, 'params': params or {}})})
        return json.loads(next(frame['raw'] for frame in reversed(self.frames) if frame['type'] == 'reply'))

    def idle(self):
        for _ in range(2000):
            if self.service.worker is None:return
            QTest.qWait(5)
        self.fail('Worker timeout')

    def task(self, action, params=None):
        reply = self.send(action, params);self.assertTrue(reply['ok'], reply);self.idle()
        self.assertEqual(self.service.job['status'], 'completed', self.service.job)
        return self.service.job['result']

    def context(self, **extra):
        return {'scanId': self.service.data.scan_id, 'revision': self.service.revision, **extra}

    def scan(self, *, subtitles=True):
        (self.media/'映序.S01E01.2160p.mkv').write_bytes(b'unchanged video')
        if subtitles:(self.media/'映序.S01E01.chs.srt').write_text('1\n00:00:01,000 --> 00:00:02,000\n字幕\n', encoding='utf8')
        self.host.receive({'type': 'folder.drop', 'path': str(self.media)})
        self.task('scan.start', {'folderId': self.service.folder_id, 'recursive': True, 'move': False})

    def preview(self):
        for row in list(self.service.data.rows):
            if row['state'] == '需确认':self.task('review.confirm', self.context(rowId=row['rowId']))
        return self.task('preview.create', self.context())

    @staticmethod
    def consent(plan):
        return {'scanId': plan['scanId'], 'reviewRevision': plan['revision'], 'snapshotId': plan['snapshotId'],
                'confirmationToken': plan['confirmationToken'], 'acknowledged': True}

    def test_confirmed_execution_once_and_exclusive_native_export(self):
        self.scan();before = {p.name: p.read_bytes() for p in self.media.iterdir()}
        plan = self.preview();self.assertEqual(before, {p.name: p.read_bytes() for p in self.media.iterdir()})
        params = self.consent(plan)
        self.assertFalse(self.send('organize.confirmAndStart', {**params, 'acknowledged': False})['ok'])
        rid = uuid4().hex;first = self.send('organize.confirmAndStart', params, rid)
        self.assertTrue(first['ok']);self.assertEqual(first, self.send('organize.confirmAndStart', params, rid));self.idle()
        self.assertEqual(self.send('organize.confirmAndStart', params)['error']['code'], 'TOKEN_USED')
        self.assertEqual(len(self.service.history.recent()), 1)
        self.assertEqual(self.service.record_page(self.service.last_result_id)['success'], 1)
        self.assertEqual((self.media/'映序.S01E01.2160p.mkv').read_bytes(), b'unchanged video')
        export = self.root/'记录.json'
        for i in range(2):
            export_rid = uuid4().hex
            self.send('result.export', {'recordId': self.service.last_result_id}, export_rid)
            native = next(frame for frame in reversed(self.frames) if frame['type'] == 'native')
            self.assertEqual(native['action'], 'result.export')
            self.host.receive({'type': 'native.result', 'action': 'result.export', 'requestId': export_rid,
                               'sessionId': self.sid, 'path': str(export)})
            self.idle()
            if i == 0:original = export.read_bytes();self.assertEqual(self.service.job['status'], 'completed')
            else:
                self.assertEqual(self.service.job['error']['code'], 'TARGET_EXISTS')
                self.assertEqual(export.read_bytes(), original)

    def test_reload_and_review_mutation_revoke_old_preview(self):
        self.scan();plan = self.preview();row = self.service.data.rows[0]
        self.task('review.skip', self.context(rowId=row['rowId'], skipped=True))
        self.assertFalse(self.send('organize.confirmAndStart', self.consent(plan))['ok'])
        self.task('review.skip', self.context(rowId=row['rowId'], skipped=False))
        plan = self.preview();self.host.receive({'type': 'reset'})
        self.sid = self.send('app.hello')['data']['sessionId']
        self.assertFalse(self.send('organize.confirmAndStart', self.consent(plan))['ok'])
        self.assertIsNone(self.service.last_result_id)

    def test_conflict_blocks_without_overwrite(self):
        self.scan();plan = self.preview();snapshot = self.service.snapshot
        target = snapshot.changes[0].target;target.write_bytes(b'occupied')
        self.task('organize.confirmAndStart', self.consent(plan))
        self.assertEqual(target.read_bytes(), b'occupied')
        self.assertTrue(snapshot.changes[0].source.exists())
        self.assertEqual(self.service.record_page(self.service.last_result_id)['errors'], 1)

    def test_native_staging_auto_preparation_preserves_media(self):
        self.scan(subtitles=False);before = {p.name: p.read_bytes() for p in self.media.iterdir()}
        controller = self.host.online;messages = [];controller.send = messages.append
        inbox = controller.profile/'subtitle-inbox'/'session';directory = inbox/'download';directory.mkdir(parents=True)
        archive = directory/'字幕.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('映序.S01E01.chs.srt', '1\n00:00:01,000 --> 00:00:02,000\n字幕\n')
        receipt = {'status': 'archive_pending', 'stagingId': uuid4().hex, 'stagingPath': str(archive),
                   'scanId': self.service.data.scan_id, 'rowId': self.service.data.rows[0]['rowId']}
        controller.receive({'type': 'staged', 'receipt': receipt, 'inbox': str(inbox)})
        self.assertFalse(messages[-1]['error'])
        controller.receive({'type': 'import', 'ids': [receipt['stagingId']], 'scanId': receipt['scanId'], 'automatic': True})
        self.idle()
        self.assertEqual(self.service.job['status'], 'completed', self.service.job)
        self.assertGreater(self.service.job['result']['imported'], 0)
        self.assertEqual(self.service.data.rows[0]['state'], '需确认')
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.media.iterdir()})
        self.assertTrue(any(frame['type'] == 'import.finished' for frame in messages))
        controller.receive({'type': 'import', 'ids': [receipt['stagingId']], 'scanId': 'stale', 'automatic': True})
        self.assertIn('扫描已变化', messages[-1]['error'])

    def test_stale_helper_response_cannot_clear_another_native_action(self):
        self.service.native_busy = True
        self.host.online.finish_open(None, None, error='invalid')
        self.assertTrue(self.service.native_busy)
        self.host.online.pending['old'] = 'old-session'
        self.host.online.finish_open('old', 'old-session', data={})
        self.assertTrue(self.service.native_busy)
        self.service.native_busy = False

    def test_real_embedded_language_satisfied_skips_online_without_extraction(self):
        from tests.media_fixtures import mkv
        mkv(self.media/'中文.mkv', [('zho', '简体中文', False)])
        mkv(self.media/'English.mkv', [('eng', 'English', False)])
        before = {p.name: p.read_bytes() for p in self.media.iterdir()}
        self.send('embedded.configure', {'enabled': True, 'language': 'chinese'})
        self.service.accept_folder(self.media)
        self.task('scan.start', {'folderId': self.service.folder_id, 'recursive': True, 'move': False})
        good = next(row for row in self.service.data.rows if row['video']['name'] == '中文.mkv')
        self.assertTrue(good['embeddedSatisfied']);self.assertEqual(good['state'], '已符合')
        self.assertEqual([task['video'].name for task in self.service.subtitle_tasks(self.context())], ['English.mkv'])
        reply = self.send('subtitle.open', self.context(rowId=good['rowId']))
        self.assertEqual(reply['error']['code'], 'ALREADY_SATISFIED')
        self.assertIsNone(self.host.online.process)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.media.iterdir()})

    def test_explicit_shutdown_with_stdin_still_open_is_clean(self):
        process = subprocess.Popen([sys.executable, '-u', '-m', 'yingxu.desktop_host.backend', '--full',
            '--profile', str(self.root/'shutdown')], cwd=ROOT, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf8')
        try:
            process.stdin.write(json.dumps({'type': 'shutdown'}) + '\n');process.stdin.flush()
            self.assertEqual(process.wait(timeout=8), 0)
            self.assertEqual(process.stderr.read(), '')
        finally:
            if process.poll() is None:process.kill();process.wait(timeout=5)
            process.stdin.close();process.stdout.close();process.stderr.close()


if __name__ == '__main__':unittest.main()
