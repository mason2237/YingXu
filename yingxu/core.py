"""Compatibility exports. Algorithms live in domain; disk inventory in adapters."""
from pathlib import Path
from .domain.matching import *
from .domain.planning import destination_for as _destination_for, build_plan as _build_plan
from .adapters.local_filesystem import collect_media


def destination_for(video, subtitle, reserved, move_to_video=False):
    return _destination_for(video, subtitle, reserved, move_to_video, exists=Path.exists)


def build_plan(videos, subtitles, move_to_video=False, *, should_stop=None, progress=None):
    return _build_plan(videos, subtitles, move_to_video, exists=Path.exists,
                       should_stop=should_stop, progress=progress)
