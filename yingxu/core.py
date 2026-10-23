"""GUI-independent scanning, matching and destination planning. No file mutation."""
from __future__ import annotations

import difflib
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


def similarity(video: Path, subtitle: Path) -> float:
    video_stem, _ = strip_language_tag(video.stem)
    subtitle_stem, _ = strip_language_tag(subtitle.stem)
    video_clean = clean_token(video_stem)
    subtitle_clean = clean_token(subtitle_stem)
    video_ep = extract_episode(video_stem)
    subtitle_ep = extract_episode(subtitle_stem)

    if not video_clean or not subtitle_clean:
        return 0.0
    score = difflib.SequenceMatcher(None, video_clean, subtitle_clean).ratio()

    if video_ep and subtitle_ep:
        v_season, v_number, _ = video_ep
        s_season, s_number, _ = subtitle_ep
        if v_number != s_number or (v_season is not None and s_season is not None and v_season != s_season):
            return 0.0
        if v_season is not None and s_season is not None:
            score = max(score, 0.70)
        else:
            score = max(score, 0.65)
    elif video_clean == subtitle_clean:
        score = 1.0

    if video.parent == subtitle.parent:
        score = min(1.0, score + 0.04)
    return score


def destination_for(video: Path, subtitle: Path, reserved: set[str], move_to_video: bool = False) -> Path:
    _, language = strip_language_tag(subtitle.stem)
    destination_dir = video.parent if move_to_video else subtitle.parent
    desired = destination_dir / f"{video.stem}{language}{subtitle.suffix}"
    if is_same_path(desired, subtitle):
        return desired

    candidate = desired
    index = 1
    while os.path.normcase(os.path.abspath(candidate)) in reserved or (candidate.exists() and not is_same_path(candidate, subtitle)):
        candidate = destination_dir / f"{video.stem}_{index}{language}{subtitle.suffix}"
        index += 1
    return candidate


def collect_media(folder: Path, recursive: bool = True, *, should_stop=None,
                  progress=None, on_error=None) -> tuple[list[Path], list[Path]]:
    videos: list[Path] = []
    subtitles: list[Path] = []
    visited = 0
    if recursive:
        for current, dirs, files in os.walk(folder, onerror=on_error or (lambda _error: None)):
            check_cancelled(should_stop)
            dirs.sort(key=str.casefold)
            for filename in files:
                check_cancelled(should_stop)
                visited += 1
                path = Path(current) / filename
                suffix = path.suffix.casefold()
                if suffix in VIDEO_EXTS:
                    videos.append(path)
                elif suffix in SUB_EXTS:
                    subtitles.append(path)
            if progress:
                progress(visited, len(videos), len(subtitles))
    else:
        try:
            for path in folder.iterdir():
                check_cancelled(should_stop)
                visited += 1
                if not path.is_file():
                    continue
                suffix = path.suffix.casefold()
                if suffix in VIDEO_EXTS:
                    videos.append(path)
                elif suffix in SUB_EXTS:
                    subtitles.append(path)
                if progress and visited % 100 == 0:
                    progress(visited, len(videos), len(subtitles))
        except OSError as error:
            if on_error:
                on_error(error)
    check_cancelled(should_stop)
    if progress:
        progress(visited, len(videos), len(subtitles))
    key = lambda path: (str(path.parent).casefold(), path.name.casefold())
    videos.sort(key=key)
    subtitles.sort(key=key)
    return videos, subtitles


def build_plan(videos: list[Path], subtitles: list[Path], move_to_video: bool = False,
               *, should_stop=None, progress=None) -> list[dict]:
    plan: list[dict] = []
    available = set(range(len(subtitles)))
    reserved_destinations: set[str] = set()

    for position, video in enumerate(videos):
        check_cancelled(should_stop)
        if progress:
            progress(position, len(videos))
        best_index = None
        best_score = MATCH_THRESHOLD
        for index in sorted(available):
            check_cancelled(should_stop)
            score = similarity(video, subtitles[index])
            if score > best_score:
                best_score = score
                best_index = index

        if best_index is None:
            plan.append({
                "video": video,
                "subtitle": None,
                "target": None,
                "score": 0.0,
                "status": "未匹配",
                "error": "",
            })
            continue

        subtitle = subtitles[best_index]
        available.remove(best_index)
        target = destination_for(video, subtitle, reserved_destinations, move_to_video)
        reserved_destinations.add(os.path.normcase(os.path.abspath(target)))
        status = "已符合" if is_same_path(subtitle, target) else ("待整理" if best_score >= AUTO_APPLY_THRESHOLD else "需确认")
        plan.append({
            "video": video,
            "subtitle": subtitle,
            "target": target,
            "score": best_score,
            "status": status,
            "error": "",
        })
    check_cancelled(should_stop)
    if progress:
        progress(len(videos), len(videos))
    return plan
