"""In-memory review plan. Scanning and review never mutate media files."""
from dataclasses import dataclass, field
from pathlib import Path
import os

from .core import (AUTO_APPLY_THRESHOLD, MATCH_THRESHOLD, build_plan,
                   check_cancelled, destination_for, is_same_path, similarity, strip_language_tag)


def language_of(path: Path) -> str:
    tag = strip_language_tag(path.stem)[1]
    return {
        ".chs": "简体中文", ".sc": "简体中文", ".cn": "简体中文", ".zh-cn": "简体中文",
        ".cht": "繁体中文", ".tc": "繁体中文", ".tw": "繁体中文", ".zh-tw": "繁体中文",
        ".eng": "英语", ".en": "英语", ".jp": "日语", ".kr": "韩语", ".zh": "中文",
    }.get(tag, "未标记")


def path_key(path: Path) -> str:
    return os.path.normcase(os.path.abspath(path)).casefold()


@dataclass
class ReviewMatch:
    source: Path
    target: Path | None = None
    score: float = 0.0
    manual: bool = False
    confirmed: bool = False


@dataclass
class ReviewRow:
    video: Path
    matches: list[ReviewMatch] = field(default_factory=list)
    skipped: bool = False
    embedded: dict = field(default_factory=dict)
    embedded_ignored: bool = False

    @property
    def uses_embedded(self):
        return bool(self.embedded.get("satisfied") and not self.embedded_ignored and not self.matches)


class ReviewPlan:
    def __init__(self, videos: list[Path], subtitles: list[Path], move: bool = False,
                 *, should_stop=None, progress=None, embedded=None):
        self.videos = tuple(videos)
        self.subtitles = tuple(subtitles)
        self.move = move
        # Only explicitly imported cache files use the video directory when move=False.
        self.imported = {}
        self.rows = [ReviewRow(video, embedded=(embedded or {}).get(path_key(video), {})) for video in videos]
        self._seed(should_stop, progress)
        self._replan(should_stop)

    def _seed(self, should_stop=None, progress=None):
        report = (lambda done, total: progress(done, total, "matching")) if progress else None
        eligible = [row for row in self.rows if not row.uses_embedded]
        for row, item in zip(eligible, build_plan([row.video for row in eligible], list(self.subtitles), self.move,
                                                 should_stop=should_stop, progress=report)):
            if item["subtitle"]:
                row.matches.append(ReviewMatch(item["subtitle"], score=item["score"]))
        # Add distinct, explicitly tagged languages only when the episode and
        # similarity checks pass. Unmarked/duplicate-language files stay candidates.
        used = {path_key(match.source) for row in self.rows for match in row.matches}
        for index, row in enumerate(self.rows):
            check_cancelled(should_stop)
            if progress:
                progress(index, len(self.rows), "languages")
            if not row.matches:
                continue
            langs = {language_of(match.source) for match in row.matches}
            options = sorted(self.subtitles, key=lambda sub: (-similarity(row.video, sub), str(sub).casefold()))
            for sub in options:
                check_cancelled(should_stop)
                lang = language_of(sub)
                if lang == "未标记" or lang in langs or path_key(sub) in used:
                    continue
                score = similarity(row.video, sub)
                if score <= MATCH_THRESHOLD:
                    continue
                row.matches.append(ReviewMatch(sub, score=score))
                langs.add(lang)
                used.add(path_key(sub))

        if progress:
            progress(len(self.rows), len(self.rows), "languages")

    def _replan(self, should_stop=None):
        reserved: set[str] = set()
        self._owners: dict[str, int] = {}
        for index, row in enumerate(self.rows):
            check_cancelled(should_stop)
            for match in row.matches:
                self._owners[path_key(match.source)] = index
                match.target = destination_for(row.video, match.source, reserved,
                                               self.move or path_key(match.source) in self.imported)
                reserved.add(path_key(match.target))

    def owner(self, subtitle: Path) -> int | None:
        return self._owners.get(path_key(subtitle))

    def add_imports(self, entries):
        """Register prepared files; only an unambiguous empty row gets a pending match."""
        grouped = {}
        new_paths = []
        known = {path_key(sub) for sub in self.subtitles}
        for path, metadata in entries:
            if path_key(path) in known:
                raise ValueError("这份字幕已经导入。")
            known.add(path_key(path))
            self.imported[path_key(path)] = metadata
            new_paths.append(path)
            grouped.setdefault(metadata["rowIndex"], []).append(path)
        self.subtitles += tuple(new_paths)
        assigned = 0
        for index, paths in grouped.items():
            row = self.rows[index]
            if len(paths) == 1 and not row.matches and not row.skipped and not row.uses_embedded:
                row.matches.append(ReviewMatch(paths[0], score=similarity(row.video, paths[0]), manual=True))
                assigned += 1
        self._replan()
        return assigned

    def candidates(self, index: int):
        row = self.rows[index]
        return sorted(((sub, similarity(row.video, sub), self.owner(sub), language_of(sub))
                       for sub in self.subtitles), key=lambda item: (-item[1], str(item[0]).casefold()))

    def assign(self, index: int, subtitle: Path, replace: Path | None = None):
        if index < 0 or index >= len(self.rows) or subtitle not in self.subtitles:
            raise ValueError("字幕不属于当前扫描结果")
        owner = self.owner(subtitle)
        if owner is not None and owner != index:
            raise ValueError("这份字幕已经分配给另一个视频")
        row = self.rows[index]
        if replace is not None and not any(match.source == replace for match in row.matches):
            raise ValueError("要替换的字幕不属于当前视频")
        if owner == index and subtitle != replace:
            raise ValueError("这份字幕已在当前视频的匹配列表中")
        lang = language_of(subtitle)
        if any(language_of(match.source) == lang and match.source != replace for match in row.matches):
            raise ValueError("同一种语言已经关联字幕，请先更换或移除原字幕")
        if replace is not None:
            row.matches = [match for match in row.matches if match.source != replace]
        row.matches.append(ReviewMatch(subtitle, score=similarity(row.video, subtitle), manual=True))
        if row.embedded.get("satisfied"):
            row.embedded_ignored = True
        row.skipped = False
        self._replan()

    def remove(self, index: int, subtitle: Path):
        row = self.rows[index]
        row.matches = [match for match in row.matches if match.source != subtitle]
        self._replan()

    def confirm(self, index: int):
        row = self.rows[index]
        if not row.matches:
            raise ValueError("请先为视频选择字幕")
        row.skipped = False
        for match in row.matches:
            match.confirmed = True

    def skip(self, index: int, value: bool = True):
        self.rows[index].skipped = value

    def use_embedded(self, index: int, use: bool):
        row = self.rows[index]
        if not row.embedded.get("satisfied"):
            raise ValueError("当前内嵌字幕语言尚未符合要求，请先核对语言设置并重新扫描。")
        row.embedded_ignored = not use
        if use:
            row.matches.clear()
        row.skipped = False
        self._replan()

    def state(self, index: int) -> str:
        row = self.rows[index]
        if row.skipped:
            return "已跳过"
        if row.uses_embedded:
            return "已符合"
        if not row.matches:
            return "未匹配"
        if any(not match.confirmed and (match.manual or match.score < AUTO_APPLY_THRESHOLD)
               for match in row.matches):
            return "需确认"
        if all(is_same_path(match.source, match.target) for match in row.matches):
            return "已符合"
        return "待整理"
