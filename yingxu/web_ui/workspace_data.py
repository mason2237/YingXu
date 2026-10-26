"""Display DTOs over the existing ReviewPlan; no filesystem mutation here."""
from collections import Counter
from copy import copy, deepcopy
from pathlib import Path
import re
from uuid import uuid4

from ..core import extract_episode, is_same_path
from ..operations import path_present
from ..review import ReviewPlan, language_of, path_key
from .protocol import ProtocolError


def episode(path):
    key = extract_episode(path.stem)
    return (f"S{key[0]:02d}E{key[1]:02d}" if key[0] is not None else f"第 {key[1]} 集") if key else "未识别集数"


def natural(value):
    return tuple((1, int(part)) if part.isdecimal() else (0, part.casefold())
                 for part in re.split(r"(\d+)", value))


class ReviewData:
    def __init__(self, review: ReviewPlan, register, *, scan_id=None, revision=1, warnings=()):
        self.review, self.register = review, register
        self.scan_id, self.revision = scan_id or uuid4().hex, revision
        self.scan_warnings = list(warnings)
        self.warning_count = len(self.scan_warnings)
        self.subtitle_ids = {register(path): path for path in review.subtitles}
        self._query_cache = None
        self.rebuild()

    def rebuild(self):
        rows = []
        for index, row in enumerate(self.review.rows):
            subtitles, warnings = [], []
            for match in row.matches:
                target = match.target
                if target and not is_same_path(match.source, target) and path_present(target):
                    warnings.append({"code":"TARGET_EXISTS", "message":f"目标名称已被占用：{target.name}。请重新扫描。"})
                subtitles.append({"subtitleId":self.register(match.source), "name":match.source.name,
                    "displayPath":str(match.source), "targetName":target.name if target else "",
                    "targetPath":str(target) if target else "", "language":language_of(match.source),
                    "score":match.score, "manual":match.manual, "confirmed":match.confirmed,
                    "imported":path_key(match.source) in self.review.imported})
            basis = [f"已识别 · {episode(row.video)}"] if extract_episode(row.video.stem) else []
            if not row.uses_embedded:
                basis.append("评分来自原有文件名相似度算法，不代表准确概率")
            if row.embedded:
                basis.append("已手动选择继续处理外挂字幕，当前不按内嵌字幕通过。" if row.embedded_ignored else row.embedded["reason"])
                if row.uses_embedded:
                    basis.append("语言依据字幕轨标签或标题；只读取信息，不导出字幕或改动视频")
            if any(match.manual for match in row.matches):
                basis.append("人工指定保留原评分，核对后确认")
            imported_count = sum(meta["rowIndex"] == index for meta in self.review.imported.values())
            if imported_count:
                basis.append(f"已导入 {imported_count} 份在线字幕候选；下载来源不证明版本或时间轴一致")
                basis.append("导入字幕确认整理后放入视频目录，原始下载包保留在暂存区")
            rows.append({"rowId":f"video-{index+1}", "video":{"fileId":self.register(row.video),
                "name":row.video.name, "displayPath":str(row.video), "extension":row.video.suffix.casefold()},
                "state":self.review.state(index), "matchCount":len(subtitles), "subtitles":subtitles,
                "warnings":warnings, "episode":episode(row.video), "basis":basis,
                "embedded": {**row.embedded, "active": row.uses_embedded, "ignored": row.embedded_ignored},
                "embeddedSatisfied": row.uses_embedded,
                "importedCandidateCount":imported_count})
        self.rows = rows
        self.by_id = {row["rowId"]:index for index, row in enumerate(rows)}
        self.counts = dict(Counter(self.state(row) for row in rows)); self.counts["all"] = len(rows)
        self.subtitle_count = sum(len(row["subtitles"]) for row in rows)
        self.search_text = {row["rowId"]:" ".join([row["video"]["name"],
            *[sub[key] for sub in row["subtitles"] for key in ("name","targetName")]]).casefold() for row in rows}
        self._query_cache = None

    @staticmethod
    def state(row):
        return "已跳过" if row["state"] == "已跳过" else "存在冲突" if row["warnings"] else row["state"]

    def index(self, row_id):
        if row_id not in self.by_id:
            raise ProtocolError("NOT_FOUND", "视频不属于当前扫描结果。")
        return self.by_id[row_id]

    def query(self, params):
        keys = ("search", "status", "fileType", "sortKey", "sortDir")
        cache_key = tuple(params.get(key) for key in keys)
        if not self._query_cache or self._query_cache[0] != cache_key:
            terms = params.get("search", "").strip().casefold().split()
            rows = [row for row in self.rows if
                (params.get("status", "all") == "all" or self.state(row) == params["status"]) and
                (not params.get("fileType") or row["video"]["extension"] == params["fileType"]) and
                all(term in self.search_text[row["rowId"]] for term in terms)]
            key = params.get("sortKey", "name")
            rows.sort(key=lambda row: -(row["subtitles"][0]["score"] if row["subtitles"] else 0)
                      if key == "score" else natural(self.state(row) if key == "state" else row["video"]["name"]),
                      reverse=params.get("sortDir", "asc") == "desc")
            self._query_cache = (cache_key, rows)
        rows = self._query_cache[1]; offset, limit = params.get("offset", 0), params.get("limit", 100)
        result = {"rows":rows[offset:offset+limit], "total":len(rows), "counts":self.counts, "revision":self.revision}
        if params.get("includeIds", True):
            result["ids"] = [row["rowId"] for row in rows]
        return result

    def candidates(self, index, offset=0, limit=50):
        row = self.review.rows[index]; video_key = extract_episode(row.video.stem)
        candidates = self.review.candidates(index); rows = []
        # Cache UUIDs must not arbitrarily reorder equal-score versions/languages.
        candidates.sort(key=lambda item: (0, -item[1], item[0].name.casefold())
            if self.review.imported.get(path_key(item[0]), {}).get("rowIndex") == index else (1, 0, ""))
        for rank, (path, score, owner, language) in enumerate(candidates[offset:offset+limit], offset):
            sub_key = extract_episode(path.stem)
            conflict = bool(video_key and sub_key and (video_key[1] != sub_key[1] or
                (video_key[0] is not None and sub_key[0] is not None and video_key[0] != sub_key[0])))
            current = any(match.source == path for match in row.matches)
            other = owner is not None and owner != index
            reason = "已关联其他视频，请先移除原关联" if other else "当前已关联" if current else "集数不一致，请谨慎核对" if conflict else "按原有名称相似度排序，请核对片源与语言"
            imported = self.review.imported.get(path_key(path))
            if imported and not other and not current:
                reason = "在线导入 · " + ("搜索此视频时下载；" if imported["rowIndex"] == index else "来自其他视频搜索；") + "请核对实际文件、集数和片源"
            rows.append({"subtitleId":self.register(path), "name":path.name, "displayPath":str(path),
                "language":language, "score":score, "episode":episode(path), "conflict":conflict,
                "reason":reason, "disabled":other or current, "recommended":rank == 0, "rank":rank,
                "imported":bool(imported)})
        return {"rows":rows,"total":len(candidates),"offset":offset,"limit":limit}

    def mutate(self, action, params):
        index = self.index(params["rowId"])
        def subtitle(key):
            value = params.get(key)
            if value is None: return None
            if value not in self.subtitle_ids: raise ProtocolError("NOT_FOUND", "字幕不属于当前扫描结果。")
            return self.subtitle_ids[value]
        if action == "review.assign": self.review.assign(index,subtitle("subtitleId"),subtitle("replaceId"))
        elif action == "review.remove":
            source = subtitle("subtitleId")
            if not any(match.source == source for match in self.review.rows[index].matches):
                raise ProtocolError("NOT_FOUND", "字幕不属于当前视频关联。")
            self.review.remove(index,source)
        elif action == "review.confirm": self.review.confirm(index)
        elif action == "review.skip": self.review.skip(index,params["skipped"])
        elif action == "review.embedded": self.review.use_embedded(index,params["use"])
        self.revision += 1; self.rebuild()
        return self

    def updated(self, action, params):
        # A failed replan must not partially mutate the version still on screen.
        updated = copy(self); updated.review = deepcopy(self.review)
        return updated.mutate(action, params)
