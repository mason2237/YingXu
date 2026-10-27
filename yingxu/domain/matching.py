"""Pure filename matching and cancellation rules; no filesystem or GUI access."""
from __future__ import annotations

import difflib
from functools import lru_cache
import os
import re
import unicodedata
from pathlib import Path


VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".m4v", ".ts", ".webm"}
SUB_EXTS = {".srt", ".ass", ".ssa", ".vtt", ".sub", ".sup"}
LANG_TAGS = (".zh-cn", ".zh-tw", ".chs", ".cht", ".eng", ".zh", ".cn", ".tw", ".en", ".jp", ".kr", ".sc", ".tc")

AUTO_APPLY_THRESHOLD = 0.76
MATCH_THRESHOLD = 0.52


class ScanCancelled(Exception):
    """Cooperative cancellation; no partial review is published."""


def check_cancelled(should_stop):
    if should_stop is not None and should_stop():
        raise ScanCancelled("扫描已取消")

EP_PATTERNS = (
    (re.compile(r"s(\d+)\s*e(\d+)", re.IGNORECASE), "season"),
    (re.compile(r"(\d+)\s*x\s*(\d+)", re.IGNORECASE), "season"),
    (re.compile(r"(?<![a-z])(?:episode|ep|e)\s*(\d{1,4})(?!\d)", re.IGNORECASE), "episode"),
    (re.compile(r"第\s*(\d{1,4})\s*(?:集|话)", re.IGNORECASE), "episode"),
)


def clean_token(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return "".join(char for char in normalized if char.isalnum())


def strip_language_tag(stem: str) -> tuple[str, str]:
    lowered = stem.casefold()
    for tag in LANG_TAGS:
        if lowered.endswith(tag):
            return stem[: -len(tag)], tag
    return stem, ""


def extract_episode(text: str) -> tuple[int | None, int, bool] | None:
    """Return season, episode and whether the marker was explicit."""
    value = text.casefold()
    for pattern, kind in EP_PATTERNS:
        match = pattern.search(value)
        if not match:
            continue
        groups = match.groups()
        if kind == "season":
            return int(groups[0]), int(groups[1]), True
        return None, int(groups[0]), True
    return None


def is_same_path(first: Path, second: Path) -> bool:
    return os.path.normcase(os.path.abspath(first)) == os.path.normcase(os.path.abspath(second))


@lru_cache(maxsize=4096)
def _filename_features(stem):
    value, _language = strip_language_tag(stem)
    return clean_token(value), extract_episode(value)


def similarity(video: Path, subtitle: Path) -> float:
    video_clean, video_ep = _filename_features(video.stem)
    subtitle_clean, subtitle_ep = _filename_features(subtitle.stem)

    if not video_clean or not subtitle_clean:
        return 0.0
    # Episode conflicts always score zero. Do not run an expensive text diff
    # for an already rejected pair; this preserves the existing score exactly.
    if video_ep and subtitle_ep:
        v_season, v_number, _ = video_ep
        s_season, s_number, _ = subtitle_ep
        if v_number != s_number or (v_season is not None and s_season is not None and v_season != s_season):
            return 0.0
    score = difflib.SequenceMatcher(None, video_clean, subtitle_clean).ratio()
    if video_ep and subtitle_ep:
        if v_season is not None and s_season is not None:
            score = max(score, 0.70)
        else:
            score = max(score, 0.65)
    elif video_clean == subtitle_clean:
        score = 1.0

    if video.parent == subtitle.parent:
        score = min(1.0, score + 0.04)
    return score
