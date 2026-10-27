"""Bounded compatibility reader for the existing local JSONL history."""
import json
from collections import deque
from pathlib import Path


class JSONLHistoryReader:
    def __init__(self, path):
        self.path = Path(path)

    def recent(self, limit=30):
        if not self.path.exists():
            return []
        entries = deque(maxlen=limit)
        with self.path.open('rb') as stream:
            while line := stream.readline(1024 * 1024 + 1):
                if len(line) > 1024 * 1024:
                    raise ValueError('单条历史记录超过读取限制，文件未修改。')
                try:
                    record = json.loads(line)
                    if isinstance(record, dict) and isinstance(record.get('run_id'), str) and isinstance(record.get('items'), list):
                        entries.append(record)
                except (ValueError, UnicodeError):
                    continue
        return list(reversed(entries))
