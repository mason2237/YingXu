"""Pure target planning. Occupancy is supplied by the caller, never read here."""
import os
from pathlib import Path
from .matching import (strip_language_tag, is_same_path, check_cancelled,
                       similarity, MATCH_THRESHOLD, AUTO_APPLY_THRESHOLD)


def destination_for(video: Path, subtitle: Path, reserved: set[str], move_to_video: bool = False, *, exists) -> Path:
    _, language = strip_language_tag(subtitle.stem)
    destination_dir = video.parent if move_to_video else subtitle.parent
    desired = destination_dir / f"{video.stem}{language}{subtitle.suffix}"
    if is_same_path(desired, subtitle):
        return desired

    candidate = desired
    index = 1
    while os.path.normcase(os.path.abspath(candidate)) in reserved or (exists(candidate) and not is_same_path(candidate, subtitle)):
        candidate = destination_dir / f"{video.stem}_{index}{language}{subtitle.suffix}"
        index += 1
    return candidate


def build_plan(videos: list[Path], subtitles: list[Path], move_to_video: bool = False,
               *, exists, should_stop=None, progress=None) -> list[dict]:
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
        target = destination_for(video, subtitle, reserved_destinations, move_to_video, exists=exists)
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
