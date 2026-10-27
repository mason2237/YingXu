"""Durable per-item intentions, one-use consent and append-only transition evidence."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from secrets import compare_digest, token_urlsafe
import sqlite3
from threading import RLock
from uuid import uuid4

from ..domain.errors import ProtocolError
from ..domain.operations import MoveStep, RunPhase, canonical, checksum, validate_intent
from .sqlite_workflow_store import storage_boundary


def now():
    return datetime.now(timezone.utc).isoformat()


class ProfileLease:
    """An OS-held lock, released by process death; never steal a stale PID lock."""
    def __init__(self, path):
        self.stream = Path(path).open('a+b', buffering=0)
        try:
            if self.stream.seek(0, 2) == 0:
                self.stream.write(b'\0')
            self.stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self.stream.close()
            raise ProtocolError('PROFILE_IN_USE', '这个数据目录已有映序在使用，请先关闭另一个窗口。') from error

    def close(self):
        if not self.stream.closed:
            self.stream.close()


class SQLiteOperationJournal:
    @storage_boundary
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lease = ProfileLease(self.root / 'profile.lock')
        self.lock = RLock()
        self.closed = False
        self.buffer_root = self.root / 'buffers'
        self.connection = None
        try:
            self.buffer_root.mkdir(exist_ok=True)
            self.connection = sqlite3.connect(self.root / 'journal.sqlite3', isolation_level=None,
                                               check_same_thread=False, timeout=5)
            version = self.connection.execute('PRAGMA user_version').fetchone()[0]
            tables = {row[0] for row in self.connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            if version not in {0, 1} or (version == 0 and tables):
                raise ProtocolError('UNSUPPORTED_JOURNAL', '操作日志版本不受支持，未自动重建。')
            if self.connection.execute('PRAGMA journal_mode=WAL').fetchone()[0].lower() != 'wal':
                raise ProtocolError('UNSUPPORTED_JOURNAL', '操作日志需要本地 WAL 存储。')
            self.connection.execute('PRAGMA synchronous=FULL')
            self.connection.execute('PRAGMA foreign_keys=ON')
            with self.transaction():
                if version == 0:
                    self.connection.execute('CREATE TABLE runs(id TEXT PRIMARY KEY, phase TEXT NOT NULL, created TEXT NOT NULL, body TEXT NOT NULL)')
                    self.connection.execute('CREATE TABLE items(run_id TEXT NOT NULL REFERENCES runs(id), n INTEGER NOT NULL, action TEXT NOT NULL, step TEXT NOT NULL, error TEXT NOT NULL, spec_hash TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(run_id,n))')
                    self.connection.execute('CREATE TABLE events(seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, item_n INTEGER, kind TEXT NOT NULL, time TEXT NOT NULL, body TEXT NOT NULL)')
                    self.connection.execute('CREATE INDEX run_phase ON runs(phase)')
                    self.connection.execute('PRAGMA user_version=1')
                elif tables != {'runs', 'items', 'events'}:
                    raise ProtocolError('CORRUPT_JOURNAL', '操作日志结构不一致，未自动修改。')
        except BaseException:
            if self.connection is not None:
                self.connection.close()
            self.lease.close()
            self.closed = True
            raise

    @contextmanager
    def transaction(self):
        with self.lock:
            if self.closed:
                raise ProtocolError('JOURNAL_CLOSED', '操作日志已关闭。')
            self.connection.execute('BEGIN IMMEDIATE')
            try:
                yield
                self.connection.commit()
            except BaseException:
                self.connection.rollback()
                raise

    def _event(self, run_id, kind, data, index=None):
        self.connection.execute('INSERT INTO events(run_id,item_n,kind,time,body) VALUES(?,?,?,?,?)',
                                (run_id, index, kind, now(), canonical(data)))

    def _put_run(self, record):
        self.connection.execute('UPDATE runs SET phase=?,body=? WHERE id=?',
                                (record['phase'], canonical(record), record['id']))

    @storage_boundary
    def create(self, specs, context, *, kind='apply', parent_id=None):
        if kind not in {'apply', 'undo'}:
            raise ProtocolError('INVALID_REQUEST', '未知文件任务类型。')
        specs = [validate_intent(spec) for spec in specs]
        record = {'id': uuid4().hex, 'snapshot_id': uuid4().hex, 'kind': kind,
                  'phase': RunPhase.PREVIEW.value, 'created': now(), 'started': '', 'finished': '',
                  'context': context, 'digest': checksum(specs), 'revision': 0, 'parent_id': parent_id,
                  'undo_child': None, 'message': '', 'ticket': None, 'approved': {}, 'checked': ''}
        with self.transaction():
            if parent_id:
                parent = self.run(parent_id)
                if parent['kind'] != 'apply' or parent['undo_child']:
                    raise ProtocolError('UNDO_ALREADY_STARTED', '这份记录已提交撤销，请查看对应撤销任务。')
            self.connection.execute('INSERT INTO runs VALUES(?,?,?,?)',
                                    (record['id'], record['phase'], record['created'], canonical(record)))
            for index, spec in enumerate(specs):
                item = {'n': index, 'spec': spec, 'step': MoveStep.PENDING.value, 'mode': '',
                        'buffer': None, 'buffer_owned': None, 'buffer_version': None,
                        'temp': None, 'temp_owned': None, 'temp_version': None, 'post_version': None,
                        'retained': [], 'error': '', 'error_code': '', 'observed': {}}
                self.connection.execute('INSERT INTO items VALUES(?,?,?,?,?,?,?)',
                    (record['id'], index, spec['action'], item['step'], '', checksum(spec), canonical(item)))
            self._event(record['id'], 'plan.persisted', {'digest': record['digest'], 'items': len(specs)})
        return record['id']

    @storage_boundary
    def run(self, run_id):
        with self.lock:
            row = self.connection.execute('SELECT phase,body FROM runs WHERE id=?', (run_id,)).fetchone()
            if row is None:
                raise ProtocolError('NOT_FOUND', '操作记录不存在。')
            try:
                value = json.loads(row[1])
                if value['id'] != run_id or value['phase'] != row[0]:
                    raise ValueError('Identity mismatch')
                RunPhase(value['phase'])
                return value
            except (ValueError, KeyError, TypeError) as error:
                raise ProtocolError('CORRUPT_JOURNAL', '操作日志内容无效，文件保持原样。') from error

    def referenced_paths(self):
        """Conservative retention: all fixed plans, including undo, keep references."""
        with self.lock:
            paths = []
            for (identifier,) in self.connection.execute('SELECT id FROM runs'):
                _run, items = self.bundle(identifier)
                for item in items:
                    for key in ('source', 'target'):
                        if item['spec'].get(key):
                            paths.append(item['spec'][key])
                    for key in ('buffer', 'temp'):
                        if item.get(key):
                            paths.append(item[key])
            return paths

    def _item(self, row):
        try:
            value = json.loads(row[3])
            validate_intent(value['spec'])
            MoveStep(value['step'])
            if (value['step'], value['error'], checksum(value['spec'])) != row[:3]:
                raise ValueError('Item index mismatch')
            return value
        except (ValueError, TypeError, KeyError) as error:
            raise ProtocolError('CORRUPT_JOURNAL', '逐项日志无效，未自动修改文件。') from error

    @storage_boundary
    def bundle(self, run_id):
        with self.lock:
            run = self.run(run_id)
            items = [self._item(row) for row in self.connection.execute(
                'SELECT step,error,spec_hash,body FROM items WHERE run_id=? ORDER BY n', (run_id,))]
            if checksum([item['spec'] for item in items]) != run['digest']:
                raise ProtocolError('CORRUPT_JOURNAL', '固定计划与日志摘要不一致，未自动处理。')
            return run, items

    @storage_boundary
    def item(self, run_id, index):
        with self.lock:
            row = self.connection.execute('SELECT step,error,spec_hash,body FROM items WHERE run_id=? AND n=?', (run_id, index)).fetchone()
            if row is None:
                raise ProtocolError('NOT_FOUND', '逐项日志不存在。')
            return self._item(row)

    @storage_boundary
    def update_item(self, run_id, index, **changes):
        allowed = {'step', 'mode', 'buffer', 'buffer_owned', 'buffer_version', 'temp', 'temp_owned',
                   'temp_version', 'post_version', 'retained', 'error', 'error_code', 'observed'}
        if changes.keys() - allowed:
            raise ProtocolError('INVALID_TRANSITION', '不能更改已经冻结的文件意图。')
        if 'step' in changes:
            MoveStep(changes['step'])
        with self.transaction():
            item = self.item(run_id, index)
            item.update(changes)
            self.connection.execute('UPDATE items SET step=?,error=?,body=? WHERE run_id=? AND n=?',
                                    (item['step'], item['error'], canonical(item), run_id, index))
            self._event(run_id, 'item.' + item['step'], changes, index)
        return item

    @storage_boundary
    def update_run(self, run_id, **changes):
        if changes.keys() - {'phase', 'message', 'finished', 'checked', 'approved'}:
            raise ProtocolError('INVALID_TRANSITION', '不能更改固定任务身份。')
        if 'phase' in changes:
            RunPhase(changes['phase'])
        with self.transaction():
            value = self.run(run_id)
            value.update(changes)
            value['revision'] += 1
            self._put_run(value)
            self._event(run_id, 'run.' + value['phase'], changes)
        return value

    @storage_boundary
    def issue_ticket(self, run_id, session_id, purpose, observations):
        if purpose not in {'execute', 'resume', 'undo'}:
            raise ProtocolError('INVALID_REQUEST', '确认用途无效。')
        token = token_urlsafe(32)
        with self.transaction():
            value = self.run(run_id)
            if value['phase'] in {'running', 'completed', 'invalidated'} or value['undo_child']:
                raise ProtocolError('STALE_PLAN', '任务状态已变化，请重新核对。')
            value['revision'] += 1
            value['ticket'] = {'hash': hashlib.sha256(token.encode()).hexdigest(), 'session': session_id,
                               'purpose': purpose, 'revision': value['revision'], 'used': False}
            value['approved'] = observations
            self._put_run(value)
            self._event(run_id, 'consent.issued', {'purpose': purpose, 'revision': value['revision']})
        return token

    @storage_boundary
    def claim(self, run_id, session_id, token, *, acknowledged, purposes=('execute', 'resume', 'undo')):
        if acknowledged is not True:
            raise ProtocolError('CONFIRMATION_REQUIRED', '请先核对原位置、目标和提示，并勾选确认。')
        if not isinstance(token, str):
            raise ProtocolError('STALE_PLAN', '确认凭证无效。')
        with self.transaction():
            value = self.run(run_id)
            ticket = value['ticket']
            if ticket and ticket['used']:
                raise ProtocolError('TOKEN_USED', '这份计划已经提交，不会重复执行。')
            if (not ticket or ticket['session'] != session_id or ticket['revision'] != value['revision'] or
                    ticket['purpose'] not in purposes or not compare_digest(ticket['hash'], hashlib.sha256(token.encode()).hexdigest())):
                raise ProtocolError('STALE_PLAN', '页面或预览凭证已失效，请重新预览。')
            if value['phase'] in {'running', 'completed', 'invalidated'} or value['undo_child']:
                raise ProtocolError('STALE_PLAN', '此任务不再接受确认。')
            if self.connection.execute("SELECT id FROM runs WHERE phase='running' AND id<>?", (run_id,)).fetchone():
                raise ProtocolError('BUSY', '另一个文件任务尚未结束。')
            if value['parent_id']:
                parent = self.run(value['parent_id'])
                if parent['undo_child'] and parent['undo_child'] != run_id:
                    raise ProtocolError('UNDO_ALREADY_STARTED', '原任务已经提交其他撤销。')
                parent['undo_child'] = run_id
                parent['revision'] += 1
                parent['ticket'] = None
                self._put_run(parent)
            value['ticket']['used'] = True
            value['phase'] = 'running'
            value['started'] = value['started'] or now()
            value['finished'] = ''
            value['message'] = ''
            value['revision'] += 1
            self._put_run(value)
            self._event(run_id, 'consent.consumed', {'purpose': ticket['purpose']})
        return value

    @storage_boundary
    def expire_tickets(self):
        with self.transaction():
            rows = list(self.connection.execute('SELECT id FROM runs'))
            for (identifier,) in rows:
                value = self.run(identifier)
                if value['ticket'] and not value['ticket']['used']:
                    value['ticket'] = None
                    value['revision'] += 1
                    self._put_run(value)

    @storage_boundary
    def interrupt_running(self):
        with self.transaction():
            values = list(self.connection.execute("SELECT id FROM runs WHERE phase='running'"))
            for (identifier,) in values:
                value = self.run(identifier)
                value.update(phase='interrupted', ticket=None, message='上次执行未完成，等待核对；不会自动继续。')
                value['revision'] += 1
                self._put_run(value)
                self._event(identifier, 'run.interrupted', {})
            return len(values)

    @storage_boundary
    def pending_ids(self):
        with self.lock:
            values = [self.run(row[0]) for row in self.connection.execute(
                "SELECT id FROM runs WHERE phase IN ('interrupted','partial','cancelled') ORDER BY created")]
            return [value['id'] for value in values if value['undo_child'] is None]

    @storage_boundary
    def history(self, limit=30):
        with self.lock:
            values = [self.run(row[0]) for row in self.connection.execute(
                'SELECT id FROM runs ORDER BY created DESC')]
            pending = set(self.pending_ids())
            values.sort(key=lambda value: (value['id'] in pending, value['created']), reverse=True)
            return [value for value in values if value['started']][:limit]

    @storage_boundary
    def page(self, run_id, offset=0, limit=20):
        with self.lock:
            return [self._item(row) for row in self.connection.execute(
                'SELECT step,error,spec_hash,body FROM items WHERE run_id=? ORDER BY n LIMIT ? OFFSET ?',
                (run_id, limit, offset))]

    @storage_boundary
    def counts(self, run_id):
        from ..domain.operations import status_for
        with self.lock:
            phase = self.run(run_id)['phase']
            counts = {}
            for action, step, error, count in self.connection.execute(
                    'SELECT action,step,error,count(*) FROM items WHERE run_id=? GROUP BY action,step,error', (run_id,)):
                status = status_for({'spec': {'action': action}, 'step': step, 'error': error}, phase)
                counts[status] = counts.get(status, 0) + count
            return counts

    @storage_boundary
    def close(self):
        with self.lock:
            if not self.closed:
                try:
                    self.connection.close()
                finally:
                    self.closed = True
                    self.lease.close()
