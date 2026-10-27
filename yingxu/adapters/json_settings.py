"""Atomic JSON preferences. An unsuccessful save leaves in-memory options alone."""
import json
import os
from pathlib import Path
from uuid import uuid4

from ..domain.errors import ProtocolError


class JSONSettings:
    def __init__(self, path, defaults):
        self.path = Path(path)
        self.defaults = dict(defaults)

    def read(self):
        try:
            if self.path.stat().st_size > 8192:
                raise ValueError('Settings too large')
            value = json.loads(self.path.read_text(encoding='utf8'))
            if not isinstance(value, dict) or set(value) != set(self.defaults):
                raise ValueError('Settings shape mismatch')
            return value
        except (OSError, ValueError, RecursionError):
            return dict(self.defaults)

    def write(self, value):
        temporary = self.path.with_name(self.path.name + '.' + uuid4().hex + '.tmp')
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open('x', encoding='utf8') as stream:
                json.dump(value, stream, ensure_ascii=False, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except (OSError, ValueError) as error:
            raise ProtocolError('SAVE_FAILED', '设置未能保存，请检查数据目录。') from error
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
