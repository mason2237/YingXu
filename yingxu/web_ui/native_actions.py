"""Shared native actions for Widget and HDR Quick hosts; file services unchanged."""
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QFileDialog
from .protocol import ProtocolError
from ..operations import StalePlan


class WorkspaceNativeActions:
    def finish_close(self):
        if self._closing:
            self.close()

    def accept_drop(self, path):
        try:
            self.bridge.service.accept_folder(path,dropped=True)
        except (ProtocolError,OSError,ValueError,StalePlan) as error:
            self.bridge.service.emit("app.error",{"message":error.message if isinstance(error,ProtocolError) else str(error)})

    def handle_native(self, action, params, rid, sid):
        service = self.bridge.service;data = None;error = None
        try:
            if self.bridge.session_id != sid or self.bridge.closing:
                return
            if action == "folder.choose":
                path = QFileDialog.getExistingDirectory(self.file_dialog_parent,"选择包含视频与字幕的文件夹",str(service.folder or Path.home()))
                if self.bridge.session_id != sid or self.bridge.closing:return
                service.native_busy = False
                data = {"cancelled":True} if not path else {"cancelled":False,"summary":service.accept_folder(path)}
            elif action == "result.export":
                path,_ = QFileDialog.getSaveFileName(self.file_dialog_parent,"导出整理记录","映序整理记录.json","JSON 记录 (*.json)",options=QFileDialog.Option.DontConfirmOverwrite)
                if self.bridge.session_id != sid or self.bridge.closing:return
                service.native_busy = False
                data = {"cancelled":True} if not path else service.export_record(params["recordId"],Path(path))
            elif action == "subtitle.open":
                from .subtitle_browser import SubtitleBrowser
                tasks = service.subtitle_tasks(params, idle=False)
                context = (params["scanId"], params["revision"])
                browser = self.subtitle_browser
                if browser is not None and browser.workspace_context[0] != context[0]:
                    if browser.busy_downloads() or browser.batch_running or browser.import_busy:
                        raise ProtocolError("BUSY", "在线字幕窗口仍在处理旧队列，请先停止后再载入新扫描结果。")
                    browser.close()
                    browser = None
                if browser is None:
                    browser = SubtitleBrowser(self.subtitle_parent)
                    self.subtitle_browser = browser
                    browser.destroyed.connect(lambda _obj=None, ref=browser: self.clear_subtitle_browser(ref))
                    browser.workspace_context = context
                    browser.set_theme(self.appearance.state()["resolvedTheme"])
                    browser.download_staged.connect(lambda receipt, ref=browser:self.register_subtitle_download(ref,receipt))
                    browser.import_requested.connect(lambda identifiers, ref=browser:self.import_subtitle_downloads(ref,identifiers))
                    browser.review_requested.connect(lambda ref=browser:self.show_subtitle_review(ref))
                browser.workspace_context = context
                count = browser.add_workspace_tasks(tasks)
                browser.showNormal()
                browser.raise_()
                browser.activateWindow()
                data = {"opened": True, "taskCount": len(browser.tasks), "added": count}
            else:
                path = service.registered_path(params["fileId"])
                if action == "file.copyName":QApplication.clipboard().setText(path.name);data = {"copied":True}
                elif action == "file.reveal":
                    folder = path if path == service.folder else path.parent
                    if not folder.is_dir():raise FileNotFoundError(f"所在文件夹已不存在：{folder}")
                    if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder))):
                        raise ProtocolError("PATH_UNREADABLE","无法打开文件所在位置。")
                    data = {"opened":True}
        except ProtocolError as caught:error = caught
        except PermissionError as caught:error = ProtocolError("PERMISSION_DENIED",str(caught))
        except (OSError,ValueError,StalePlan) as caught:error = ProtocolError("PATH_UNREADABLE",str(caught))
        except Exception:error = ProtocolError("INTERNAL_ERROR","原生操作未完成，请重试。")
        finally:
            service.native_busy = False
            self.bridge.finish_native(rid,sid,data=data,error=error)
            service.emit("native.idle")

    def register_subtitle_download(self, browser, receipt):
        entry = next((item for item in browser.downloads.values() if item.get("stagingId") == receipt["stagingId"]), None)
        try:
            self.bridge.service.register_download(receipt, browser.inbox)
            if entry is not None: entry["registered"] = True
        except (ProtocolError, OSError, ValueError, StalePlan) as error:
            message = error.message if isinstance(error, ProtocolError) else str(error)
            if entry is not None: entry["import_error"] = message

    def import_subtitle_downloads(self, browser, identifiers):
        service = self.bridge.service
        try:
            # Revisions may have advanced through review; the scan/row identity must match.
            context = {"scanId":browser.workspace_context[0],"revision":service.revision}
            job = service.import_downloads(identifiers,context)
            self._subtitle_import = (browser,job["jobId"])
        except (ProtocolError, OSError, ValueError, StalePlan) as error:
            if isinstance(error,ProtocolError) and error.code=='BUSY' and not browser.return_after_import:
                for entry in browser.downloads.values():
                    if entry.get('stagingId') in identifiers: entry['auto_attempted'] = False
                browser.import_finished(error='下载已完成，当前任务结束后会自动解压。')
                return
            browser.import_finished(error=error.message if isinstance(error,ProtocolError) else str(error))

    def schedule_subtitle_imports(self):
        if not self._closing and self.subtitle_browser is not None:
            self.subtitle_browser.schedule_auto_import()

    def show_subtitle_review(self,browser):
        if browser.import_busy: return
        browser.hide()
        if self.isMinimized(): self.showNormal()
        else: self.show()
        self.raise_();self.activateWindow()

    def finish_subtitle_import(self):
        if self._subtitle_import is None: return
        browser, job_id = self._subtitle_import
        job = self.bridge.service.job
        if not job or job["jobId"] != job_id: return
        self._subtitle_import = None
        if job["status"] == "completed":
            browser.workspace_context = (self.bridge.service.data.scan_id,self.bridge.service.revision)
            browser.import_finished(job["result"])
            if job["result"]["imported"] and not self._closing and browser.return_after_import:
                browser.hide()
                self.showNormal();self.raise_();self.activateWindow()
        else:
            browser.import_finished(error=job["message"])

    def clear_subtitle_browser(self, browser):
        if self.subtitle_browser is browser:
            self.subtitle_browser = None

