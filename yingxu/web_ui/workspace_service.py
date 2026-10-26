"""Python owns the review, frozen targets, one-use consent and background jobs."""
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from secrets import token_urlsafe, compare_digest
from threading import RLock
from uuid import uuid4
import os

from PySide6.QtCore import QObject, Signal

from ..core import collect_media, check_cancelled
from ..review import ReviewPlan, path_key
from ..operations import (HistoryStore, BatchResult, ItemResult, dir_mark,
                          snapshot_from_review, run_batch, export_result, file_mark, StalePlan)
from ..embedded_subtitles import ProbeSession, assess
from ..subtitle_sources.imports import prepare_download, private_path
from .protocol import ProtocolError
from .workspace_data import ReviewData
from .workspace_worker import WorkspaceWorker
from .embedded_settings import EmbeddedSettings

RESULT_LABELS = {"success":"成功", "error":"失败", "blocked":"已阻止", "cancelled":"未执行",
                 "skipped":"跳过", "unmatched":"未匹配", "unchanged":"无需变更"}


class WorkspaceService(QObject):
    changed = Signal(str, object)
    idle = Signal()
    native_requested = Signal(str, object, str, str)

    def __init__(self, parent=None, *, history=None, embedded_settings=None):
        super().__init__(parent)
        self.history = history or HistoryStore()
        self.worker = None; self.job = None; self.native_busy = False
        self.session_id = None; self.folder = None; self.folder_id = None; self.folder_mark = None
        self.folder_pending = False; self.data = None; self.revision = 0
        self.options = {"recursive":True,"move":False}
        self.paths = {}; self.path_ids = {}; self._path_lock = RLock()
        self.snapshot = None; self.ticket = None; self.consumed = OrderedDict();self._preview_version = 0
        self.records = OrderedDict(); self.history_error = ""; self.last_result_id = None
        self.finished = False; self._complete = None
        self.staged_downloads = {}
        self.embedded_settings = EmbeddedSettings(embedded_settings)
        self._embedded_cache = OrderedDict()

    @property
    def busy(self): return self.worker is not None or self.native_busy

    def require_idle(self):
        if self.busy: raise ProtocolError("BUSY","当前任务尚未结束，请稍候。",retryable=True)

    def new_page(self, session_id):
        self.session_id = session_id; self.invalidate_preview()
        if self.job and self.job["kind"] == "preview" and not self.worker:
            self.job = None

    def invalidate_preview(self):
        self._preview_version += 1
        self.snapshot = self.ticket = None

    def register(self, path):
        with self._path_lock:
            key = path_key(path)
            if key not in self.path_ids:
                identifier = uuid4().hex; self.path_ids[key] = identifier; self.paths[identifier] = Path(path)
            return self.path_ids[key]

    def registered_path(self, identifier):
        if identifier not in self.paths: raise ProtocolError("NOT_FOUND","文件不属于已登记的本地记录。")
        return self.paths[identifier]

    def accept_folder(self, path, *, dropped=False):
        """Only called by the native folder dialog/drop handler, never from JSON."""
        self.require_idle()
        folder = Path(path).resolve(strict=True)
        mark = dir_mark(folder)
        with os.scandir(folder): pass
        self.folder, self.folder_mark = folder, mark
        with self._path_lock:
            self.paths.clear(); self.path_ids.clear()
        self.folder_id = self.register(folder); self.data = None; self.revision += 1
        self.folder_pending = True; self.finished = False; self.invalidate_preview()
        self.emit("folder.changed",{"dropped":dropped})
        return self.summary()

    def summary(self):
        return {"mode":"local", "scanId":self.data.scan_id if self.data else None,
            "revision":self.data.revision if self.data else self.revision,
            "folderId":self.folder_id, "folderName":(self.folder.name or str(self.folder)) if self.folder else "尚未选择文件夹",
            "displayPath":str(self.folder) if self.folder else "",
            "counts":self.data.counts if self.data else {"all":0},
            "subtitleCount":self.data.subtitle_count if self.data else 0,
            "embeddedSatisfiedCount":sum(row.uses_embedded and not row.skipped for row in self.data.review.rows) if self.data else 0,
            "embeddedOptions":dict(self.embedded_settings.options),
            "options":dict(self.options), "needsScan":bool(self.folder and not self.data),
            "folderPending":self.folder_pending, "finished":self.finished,
            "lastResultId":self.last_result_id,
            "scanWarnings":self.data.scan_warnings if self.data else [],
            "scanWarningCount":self.data.warning_count if self.data else 0}

    def state(self):
        return {"stage":7,"mode":"local","summary":self.summary(),"job":self.job,
                "busy":self.busy,"nativePending":self.native_busy,"executionAvailable":True}

    def emit(self, kind, payload=None): self.changed.emit(kind,payload or {})

    def require_review(self, params, *, revision_key="revision", idle=True):
        if idle: self.require_idle()
        if not self.data or params.get("scanId") != self.data.scan_id or params.get(revision_key) != self.data.revision:
            raise ProtocolError("STALE_REVIEW","扫描或审阅版本已变化，请刷新列表或重新扫描。",retryable=True)
        return self.data

    def subtitle_tasks(self, params, *, idle=True):
        """Resolve online-search inputs solely from the current Python review."""
        data = self.require_review(params, idle=idle)
        indices = [data.index(params["rowId"])] if "rowId" in params else [
            i for i, row in enumerate(data.review.rows) if not row.matches and not row.skipped and not row.uses_embedded]
        if "rowId" in params and data.review.rows[indices[0]].uses_embedded:
            raise ProtocolError("ALREADY_SATISFIED", "内嵌字幕已符合语言要求；如需外挂，请先选择“仍需外挂字幕”。")
        if not indices:
            raise ProtocolError("NOT_FOUND", "没有未匹配的视频。也可在匹配详情中为当前视频查找在线字幕。")
        return [{"rowId": data.rows[i]["rowId"], "video": data.review.rows[i].video,
                 "scanId": data.scan_id, "revision": data.revision} for i in indices]

    def register_download(self, receipt, root):
        """Native download callback only; no channel action accepts cache paths."""
        if receipt.get("status") not in {"archive_pending", "subtitle_candidate"}:
            raise ValueError("下载未通过格式初检。")
        if not self.data or receipt.get("scanId") != self.data.scan_id:
            raise ProtocolError("STALE_REVIEW", "下载对应的扫描已失效；文件保留在暂存目录。")
        index = self.data.index(receipt["rowId"])
        path = private_path(Path(receipt["stagingPath"]), root)
        key = receipt["stagingId"]
        if key not in self.staged_downloads:
            if len(self.staged_downloads) >= 200:
                raise ValueError("本次工作台已登记 200 份下载，请先完成整理。")
            self.staged_downloads[key] = {"path":path, "root":Path(root), "mark":file_mark(path),
                "scanId":self.data.scan_id, "rowId":receipt["rowId"], "used":False,
                "videoMark":file_mark(self.data.review.rows[index].video)}
        return key

    def import_downloads(self, identifiers, params):
        data = self.require_review(params)
        if not identifiers or len(identifiers) > 20 or len(set(identifiers)) != len(identifiers):
            raise ValueError("请选择 1–20 份未导入的下载，不能重复选择。")
        selected = []
        for key in identifiers:
            entry = self.staged_downloads.get(key)
            if not entry or entry["scanId"] != data.scan_id:
                raise ProtocolError("STALE_REVIEW", "下载不属于当前扫描，未导入。")
            if entry["used"]:
                raise ProtocolError("ALREADY_IMPORTED", "这份下载已经导入，不能重复登记。")
            selected.append((key, entry, data.index(entry["rowId"])))
        self.invalidate_preview()

        def work(worker):
            entries, outcomes = [], []
            total_bytes = 0
            budget = {"bytes":128 * 1024 * 1024,"files":200}
            for done, (key, entry, index) in enumerate(selected):
                check_cancelled(worker.stop.is_set)
                worker.report(done, len(selected), f"检查字幕 · {entry['path'].name}", "import")
                try:
                    if file_mark(data.review.rows[index].video) != entry["videoMark"]:
                        raise StalePlan("视频已变化，请重新扫描。")
                    files, skipped = prepare_download(entry["path"], entry["root"], entry["mark"],
                                                      should_stop=worker.stop.is_set,budget=budget)
                    size = sum(item.mark.size for item in files)
                    if len(entries) + len(files) > 200 or total_bytes + size > 128 * 1024 * 1024:
                        raise ValueError("本次导入超过 200 份字幕或 128 MiB 限制，请分批处理。")
                    total_bytes += size
                    for item in files:
                        entries.append((item.path, {"rowIndex":index, "mark":item.mark,
                            "stagingId":key, "originalName":item.original_name}))
                    outcomes.append({"stagingId":key,"count":len(files),"skipped":skipped,"error":""})
                except (OSError, ValueError, StalePlan) as error:
                    outcomes.append({"stagingId":key,"count":0,"skipped":[],"error":str(error)})
            check_cancelled(worker.stop.is_set)
            review = deepcopy(data.review)
            assigned = review.add_imports(entries) if entries else 0
            warnings = list(data.scan_warnings)
            for outcome in outcomes:
                if outcome["error"]:
                    warnings.append("在线字幕：" + outcome["error"])
                warnings.extend("在线字幕：" + text for text in outcome["skipped"])
            updated = ReviewData(review, self.register, scan_id=data.scan_id,
                revision=data.revision + 1, warnings=warnings[:50])
            updated.warning_count = data.warning_count + len(warnings) - len(data.scan_warnings)
            worker.report(len(selected),len(selected),"字幕检查完成，等待审阅", "import")
            return updated, {"outcomes":outcomes,"imported":len(entries),"assigned":assigned,
                "unassigned":len(entries)-assigned,"rowId":selected[0][1]["rowId"]}

        def complete(value):
            updated, result = value
            if self.data is not data:
                raise ProtocolError("STALE_REVIEW", "审阅已变化，缓存文件保留，请重新导入。")
            self.data = updated; self.revision = updated.revision
            for outcome in result["outcomes"]:
                if outcome["count"]:
                    self.staged_downloads[outcome["stagingId"]]["used"] = True
            return {**result,"revision":updated.revision}

        return self.launch("import",work,complete,"正在检查下载内容；不会修改视频目录…")

    def launch(self, kind, work, complete, message):
        self.require_idle()
        self.job = {"jobId":uuid4().hex,"kind":kind,"status":"running","phase":kind,
                    "message":message,"done":0,"total":None,"stopRequested":False,"result":None,"error":None}
        self._complete = complete
        worker = WorkspaceWorker(work,self); self.worker = worker
        worker.progress.connect(self._progress); worker.result.connect(self._result)
        worker.failed.connect(self._failed); worker.finished.connect(self._finished)
        worker.start(); self.emit("job.started")
        return {"jobId":self.job["jobId"]}

    def _progress(self, done, total, message, phase):
        self.job.update(done=done,total=total,message=message,phase=phase)
        self.emit("job.progress")

    def _result(self, value):
        if self.job["kind"] == "scan" and self.worker.stop.is_set():
            self._failed("CANCELLED","扫描已取消，未发布部分结果。");return
        try:
            result = self._complete(value)
            self.job.update(status="completed",result=result,message="任务已完成")
        except ProtocolError as error:
            self._failed(error.code,error.message); return
        except Exception:
            self._failed("INTERNAL_ERROR","任务结果未能载入，请重新扫描核对文件状态。"); return
        self.emit("job.completed")

    def _failed(self, code, message):
        if self.job["kind"] == "apply":
            self.data = None;self.revision += 1;self.finished = True
        self.job.update(status="cancelled" if code == "CANCELLED" else "failed",error={"code":code,"message":message},message=message)
        self.emit("job.failed")

    def _finished(self):
        worker, self.worker = self.worker, None; self._complete = None
        worker.deleteLater()
        if self.job["status"] == "running": self._failed("INTERNAL_ERROR","任务意外结束，请重新扫描。")
        self.emit("job.idle"); self.idle.emit()

    def start_scan(self, params):
        self.require_idle()
        if not self.folder or params["folderId"] != self.folder_id:
            raise ProtocolError("NOT_FOUND","请先选择有效的文件夹。")
        if dir_mark(self.folder) != self.folder_mark:
            raise ProtocolError("PATH_UNREADABLE","所选文件夹已变化，请重新选择。")
        self.invalidate_preview(); self.folder_pending = False; self.finished = False
        self.options = {"recursive":params["recursive"],"move":params["move"]}
        root, mark, options, revision = self.folder, self.folder_mark, dict(self.options), self.revision+1
        embedded_options = dict(self.embedded_settings.options)
        def work(worker):
            errors = []; error_count = 0
            def warning(error):
                nonlocal error_count
                error_count += 1
                if len(errors) < 50: errors.append(str(error))
            with os.scandir(root): pass
            videos, subtitles = collect_media(root,options["recursive"],should_stop=worker.stop.is_set,
                progress=lambda done,videos,subs: worker.report(done,None,f"已读取 {done} 项 · {videos} 个视频 · {subs} 份字幕","collect"),on_error=warning)
            def inside(paths):
                accepted = []
                for path in paths:
                    check_cancelled(worker.stop.is_set)
                    try:
                        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(root):
                            warning(f"已跳过指向所选目录之外或符号链接的文件：{path}");continue
                        accepted.append(path)
                    except OSError as error: warning(error)
                return accepted
            videos, subtitles = inside(videos), inside(subtitles)
            embedded = {}
            with ProbeSession(worker.stop.is_set) as reader:
                for done, video in enumerate(videos):
                    check_cancelled(worker.stop.is_set)
                    if embedded_options["enabled"]:
                        worker.report(done, len(videos), f"检查内嵌字幕 · {done+1} / {len(videos)}", "embedded")
                        try:
                            before = file_mark(video)
                            key = (path_key(video), before)
                            info = self._embedded_cache.get(key)
                            if info is None:
                                info = reader.probe(video)
                                if file_mark(video) != before:
                                    raise StalePlan("读取字幕轨道期间视频已变化，请重新扫描。")
                                if info["status"] == "ok":
                                    self._embedded_cache[key] = deepcopy(info)
                                    self._embedded_cache.move_to_end(key)
                                    while len(self._embedded_cache) > 512:self._embedded_cache.popitem(last=False)
                            embedded[path_key(video)] = assess(info, embedded_options)
                        except (OSError, StalePlan) as error:
                            embedded[path_key(video)] = assess({"status":"error","tracks":[],"error":str(error)}, embedded_options)
                    else:
                        embedded[path_key(video)] = assess({"status":"disabled","tracks":[]}, embedded_options)
                if reader.unavailable: warning("内嵌字幕读取组件不可用；未自动通过任何视频，请使用完整运行包。")
            if dir_mark(root) != mark: raise ProtocolError("PATH_UNREADABLE","扫描时文件夹已变化，请重新选择。")
            review = ReviewPlan(videos,subtitles,options["move"],should_stop=worker.stop.is_set,
                progress=lambda done,total,phase: worker.report(done,total,
                    f"{'计算匹配' if phase == 'matching' else '核对多语言字幕'} · {done} / {total}",phase),embedded=embedded)
            check_cancelled(worker.stop.is_set)
            result = ReviewData(review,self.register,revision=revision,warnings=errors)
            result.warning_count = error_count
            return result
        def complete(data):
            self.data = data;self.revision = data.revision
            return {"scanId":data.scan_id,"summary":self.summary()}
        return self.launch("scan",work,complete,"正在读取视频与字幕文件…")

    def create_preview(self, params, session_id):
        data = self.require_review(params); self.invalidate_preview()
        scan_id, revision = data.scan_id, data.revision
        generation = self._preview_version
        def complete(snapshot):
            if generation != self._preview_version or session_id != self.session_id or not self.data or self.data.scan_id != scan_id or self.data.revision != revision:
                raise ProtocolError("STALE_PLAN","页面或审阅已变化，请重新打开预览。")
            self.snapshot = snapshot
            self.ticket = {"sessionId":session_id,"scanId":scan_id,"revision":revision,
                           "snapshotId":snapshot.snapshot_id,"token":token_urlsafe(32)}
            return self.preview_info(include_token=True)
        def freeze(worker):
            for row in data.review.rows:
                if row.skipped: continue
                for match in row.matches:
                    imported = data.review.imported.get(path_key(match.source))
                    if imported and file_mark(match.source) != imported["mark"]:
                        raise StalePlan("导入字幕在审阅后发生变化，请移除关联并重新下载导入。")
            return snapshot_from_review(data.review)
        return self.launch("preview",freeze,complete,"正在冻结文件变更并检查源文件…")

    def preview_info(self, *, include_token=False):
        snapshot = self.snapshot
        if not snapshot or not self.ticket: raise ProtocolError("STALE_PLAN","预览已失效，请重新生成。")
        info = {"snapshotId":snapshot.snapshot_id,"revision":self.ticket["revision"],"scanId":self.ticket["scanId"],
            "changeCount":len(snapshot.changes),"pendingCount":snapshot.pending_count,"conflictCount":0,
            "unmatchedCount":sum(item.action == "unmatched" for item in snapshot.items),"itemCount":len(snapshot.items),
            "canExecute":bool(snapshot.changes) and not snapshot.pending_count}
        if include_token: info["confirmationToken"] = self.ticket["token"]
        return info

    def preview_page(self, params):
        info = self.preview_info()
        if params["snapshotId"] != info["snapshotId"]: raise ProtocolError("STALE_PLAN","预览已失效。")
        offset, limit = params.get("offset",0),params.get("limit",20)
        return {"items":[{"videoName":item.video.name,"sourceName":item.source.name if item.source else "未关联字幕",
            "sourcePath":str(item.source or item.video),"targetName":item.target.name if item.target else "—",
            "targetPath":str(item.target) if item.target else "—","action":item.action}
            for item in self.snapshot.items[offset:offset+limit]],"itemCount":info["itemCount"]}

    def confirm(self, params, session_id):
        self.require_idle()
        token = params["confirmationToken"]
        if token in self.consumed: raise ProtocolError("TOKEN_USED","这个整理计划已经提交，不能重复执行。")
        self.require_review(params,revision_key="reviewRevision")
        ticket = self.ticket
        if (not ticket or session_id != ticket["sessionId"] or params["snapshotId"] != ticket["snapshotId"] or
                params["scanId"] != ticket["scanId"] or params["reviewRevision"] != ticket["revision"] or
                not compare_digest(token,ticket["token"])):
            raise ProtocolError("STALE_PLAN","预览凭证已失效，请重新生成并核对。")
        if params["acknowledged"] is not True:
            raise ProtocolError("CONFIRMATION_REQUIRED","请先核对原文件与目标名称，并勾选确认。")
        snapshot = self.snapshot
        if not snapshot.changes or snapshot.pending_count:
            raise ProtocolError("STALE_PLAN","没有可执行的变更，或仍有匹配待确认。")
        # Reserve and consume synchronously before the worker can change a file.
        self.consumed[token] = True
        if len(self.consumed) > 128: self.consumed.popitem(last=False)
        self.invalidate_preview()
        self.last_result_id = None
        def work(worker):
            worker.report(0,len(snapshot.changes),"正在复查已确认的文件计划…","verifying")
            return run_batch(snapshot,should_stop=worker.stop.is_set,
                progress=lambda done,total,name:worker.report(done,total,f"已处理 {done} / {total} · {name}","applying"),history=self.history)
        def complete(result):
            record = result.to_record(); record["history_error"] = result.history_error
            self.remember(record);self.last_result_id = result.run_id
            self.data = None;self.revision += 1;self.finished = True
            return {"batchId":result.run_id}
        return self.launch("apply",work,complete,"正在准备执行已确认的整理计划…")

    def stop_job(self, params):
        if not self.worker or self.job["jobId"] != params["jobId"]:
            raise ProtocolError("NOT_FOUND","当前没有这个运行中的任务。")
        if self.job["kind"] not in {"scan","apply"}:
            raise ProtocolError("BUSY","当前正在更新计划，请等待本次操作结束。")
        self.worker.stop.set();self.job["stopRequested"] = True
        self.job["message"] = "正在取消扫描…" if self.job["kind"] == "scan" else "将在当前文件完成后停止；已完成的变更会保留。"
        self.emit("job.progress")
        return {"stopRequested":True}

    def remember(self, record):
        self.records[record["run_id"]] = record
        self.records = OrderedDict(sorted(self.records.items(),key=lambda item:item[1].get("finished_at","")))
        if len(self.records) > 30: self.records.popitem(last=False)

    def record_meta(self, record):
        counts = {status:sum(item.get("status") == status for item in record.get("items",[])) for status in RESULT_LABELS}
        source = next((item.get("video") for item in record.get("items",[]) if item.get("video")),"")
        return {"recordId":record["run_id"],"title":Path(source).parent.name if source else "整理结果",
            "time":record.get("finished_at",""),"success":counts["success"],"skipped":counts["skipped"],
            "errors":counts["error"]+counts["blocked"],"unchanged":counts["unchanged"],
            "unmatched":counts["unmatched"],"cancelled":counts["cancelled"],"itemCount":len(record.get("items",[])),
            "issue":record.get("issue", ""),"historyError":record.get("history_error","")}

    def history_list(self, limit):
        def complete(records):
            for record in reversed(records):
                if isinstance(record,dict) and isinstance(record.get("run_id"),str) and isinstance(record.get("items"),list):
                    if record["run_id"] not in self.records:self.remember(record)
            values = sorted(self.records.values(),key=lambda record:record.get("finished_at",""),reverse=True)[:limit]
            return [self.record_meta(record) for record in values]
        return self.launch("history",lambda worker:self.history.recent(limit),complete,"正在读取本地整理记录…")

    def record_page(self, identifier, offset=0, limit=20):
        if identifier not in self.records: raise ProtocolError("NOT_FOUND","整理记录不可用，请重新打开记录列表。")
        record = self.records[identifier]; result = self.record_meta(record)
        result["items"] = [{"source":Path(item["source"]).name if item.get("source") else Path(item["video"]).name,
            "target":Path(item["target"]).name if item.get("target") else "—", "state":RESULT_LABELS.get(item.get("status"),"未知"),
            "status":item.get("status"),"error":item.get("error", ""),
            "sourcePath":item.get("source") or item.get("video"),"targetPath":item.get("target") or ""}
            for item in record.get("items",[])[offset:offset+limit]]
        return result

    def export_record(self, identifier, path):
        self.require_idle()
        if identifier not in self.records: raise ProtocolError("NOT_FOUND","整理记录不可用。")
        record = self.records[identifier]
        batch = BatchResult(record["run_id"],record["snapshot_id"],record["started_at"],record["finished_at"],tuple(
            ItemResult(Path(item["video"]),Path(item["source"]) if item.get("source") else None,
                Path(item["target"]) if item.get("target") else None,item["status"],item.get("error","")) for item in record["items"]),record.get("issue",""))
        return self.launch("export",lambda worker:export_result(batch,Path(path)),
            lambda value:{"exported":True,"displayPath":str(path)},"正在导出整理记录…")

    def dispatch(self, action, params, session_id):
        if action == "app.state": return self.state()
        if action == "embedded.configure":
            self.require_idle()
            if params != self.embedded_settings.options:
                self.embedded_settings.update(params)
                self.data = None;self.revision += 1;self.finished = False
                self.invalidate_preview();self.emit("review.invalidated")
            return self.summary()
        if action == "scan.configure":
            self.require_idle()
            if params != self.options:
                self.options = dict(params);self.data = None;self.revision += 1
                self.finished = False;self.invalidate_preview();self.emit("review.invalidated")
            return self.summary()
        if action == "scan.start": return self.start_scan(params)
        if action in {"scan.cancel","job.stop"}: return self.stop_job(params)
        if action == "preview.create": return self.create_preview(params,session_id)
        if action == "preview.query": return self.preview_page(params)
        if action == "preview.discard":
            if not params.get("snapshotId") or (self.snapshot and params["snapshotId"] == self.snapshot.snapshot_id): self.invalidate_preview()
            return {"discarded":True}
        if action == "organize.confirmAndStart": return self.confirm(params,session_id)
        if action == "review.query" and self.data is None:
            if params["scanId"] is not None or params["revision"] != self.revision:
                raise ProtocolError("STALE_REVIEW","扫描结果已变化，请刷新。")
            return {"rows":[],"ids":[],"total":0,"counts":{"all":0},"revision":self.revision}
        if action.startswith("review."):
            data = self.require_review(params)
            if action == "review.query": return data.query(params)
            index = data.index(params["rowId"])
            if action == "review.details": return data.rows[index]
            if action == "review.candidates":
                return self.launch("candidates",lambda worker:data.candidates(index,params.get("offset",0),params.get("limit",6)),lambda value:value,"正在比较字幕候选…")
            self.invalidate_preview()
            def complete(value): self.data = value;self.revision = value.revision;return {"revision":value.revision}
            return self.launch("review",lambda worker:data.updated(action,params),complete,"正在更新匹配计划…")
        if action == "history.list": return self.history_list(params.get("limit",30))
        if action in {"history.get","result.get"}: return self.record_page(params.get("recordId") or params["batchId"],params.get("offset",0),params.get("limit",20))
        raise ProtocolError("ACTION_UNAVAILABLE","当前不提供此操作。")
