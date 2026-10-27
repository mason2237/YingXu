"""Real v2 stdio and filesystem use cases in a Python -S process."""
import json
import os
from pathlib import Path
from queue import Queue
import subprocess
import sys
import tempfile
from threading import Thread
import time
import unittest
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]


class Client:
    def __init__(self, profile, runtime=None):
        program = str(runtime or os.environ.get('YINGXU_TEST_BACKEND') or sys.executable)
        entry = ['--desktop-backend'] if Path(program).name == 'YingXuBackend.exe' else ['-S', '-u', '-m', 'yingxu.desktop.host']
        self.process = subprocess.Popen([program, *entry, '--profile', str(profile)], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding='utf8', env={**os.environ, 'PYTHONUTF8': '1'},
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.queue = Queue()
        self.events = []
        self.max_bytes = 0
        def read():
            for line in self.process.stdout:
                self.max_bytes = max(self.max_bytes, len(line.rstrip('\n').encode('utf8')))
                self.queue.put(json.loads(line))
        Thread(target=read, daemon=True).start()
        self.ready = self.queue.get(timeout=10)
        self.sid = self.call('app.hello')['sessionId']
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            state=self.call('app.state')
            if not state['busy'] or state.get('job',{}).get('kind') not in {'restore','reconcile'}:break
            time.sleep(.01)

    def feed(self, value):
        self.process.stdin.write(json.dumps({'v': 2, **value}, ensure_ascii=False) + '\n')
        self.process.stdin.flush()

    def wait(self, predicate):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            frame = self.queue.get(timeout=max(.01, deadline - time.monotonic()))
            self.events.append(frame)
            if predicate(frame):
                return frame
        raise TimeoutError('No expected v2 response')

    def send(self, action, params=None):
        rid = uuid4().hex
        self.feed({'type': 'request', 'requestId': rid, 'sessionId': None if action == 'app.hello' else getattr(self, 'sid', None),
                   'action': action, 'params': params or {}})
        return rid

    def response(self, rid):
        frame = self.wait(lambda value: value.get('type') == 'reply' and value.get('requestId') == rid)
        if not frame['ok']:
            raise RuntimeError(json.dumps(frame['error'], ensure_ascii=False))
        return frame['data']

    def call(self, action, params=None):
        return self.response(self.send(action, params))

    def choose(self, folder):
        rid = self.send('folder.choose')
        frame = self.wait(lambda value: value.get('type') == 'native' and value['requestId'] == rid)
        self.feed({'type': 'native.result', 'requestId': rid, 'sessionId': self.sid, 'action': frame['action'], 'path': str(folder)})
        return self.response(rid)

    def job(self, action, params=None):
        job_id = self.call(action, params)['jobId']
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            state = self.call('app.state')
            if not state['busy'] and state['job']['jobId'] == job_id:
                if state['job']['status'] != 'completed':
                    raise RuntimeError(str(state['job']))
                value = self.call('job.result', {'jobId': job_id})
                return value['value'] if value['shape'] == 'value' else value
            time.sleep(.01)
        raise TimeoutError('Task did not finish')

    def close(self):
        if self.process.stderr.closed:
            return
        if self.process.poll() is None:
            self.feed({'type': 'shutdown'})
            self.process.wait(timeout=15)
        error = self.process.stderr.read()
        self.process.stdin.close()
        self.process.stdout.close()
        self.process.stderr.close()
        if self.process.returncode or error:
            raise AssertionError(f'Host exit={self.process.returncode}: {error}')


class NoQtHostIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='noqt-host-', dir=ROOT / 'work/test-results')
        self.root = Path(self.temp.name)
        self.media = self.root / '中文视频'
        self.media.mkdir()
        self.client = Client(self.root / 'profile')
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.client.close)

    def prepare(self, count=3):
        for index in range(count):
            (self.media / f'Atlas.S01E{index+1:03}.1080p.mkv').write_bytes(b'unchanged video')
        (self.media / 'Atlas.S01E001.chs.srt').write_text('subtitle', encoding='utf8')
        (self.media / 'Spare.S09E099.eng.srt').write_text('manual candidate', encoding='utf8')
        self.client.choose(self.media)
        self.client.call('embedded.configure', {'enabled': False, 'language': 'chinese'})
        state = self.client.call('app.state')
        self.client.job('scan.start', {'folderId': state['summary']['folderId'], 'recursive': True, 'move': False})
        summary = self.client.call('app.state')['summary']
        return {'scanId': summary['scanId'], 'revision': summary['revision']}

    def test_real_scan_manual_review_preview_and_no_unconfirmed_execution(self):
        context = self.prepare()
        before = {path.name: path.read_bytes() for path in self.media.iterdir()}
        self.assertFalse(self.client.ready['qtImported'])
        self.assertEqual(self.client.ready['runtime'], 'python-stdlib')
        candidates = self.client.job('review.candidates', {**context, 'rowId': 'video-2', 'limit': 6})
        spare = next(row for row in candidates['entries'] if row['name'].startswith('Spare'))
        self.client.job('review.assign', {**context, 'rowId': 'video-2', 'subtitleId': spare['subtitleId']})
        summary = self.client.call('app.state')['summary']
        context = {'scanId': summary['scanId'], 'revision': summary['revision']}
        self.assertEqual(self.client.call('review.details', {**context, 'rowId': 'video-2'})['state'], '需确认')
        self.client.job('review.confirm', {**context, 'rowId': 'video-2'})
        summary = self.client.call('app.state')['summary']
        context['revision'] = summary['revision']
        plan = self.client.job('preview.create', context)
        self.assertEqual(plan['changeCount'], 2)
        self.assertTrue(plan['canExecute'])
        page = self.client.call('preview.query', {'snapshotId': plan['snapshotId'], 'limit': 20})
        self.assertEqual(len(page['items']), 3)
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.media.iterdir()})
        self.assertLessEqual(self.client.max_bytes, 8192)

    def test_large_review_is_paged_without_losing_ids(self):
        context = self.prepare(300)
        offset, ids, rows = 0, [], []
        while offset < 300:
            page = self.client.call('review.query', {**context, 'offset': offset, 'limit': 200, 'includeIds': False})
            rows.extend(page['rows'])
            offset = page['nextOffset'] or 300
        offset = 0
        while offset < 300:
            page = self.client.call('review.ids', {**context, 'offset': offset, 'limit': 200})
            ids.extend(page['ids'])
            offset += len(page['ids'])
        self.assertEqual(len(rows), 300)
        self.assertEqual(len(set(ids)), 300)
        self.assertEqual({row['rowId'] for row in rows}, set(ids))
        self.assertLessEqual(self.client.max_bytes, 8192)

    def test_confirmed_execute_restart_history_and_undo(self):
        context = self.prepare(1)
        before = {path.name: path.read_bytes() for path in self.media.iterdir()}
        plan = self.client.job('preview.create', context)
        params = {'scanId': context['scanId'], 'reviewRevision': context['revision'],
                  'snapshotId': plan['snapshotId'], 'confirmationToken': plan['confirmationToken'], 'acknowledged': False}
        with self.assertRaisesRegex(RuntimeError, 'CONFIRMATION_REQUIRED'):
            self.client.call('organize.confirmAndStart', params)
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.media.iterdir()})
        params['acknowledged'] = True
        result = self.client.job('organize.confirmAndStart', params)
        record = self.client.call('result.get', {'batchId': result['batchId']})
        self.assertEqual(record['success'], 1)
        with self.assertRaisesRegex(RuntimeError, 'STALE_PLAN'):
            self.client.call('organize.confirmAndStart', params)
        self.client.close()
        self.client = Client(self.root / 'profile')
        self.addCleanup(self.client.close)
        records = self.client.job('history.list')
        self.assertEqual(records['entries'][0]['recordId'], result['batchId'])
        undo = self.client.job('operation.undoPreview', {'runId': result['batchId']})
        self.assertTrue(undo['canExecute'])
        self.client.job('operation.confirm', {'runId': undo['runId'], 'snapshotId': undo['snapshotId'],
            'confirmationToken': undo['confirmationToken'], 'acknowledged': True})
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.media.iterdir()})
        self.assertTrue(self.client.call('history.get', {'recordId': result['batchId']})['undone'])
        self.assertLessEqual(self.client.max_bytes, 8192)

    def test_browser_results_are_validated_and_stale_context_cannot_associate(self):
        context = self.prepare()
        self.client.call('subtitle.open', context)
        task = self.client.call('online.query')['tasks'][0]
        self.assertEqual(task['query'], 'Atlas')
        self.client.call('online.start', {'taskId': task['taskId'], 'query': 'Atlas', 'provider': 'subhd'})
        search = next(frame for frame in reversed(self.client.events) if frame.get('type') == 'browser.search')
        raw = json.dumps({'status': 'ready', 'rows': [
            {'url': 'file:///C:/malicious.srt', 'title': 'Invalid', 'release': 'Invalid', 'metadata': ''},
            {'url': 'https://subhd.me/a/TEST123', 'title': 'Atlas', 'release': 'Atlas S01E002', 'metadata': '简体 英语 双语'}]})
        self.client.feed({'type': 'browser.result', 'taskId': task['taskId'], 'effectId': search['effectId'],
                          'generation': search['generation'], 'status': 'results', 'raw': raw, 'final': True})
        result = self.client.call('online.candidates', {'taskId': task['taskId']})
        self.assertEqual(result['total'], 1)
        self.assertNotIn('url', result['rows'][0])
        self.client.call('online.openCandidate', {'taskId': task['taskId'], 'candidateId': result['rows'][0]['candidateId']})
        opened = next(frame for frame in reversed(self.client.events) if frame.get('type') == 'browser.open')
        self.assertEqual(opened['url'], 'https://subhd.me/a/TEST123')
        self.client.job('review.skip', {**context, 'rowId': 'video-3', 'skipped': True})
        self.client.feed({'type': 'browser.result', 'taskId': task['taskId'], 'effectId': search['effectId'],
                          'generation': search['generation'], 'status': 'results', 'raw': raw, 'final': True})
        self.assertEqual(self.client.call('online.query')['total'], 0)

    def test_pythonw_uses_inherited_pipes_and_exits_cleanly(self):
        runtime = Path(sys.executable).with_name('pythonw.exe')
        if not runtime.exists():
            self.skipTest('Windows pythonw is unavailable')
        other = Client(self.root / 'windowless', runtime=runtime)
        self.assertFalse(other.ready['qtImported'])
        other.close()

    def test_embedded_language_satisfied_skips_search_without_extracting(self):
        from tests.media_fixtures import mkv
        mkv(self.media / '中文电影.mkv', [('zho', '简体中文', False)])
        mkv(self.media / 'English.mkv', [('eng', 'English', False)])
        before = {path.name: path.read_bytes() for path in self.media.iterdir()}
        self.client.choose(self.media)
        folder = self.client.call('app.state')['summary']['folderId']
        self.client.job('scan.start', {'folderId': folder, 'recursive': True, 'move': False})
        summary = self.client.call('app.state')['summary']
        context = {'scanId': summary['scanId'], 'revision': summary['revision']}
        rows = self.client.call('review.query', context)['rows']
        chinese = next(row for row in rows if row['video']['name'] == '中文电影.mkv')
        self.assertTrue(chinese['embeddedSatisfied'])
        self.assertEqual(chinese['subtitles'], [])
        self.assertEqual(summary['embeddedSatisfiedCount'], 1)
        with self.assertRaisesRegex(RuntimeError, 'ALREADY_SATISFIED'):
            self.client.call('subtitle.open', {**context, 'rowId': chinese['rowId']})
        self.assertEqual(self.client.call('subtitle.open', context)['taskCount'], 1)
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.media.iterdir()})

    def test_conflict_after_scan_blocks_preview_and_preserves_existing_file(self):
        context = self.prepare()
        occupied = self.media / 'Atlas.S01E001.1080p.chs.srt'
        occupied.write_bytes(b'preserve existing content')
        with self.assertRaisesRegex(RuntimeError, 'STALE_PLAN'):
            self.client.job('preview.create', context)
        self.assertEqual(occupied.read_bytes(), b'preserve existing content')


if __name__ == '__main__':
    unittest.main()
