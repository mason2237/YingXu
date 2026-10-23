"""Compatibility entry. Canonical application code is in the yingxu package."""
import sys
from pathlib import Path

# Support launching the historical filename directly from another directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from yingxu.core import (
    AUTO_APPLY_THRESHOLD, MATCH_THRESHOLD, VIDEO_EXTS, SUB_EXTS, LANG_TAGS,
    clean_token, strip_language_tag, extract_episode, is_same_path,
    similarity, destination_for, collect_media, build_plan,
)
from yingxu.legacy_ui import SubtitleOrganizerApp


if __name__ == "__main__":
    SubtitleOrganizerApp().run()
