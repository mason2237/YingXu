from __future__ import annotations

import csv
import os
import sys
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter.font as tkfont


from .core import (
    AUTO_APPLY_THRESHOLD, MATCH_THRESHOLD, VIDEO_EXTS, SUB_EXTS, LANG_TAGS,
    clean_token, strip_language_tag, extract_episode, is_same_path,
    similarity, destination_for, collect_media, build_plan,
)

APP_NAME = "映序 · 视频字幕整理器"

BG = "#F4F6FA"
WHITE = "#FFFFFF"
INK = "#202B3C"
MUTED = "#7C8799"
LINE = "#E7EBF2"
ACCENT = "#526FE4"
ACCENT_HOVER = "#405DCE"
ACCENT_SOFT = "#EEF1FF"
GREEN = "#21856D"
GREEN_SOFT = "#EAF6F2"
AMBER = "#B57B2B"
AMBER_SOFT = "#FFF5E6"
RED = "#B95757"
RED_SOFT = "#FCEEEE"
PURPLE_SOFT = "#F3F0FF"
PURPLE = "#7656D9"
SLATE_SOFT = "#F5F7FB"
PINK_SOFT = "#FFF0F6"

class SubtitleOrganizerApp:
    def __init__(self) -> None:
        self._set_dpi_awareness()
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("1240x840")
        self.root.minsize(1160, 760)
        self.root.configure(bg=BG)
        icon_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1] / "outputs")) / "subtitle_organizer.ico"
        if icon_path.exists():
            self.root.iconbitmap(str(icon_path))

        self.font_family = self._choose_font()
        tkfont.nametofont("TkDefaultFont").configure(family=self.font_family, size=10)
        tkfont.nametofont("TkTextFont").configure(family=self.font_family, size=10)
        tkfont.nametofont("TkMenuFont").configure(family=self.font_family, size=10)

        self.folder: Path | None = None
        self.plan: list[dict] = []
        self.discovered_subtitles: list[Path] = []
        self.video_count = 0
        self.subtitle_count = 0
        self.busy = False
        self.operation = ""
        self.scanned_move = False
        self.events: queue.Queue = queue.Queue()
        self.row_iids: dict[int, str] = {}
        self.selected_index: int | None = None
        self.folder_var = tk.StringVar(value="尚未选择文件夹")
        self.status_var = tk.StringVar(value="选择一个文件夹，开始扫描匹配。")
        self.detail_var = tk.StringVar(value="扫描结果会先显示在这里，确认后才会整理文件。")
        self.detail_video_var = tk.StringVar(value="尚未选择项目")
        self.detail_subtitle_var = tk.StringVar(value="—")
        self.detail_target_var = tk.StringVar(value="—")
        self.detail_confidence_var = tk.StringVar(value="等待扫描")
        self.filter_var = tk.StringVar(value="全部")
        self.search_var = tk.StringVar()
        self.recursive = tk.BooleanVar(value=True)
        self.move_to_video = tk.BooleanVar(value=False)

        self._configure_style()
        self._build_ui()
        self._bind_shortcuts()
        self._refresh_counts()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(80, self._drain_events)

    @staticmethod
    def _set_dpi_awareness() -> None:
        if os.name != "nt":
            return
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except Exception:
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                pass

    @staticmethod
    def _choose_font() -> str:
        try:
            available = set(tkfont.families())
        except Exception:
            available = set()
        for name in ("Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI"):
            if name in available:
                return name
        return "TkDefaultFont"

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=WHITE)
        style.configure("TLabel", background=BG, foreground=INK, font=(self.font_family, 10))
        style.configure("Panel.TLabel", background=WHITE, foreground=INK, font=(self.font_family, 10))
        style.configure("Muted.TLabel", background=WHITE, foreground=MUTED, font=(self.font_family, 9))
        style.configure("Title.TLabel", background=WHITE, foreground=INK, font=(self.font_family, 17, "bold"))
        style.configure("Brand.TLabel", background=WHITE, foreground=INK, font=(self.font_family, 16, "bold"))
        style.configure("CardTitle.TLabel", background=WHITE, foreground=INK, font=(self.font_family, 10, "bold"))
        style.configure("BigNumber.TLabel", background=WHITE, foreground=INK, font=(self.font_family, 19, "bold"))
        style.configure("Accent.TButton", background=ACCENT, foreground=WHITE, borderwidth=0, padding=(16, 9), font=(self.font_family, 10, "bold"))
        style.map("Accent.TButton", background=[("disabled", "#B9C3E8"), ("active", ACCENT_HOVER), ("pressed", ACCENT_HOVER)], foreground=[("disabled", "#F7F8FC")])
        style.configure("Soft.TButton", background=ACCENT_SOFT, foreground=ACCENT, borderwidth=0, padding=(13, 8), font=(self.font_family, 10, "bold"))
        style.map("Soft.TButton", background=[("disabled", "#F4F5F8"), ("active", "#E1E7FF"), ("pressed", "#E1E7FF")], foreground=[("disabled", "#A4AAB7")])
        style.configure("Plain.TButton", background=SLATE_SOFT, foreground=INK, borderwidth=0, relief="flat", padding=(10, 7), font=(self.font_family, 9))
        style.map("Plain.TButton", background=[("active", "#F6F7FA"), ("pressed", "#EEF0F5")])
        style.configure("Danger.TButton", background=RED_SOFT, foreground=RED, borderwidth=0, padding=(10, 7), font=(self.font_family, 9, "bold"))
        style.map("Danger.TButton", background=[("active", "#F9DFDF"), ("pressed", "#F3D1D1")])
        style.configure("Icon.TButton", background=SLATE_SOFT, foreground=INK, borderwidth=0, padding=(8, 6), font=(self.font_family, 9, "bold"))
        style.map("Icon.TButton", background=[("active", "#EAEFF8"), ("pressed", "#E1E7F3")])
        style.configure("TCheckbutton", background=WHITE, foreground=INK, font=(self.font_family, 9), padding=(0, 3))
        style.map("TCheckbutton", background=[("active", WHITE)])
        style.configure("Treeview", background=WHITE, fieldbackground=WHITE, foreground=INK, rowheight=40, borderwidth=0, font=(self.font_family, 9))
        style.configure("Treeview.Heading", background="#F8F9FC", foreground=MUTED, relief="flat", borderwidth=0, font=(self.font_family, 9, "bold"), padding=(10, 9))
        style.map("Treeview", background=[("selected", ACCENT_SOFT)], foreground=[("selected", INK)])
        style.configure("TProgressbar", background=ACCENT, troughcolor="#E9EDF5", bordercolor="#E9EDF5", lightcolor=ACCENT, darkcolor=ACCENT, thickness=7)
        style.configure("Search.TEntry", fieldbackground="#F7F8FC", background="#F7F8FC", foreground=INK, bordercolor="#E4E8F1", lightcolor="#F7F8FC", darkcolor="#F7F8FC", padding=(10, 8), font=(self.font_family, 9))

    def _panel(self, parent: tk.Widget, **kwargs) -> tk.Frame:
        background = parent.cget("bg")
        frame = tk.Frame(parent, bg=background, highlightthickness=0, bd=0, **kwargs)
        surface = tk.Canvas(frame, bg=background, bd=0, highlightthickness=0)
        surface.place(x=0, y=0, relwidth=1, relheight=1, bordermode="ignore")
        frame.tk.call("lower", surface._w)
        def redraw(event):
            w, h, r = event.width - 1, event.height - 1, 16
            surface.delete("all")
            surface.create_polygon(
                r, 1, w-r, 1, w, 1, w, r, w, h-r, w, h,
                w-r, h, r, h, 1, h, 1, h-r, 1, r, 1, 1,
                smooth=True, splinesteps=24, fill=WHITE, outline=LINE)
        frame.bind("<Configure>", redraw)
        return frame

    def _build_ui(self) -> None:
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        header = tk.Frame(self.root, bg=WHITE, height=66, highlightthickness=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(2, weight=1)

        mark = tk.Canvas(header, width=42, height=42, bg=WHITE, highlightthickness=0)
        mark.grid(row=0, column=0, padx=(26, 11), pady=11)
        mark.create_oval(3, 3, 39, 39, fill=ACCENT, outline="")
        mark.create_text(21, 21, text="映", fill=WHITE, font=(self.font_family, 16, "bold"))
        brand = ttk.Frame(header, style="Panel.TFrame")
        brand.grid(row=0, column=1, sticky="w")
        ttk.Label(brand, text="映序", style="Brand.TLabel").pack(anchor="w")
        ttk.Label(brand, text="视频与字幕整理器", style="Muted.TLabel").pack(anchor="w", pady=(1, 0))

        chip = tk.Frame(header, bg=GREEN_SOFT, padx=12, pady=7)
        chip.grid(row=0, column=3, padx=(10, 28), pady=14, sticky="e")
        tk.Canvas(chip, width=9, height=9, bg=GREEN_SOFT, highlightthickness=0).pack(side="left", padx=(0, 7))
        chip.winfo_children()[0].create_oval(1, 1, 8, 8, fill=GREEN, outline="")
        tk.Label(chip, text="本地处理 · 文件不上传", bg=GREEN_SOFT, fg=GREEN, font=(self.font_family, 9, "bold")).pack(side="left")

        content = tk.Frame(self.root, bg=BG, padx=22, pady=14)
        content.grid(row=1, column=0, sticky="nsew")
        content.grid_columnconfigure(0, minsize=296)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)

        self._build_sidebar(content)
        self._build_workspace(content)

        footer = tk.Frame(self.root, bg=WHITE, height=38, highlightthickness=1, highlightbackground=LINE)
        footer.grid(row=2, column=0, sticky="ew")
        footer.grid_propagate(False)
        ttk.Label(footer, textvariable=self.status_var, style="Muted.TLabel").pack(side="left", padx=24, pady=9)
        tk.Label(footer, text="映序  ·  轻松整理每一集", bg=WHITE, fg="#A0A8B6", font=(self.font_family, 8)).pack(side="right", padx=24)

    def _build_sidebar(self, parent: tk.Widget) -> None:
        sidebar = tk.Frame(parent, bg=BG)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        sidebar.grid_columnconfigure(0, weight=1)

        folder_card = self._panel(sidebar, padx=18, pady=17)
        folder_card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        ttk.Label(folder_card, text="工作目录", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(folder_card, text="选择包含视频和字幕的文件夹", style="Muted.TLabel").pack(anchor="w", pady=(4, 12))
        self.folder_label = tk.Label(folder_card, textvariable=self.folder_var, bg="#F7F8FB", fg=MUTED, anchor="w", justify="left", wraplength=240, padx=10, pady=9, font=(self.font_family, 9))
        self.folder_label.pack(fill="x", pady=(0, 10))
        tk.Label(folder_card, text="Ctrl + O  快速选择", bg=WHITE, fg="#A1A9B8", font=(self.font_family, 8)).pack(anchor="e", pady=(0, 4))
        self.choose_button = ttk.Button(folder_card, text="选择文件夹", style="Plain.TButton", command=self.choose_folder)
        self.choose_button.pack(fill="x")
        self.scan_button = ttk.Button(folder_card, text="扫描并预览", style="Accent.TButton", command=self.scan_folder, state="disabled")
        self.scan_button.pack(fill="x", pady=(8, 0))

        options = self._panel(sidebar, padx=18, pady=16)
        options.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        ttk.Label(options, text="扫描选项", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 8))
        self.recursive_check = ttk.Checkbutton(options, text="同时扫描子文件夹", variable=self.recursive)
        self.recursive_check.pack(anchor="w")
        self.move_check = ttk.Checkbutton(options, text="整理后移到视频所在目录", variable=self.move_to_video)
        self.move_check.pack(anchor="w", pady=(2, 0))
        tk.Frame(options, bg=LINE, height=1).pack(fill="x", pady=10)
        tk.Label(options, text="默认只修改字幕名称，不改变目录。支持 SRT、ASS、VTT 等格式。", bg=WHITE, fg=MUTED, justify="left", wraplength=245, font=(self.font_family, 9)).pack(anchor="w")

        stats = self._panel(sidebar, padx=18, pady=16)
        ttk.Label(stats, text="本次扫描", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 12))
        stats_grid = tk.Frame(stats, bg=WHITE)
        stats_grid.pack(fill="x")
        stats_grid.grid_columnconfigure(0, weight=1)
        stats_grid.grid_columnconfigure(1, weight=1)
        self.stat_video = self._stat_cell(stats_grid, "视频", "0", 0, 0)
        self.stat_subtitle = self._stat_cell(stats_grid, "字幕", "0", 0, 1)
        self.stat_match = self._stat_cell(stats_grid, "已匹配", "0", 1, 0)
        self.stat_pending = self._stat_cell(stats_grid, "需检查", "0", 1, 1)

        artwork = tk.Canvas(sidebar, width=260, height=152, bg=BG, highlightthickness=0)
        artwork.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        def paint_guide(event):
            artwork.delete("all")
            w = event.width
            artwork.create_rectangle(0, 0, w, 152, fill="#E9EDFF", outline="")
            artwork.create_oval(w-100, -55, w+90, 135, fill="#DBE2FF", outline="")
            artwork.create_oval(w-42, 30, w+78, 150, fill="#CFD9FF", outline="")
            artwork.create_text(20, 28, text="每一集，都井然有序", anchor="w",
                                fill=INK, font=(self.font_family, 13, "bold"))
            artwork.create_text(20, 68, text="01   选择目录\n02   检查匹配\n03   确认整理",
                                anchor="nw", fill=ACCENT_HOVER, font=(self.font_family, 9))
        artwork.bind("<Configure>", paint_guide)
        tk.Label(sidebar, text="先预览，再整理  ·  已有文件不会被覆盖", bg=BG, fg=MUTED, font=(self.font_family, 8)).grid(row=3, column=0, sticky="w", padx=3, pady=(1, 0))

    def _stat_cell(self, parent: tk.Widget, label: str, value: str, row: int, column: int) -> tk.Label:
        cell = tk.Frame(parent, bg="#F8F9FC", padx=10, pady=9)
        cell.grid(row=row, column=column, sticky="ew", padx=(0 if column == 0 else 5, 5 if column == 0 else 0), pady=(0 if row == 0 else 5, 5 if row == 0 else 0))
        tk.Label(cell, text=label, bg="#F8F9FC", fg=MUTED, font=(self.font_family, 8)).pack(anchor="w")
        value_label = tk.Label(cell, text=value, bg="#F8F9FC", fg=INK, font=(self.font_family, 16, "bold"))
        value_label.pack(anchor="w", pady=(2, 0))
        return value_label

    def _build_workspace(self, parent: tk.Widget) -> None:
        workspace = tk.Frame(parent, bg=BG)
        workspace.grid(row=0, column=1, sticky="nsew")
        workspace.grid_columnconfigure(0, weight=1)
        workspace.grid_rowconfigure(2, weight=1)

        title_row = tk.Frame(workspace, bg=BG)
        title_row.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        title_row.grid_columnconfigure(0, weight=1)
        heading = tk.Frame(title_row, bg=BG)
        heading.grid(row=0, column=0, sticky="w")
        tk.Label(heading, text="整理工作台", bg=BG, fg=INK, font=(self.font_family, 19, "bold")).pack(anchor="w")
        tk.Label(heading, text="先预览匹配结果，再一次完成字幕整理", bg=BG, fg=MUTED, font=(self.font_family, 9)).pack(anchor="w", pady=(3, 0))
        action_row = tk.Frame(title_row, bg=BG)
        action_row.grid(row=0, column=1, sticky="e")
        self.export_button = ttk.Button(action_row, text="导出清单", style="Plain.TButton", command=self.export_report, state="disabled")
        self.export_button.pack(side="left", padx=(0, 8))
        self.apply_button = ttk.Button(action_row, text="开始整理", style="Accent.TButton", command=self.apply_plan, state="disabled")
        self.apply_button.pack(side="left")

        summary = tk.Frame(workspace, bg=BG)
        summary.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        for column in range(3):
            summary.grid_columnconfigure(column, weight=1)
        self.summary_videos = self._summary_card(summary, "视频文件", "0", "本次扫描到的视频", 0)
        self.summary_matched = self._summary_card(summary, "可直接整理", "0", "高置信度匹配", 1)
        self.summary_unmatched = self._summary_card(summary, "需要检查", "0", "低置信度或未匹配", 2)

        table_panel = self._panel(workspace, padx=0, pady=0)
        table_panel.grid(row=2, column=0, sticky="nsew")
        table_panel.grid_columnconfigure(0, weight=1)
        table_panel.grid_rowconfigure(1, weight=1)
        table_top = tk.Frame(table_panel, bg=WHITE)
        table_top.grid(row=0, column=0, sticky="ew", padx=17, pady=(14, 10))
        table_top.grid_columnconfigure(1, weight=1)
        tk.Label(table_top, text="整理计划", bg=WHITE, fg=INK, font=(self.font_family, 10, "bold")).grid(row=0, column=0, sticky="w", padx=(0, 14))
        self.filter_bar = tk.Frame(table_top, bg=WHITE)
        self.filter_bar.grid(row=0, column=1, sticky="w")
        self.filter_buttons: dict[str, tk.Button] = {}
        for label in ("全部", "待整理", "需检查", "已完成"):
            button = tk.Button(
                self.filter_bar, text=label, command=lambda value=label: self._set_filter(value),
                bd=0, padx=10, pady=5, cursor="hand2", font=(self.font_family, 8, "bold"),
                highlightthickness=0,
            )
            button.pack(side="left", padx=(0, 5))
            self.filter_buttons[label] = button
        self._refresh_filter_buttons()
        tk.Label(table_top, text="搜索", bg=WHITE, fg=MUTED, font=(self.font_family, 8)).grid(row=0, column=2, padx=(8, 6))
        self.search_entry = ttk.Entry(table_top, textvariable=self.search_var, style="Search.TEntry", width=16)
        self.search_entry.grid(row=0, column=3, sticky="e")
        self.search_entry.insert(0, "")
        self.search_entry.bind("<KeyRelease>", lambda _event: self._render_table())

        table_frame = tk.Frame(table_panel, bg=WHITE)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=(13, 13), pady=(0, 8))
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)
        columns = ("video", "subtitle", "target", "match", "status")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("video", text="视频文件")
        self.tree.heading("subtitle", text="当前字幕")
        self.tree.heading("target", text="整理后的名称")
        self.tree.heading("match", text="匹配度")
        self.tree.heading("status", text="状态")
        self.tree.column("video", width=220, minwidth=140, anchor="w", stretch=True)
        self.tree.column("subtitle", width=190, minwidth=130, anchor="w", stretch=True)
        self.tree.column("target", width=205, minwidth=140, anchor="w", stretch=True)
        self.tree.column("match", width=88, minwidth=75, anchor="center", stretch=False)
        self.tree.column("status", width=92, minwidth=78, anchor="center", stretch=False)
        self.tree.tag_configure("matched", foreground=GREEN)
        self.tree.tag_configure("unmatched", foreground=RED)
        self.tree.tag_configure("review", foreground=AMBER)
        self.tree.tag_configure("skipped", foreground=MUTED)
        self.tree.tag_configure("done", foreground=GREEN)
        self.tree.tag_configure("pending", foreground=INK)
        self.tree.tag_configure("even", background=WHITE)
        self.tree.tag_configure("odd", background="#FAFBFD")
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        xscroll.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.bind("<<TreeviewSelect>>", self._show_selected_detail)
        self.tree.bind("<Double-1>", lambda _event: self.change_selected_subtitle())

        self.empty_label = tk.Label(table_panel, text="选择一个工作目录，映序会为你生成一份可检查的整理计划。", bg=WHITE, fg=MUTED, font=(self.font_family, 10))
        self.empty_label.place(relx=0.5, rely=0.58, anchor="center")
        self.table_hint = tk.Label(table_panel, text="双击一行可重新选择字幕。", bg=WHITE, fg="#98A2B3", anchor="w", font=(self.font_family, 8))
        self.table_hint.grid(row=2, column=0, sticky="ew", padx=17, pady=(1, 9))

        self._build_inspector(workspace)
        progress_row = tk.Frame(workspace, bg=BG)
        progress_row.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        progress_row.grid_columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(progress_row, mode="determinate", maximum=100, value=0)
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.progress_label = tk.Label(progress_row, text="等待扫描", bg=BG, fg=MUTED, font=(self.font_family, 8))
        self.progress_label.grid(row=0, column=1, sticky="e")

    def _build_inspector(self, parent: tk.Widget) -> None:
        inspector = self._panel(parent, padx=16, pady=13)
        inspector.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        inspector.grid_columnconfigure(1, weight=1)

        header = tk.Frame(inspector, bg=WHITE)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        header.grid_columnconfigure(1, weight=1)
        tk.Label(header, text="项目详情", bg=WHITE, fg=INK, font=(self.font_family, 10, "bold")).grid(row=0, column=0, sticky="w")
        self.detail_badge = tk.Label(header, text="等待扫描", bg=SLATE_SOFT, fg=MUTED, padx=9, pady=3, font=(self.font_family, 8, "bold"))
        self.detail_badge.grid(row=0, column=1, sticky="w", padx=(9, 0))
        actions = tk.Frame(header, bg=WHITE)
        actions.grid(row=0, column=2, sticky="e")
        self.copy_button = ttk.Button(actions, text="复制路径", style="Icon.TButton", command=self.copy_selected_path, state="disabled")
        self.copy_button.pack(side="left", padx=(0, 6))
        self.open_button = ttk.Button(actions, text="打开目录", style="Icon.TButton", command=self.open_selected_folder, state="disabled")
        self.open_button.pack(side="left", padx=(0, 6))
        self.change_button = ttk.Button(actions, text="更换字幕", style="Soft.TButton", command=self.change_selected_subtitle, state="disabled")
        self.change_button.pack(side="left", padx=(0, 6))
        self.skip_button = ttk.Button(actions, text="跳过", style="Danger.TButton", command=self.skip_selected, state="disabled")
        self.skip_button.pack(side="left")
        self.confirm_button = ttk.Button(actions, text="确认匹配", style="Soft.TButton",
                                        command=self.confirm_selected, state="disabled")
        self.confirm_button.pack(side="left", padx=(6, 0))

        mapping = tk.Frame(inspector, bg="#FBFCFE", padx=12, pady=9)
        mapping.grid(row=1, column=0, columnspan=2, sticky="ew")
        mapping.grid_columnconfigure(0, weight=1)
        mapping.grid_columnconfigure(1, weight=1)
        mapping.grid_columnconfigure(2, weight=1)
        self._detail_block(mapping, "视频", self.detail_video_var, 0)
        self._detail_block(mapping, "当前字幕", self.detail_subtitle_var, 1)
        self._detail_block(mapping, "整理后名称", self.detail_target_var, 2)

        self.detail_note = tk.Label(inspector, textvariable=self.detail_var, bg=WHITE, fg=MUTED, anchor="w", justify="left", height=2, wraplength=760, font=(self.font_family, 8))
        self.detail_note.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(9, 0))

    def _detail_block(self, parent: tk.Widget, title: str, value: tk.StringVar, column: int) -> None:
        block = tk.Frame(parent, bg="#FBFCFE")
        block.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 13, 13 if column < 2 else 0))
        tk.Label(block, text=title, bg="#FBFCFE", fg="#98A2B3", font=(self.font_family, 8, "bold")).pack(anchor="w")
        tk.Label(block, textvariable=value, bg="#FBFCFE", fg=INK, anchor="w", justify="left", wraplength=210, font=(self.font_family, 9)).pack(anchor="w", pady=(3, 0))

    def _summary_card(self, parent: tk.Widget, title: str, value: str, note: str, column: int) -> tk.Label:
        card = self._panel(parent, padx=14, pady=11)
        card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 6, 6 if column < 2 else 0))
        tk.Label(card, text=title, bg=WHITE, fg=MUTED, font=(self.font_family, 8)).pack(anchor="w")
        value_label = tk.Label(card, text=value, bg=WHITE, fg=INK, font=(self.font_family, 17, "bold"))
        value_label.pack(anchor="w", pady=(1, 0))
        return value_label

    def choose_folder(self) -> None:
        selected = filedialog.askdirectory(title="选择视频与字幕所在文件夹", mustexist=True)
        if not selected:
            return
        self.folder = Path(selected)
        self.folder_var.set(str(self.folder))
        self.scan_button.configure(state="normal")
        self.plan.clear()
        self.discovered_subtitles.clear()
        self.video_count = 0
        self.subtitle_count = 0
        self.selected_index = None
        self.search_var.set("")
        self.filter_var.set("全部")
        self._refresh_filter_buttons()
        self._reset_inspector()
        self._render_table()
        self._refresh_counts()
        self.export_button.configure(state="disabled")
        self.apply_button.configure(state="disabled")
        self.status_var.set("文件夹已选择。点击“扫描并预览”查看匹配结果。")
        self.progress.configure(mode="determinate", maximum=100, value=0)
        self.progress_label.configure(text="等待扫描")

    def scan_folder(self) -> None:
        if self.busy or not self.folder:
            return
        if not self.folder.is_dir():
            messagebox.showerror("无法扫描", "所选文件夹已不存在，请重新选择。", parent=self.root)
            return
        self.plan.clear()
        self.discovered_subtitles.clear()
        self.video_count = 0
        self.subtitle_count = 0
        self.selected_index = None
        self._reset_inspector()
        self._render_table()
        self._refresh_counts()
        self._set_busy(True, "正在扫描文件并计算匹配…", "scan")
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        folder = self.folder
        recursive = self.recursive.get()
        move_to_video = self.move_to_video.get()
        self.scanned_move = move_to_video
        threading.Thread(target=self._scan_worker, args=(folder, recursive, move_to_video), daemon=True).start()

    def _scan_worker(self, folder: Path, recursive: bool, move_to_video: bool) -> None:
        try:
            videos, subtitles = collect_media(folder, recursive)
            plan = build_plan(videos, subtitles, move_to_video)
            self.events.put(("scan_done", videos, subtitles, plan))
        except Exception as error:
            self.events.put(("scan_error", str(error)))

    def apply_plan(self) -> None:
        if self.busy:
            return
        ready = [row for row in self.plan if row["status"] == "待整理"]
        if not ready:
            messagebox.showinfo("无需整理", "当前没有需要重命名的字幕文件。", parent=self.root)
            return
        review_count = sum(row["status"] == "需确认" for row in ready)
        review_note = f"其中 {review_count} 项匹配度较低，建议先在详情中确认。\n\n" if review_count else ""
        answer = messagebox.askyesno(
            "确认整理",
            f"将为 {len(ready)} 份字幕整理文件名。\n\n{review_note}字幕内容不会改动；未匹配项目会跳过，已有目标文件不会被覆盖。\n\n现在开始吗？",
            parent=self.root,
        )
        if not answer:
            return
        indices = [index for index, row in enumerate(self.plan) if row["status"] == "待整理"]
        self._set_busy(True, f"正在整理 {len(indices)} 份字幕…", "apply")
        self.progress.stop()
        self.progress.configure(mode="determinate", maximum=max(1, len(indices)), value=0)
        self.progress_label.configure(text=f"0 / {len(indices)}")
        threading.Thread(target=self._apply_worker, args=(indices,), daemon=True).start()

    def _apply_worker(self, indices: list[int]) -> None:
        succeeded = 0
        for completed, index in enumerate(indices, start=1):
            row = self.plan[index]
            source: Path = row["subtitle"]
            target: Path = row["target"]
            try:
                if not source.exists():
                    raise FileNotFoundError("源字幕文件已不存在")
                if target.exists() and not is_same_path(source, target):
                    raise FileExistsError("目标文件已存在，为避免覆盖已跳过")
                if not is_same_path(source, target):
                    source.rename(target)
                succeeded += 1
                self.events.put(("apply_step", index, "已整理", "", completed, len(indices)))
            except Exception as error:
                self.events.put(("apply_step", index, "整理失败", str(error), completed, len(indices)))
        self.events.put(("apply_done", succeeded, len(indices)))

    def _drain_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "scan_done":
                    _, videos, subtitles, plan = event
                    self.progress.stop()
                    self.progress.configure(mode="determinate", maximum=100, value=100)
                    self.plan = plan
                    self.discovered_subtitles = subtitles
                    self.video_count = len(videos)
                    self.subtitle_count = len(subtitles)
                    self._set_busy(False, f"扫描完成：{len(videos)} 个视频，{len(subtitles)} 份字幕。", "")
                    self.progress_label.configure(text="扫描完成")
                    self.export_button.configure(state="normal")
                    self._render_table()
                    self._refresh_counts(len(videos), len(subtitles))
                    ready = sum(row["status"] == "待整理" for row in plan)
                    matched = sum(row["subtitle"] is not None for row in plan)
                    review = sum(row["status"] in {"需确认", "未匹配"} for row in plan)
                    self.apply_button.configure(text=f"整理 {ready} 项", state="normal" if ready else "disabled")
                    self.status_var.set(f"扫描完成 · 匹配 {matched} 项 · 需检查 {review} 项")
                    if not videos:
                        self.status_var.set(f"没有找到视频文件。扫描到 {len(subtitles)} 份字幕，请检查文件夹或扫描选项。")
                        self.empty_label.configure(text="这里没有找到支持的视频文件。请重新选择文件夹或关闭子文件夹扫描后再试。")
                        self.empty_label.place(relx=0.5, rely=0.58, anchor="center")
                elif kind == "scan_error":
                    _, error = event
                    self.progress.stop()
                    self.progress.configure(mode="determinate", value=0)
                    self._set_busy(False, "扫描没有完成。", "")
                    self.progress_label.configure(text="扫描失败")
                    messagebox.showerror("扫描失败", error, parent=self.root)
                elif kind == "apply_step":
                    _, index, status, error, completed, total = event
                    self.plan[index]["status"] = status
                    self.plan[index]["error"] = error
                    self.progress.configure(maximum=max(1, total), value=completed)
                    self.progress_label.configure(text=f"{completed} / {total}")
                    self._refresh_row(index)
                    self._refresh_counts()
                elif kind == "apply_done":
                    _, succeeded, total = event
                    self._set_busy(False, f"整理完成：{succeeded} / {total} 份字幕已更新。", "")
                    remaining = sum(row["status"] == "待整理" for row in self.plan)
                    self.apply_button.configure(text=f"整理 {remaining} 项", state="normal" if remaining else "disabled")
                    self.progress_label.configure(text="整理完成")
                    self.status_var.set(f"整理完成 · {succeeded} 份成功，{total - succeeded} 份需要检查")
                    self.detail_var.set("原字幕只会在确认后重命名；已存在的目标文件不会被覆盖。")
        except queue.Empty:
            pass
        self.root.after(80, self._drain_events)

    def _set_busy(self, busy: bool, status: str, operation: str) -> None:
        self.busy = busy
        self.operation = operation
        self.status_var.set(status)
        self.choose_button.configure(state="disabled" if busy else "normal")
        self.scan_button.configure(state="disabled" if busy or self.folder is None else "normal")
        self.recursive_check.configure(state="disabled" if busy else "normal")
        self.move_check.configure(state="disabled" if busy else "normal")
        self.search_entry.configure(state="disabled" if busy else "normal")
        for button in self.filter_buttons.values():
            button.configure(state="disabled" if busy else "normal")
        self.export_button.configure(state="disabled" if busy or not self.plan else "normal")
        ready = any(row["status"] == "待整理" for row in self.plan)
        self.apply_button.configure(state="disabled" if busy or not ready else "normal")
        if busy:
            self.copy_button.configure(state="disabled")
            self.open_button.configure(state="disabled")
            self.change_button.configure(state="disabled")
            self.skip_button.configure(state="disabled")
            self.confirm_button.configure(state="disabled")
        else:
            self._update_inspector()

    def _refresh_counts(self, video_count: int | None = None, subtitle_count: int | None = None) -> None:
        if video_count is not None:
            self.video_count = video_count
        if subtitle_count is not None:
            self.subtitle_count = subtitle_count
        video_count = self.video_count
        subtitle_count = self.subtitle_count
        matched = sum(row["subtitle"] is not None for row in self.plan)
        direct = sum(row["status"] == "待整理" for row in self.plan)
        review = sum(row["status"] in {"需确认", "未匹配", "整理失败"} for row in self.plan)
        unused_subtitles = max(0, subtitle_count - matched)
        self.stat_video.configure(text=str(video_count))
        self.stat_subtitle.configure(text=str(subtitle_count))
        self.stat_match.configure(text=str(matched))
        self.stat_pending.configure(text=str(review))
        self.summary_videos.configure(text=str(video_count))
        self.summary_matched.configure(text=str(direct))
        self.summary_unmatched.configure(text=str(review))
        if self.plan:
            self.table_hint.configure(text=f"已分配 {matched} 份字幕，另有 {unused_subtitles} 份未分配。双击一行可重新选择字幕。")
        else:
            self.table_hint.configure(text="扫描后可在这里筛选、检查或手动更换字幕。")

    @staticmethod
    def _status_display(status: str) -> str:
        display = {
            "待整理": "● 待整理",
            "需确认": "● 需确认",
            "未匹配": "● 未匹配",
            "已符合": "● 已符合",
            "已整理": "● 已整理",
            "整理失败": "● 失败",
            "已跳过": "● 已跳过",
        }
        return display.get(status, status)

    @staticmethod
    def _status_colors(status: str) -> tuple[str, str]:
        colors = {
            "待整理": (GREEN_SOFT, GREEN),
            "需确认": (AMBER_SOFT, AMBER),
            "未匹配": (RED_SOFT, RED),
            "已符合": (PURPLE_SOFT, PURPLE),
            "已整理": (GREEN_SOFT, GREEN),
            "整理失败": (RED_SOFT, RED),
            "已跳过": (SLATE_SOFT, MUTED),
        }
        return colors.get(status, (SLATE_SOFT, MUTED))

    def _set_filter(self, value: str) -> None:
        self.filter_var.set(value)
        self._refresh_filter_buttons()
        self._render_table()

    def _refresh_filter_buttons(self) -> None:
        active = self.filter_var.get()
        for label, button in self.filter_buttons.items():
            selected = label == active
            button.configure(
                bg=ACCENT if selected else SLATE_SOFT,
                fg=WHITE if selected else MUTED,
                activebackground=ACCENT_HOVER if selected else "#E9EDF5",
                activeforeground=WHITE if selected else INK,
            )

    def _row_is_visible(self, row: dict) -> bool:
        status = row["status"]
        selected_filter = self.filter_var.get()
        if selected_filter == "待整理" and status != "待整理":
            return False
        if selected_filter == "需检查" and status not in {"需确认", "未匹配", "整理失败"}:
            return False
        if selected_filter == "已完成" and status not in {"已符合", "已整理", "已跳过"}:
            return False
        query = clean_token(self.search_var.get())
        if not query:
            return True
        searchable = " ".join(str(value or "") for value in (row["video"].name, row["subtitle"], row["target"], row["status"]))
        return query in clean_token(searchable)

    def _render_table(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.row_iids.clear()
        for index, row in enumerate(self.plan):
            if not self._row_is_visible(row):
                continue
            video: Path = row["video"]
            subtitle: Path | None = row["subtitle"]
            target: Path | None = row["target"]
            score = f"{round(row['score'] * 100)}%" if subtitle else "—"
            status = row["status"]
            tags = []
            if status in {"未匹配", "整理失败"}:
                tags.append("unmatched")
            elif status == "需确认":
                tags.append("review")
            elif status == "已跳过":
                tags.append("skipped")
            elif status in {"已整理", "已符合"}:
                tags.append("done")
            else:
                tags.append("pending")
            tags.append("even" if len(self.row_iids) % 2 == 0 else "odd")
            item = self.tree.insert("", "end", values=(video.name, subtitle.name if subtitle else "—", target.name if target else "—", score, status), tags=tuple(tags))
            self.row_iids[index] = item
        if self.plan:
            self.empty_label.place_forget()
        else:
            self.empty_label.place(relx=0.5, rely=0.58, anchor="center")
        if self.plan and not self.row_iids:
            self.empty_label.configure(text="当前筛选下没有项目。试试其他分类或清除搜索。")
            self.empty_label.place(relx=0.5, rely=0.58, anchor="center")
        elif not self.plan:
            self.empty_label.configure(text="选择工作目录并扫描后，匹配结果会显示在这里。")
        if self.selected_index in self.row_iids:
            self.tree.selection_set(self.row_iids[self.selected_index])
            self.tree.see(self.row_iids[self.selected_index])
        elif self.selected_index is not None:
            self._reset_inspector()

    def _refresh_row(self, index: int) -> None:
        item = self.row_iids.get(index)
        if not item or not self.tree.exists(item):
            return
        row = self.plan[index]
        status = row["status"]
        tags = ["done" if status in {"已整理", "已符合"} else "pending", "even" if index % 2 == 0 else "odd"]
        if status == "整理失败":
            tags[0] = "unmatched"
        self.tree.item(item, values=(row["video"].name, row["subtitle"].name if row["subtitle"] else "—", row["target"].name if row["target"] else "—", f"{round(row['score'] * 100)}%" if row["subtitle"] else "—", status), tags=tuple(tags))
        if self.selected_index == index:
            self._update_inspector()

    def _show_selected_detail(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        selected = selection[0]
        for index, item in self.row_iids.items():
            if item == selected:
                self.selected_index = index
                self._update_inspector()
                break

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-o>", lambda event: self.choose_folder() if not self.busy else None)
        self.root.bind("<Control-f>", lambda event: self.search_entry.focus_set())
        self.root.bind("<F5>", lambda event: self.scan_folder())
        self.root.bind("<Escape>", lambda event: self._clear_search())

    def _clear_search(self) -> None:
        self.search_var.set("")
        self._render_table()

    def _reset_inspector(self) -> None:
        self.selected_index = None
        self.detail_video_var.set("选择一行查看详情")
        self.detail_subtitle_var.set("—")
        self.detail_target_var.set("—")
        self.detail_var.set("可检查完整路径、替换字幕，或跳过不需要整理的项目。")
        self.detail_badge.configure(text="未选择", bg=SLATE_SOFT, fg=MUTED)
        for button in (self.copy_button, self.open_button, self.change_button, self.skip_button):
            button.configure(state="disabled")
        self.confirm_button.configure(state="disabled")

    def _update_inspector(self) -> None:
        if self.selected_index is None or self.selected_index >= len(self.plan):
            self._reset_inspector()
            return
        row = self.plan[self.selected_index]
        self.detail_video_var.set(row["video"].name)
        self.detail_subtitle_var.set(row["subtitle"].name if row["subtitle"] else "尚未匹配")
        self.detail_target_var.set(row["target"].name if row["target"] else "—")
        bg, fg = self._status_colors(row["status"])
        self.detail_badge.configure(text=row["status"], bg=bg, fg=fg)
        self.detail_var.set(row.get("error") or (
            f"来源：{row['subtitle'] or row['video']}\n目标：{row['target'] or '请选择字幕'}"
        ))
        editable = not self.busy and row["status"] not in {"已整理", "已符合"}
        self.copy_button.configure(state="disabled" if self.busy else "normal")
        self.open_button.configure(state="disabled" if self.busy else "normal")
        self.change_button.configure(state="normal" if editable else "disabled")
        self.skip_button.configure(text="恢复" if row["status"] == "已跳过" else "跳过",
                                   state="normal" if editable else "disabled")
        self.confirm_button.configure(state="normal" if editable and row["status"] == "需确认" else "disabled")

    def confirm_selected(self) -> None:
        if self.busy or self.selected_index is None:
            return
        row = self.plan[self.selected_index]
        if row["status"] == "需确认":
            row["status"] = "待整理"
            self._after_edit()

    def _after_edit(self) -> None:
        self._render_table()
        self._refresh_counts()
        self._update_inspector()
        count = sum(row["status"] == "待整理" for row in self.plan)
        self.apply_button.configure(text=f"整理 {count} 项", state="normal" if count else "disabled")

    def skip_selected(self) -> None:
        if self.busy or self.selected_index is None:
            return
        row = self.plan[self.selected_index]
        if row["status"] == "已跳过":
            row["status"] = row.pop("before_skip", "需确认" if row["subtitle"] else "未匹配")
        elif row["status"] not in {"已整理", "已符合"}:
            row["before_skip"] = row["status"]
            row["status"] = "已跳过"
        self._after_edit()

    def change_selected_subtitle(self) -> None:
        if self.busy or self.selected_index is None:
            return
        row = self.plan[self.selected_index]
        if row["status"] in {"已整理", "已符合"}:
            return
        selected = filedialog.askopenfilename(
            parent=self.root, title="为此视频选择字幕",
            initialdir=str(row["video"].parent),
            filetypes=(("字幕", "*.srt *.ass *.ssa *.vtt *.sub *.sup"),),
        )
        if not selected:
            return
        subtitle = Path(selected)
        if subtitle.suffix.casefold() not in SUB_EXTS:
            messagebox.showerror("格式不支持", "请选择支持的字幕文件。", parent=self.root)
            return
        for index, other in enumerate(self.plan):
            if index != self.selected_index and other["subtitle"] and is_same_path(other["subtitle"], subtitle):
                messagebox.showinfo("字幕已分配", "此字幕已分配给另一条视频，请选择其他字幕。", parent=self.root)
                return
        reserved = {os.path.normcase(os.path.abspath(other["target"]))
                    for index, other in enumerate(self.plan)
                    if index != self.selected_index and other["target"]}
        target = destination_for(row["video"], subtitle, reserved, self.scanned_move)
        row.update(subtitle=subtitle, target=target, score=1.0, error="",
                   status="已符合" if is_same_path(subtitle, target) else "待整理")
        self._after_edit()

    def copy_selected_path(self) -> None:
        if self.selected_index is None:
            return
        row = self.plan[self.selected_index]
        path = row["target"] if row["status"] == "已整理" else (row["subtitle"] or row["video"])
        self.root.clipboard_clear()
        self.root.clipboard_append(str(path))
        self.status_var.set("路径已复制到剪贴板。")

    def open_selected_folder(self) -> None:
        if self.selected_index is None:
            return
        row = self.plan[self.selected_index]
        path = row["target"] if row["status"] == "已整理" else (row["subtitle"] or row["video"])
        try:
            os.startfile(str(path.parent))
        except OSError as error:
            messagebox.showerror("无法打开目录", str(error), parent=self.root)

    def export_report(self) -> None:
        if not self.plan:
            return
        path = filedialog.asksaveasfilename(
            title="导出整理清单",
            defaultextension=".csv",
            initialfile="映序_字幕整理清单.csv",
            filetypes=(("CSV 文件", "*.csv"),),
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as stream:
                writer = csv.writer(stream)
                writer.writerow(("视频路径", "当前字幕路径", "整理后路径", "匹配度", "状态", "备注"))
                for row in self.plan:
                    writer.writerow((
                        str(row["video"]),
                        str(row["subtitle"] or ""),
                        str(row["target"] or ""),
                        f"{round(row['score'] * 100)}%" if row["subtitle"] else "",
                        row["status"],
                        row.get("error", ""),
                    ))
            self.status_var.set(f"清单已导出：{path}")
        except OSError as error:
            messagebox.showerror("导出失败", str(error), parent=self.root)

    def _on_close(self) -> None:
        if self.busy:
            messagebox.showinfo("正在处理", "当前任务完成后即可关闭窗口。", parent=self.root)
            return
        self.root.destroy()

    def run(self) -> None:
        try:
            self.root.attributes("-alpha", 0.0)
            def fade(step=0):
                self.root.attributes("-alpha", min(1.0, step / 10))
                if step < 10:
                    self.root.after(18, lambda: fade(step + 1))
            self.root.after(0, fade)
        except tk.TclError:
            pass
        self.root.mainloop()


if __name__ == "__main__":
    SubtitleOrganizerApp().run()
