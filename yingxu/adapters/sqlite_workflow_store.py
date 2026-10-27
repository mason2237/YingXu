"""Transactional workflow metadata, independent of Qt, IPC and media operations.

This ledger records task states and command receipts. It does not make filesystem
changes durable, resume downloads, or implement undo. An evolve callback must be
pure and short: no file, network, GUI or subprocess operations in the transaction.
"""
from __future__ import annotations

import json
from functools import wraps
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Callable

from ..domain.models import CommandReceipt, SubtitleTask, WorkflowCommand, WorkflowError


SCHEMA_VERSION = 1


def storage_boundary(method):
    @wraps(method)
    def call(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except (sqlite3.Error, OSError) as error:
            code = getattr(error, 'sqlite_errorcode', 0) & 255
            label = ('STORAGE_BUSY' if code in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED} else
                     'CORRUPT_STORAGE' if code in {sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB} else
                     'STORAGE_FAILED')
            raise WorkflowError(label, '任务存储不可用；未自动清空或重建，请保留数据目录。') from error
    return call


class SQLiteWorkflowStore:
    """Persist each state transition and its idempotent receipt in one commit."""

    @storage_boundary
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._closed = False
        self._connection = sqlite3.connect(
            self.path, timeout=5.0, isolation_level=None, check_same_thread=False
        )
        try:
            version = self._connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, SCHEMA_VERSION):
                raise WorkflowError("UNSUPPORTED_SCHEMA", "任务存储版本不受支持，请使用兼容版本。")
            if version == 0 and self._tables():
                raise WorkflowError("UNSUPPORTED_SCHEMA", "该文件不是可初始化的空任务存储。")
            mode = self._connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            if mode.lower() != "wal":
                raise WorkflowError("UNSUPPORTED_STORAGE", "任务存储需要支持 WAL 的本地数据库文件。")
            self._connection.execute("PRAGMA synchronous=FULL")
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._initialize()
        except BaseException:
            self._connection.close()
            self._closed = True
            raise

    def _tables(self) -> set[str]:
        return {row[0] for row in self._connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}

    def _initialize(self) -> None:
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            version = self._connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, SCHEMA_VERSION):
                raise WorkflowError("UNSUPPORTED_SCHEMA", "任务存储版本不受支持，请使用兼容版本。")
            if version == 0:
                if self._tables():
                    raise WorkflowError("UNSUPPORTED_SCHEMA", "该文件不是可初始化的空任务存储。")
                self._connection.execute(
                    "CREATE TABLE workflow_tasks (task_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, "
                    "task_json TEXT NOT NULL)"
                )
                self._connection.execute(
                    "CREATE TABLE workflow_receipts (task_id TEXT NOT NULL, command_id TEXT NOT NULL, "
                    "fingerprint TEXT NOT NULL, result_json TEXT NOT NULL, "
                    "PRIMARY KEY (task_id, command_id), "
                    "FOREIGN KEY (task_id) REFERENCES workflow_tasks(task_id))"
                )
                self._connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            elif self._tables() != {"workflow_tasks", "workflow_receipts"}:
                raise WorkflowError("UNSUPPORTED_SCHEMA", "任务存储结构与版本声明不符。")
            self._connection.commit()
        except BaseException:
            self._connection.rollback()
            raise

    def _require_open(self) -> None:
        if self._closed:
            raise WorkflowError("STORE_CLOSED", "任务存储已关闭。")

    @staticmethod
    def _dump(task: SubtitleTask) -> str:
        return json.dumps(task.to_dict(), ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False)

    @staticmethod
    def _decode(raw: str) -> SubtitleTask:
        try:
            return SubtitleTask.from_dict(json.loads(raw))
        except (ValueError, TypeError, KeyError, WorkflowError) as error:
            raise WorkflowError("CORRUPT_TASK", "任务存储内容无效，未自动修改。") from error

    def _get(self, task_id: str) -> SubtitleTask:
        row = self._connection.execute(
            "SELECT revision, task_json FROM workflow_tasks WHERE task_id=?", (task_id,)
        ).fetchone()
        if row is None:
            raise WorkflowError("NOT_FOUND", "没有找到该任务。")
        task = self._decode(row[1])
        if task.task_id != task_id or task.revision != row[0]:
            raise WorkflowError("CORRUPT_TASK", "任务身份或版本与存储索引不一致，未自动修改。")
        return task

    @storage_boundary
    def create(self, task: SubtitleTask) -> SubtitleTask:
        raw = self._dump(task)
        with self._lock:
            self._require_open()
            try:
                self._connection.execute(
                    "INSERT INTO workflow_tasks(task_id, revision, task_json) VALUES (?, ?, ?)",
                    (task.task_id, task.revision, raw),
                )
            except sqlite3.IntegrityError as error:
                raise WorkflowError("ALREADY_EXISTS", "任务标识已存在。") from error
            return task

    @storage_boundary
    def get(self, task_id: str) -> SubtitleTask:
        with self._lock:
            self._require_open()
            return self._get(task_id)

    @storage_boundary
    def apply(self, command: WorkflowCommand,
              evolve: Callable[[SubtitleTask], SubtitleTask]) -> CommandReceipt:
        fingerprint = command.fingerprint()
        with self._lock:
            self._require_open()
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                previous = self._connection.execute(
                    "SELECT fingerprint, result_json FROM workflow_receipts "
                    "WHERE task_id=? AND command_id=?", (command.task_id, command.command_id),
                ).fetchone()
                if previous is not None:
                    if previous[0] != fingerprint:
                        raise WorkflowError("COMMAND_ID_REUSED", "命令标识已用于不同内容。")
                    result = CommandReceipt(self._decode(previous[1]), duplicate=True)
                    self._connection.commit()
                    return result
                current = self._get(command.task_id)
                if current.revision != command.expected_revision:
                    raise WorkflowError("REVISION_CONFLICT", "任务版本已变化，请读取最新状态。")
                if (current.workspace_id != command.workspace_id or
                        current.review_revision != command.review_revision):
                    raise WorkflowError("CONTEXT_MISMATCH", "命令不属于当前工作区审阅版本。")
                updated = evolve(current)
                if not isinstance(updated, SubtitleTask) or updated.revision != current.revision + 1:
                    raise WorkflowError("INVALID_TRANSITION", "状态更新必须生成下一个任务版本。")
                if (updated.task_id != current.task_id or updated.workspace_id != current.workspace_id or
                        updated.review_revision != current.review_revision):
                    raise WorkflowError("CONTEXT_MISMATCH", "状态更新不能替换任务身份或审阅上下文。")
                raw = self._dump(updated)
                changed = self._connection.execute(
                    "UPDATE workflow_tasks SET revision=?, task_json=? WHERE task_id=? AND revision=?",
                    (updated.revision, raw, current.task_id, command.expected_revision),
                )
                if changed.rowcount != 1:
                    raise WorkflowError("REVISION_CONFLICT", "任务版本已变化，请读取最新状态。")
                self._connection.execute(
                    "INSERT INTO workflow_receipts(task_id, command_id, fingerprint, result_json) "
                    "VALUES (?, ?, ?, ?)", (command.task_id, command.command_id, fingerprint, raw),
                )
                self._connection.commit()
                return CommandReceipt(updated)
            except BaseException:
                self._connection.rollback()
                raise

    @storage_boundary
    def active_tasks(self):
        """Startup reconciliation input; never replays external side effects."""
        from ..domain.models import ACTIVE_PHASES
        with self._lock:
            self._require_open()
            values = self._connection.execute('SELECT task_json FROM workflow_tasks').fetchall()
            return [task for row in values if (task := self._decode(row[0])).phase in ACTIVE_PHASES]

    @storage_boundary
    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._connection.close()
                self._closed = True
