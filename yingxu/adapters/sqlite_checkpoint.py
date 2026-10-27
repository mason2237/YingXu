"""Checksummed, atomic local checkpoints; corruption is never silently reset."""
import hashlib
import json
from pathlib import Path
import sqlite3
from threading import RLock

from ..domain.errors import ProtocolError
from .sqlite_workflow_store import storage_boundary

LIMIT = 16*1024*1024


class SQLiteCheckpoints:
    @storage_boundary
    def __init__(self, path):
        self.lock = RLock()
        self.connection = sqlite3.connect(Path(path), isolation_level=None, check_same_thread=False)
        try:
            version = self.connection.execute('PRAGMA user_version').fetchone()[0]
            tables = {row[0] for row in self.connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            if version not in {0,1} or (version == 0 and tables) or (version == 1 and tables != {'checkpoints'}):
                raise ProtocolError('UNSUPPORTED_CHECKPOINT', '草稿存储版本或结构不受支持，未自动重建。')
            if self.connection.execute('PRAGMA journal_mode=WAL').fetchone()[0].lower() != 'wal':
                raise ProtocolError('UNSUPPORTED_CHECKPOINT', '草稿需要本地 WAL 存储。')
            self.connection.execute('PRAGMA synchronous=FULL')
            self.connection.execute('BEGIN IMMEDIATE')
            self.connection.execute('CREATE TABLE IF NOT EXISTS checkpoints(key TEXT PRIMARY KEY,body TEXT NOT NULL,digest TEXT NOT NULL)')
            self.connection.execute('PRAGMA user_version=1'); self.connection.commit()
        except BaseException:
            self.connection.close(); raise

    @storage_boundary
    def load(self, key):
        with self.lock:
            row = self.connection.execute('SELECT body,digest FROM checkpoints WHERE key=?',(key,)).fetchone()
            if row is None: return None
            raw = row[0].encode('utf8')
            if len(raw)>LIMIT or hashlib.sha256(raw).hexdigest()!=row[1]:
                raise ProtocolError('CORRUPT_CHECKPOINT', '草稿摘要不一致，请保留数据目录。')
            value = json.loads(raw)
            if not isinstance(value,dict) or value.get('v')!=1:
                raise ProtocolError('CORRUPT_CHECKPOINT', '草稿格式无效，未自动修改。')
            return value

    @storage_boundary
    def save(self, key, value):
        raw = json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
        if len(raw.encode('utf8'))>LIMIT:
            raise ProtocolError('CHECKPOINT_TOO_LARGE','草稿超过 16 MiB，未替换之前的检查点。')
        digest = hashlib.sha256(raw.encode('utf8')).hexdigest()
        with self.lock:
            self.connection.execute('BEGIN IMMEDIATE')
            try:
                self.connection.execute('INSERT INTO checkpoints VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET body=excluded.body,digest=excluded.digest',(key,raw,digest))
                self.connection.commit()
            except BaseException:
                self.connection.rollback(); raise

    @storage_boundary
    def clear(self, *keys):
        with self.lock:
            self.connection.execute('BEGIN IMMEDIATE')
            try:
                self.connection.executemany('DELETE FROM checkpoints WHERE key=?',[(key,) for key in keys])
                self.connection.commit()
            except BaseException:
                self.connection.rollback(); raise

    def close(self):
        self.connection.close()
