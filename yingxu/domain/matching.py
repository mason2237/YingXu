"""Pure filename matching and cancellation rules; no filesystem or GUI access."""
from __future__ import annotations

import difflib
from dataclasses import dataclass
from functools import lru_cache
import os
import re
import unicodedata
from pathlib import Path

from .subtitle_variants import split_variant


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
    base, _variant, suffix = split_variant(stem)
    return base, suffix


def extract_episode(text: str) -> tuple[int | None, int, bool] | None:
    """Return season, episode and whether the marker was explicit."""
    value = unicodedata.normalize("NFKC", text).casefold()
    for pattern, kind in EP_PATTERNS:
        match = pattern.search(value)
        if not match:
            continue
        groups = match.groups()
        if kind == "season":
            return int(groups[0]), int(groups[1]), True
        return None, int(groups[0]), True
    return None


@dataclass(frozen=True)
class EpisodeIdentity:
    season: int | None
    episodes: frozenset[int]
    complete: bool = True


@lru_cache(maxsize=4096)
def episode_identity(text: str) -> EpisodeIdentity | None:
    """Read explicit episode coverage, without treating a pack as its first episode.

    Supports the existing markers plus S01E01E02 / S01E01-E03 / S01E01-03
    and their 1x01x02 equivalents. Bare numbers are never inferred. Mixed
    seasons and reversed/oversized ranges remain uncertain and cannot auto-pair.
    This is a conservative filename guard, not a general release-name parser.
    """
    value = unicodedata.normalize("NFKC", text).casefold()
    for pattern, kind in EP_PATTERNS:
        matches = tuple(pattern.finditer(value))
        if not matches:
            continue
        seasons, numbers = set(), set()
        complete = True
        covered_until = 0
        for match in matches:
            # In 1x01x02x03, 02x03 belongs to the preceding continuation;
            # it must not be read again as season 2, episode 3.
            if match.start() < covered_until:
                continue
            if kind == "season":
                season, number = map(int, match.groups())
                seasons.add(season)
            else:
                number = int(match.group(1))
            numbers.add(number)
            if kind != "season":
                continue
            marker = "x" if "x" in match.group() else "e"
            # A bare range endpoint is bounded to three digits and must end at
            # a token boundary, so -1080p / -x265 never become episode ranges.
            continuation = re.compile(
                rf"[ ._]*(?:(?P<range>[-–—])[ ._]*(?:{marker}(?P<marked>\d{{1,4}})(?!\d)"
                rf"|(?P<end>\d{{1,3}})(?={marker}\d|[^a-z0-9]|$))|{marker}(?P<next>\d{{1,4}})(?!\d))"
            )
            end = match.end()
            while extra := continuation.match(value, end):
                following = int(extra.group("marked") or extra.group("end") or extra.group("next"))
                if extra.group("range"):
                    if not number <= following <= number + 99:
                        complete = False
                        break
                    numbers.update(range(number, following + 1))
                else:
                    numbers.add(following)
                number, end = following, extra.end()
            covered_until = end
        return EpisodeIdentity(next(iter(seasons)) if len(seasons) == 1 else None,
                               frozenset(numbers), complete and len(seasons) <= 1)
    return None


def _episode_conflict(first, second) -> bool:
    if (first and not first.complete) or (second and not second.complete):
        return True
    return bool(first and second and (
        first.episodes != second.episodes
        or (first.season is not None and second.season is not None and first.season != second.season)
    ))


def episode_conflict(first: str, second: str) -> bool:
    """Share the same conservative conflict rule with ranking and review explanations."""
    return _episode_conflict(episode_identity(first), episode_identity(second))


def is_same_path(first: Path, second: Path) -> bool:
    return os.path.normcase(os.path.abspath(first)) == os.path.normcase(os.path.abspath(second))


@lru_cache(maxsize=4096)
def _filename_features(stem):
    value, _language = strip_language_tag(stem)
    return clean_token(value), episode_identity(value)


def similarity(video: Path, subtitle: Path) -> float:
    video_clean, video_ep = _filename_features(video.stem)
    subtitle_clean, subtitle_ep = _filename_features(subtitle.stem)

    if not video_clean or not subtitle_clean:
        return 0.0
    # Reject explicit coverage conflicts before text similarity can hide them.
    if _episode_conflict(video_ep, subtitle_ep):
        return 0.0
    score = difflib.SequenceMatcher(None, video_clean, subtitle_clean).ratio()
    if video_ep and subtitle_ep:
        if video_ep.season is not None and subtitle_ep.season is not None:
            score = max(score, 0.70)
        else:
            score = max(score, 0.65)
    elif video_clean == subtitle_clean:
        score = 1.0

    if video.parent == subtitle.parent:
        score = min(1.0, score + 0.04)
    return score
