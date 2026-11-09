"""Bounded local bytes and strict decoding, with no write capability."""
from pathlib import Path
from typing import Protocol
from ..domain.subtitle_document import SubtitleRead


class SubtitleReader(Protocol):
    def read(self, path: Path, *, encoding='auto', should_stop=None) -> SubtitleRead: ...
