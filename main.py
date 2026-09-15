# -*- coding: utf-8 -*-
"""
音乐下载器 (Python 复刻版)
对应原 Java Swing 项目 MusicPlayer 的 Maininterface / Function / Search / SlidePanel
布局坐标、层级、字体复刻自原版; 列表/推荐/表头文字直接合并在背景图上, 还原
Java 的 setOpaque(false) 透明效果。

重设计 (浅色极简 + 音乐绿):
- 纯色浅底 + 白卡片; 微软雅黑; 侧栏文字导航 + 绿色胶囊选中
- 去掉大轮播横幅; 顶栏搜索 + 内容卡片; 底部播放条浅色重排
- WinMM/MCI 进程内播放引擎; 歌词面板 (QQ 风格, 绿色高亮)
"""
import os
import queue
import re
import sys
import tempfile
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk
from PIL import Image

from kuwo import KuwoAPI
import requests
from widgets import PICTRUE, load_image, BgLabel, \
    ImagePanel, Carousel, RecommendGrid, ImageCheckList, ImageList, \
    apply_tk_theme, LyricsPanel, ProgressBar, BORDER_HEX, \
    round_cover_photo, placeholder_cover
from engine import CrossPlatformEngine, open_path
import dialogs
import widgets
from lyrics import parse_lrc, read_uslt, read_cover, fetch_lyrics, save_lrc


def ui_font(*sizes):
    """按平台返回中文字体族: macOS 用苹方, 其余用微软雅黑。"""
    family = "PingFang SC" if sys.platform == "darwin" else "微软雅黑"
    return (family,) + tuple(sizes)


def symbol_font(*sizes):
    """按平台返回符号字体族: macOS 用 Apple Symbols, Windows 用 Segoe UI Symbol。"""
    family = "Apple Symbols" if sys.platform == "darwin" else "Segoe UI Symbol"
    return (family,) + tuple(sizes)


def init_global_font():
    """全局中文字体 (macOS 苹方 / Windows 微软雅黑)。"""
    family = "PingFang SC" if sys.platform == "darwin" else "微软雅黑"
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont",
                 "TkHeadingFont", "TkCaptionFont", "TkIconFont"):
        try:
            tkfont.nametofont(name).configure(family=family, size=11)
        except Exception:  # noqa: BLE001
            pass


def _probe_meta(path):
    """后台线程用: 读文件时长(格式化串)与歌手, 供下载列表列显示。"""
    dur, artist = "", ""
    try:
        import mutagen
        f = mutagen.File(path)
        if f:
            info = getattr(f, "info", None)
            if info is not None and getattr(info, "length", None):
                dur = widgets.fmt_duration(float(info.length))
            tags = getattr(f, "tags", None)
            if tags:
                try:
                    fr = tags.get("TPE1")
                    if fr:
                        t = getattr(fr, "text", None)
                        if t:
                            try:
                                artist = str(t[0]).split("\x00")[-1].strip()
                            except Exception:  # noqa: BLE001
                                artist = str(t).strip()
                except Exception:  # noqa: BLE001
                    pass
    except Exception:  # noqa: BLE001
        pass
    return dur, artist


class DownloadList(ImageList):
    """下载管理列表: 自定义 6 列 (序号/歌名/歌手/时长/大小/状态)。"""

    def __init__(self, master, width=800, height=416, **kw):
        super().__init__(master, width=width, height=height,
                         header=widgets.DOWNLOAD_HEADER_COLS, **kw)

    def _make_photo(self, i, row):
        if row is None:
            return self._empty_photo(i)
        if len(row) < 6:
            n, title, artist, dur = widgets.row_parts(row)
            size, status = "", ""
        else:
            n, title, artist, dur, size, status = row
        cells = [
            (str(artist or ""), 480, "#6B7280"),
            (str(dur or ""), 560, "#6B7280"),
            (str(size or ""), 660, "#6B7280"),
            (str(status or ""), 775, self._status_fg(status)),
        ]
        return widgets.compose_dl_row(
            self._slices(i), n, title, cells,
            hover=(i == self._hover_idx or i == self.selected_index))

    @staticmethod
    def _status_fg(status):
        if str(status).startswith("✓"):
            return "#0F9D4A"
        if "失败" in str(status):
            return "#EF4444"
        return "#6B7280"


class ToolButton(tk.Label):
    """无边框图标按钮, 等价于原项目的图片按钮 (but1..but5)。"""

    def __init__(self, master, image_path, command=None, size=30,
                 tooltip="", bg=None):
        super().__init__(master, bg=bg, cursor="hand2")
        self.command = command
        self.size = size
        if not os.path.isabs(image_path):
            image_path = os.path.join(PICTRUE, image_path)
        self._normal = load_image(image_path, size, size)
        self.configure(image=self._normal)
        self.image = self._normal
        self._tooltip = tooltip
        self._tip = None
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _on_enter(self, _e):
        if self._tooltip:
            self._show_tip()

    def _on_leave(self, _e):
        self._hide_tip()

    def _on_click(self, _e):
        if self.command:
            self.command()

    def _show_tip(self):
        try:
            tip = tk.Toplevel(self, bg="#FFFFE0")
            tip.overrideredirect(True)
            tk.Label(tip, text=self._tooltip, bg="#FFFFE0",
                     font=("宋体", 12)).pack(padx=4, pady=2)
            tip.wm_geometry("+%d+%d" % (self.winfo_rootx(),
                                        self.winfo_rooty() + self.size + 2))
            self._tip = tip
        except Exception:  # noqa: BLE001
            pass

    def _hide_tip(self):
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:  # noqa: BLE001
                pass
            self._tip = None


class _CircleBtn(tk.Canvas):
    """圆形图标按钮 (播放条/顶栏用): 悬停变色。"""

    def __init__(self, master, glyph, command, size=40, bg="#FFFFFF",
                 fill="#F3F4F6", active="#E4E7EC", fg="#3A424C",
                 font=symbol_font(14)):
        super().__init__(master, width=size, height=size, bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self._size = size
        self._glyph = glyph
        self._cmd = command
        self._fill = fill
        self._active = active
        self._fg = fg
        self._font = font
        self._draw(fill)
        self.bind("<Button-1>", lambda e: command())
        self.bind("<Enter>", lambda e: self._draw(active))
        self.bind("<Leave>", lambda e: self._draw(fill))

    def _draw(self, fill):
        self.delete("all")
        s = self._size
        self.create_oval(1, 1, s - 1, s - 1, fill=fill, outline="")
        self.create_text(s // 2, s // 2, text=self._glyph, fill=self._fg,
                         font=self._font)

    def set_glyph(self, glyph, fg=None):
        self._glyph = glyph
        if fg:
            self._fg = fg
        self._draw(self._fill)

    def set_fill(self, fill, active):
        self._fill = fill
        self._active = active
        self._draw(fill)


class _NavItem(tk.Label):
    """侧栏导航项: 悬停浅灰, 选中 = 浅绿底 + 绿字 + 左侧绿条。"""

    def __init__(self, menu, y, text, command):
        super().__init__(menu, text=text, anchor="w", cursor="hand2",
                         font=ui_font(13, "bold"), padx=20)
        self._bar = tk.Frame(menu, bg=widgets.ACCENT_HEX, width=3)
        self._cmd = command
        self._sel = False
        self._y, self._h = y, 38
        self.place(x=12, y=y, width=176, height=self._h)
        self.set_selected(False)
        self.bind("<Enter>", lambda e: self._on_enter())
        self.bind("<Leave>", lambda e: self._on_leave())
        self.bind("<ButtonRelease-1>", lambda e: self._cmd())

    def _on_enter(self):
        if not self._sel:
            self.configure(bg="#F3F4F6")

    def _on_leave(self):
        self.configure(bg=widgets.ACCENT_SOFT_HEX if self._sel else "#FFFFFF")

    def set_selected(self, on):
        self._sel = on
        self.configure(bg=widgets.ACCENT_SOFT_HEX if on else "#FFFFFF",
                       fg=widgets.ACCENT_TXT_HEX if on else "#5A6472")
        if on:
            self._bar.configure(bg=widgets.ACCENT_HEX)
            self._bar.place(x=12, y=self._y, width=3, height=self._h)
        else:
            self._bar.place_forget()


_MciEngine = CrossPlatformEngine  # 跨平台引擎 (原 winmm 已迁移至 engine.py)


class MainWindow:
    """主界面, 布局/层级与原 Maininterface 一致 (1000x600)。"""

    W, H = 1000, 600

    def __init__(self):
        self.root = tk.Tk()
        init_global_font()
        apply_tk_theme(self.root)
        self.root.title("音乐下载器")
        self.root.geometry("%dx%d" % (self.W, self.H))
        self._splash_mode = False
        if sys.platform == "darwin":
            # macOS 上 overrideredirect 窗口永远无法成为 key window——
            # KeyPress/FocusIn/FocusOut 事件根本不送达, 导致输入框无法
            # 获得光标/键盘输入/鼠标文本选中。改用 splash 型无边框窗口。
            try:
                self.root.attributes("-type", "splash")
                self._splash_mode = True
            except tk.TclError:
                pass
        if not self._splash_mode:
            self.root.overrideredirect(True)
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)
        self.root.bind("<Map>", self._on_map)
        self.center()

        self.api = KuwoAPI()
        self.search_array = []     # 每项: "<rid> 《<歌名>》 <artist>"
        self.download_paths = []   # 与下载列表同步的文件路径
        self.page = 1
        self._search_seq = 0   # 并发搜索守卫: 旧结果不得覆盖新结果
        self._active_search_seq = 0   # 当前有效搜索序号 (翻页加载校验用)
        self._has_more = False        # 是否还有下一页
        self._load_more_busy = False  # 加载更多去重
        self.current_kw = "陈奕迅"
        self.drag_off = (0, 0)
        self.tray_icon = None
        self.tray_active = False
        self._minimizing = False
        self.scan_dialog = None
        self.local_paths = []           # 与本地列表同步的真实文件路径
        self._ui_queue = queue.Queue()   # 线程 -> 主线程 UI 回调队列

        # ---- 播放引擎 (跨平台, pygame.mixer): 进程内播放
        self._engine = CrossPlatformEngine()
        self._engine.start()
        self._pb_playlist = []
        self._pb_idx = -1
        self._pb_path = None
        self._pb_ext = False
        self._pb_dur = 1.0
        self._pb_pos = 0.0
        self._pb_last_set = 0.0
        self._pb_syncing = False   # 进度条程序化同步守卫 (防止 set() 触发 seek)
        self._pb_mode = 1          # 0顺序 1列表循环 2单曲循环 3随机
        self._pb_was_playing = False
        self._pb_vol_val = 50
        self._pb_muted = False
        self._pb_vol_prev = 50
        self._settings_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "settings.json")
        self._cover_by_title = {}   # 歌名(显示名) → 封面 URL (搜索结果)
        self._cover_cache = {}      # 封面 URL → 已缓存 PhotoImage
        self._queue = []            # 播放队列: [{"title","type","row"|"path"}]
        self._queue_dlg = None
        self._dl_state = {}          # path → {"row","status","mb"}
        self._dl_failed = {}         # path → {"rid","display"} 用于重试
        self._dl_last_mb = {}        # path → 上次已显示的 MB (节流)
        self._dl_meta = {}           # path → (时长格式化串, 歌手) 后台探读

        self._build_ui()
        self._load_settings()   # 恢复模式/音量/静音 (不自动播放)
        self._bind_shortcuts()

        # 启动线程读取下载目录歌曲 (避免影响打开速度)
        threading.Thread(target=self._load_download_dir, daemon=True).start()

        # 主线程轮询执行工作线程发来的 UI 更新 (Tk 非线程安全, 不能跨线程 after)
        self.root.after(150, self._poll_ui)
        self.root.after(200, self._poll_player)

        self.root.mainloop()

# ================================================================== 框架
    def center(self):
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - self.W) // 2
        y = (self.root.winfo_screenheight() - self.H) // 2
        self.root.geometry("+%d+%d" % (x, y))

    def _build_ui(self):
        self._build_menu()
        self._build_main()
        self._build_top_right()
        self._build_playbar()
        self._bind_drag_all()
        self.show_home()

    def _bind_drag_all(self):
        """让无边框窗口在更大区域可拖拽 (面板空白/播放条/表头等)。"""
        for wgt in (self.content_panel, self.lyrics_panel, self.playbar,
                    self.music_panel, self.music_panel2):
            self._bind_drag(wgt)
            if hasattr(wgt, "_bg_label"):
                self._bind_drag(wgt._bg_label)
        for lst in (self.results_list, self.download_list, self.local_list):
            try:
                self._bind_drag(lst._header_lbl)
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------- 左栏导航 (200px 白)
    def _build_menu(self):
        menu = tk.Frame(self.root, bg="#FFFFFF", width=200,
                        height=self.H - 64)
        menu.place(x=0, y=0)
        menu.pack_propagate(False)
        tk.Frame(menu, bg=BORDER_HEX, width=1).place(x=199, y=0, relheight=1)
        self.menu = menu
        self._draw_logo()

        self._nav = {}
        self.b1 = _NavItem(menu, 116, "推荐", self.show_home)
        self.b2 = _NavItem(menu, 160, "下载管理", self.show_download_panel)
        self.b3 = _NavItem(menu, 204, "本地音乐", self.show_local_music)
        self._nav["home"] = self.b1
        self._nav["download"] = self.b2
        self._nav["local"] = self.b3
        self._bind_drag(menu)

    def _draw_logo(self):
        """Logo: 绿圆音符 + 应用名 (微软雅黑)。"""
        self.logo_box = tk.Canvas(self.menu, width=200, height=96,
                                  bg="#FFFFFF", highlightthickness=0)
        self.logo_box.place(x=0, y=0, width=200, height=96)
        c = self.logo_box
        c.create_oval(24, 26, 24 + 44, 26 + 44, fill=widgets.ACCENT_HEX, outline="")
        c.create_text(46, 48, text="♪", fill="#FFFFFF",
                      font=symbol_font(24))
        c.create_text(78, 36, text="音乐下载器", fill="#1F2430",
                      font=ui_font(15, "bold"), anchor="w")
        c.create_text(78, 62, text="Music Player", fill="#9AA3B0",
                      font=ui_font(10), anchor="w")

    # ------------------------------- 主区域 (X=200, 800px)
    def _build_main(self):
        self.main = tk.Frame(self.root, width=800, height=self.H - 64,
                             bg="#F7F8FA")
        self.main.place(x=200, y=0)

        # ---- 顶栏 (白底, 搜索框 + 下边框) ----
        self.search_panel = ImagePanel(self.main, kind="search")
        self.search_panel.place(x=0, y=0, width=800, height=64)
        tk.Frame(self.search_panel, bg=BORDER_HEX, height=1).place(
            x=0, y=63, relwidth=1.0)
        self._build_search_area()
        self._bind_drag(self.search_panel)
        self._bind_drag(self.search_panel._bg_label)

        # ---- 内容区 (y=64, 800x472): 推荐网格 / 搜索结果 ----
        self.content_panel = tk.Frame(self.main, width=800, height=472,
                                      bg="#F7F8FA")
        self.content_panel.place(x=0, y=64, width=800, height=472)

        self.recommend_grid = RecommendGrid(self.content_panel,
                                            self.on_recommend_click,
                                            width=800, viewport=472)
        self.recommend_grid.place(x=0, y=0, width=800, height=472)

        self._build_control_bar()
        self.results_list = ImageCheckList(self.content_panel, 800, 428,
                                           header=(("序号", 44, "l"),
                                                   ("歌名", 78, "l"),
                                                   ("歌手", 700, "r")),
                                           on_scroll_end=self._load_more,
                                           on_double=self.on_search_play)
        self.results_list.place(x=0, y=44, width=800, height=428)

        # ---- 下载管理面板 ----
        self.music_panel = ImagePanel(self.main, kind="main")
        self.music_panel.place(x=0, y=0, width=800, height=472)
        tk.Label(self.music_panel, text="下载管理", bg="#FFFFFF",
                 fg="#1F2430", font=ui_font(16, "bold"),
                 anchor="w").place(x=20, y=12, width=200, height=32)
        self.download_list = DownloadList(self.music_panel, 800, 416,
                                          on_double=self.on_download_play)
        self.download_list.place(x=0, y=52, width=800, height=416)

        # 下载管理操作按钮 (右键菜单同功能)
        def dbtn(x, text, cmd):
            tk_btn = ttk.Button(self.music_panel, text=text, command=cmd,
                                cursor="hand2", style="TButton")
            tk_btn.place(x=x, y=8, width=76, height=32)
        dbtn(528, "加入队列", self.on_dl_add_queue)
        dbtn(616, "删除", self.on_dl_delete)
        dbtn(704, "本地打开", self.on_dl_show_dir)

        self._dl_menu_idx = -1
        self._dl_menu = tk.Menu(self.root, tearoff=0)
        self._dl_menu.add_command(label="加入播放队列",
                                  command=self._dl_menu_add_queue)
        self._dl_menu.add_command(label="删除",
                                  command=self._dl_menu_delete)
        self._dl_menu.add_command(label="从本地文件夹显示",
                                  command=self._dl_menu_show_dir)
        self.download_list.canvas.bind("<Button-3>", self._dl_right_click)

        # ---- 本地音乐面板 ----
        self.music_panel2 = ImagePanel(self.main, kind="main")
        self.music_panel2.place(x=0, y=0, width=800, height=472)
        tk.Label(self.music_panel2, text="本地音乐", bg="#FFFFFF",
                 fg="#1F2430", font=ui_font(16, "bold"),
                 anchor="w").place(x=20, y=12, width=200, height=32)
        self.local_list = ImageList(self.music_panel2, 800, 416,
                                    on_double=self.on_local_play)
        self.local_list.place(x=0, y=52, width=800, height=416)

# ---- 歌词面板 (覆盖内容区) ----
        self.lyrics_panel = LyricsPanel(self.main, width=800, height=536)
        self.lyrics_panel.place(x=0, y=0, width=800, height=536)
        self.lyrics_panel.set_fetch_callback(self._fetch_lyrics_for_current)
        self._lyrics_visible = False
        self._cur_panel = "home"

    def _build_search_area(self):
        sp = self.search_panel
        self._history = ["陈奕迅"]
        # 圆角胶囊容器 (半高圆角 = 胶囊)
        pill = tk.Canvas(sp, width=392, height=36, bg="#F7F8FA",
                         highlightthickness=0)
        pill.place(x=20, y=14, width=392, height=36)
        pill.create_rectangle(18, 0, 374, 36, fill="#F3F4F6", outline="",
                              width=0)
        pill.create_oval(0, 0, 36, 36, fill="#F3F4F6", outline="", width=0)
        pill.create_oval(356, 0, 392, 36, fill="#F3F4F6", outline="", width=0)

        # 用 tk.Entry 替代 ttk.Combobox: macOS 下原生支持鼠标选中文本与光标闪烁
        self.box = tk.Entry(sp, font=ui_font(12), bg="#FFFFFF", fg="#1F2430",
                            bd=0, relief="flat", insertbackground="#1F2430",
                            highlightthickness=0,
                            selectbackground=widgets.ACCENT_HEX,
                            selectforeground="#FFFFFF")
        self.box.insert(0, "陈奕迅")
        self.box.place(x=26, y=18, width=272, height=28)
        self.box.bind("<Return>", lambda e: self.on_search())
        self.box.bind("<Button-1>", lambda e: (self.box.focus_set(),
                                               self.root.tkraise(),
                                               self.box.focus_force()))

        # 历史下拉按钮 (取代 Combobox 箭头): 弹出搜索历史菜单
        self._history_menu = tk.Menu(self.root, tearoff=0)
        arrow = tk.Label(sp, text="\u25BE", font=symbol_font(11),
                         bg="#FFFFFF", fg="#8A93A0", cursor="hand2", bd=0)
        arrow.place(x=298, y=18, width=34, height=28)
        arrow.bind("<Button-1>", lambda e: self._pop_search_history())
        self._history_arrow = arrow

        self.btn_search = _CircleBtn(sp, "\U0001F50D", self.on_search,
                                     size=30, fill=widgets.ACCENT_HEX,
                                     active=widgets.ACCENT_DK_HEX,
                                     fg="#FFFFFF", bg="#F3F4F6",
                                     font=symbol_font(11))
        self.btn_search.place(x=354, y=19, width=30, height=30)

    def _build_control_bar(self):
        bar = tk.Frame(self.content_panel, width=800, height=44,
                       bg="#F7F8FA")
        bar.place(x=0, y=0, width=800, height=44)
        self.control_bar = bar

        self.select_all_var = tk.BooleanVar(value=False)
        self.select_all = ttk.Checkbutton(bar, text="全选",
                                          variable=self.select_all_var,
                                          command=self.toggle_check_all,
                                          cursor="hand2", style="TCheckbutton")
        self.select_all.place(x=16, y=6, width=66, height=30)

        def btn(x, text, command, accent=False):
            tk_btn = ttk.Button(bar, text=text, command=command,
                                cursor="hand2",
                                style="Accent.TButton" if accent
                                else "TButton")
            tk_btn.place(x=x, y=6, width=76, height=32)

        btn(96, "下载", self.on_download, accent=True)
        btn(184, "播放", self.on_play_online)
        btn(272, "加入队列", self.on_add_queue)
        tk.Label(bar, text="滚动到底部自动加载更多", bg="#F7F8FA",
                 fg="#9AA3B0", font=ui_font(10)).place(x=368, y=10)

    def _build_top_right(self):
        """右上角 4 个圆角图标按钮 (设置/下载/最小化/关闭)。"""
        x0 = 812
        y0 = 14
        btn = _CircleBtn(self.root, "\u2699", self.on_settings,
                         size=32, fill="#FFFFFF", active="#EEF0F3",
                         fg="#5A6472", bg="#F7F8FA", font=symbol_font(13))
        btn.place(x=x0, y=y0, width=32, height=32)
        btn2 = _CircleBtn(self.root, "\u2B07", self.show_download_panel,
                          size=32, fill="#FFFFFF", active="#EEF0F3",
                          fg="#5A6472", bg="#F7F8FA", font=symbol_font(13))
        btn2.place(x=x0 + 40, y=y0, width=32, height=32)
        btn3 = _CircleBtn(self.root, "\u2013", self.minimize,
                          size=32, fill="#FFFFFF", active="#EEF0F3",
                          fg="#5A6472", bg="#F7F8FA", font=symbol_font(13))
        btn3.place(x=x0 + 80, y=y0, width=32, height=32)
        btn4 = _CircleBtn(self.root, "\u00D7", self.exit_app,
                          size=32, fill="#FFFFFF", active="#FDE8E9",
                          fg="#E5484D", bg="#F7F8FA", font=symbol_font(14))
        btn4.place(x=x0 + 120, y=y0, width=32, height=32)

    # ------------------------------- 底部播放条 (浅色)
    def _build_playbar(self):
        bar = tk.Frame(self.root, bg="#FFFFFF", width=self.W, height=64)
        bar.place(x=0, y=self.H - 64, width=self.W, height=64)
        self.playbar = bar
        tk.Frame(bar, bg=BORDER_HEX, height=1).place(x=0, y=0, relwidth=1.0)

        # 封面 + 曲名
        self._pb_cover = tk.Label(bar, bg="#FFFFFF")
        self._pb_cover.place(x=14, y=8, width=48, height=48)
        self._pb_cover_ph = None
        self._pb_track = tk.Label(bar, text="未在播放", bg="#FFFFFF",
                                  fg="#1F2430", font=ui_font(12, "bold"),
                                  anchor="w")
        self._pb_track.place(x=70, y=8, width=190, height=48)

        # 传输控制
        self._pb_btn_prev = _CircleBtn(bar, "\u23EE", lambda: self._pb_prev_next(-1),
                                       size=40, fill="#F3F4F6", active="#E4E7EC",
                                       fg="#3A424C", bg="#FFFFFF",
                                       font=symbol_font(13))
        self._pb_btn_prev.place(x=268, y=12, width=40, height=40)
        self._pb_btn_play = _CircleBtn(bar, "\u25B6", self._pb_toggle,
                                       size=44, fill=widgets.ACCENT_HEX, active=widgets.ACCENT_DK_HEX,
fg="#FFFFFF", bg="#FFFFFF",
                                       font=symbol_font(14))
        self._pb_btn_play.place(x=312, y=10, width=44, height=44)
        self._pb_btn_next = _CircleBtn(bar, "\u23ED", lambda: self._pb_prev_next(1),
                                       size=40, fill="#F3F4F6", active="#E4E7EC",
                                       fg="#3A424C", bg="#FFFFFF",
                                       font=symbol_font(13))
        self._pb_btn_next.place(x=360, y=12, width=40, height=40)

        # 播放模式 (顺序/列表循环/单曲循环/随机) — 与传输三键同组
        self._pb_btn_mode = _CircleBtn(bar, "\U0001F501", self._pb_cycle_mode,
                                       size=28, fill="#F3F4F6", active="#E4E7EC",
                                       fg="#3A424C", bg="#FFFFFF",
                                       font=symbol_font(12))
        self._pb_btn_mode.place(x=406, y=18, width=28, height=28)

        # 进度 + 时间
        self._pb_time = tk.Label(bar, text="0:00 / 0:00", bg="#FFFFFF",
                                 fg="#6B7280", font=ui_font(10))
        self._pb_time.place(x=440, y=6, width=310)
        self._pb_progress = ProgressBar(bar, width=310, height=18,
                                        command=self._pb_seek, bg="#FFFFFF")
        self._pb_progress.place(x=440, y=32, width=310, height=18)

        # 音量 (静音按钮 + 滑杆)
        self._pb_btn_mute = _CircleBtn(bar, "\U0001F50A", self._pb_toggle_mute,
                                       size=28, fill="#F3F4F6", active="#E4E7EC",
                                       fg="#3A424C", bg="#FFFFFF",
                                       font=symbol_font(12))
        self._pb_btn_mute.place(x=764, y=18, width=28, height=28)
        self._pb_vol = ttk.Scale(bar, from_=0, to=100, value=50,
                                 style="TScale", command=self._pb_on_vol,
                                 cursor="hand2")
        self._pb_vol.place(x=794, y=34, width=56)

# 词 / 外部 / 队列
        self._pb_btn_queue = ttk.Button(bar, text="队列", command=self.open_queue,
                                        cursor="hand2", style="Ghost.TButton",
                                        takefocus=False)
        self._pb_btn_queue.place(x=858, y=18, width=44, height=28)
        self._pb_btn_lyr = ttk.Button(bar, text="词", command=self._toggle_lyrics,
                                      cursor="hand2", style="Ghost.TButton",
                                      takefocus=False)
        self._pb_btn_lyr.place(x=906, y=18, width=40, height=28)
        self._pb_btn_ext = ttk.Button(bar, text="外部", command=self._open_external,
                                      cursor="hand2", style="Ghost.TButton",
                                      takefocus=False)
        self._pb_btn_ext.place(x=950, y=18, width=44, height=28)

    # ============================================================== 层级切换
    def show_home(self):
        """对应 b1 -> Function.restore"""
        self._cur_panel = "home"
        self.lyrics_panel.lower()
        self.lyrics_panel.set_active(False)
        self._lyrics_visible = False
        self._pb_btn_lyr.configure(text="\u8bcd")  # 词
        for k, item in self._nav.items():
            item.set_selected(k == "home")
        self.recommend_grid.tkraise()
        self.control_bar.lower()
        self.content_panel.tkraise()
        self.music_panel.lower()
        self.music_panel2.lower()
        self.search_panel.tkraise()
        self.playbar.tkraise()
        if self.scan_dialog is not None:
            try:
                if self.scan_dialog.winfo_exists():
                    self.scan_dialog.destroy()
            except Exception:  # noqa: BLE001
                pass
            self.scan_dialog = None

    def show_download_panel(self):
        """对应 b2 / but2 下载管理"""
        self._cur_panel = "download"
        self.lyrics_panel.lower()
        self.lyrics_panel.set_active(False)
        self._lyrics_visible = False
        self._pb_btn_lyr.configure(text="\u8bcd")
        for k, item in self._nav.items():
            item.set_selected(k == "download")
        self.content_panel.lower()
        self.music_panel2.lower()
        self.music_panel.tkraise()
        self.search_panel.tkraise()
        self.playbar.tkraise()

    def show_local_music(self):
        """对应 b3 本地音乐"""
        self._cur_panel = "local"
        self.lyrics_panel.lower()
        self.lyrics_panel.set_active(False)
        self._lyrics_visible = False
        self._pb_btn_lyr.configure(text="\u8bcd")
        for k, item in self._nav.items():
            item.set_selected(k == "local")
        self.content_panel.lower()
        self.music_panel.lower()
        self.music_panel2.tkraise()
        self.search_panel.tkraise()
        self.playbar.tkraise()
        if self.scan_dialog is not None and self.scan_dialog.winfo_exists():
            try:
                self.scan_dialog.deiconify()
                self.scan_dialog.center()
                self.scan_dialog.lift()
                self.scan_dialog.focus_force()
            except Exception:  # noqa: BLE001
                pass
        else:
            self.scan_dialog = dialogs.LocalScanDialog(self.root,
                                                       self.add_local_song)

    # ============================================================== 搜索逻辑
    def _do_search(self, keyword, page, commit_page=False):
        """异步搜索: 网络在后台线程, 完成经 _ui_queue 回主线程更新列表。

        commit_page=True 表示成功后把 page 写回 self.page (翻页用)。
"""
        self._search_seq += 1
        seq = self._search_seq
        self._active_search_seq = seq      # 当前有效搜索 (翻页加载校验)
        self._has_more = False
        self._load_more_busy = False
        self.root.configure(cursor="watch")

        def worker():
            try:
                items = self.api.search(keyword, page)
            except Exception as exc:  # noqa: BLE001
                print("搜索失败:", exc)
                items = None

            def apply():
                if seq != self._search_seq:
                    return            # 已被更新的搜索取代, 丢弃旧结果
                self.root.configure(cursor="")
                if items:
                    self._record_covers(items)
                    self.search_array = [KuwoAPI.format_row(it) for it in items]
                    rows = [(str(i + 1), KuwoAPI.display_name(row),
                             KuwoAPI.artist_name(row), "")
                            for i, row in enumerate(self.search_array)]
                    self.results_list.set_data(rows)
                    self._has_more = len(items) >= 30   # 满页则可能还有下一页
                    # 无论当前在哪个页面, 搜索完成都切回搜索结果视图
                    self.show_home()
                    self.results_list.tkraise()
                    self.control_bar.tkraise()
                    if commit_page:
                        self.page = page
                else:
                    messagebox.showinfo("提示", "呜呜，搜索不到了。。。")

            self._ui_queue.put(apply)

        threading.Thread(target=worker, daemon=True).start()

    def _load_more(self):
        """滚轮触底: 异步加载下一页并追加 (无限滚动, 不重置滚动位置)。"""
        if self._load_more_busy or not self._has_more:
            return
        if not self.current_kw:
            return
        self._load_more_busy = True
        nxt = self.page + 1
        seq = self._active_search_seq

        def worker():
            try:
                items = self.api.search(self.current_kw, nxt)
            except Exception as exc:  # noqa: BLE001
                print("加载更多失败:", exc)
                items = None

            def apply():
                self._load_more_busy = False
                if seq != self._active_search_seq:
                    return            # 已换搜索, 丢弃
                if not items:
                    self._has_more = False
                    return
                more = [KuwoAPI.format_row(it) for it in items]
                self._record_covers(items)
                base = len(self.search_array)
                rows = [(str(base + i + 1), KuwoAPI.display_name(row),
                         KuwoAPI.artist_name(row), "")
                        for i, row in enumerate(more)]
                self.search_array.extend(more)
                self.results_list.append_rows(rows)
                self.page = nxt
                self._has_more = len(items) >= 30

            self._ui_queue.put(apply)

        threading.Thread(target=worker, daemon=True).start()

    def on_search(self):
        kw = self.box.get().strip() or "陈奕迅"
        self.current_kw = kw
        self.page = 1
        self.add_history(kw)
        self._do_search(kw, 1)

    def add_history(self, kw):
        """与原项目 box.addItem 一致: 不查重, 每次都追加。"""
        self._history.append(kw)
        self.box.delete(0, "end")
        self.box.insert(0, kw)

    def _pop_search_history(self):
        """弹出搜索历史下拉菜单 (取代 Combobox 箭头)。"""
        m = self._history_menu
        m.delete(0, "end")
        seen = []
        for kw in reversed(self._history):
            if kw and kw not in seen:
                seen.append(kw)
                m.add_command(label=kw,
                              command=lambda k=kw: self._apply_history(k))
        if not seen:
            m.add_command(label="(暂无历史)", state="disabled")
        try:
            m.tk_popup(self._history_arrow.winfo_rootx(),
                       self._history_arrow.winfo_rooty() + 30)
        finally:
            m.grab_release()

    def _apply_history(self, kw):
        self.box.delete(0, "end")
        self.box.insert(0, kw)
        self.on_search()

    def on_recommend_click(self, name):
        self.current_kw = name
        self.page = 1
        self.add_history(name)
        self._do_search(name, 1)

    def toggle_check_all(self):
        self.results_list.check_all(self.select_all_var.get())

    # ============================================================== 下载/播放
    def on_download(self):
        idxs = self.results_list.checked_indices()
        if not idxs:
            messagebox.showinfo("提示", "别闹，请选择要下载的歌曲")
            return
        os.makedirs(dialogs.DOWNLOAD_DIR, exist_ok=True)
        for idx in idxs:
            row = self.search_array[idx]
            display = KuwoAPI.display_name(row)      # 《歌名》.mp3 (保留书名号)
            n = str(len(self.download_paths) + 1)
            self.download_list.add((n, display,
                                    KuwoAPI.artist_name(row), "", "",
                                    "下载中..."))
            path = os.path.join(dialogs.DOWNLOAD_DIR, display)
            cover = self._cover_by_title.get(KuwoAPI.song_name(row))
            self.download_paths.append(path)
            self._dl_state[path] = {"row": len(self.download_paths) - 1,
                                "status": "downloading", "mb": 0,
                                "rid": KuwoAPI.row_rid(row),
                                "display": display,
                                "title": KuwoAPI.song_name(row),
                                "artist": KuwoAPI.artist_name(row),
                                "cover": cover}
            self._dl_failed.pop(path, None)
            self.api.download(KuwoAPI.row_rid(row), display,
                              dialogs.DOWNLOAD_DIR,
                              on_done=lambda p, fp=path: self._dl_finished(fp, p),
                              on_progress=lambda b, fp=path: self._dl_progress(fp, b),
                              title=KuwoAPI.song_name(row),
                              artist=KuwoAPI.artist_name(row),
                              cover=cover)
            print("开始下载:", KuwoAPI.song_name(row))

    # ------------------------------------------------------ 下载进度/重试
    def _dl_progress(self, path, bytes_done):
        """下载线程进度回调 (非主线程): 节流后更新第4列 MB。"""
        mb = bytes_done / (1024.0 * 1024.0)
        last = self._dl_last_mb.get(path, 0.0)
        if mb - last < 0.5:
            return
        self._dl_last_mb[path] = mb
        self._ui_queue.put(lambda: self._dl_progress_ui(path, mb))

    def _dl_progress_ui(self, path, mb):
        st = self._dl_state.get(path)
        if not st:
            return
        if st["status"] != "downloading":
            return
        st["mb"] = mb
        i = st["row"]
        old = self.download_list._rows[i] if i < len(self.download_list._rows) \
            else None
        if old:
            parts = list(old)
            if len(parts) < 6:
                parts += [""] * (6 - len(parts))
            parts[4] = widgets.fmt_size(mb * 1024 * 1024)
            parts[5] = "下载中 %.1fMB" % mb
            self.download_list.update_row(i, tuple(parts))

    def _dl_finished(self, path, result_path):
        """下载线程完成回调 (非主线程): 转投主线程更新状态。"""
        self._ui_queue.put(lambda: self._dl_finished_ui(path, result_path))

    def _dl_finished_ui(self, path, result_path):
        """下载完成/失败: 更新状态列, 完成的后台补读时长/歌手。"""
        st = self._dl_state.get(path)
        if not st:
            return
        if result_path:
            st["status"] = "done"
            self._threaded_meta(path)
        else:
            st["status"] = "failed"
            self._dl_failed[path] = {"rid": st.get("rid", ""),
                                     "display": st.get("display", ""),
                                     "title": st.get("title", ""),
                                     "artist": st.get("artist", ""),
                                     "cover": st.get("cover")}
        self._dl_refresh(path)

    def _dl_row(self, i, path):
        """生成下载列表行: (序号, 歌名, 歌手, 时长, 大小, 状态)。"""
        st = self._dl_state.get(path) or {}
        display = st.get("display") or os.path.basename(path)
        meta_dur, meta_artist = self._dl_meta.get(path, ("", ""))
        artist = st.get("artist") or meta_artist
        if path in self._dl_failed:
            status = "失败·双击重试"
        elif st.get("status") == "done":
            status = "✓ 完成"
        elif st.get("status") == "downloading":
            status = "下载中 %.1fMB" % st.get("mb", 0.0)
        else:
            status = ""
        size = widgets.fmt_size(os.path.getsize(path)) \
            if os.path.exists(path) else ""
        return (str(i + 1), display, artist, meta_dur, size, status)

    def _dl_refresh(self, path):
        """按 path 刷新下载列表该行 (主线程调用)。"""
        if path not in self.download_paths:
            return
        i = self.download_paths.index(path)
        st = self._dl_state.get(path)
        if st:
            st["row"] = i
        try:
            self.download_list.update_row(i, self._dl_row(i, path))
        except Exception:  # noqa: BLE001
            pass

    def _threaded_meta(self, path):
        """后台探读时长/歌手, 完成后回投刷新该行 (避免 UI 卡顿)。"""
        def worker():
            dur, artist = _probe_meta(path)
            self._dl_meta[path] = (dur, artist)
            if path in self.download_paths:
                self._ui_queue.put(lambda: self._dl_refresh(path))
        threading.Thread(target=worker, daemon=True).start()

    def _dl_retry(self, path):
        """失败行双击重试 (复用 on_download_play 入口)。"""
        info = self._dl_failed.get(path)
        if not info:
            return
        self._dl_state[path]["status"] = "downloading"
        self._dl_state[path]["mb"] = 0
        self._dl_failed.pop(path, None)
        self._dl_refresh(path)
        self.api.download(info["rid"], info["display"], dialogs.DOWNLOAD_DIR,
                          on_done=lambda p, fp=path: self._dl_finished(fp, p),
                          on_progress=lambda b, fp=path: self._dl_progress(fp, b),
                          title=info["title"], artist=info["artist"],
                          cover=info.get("cover"))

    def on_play_online(self):
        """在线播放: 下载到临时目录后, 在 APP 内部用 MCI 直接播放 (不再跳浏览器)。"""
        idxs = self.results_list.checked_indices()
        if not idxs:
            messagebox.showinfo("提示", "别闹，请选择要播放的歌曲")
            return
        self._play_online_row(self.search_array[idxs[0]])

    def _play_online_row(self, row):
        """把某条搜索结果行下载到临时目录后进程内播放。"""
        display = KuwoAPI.display_name(row)
        temp_dir = os.path.join(tempfile.gettempdir(), "musicplayer_online")
        os.makedirs(temp_dir, exist_ok=True)
        target = os.path.join(temp_dir, display)
        self._pb_online_target = target
        self._pb_track.configure(text="正在加载：%s" % KuwoAPI.song_name(row))
        self._pb_btn_play.set_glyph("\u25B6")
        # 下载线程完成回调会投递到主线程执行, 避免跨线程碰 UI
        self.api.download(KuwoAPI.row_rid(row), display, temp_dir,
                          on_done=self._online_ready,
                          title=KuwoAPI.song_name(row),
                          artist=KuwoAPI.artist_name(row),
                          cover=self._cover_by_title.get(
                              KuwoAPI.song_name(row)))

    def on_search_play(self, index):
        """搜索结果双击 → 直接在线播放该行。"""
        if 0 <= index < len(self.search_array):
            self._play_online_row(self.search_array[index])

    # ------------------------------------------------------ 播放队列
    def on_add_queue(self):
        """把勾选的搜索结果加入播放队列 (在线歌曲, 播放时自动下载)。"""
        idxs = self.results_list.checked_indices()
        if not idxs:
            messagebox.showinfo("提示", "别闹，请先勾选要加入队列的歌曲")
            return
        for idx in idxs:
            row = self.search_array[idx]
            self._queue.append({"title": KuwoAPI.song_name(row),
                                "type": "online", "row": row})
        if self._queue_dlg is not None:
            try:
                if self._queue_dlg.winfo_exists():
                    self._queue_dlg.refresh()
            except Exception:  # noqa: BLE001
                pass
        messagebox.showinfo("播放队列", "已加入 %d 首歌曲" % len(idxs))

    def open_queue(self):
        if self._queue_dlg is None or not self._queue_dlg.winfo_exists():
            self._queue_dlg = dialogs.QueueDialog(
                self.root, self, self._queue_play, self._queue_clear)
        else:
            self._queue_dlg.refresh()
            self._queue_dlg.deiconify()
            self._queue_dlg.lift()

    def _queue_play(self, index):
        if 0 <= index < len(self._queue):
            item = self._queue[index]
            if item.get("type") == "file":
                self._pb_playlist = [p.get("path") for p in self._queue
                                     if p.get("type") == "file"]
                self._pb_idx = index
                self._play_path(item["path"])
            else:
                self._play_online_row(item["row"])

    def _queue_clear(self):
        self._queue = []
        if self._queue_dlg is not None:
            try:
                self._queue_dlg.refresh()
            except Exception:  # noqa: BLE001
                pass

    def _online_ready(self, path):
        """下载线程回调 (非主线程): 转投主线程队列。"""
        self._ui_queue.put(lambda: self._online_ready_ui(path))

    def _online_ready_ui(self, path):
        """主线程: 临时文件就绪后进程内播放。"""
        if not path or not os.path.exists(path):
            self._pb_track.configure(text="在线播放加载失败")
            return
        self._pb_playlist = [path]
        self._pb_idx = 0
        self._play_path(path)

    def on_download_play(self, index):
        if 0 <= index < len(self.download_paths):
            path = self.download_paths[index]
            if path in self._dl_failed:
                self._dl_retry(path)      # 失败行双击 → 重试
                return
            self._pb_playlist = list(self.download_paths)
            self._pb_idx = index
            self._play_path(path)

    # ------------------------------------------------------ 下载管理操作
    def _dl_path_at(self, index):
        """返回第 index 行的下载路径, 越界/未完成返回 None。"""
        if not (0 <= index < len(self.download_paths)):
            return None
        path = self.download_paths[index]
        if path in self._dl_failed:
            return None
        st = self._dl_state.get(path) or {}
        if st.get("status") == "downloading":
            return None
        return path

    def _dl_add_queue(self, index):
        path = self._dl_path_at(index)
        if not path:
            messagebox.showinfo("提示", "该歌曲尚未下载完成")
            return
        title = (self._dl_state.get(path) or {}).get("display") or \
            os.path.basename(path)
        for q in self._queue:
            if q.get("type") == "file" and q.get("path") == path:
                messagebox.showinfo("播放队列", "该歌曲已在队列中")
                return
        self._queue.append({"type": "file", "path": path, "title": title})
        if self._queue_dlg is not None:
            try:
                if self._queue_dlg.winfo_exists():
                    self._queue_dlg.refresh()
            except Exception:  # noqa: BLE001
                pass
        messagebox.showinfo("播放队列", "已加入播放队列")

    def _dl_show_dir(self, index):
        if not (0 <= index < len(self.download_paths)):
            return
        folder = os.path.dirname(self.download_paths[index])
        if not os.path.isdir(folder):
            messagebox.showerror("错误", "下载文件夹不存在")
            return
        open_path(folder)

    def _dl_delete(self, index):
        if not (0 <= index < len(self.download_paths)):
            return
        path = self.download_paths[index]
        if path in self._dl_failed:
            self._dl_failed.pop(path, None)
        st = self._dl_state.get(path)
        if st and st.get("status") == "downloading":
            messagebox.showinfo("提示", "下载中的歌曲暂不能删除")
            return
        if not os.path.exists(path):
            if not messagebox.askyesno("删除", "歌曲文件不存在，要从列表中移除吗？"):
                return
        else:
            if not messagebox.askyesno("删除",
                                       "确定删除《%s》及歌词文件吗？" %
                                       os.path.basename(path)):
                return
            try:
                os.remove(path)
                lrc = os.path.splitext(path)[0] + ".lrc"
                if os.path.isfile(lrc):
                    os.remove(lrc)
            except OSError as exc:  # noqa: BLE001
                messagebox.showerror("删除失败", str(exc))
                return
        self.download_paths.pop(index)
        self._dl_state.pop(path, None)
        self._dl_failed.pop(path, None)
        if self._pb_path == path:      # 正在播放被删文件 → 停
            try:
                self._engine.stop()
                self._pb_path = None
                self._pb_btn_play.set_glyph("\u25B6")
                self._pb_track.configure(text="未在播放")
                self._pb_time.configure(text="0:00 / 0:00")
            except Exception:  # noqa: BLE001
                pass

        def rebuild():
            try:
                self.download_list.set_rows(rows)
            except Exception:  # noqa: BLE001
                pass
        rows = []
        for i, p in enumerate(self.download_paths):
            rows.append(self._dl_row(i, p))
        for i, p in enumerate(self.download_paths):
            stt = self._dl_state.get(p)
            if stt:
                stt["row"] = i
        self._ui_queue.put(rebuild)

    def _dl_right_click(self, event):
        idx = self.download_list._index_at(event.y)
        if idx is None:
            return
        self._dl_menu_idx = idx
        try:
            self._dl_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._dl_menu.grab_release()

    def _dl_menu_add_queue(self):
        self._dl_add_queue(self._dl_menu_idx)

    def _dl_menu_delete(self):
        self._dl_delete(self._dl_menu_idx)

    def _dl_menu_show_dir(self):
        self._dl_show_dir(self._dl_menu_idx)

    def on_dl_add_queue(self):
        idx = self.download_list.selected_index
        if idx is None:
            messagebox.showinfo("提示", "请先在列表里单击选中要操作的歌曲")
            return
        self._dl_add_queue(idx)

    def on_dl_delete(self):
        idx = self.download_list.selected_index
        if idx is None:
            messagebox.showinfo("提示", "请先在列表里单击选中要操作的歌曲")
            return
        self._dl_delete(idx)

    def on_dl_show_dir(self):
        idx = self.download_list.selected_index
        if idx is None:
            messagebox.showinfo("提示", "请先在列表里单击选中要操作的歌曲")
            return
        self._dl_show_dir(idx)

    def on_local_play(self, index):
        if 0 <= index < len(self.local_paths):
            self._pb_playlist = list(self.local_paths)
            self._pb_idx = index
            self._play_path(self.local_paths[index])

    def add_local_song(self, full):
        n = str(len(self.local_list.items()) + 1)
        self.local_list.add((n, os.path.basename(full), "", ""))
        self.local_paths.append(full)

    # ============================================================== 播放引擎
    def _open_external(self):
        """手动把当前歌曲交给"系统播放器"打开 (仅用户点击"外部"按钮时启动)。"""
        if not self._pb_path:
            return
        self._pb_ext = True
        self._pb_btn_play.set_glyph("\u25B6")
        try:
            self._pb_progress.configure(state="disabled")
        except Exception:  # noqa: BLE001
            pass
        if not open_path(self._pb_path):
            print("外部播放失败: 无法打开文件")
            messagebox.showerror("错误", "无法用系统播放器打开歌曲")
            self._pb_ext = False
            return
        self._pb_time.configure(text="外部播放器")
        self._pb_btn_ext.configure(text="外部\u2713")

    def _play_path(self, path):
        if not os.path.exists(path):
            messagebox.showerror("错误", "无法播放，歌曲可能已被删除")
            return
        self._pb_path = path
        self._pb_ext = False
        self._pb_dur = 1.0
        self._pb_track.configure(text=os.path.basename(path))
        self._update_cover()   # 封面异步加载
        try:
            self._pb_progress.configure(state="normal")
        except Exception:  # noqa: BLE001
            pass
        self._pb_time.configure(text="0:00 / 0:00")

        # ---- 加载歌词 (优先 .lrc 侧车文件, 再 fallback 嵌入 USLT) ----
        try:
            lrc_path = os.path.splitext(path)[0] + ".lrc"
            if os.path.isfile(lrc_path):
                with open(lrc_path, encoding="utf-8", errors="replace") as f:
                    pairs = parse_lrc(f.read())
                times = [p[0] for p in pairs]
                texts = [p[1] for p in pairs]
                self.lyrics_panel.set_lyrics(list(zip(times, texts)),
                                             title=os.path.basename(path))
            else:
                txt, _ = read_uslt(path)
                if txt and txt.strip():
                    texts = [l for l in txt.splitlines() if l.strip()]
                    self.lyrics_panel.set_static(texts,
                                                 title=os.path.basename(path))
                else:
                    self.lyrics_panel.clear("暂无歌词")
        except Exception:  # noqa: BLE001
            self.lyrics_panel.clear("歌词加载失败")

        if not self._engine.st.get("ok"):
            messagebox.showerror(
                "错误",
                "内部播放器不可用（%s）\n请点击右侧“外部”按钮改用系统播放器。"
                % self._engine.st.get("err"))
            return
        try:
            self._engine.play(path)
            self._pb_btn_play.set_glyph("\u23F8")
        except Exception as exc:  # noqa: BLE001
            print("播放错误:", exc)
            messagebox.showerror("错误", "播放失败（%s）" % exc)

    # ============================================================== 歌词获取
    @staticmethod
    def _song_title_artist(path):
        """从文件名解析 (歌名, 歌手): 支持《歌名》.mp3 与 歌名.mp3。"""
        base = os.path.splitext(os.path.basename(path))[0]
        m = re.search(r"《(.+)》", base)
        title = m.group(1).strip() if m else base.strip()
        return title, ""

    # ------------------------------------------------------ 封面 (真实优先)
    def _record_covers(self, items):
        """记录搜索结果 歌名→封面URL (rid 元组第 4 项)。"""
        for it in items:
            if len(it) < 4 or not it[3]:
                continue
            row = KuwoAPI.format_row(it)
            self._cover_by_title[KuwoAPI.song_name(row)] = \
                KuwoAPI.cover_url(it[3])

    def _update_cover(self):
        """播放条封面: 内嵌APIC → 同目录jpg → 在线封面URL → 占位。"""
        path = self._pb_path
        if not hasattr(self, "_pb_cover"):
            return
        ph = self._cover_cache.get("placeholder")
        if ph is None:
            ph = placeholder_cover(48)
            self._cover_cache["placeholder"] = ph
        self._pb_cover.configure(image=ph)
        self._pb_cover.image = ph
        if not path:
            return

        title = self._song_title_artist(path)[0]
        # 按歌名查搜索结果封面 URL (不管本地还是在线, 能识别同名歌曲即用)
        url = self._cover_by_title.get(title, "")

        def worker():
            img = None
            try:
                img = read_cover(path)               # 1 内嵌 APIC
            except Exception:  # noqa: BLE001
                img = None
            if img is None:
                base = os.path.splitext(path)[0]     # 2 同目录 jpg
                for cand in (base + ".jpg",
                             os.path.join(os.path.dirname(path), "cover.jpg"),
                             os.path.join(os.path.dirname(path), "folder.jpg")):
                    if os.path.isfile(cand):
                        try:
                            from PIL import Image as _I
                            img = _I.open(cand)
                        except Exception:  # noqa: BLE001
                            img = None
                        if img:
                            break
            if img is None and url:                  # 3 在线封面
                try:
                    r = requests.get(url, timeout=8)
                    if r.status_code == 200:
                        from PIL import Image as _I2
                        import io
                        img = _I2.open(io.BytesIO(r.content))
                except Exception:  # noqa: BLE001
                    img = None

            def apply():
                if self._pb_path != path:
                    return          # 已切歌
                if img is not None:
                    try:
                        ph2 = round_cover_photo(img, 48, 10)
                    except Exception:  # noqa: BLE001
                        return
                    self._pb_cover.configure(image=ph2)
                    self._pb_cover.image = ph2
                # else: 保持占位

            self._ui_queue.put(apply)

        threading.Thread(target=worker, daemon=True).start()

    def _fetch_lyrics_for_current(self):
        """当前歌曲无歌词时, 从多源抓取 (酷我→QQ→网易云), 成功后写入 .lrc。"""
        path = self._pb_path
        if not path:
            self.lyrics_panel.finish_fetch(False)
            return
        title, artist = self._song_title_artist(path)

        def worker():
            try:
                lrc = fetch_lyrics(0, title, artist)
            except Exception:  # noqa: BLE001
                lrc = None

            def apply():
                if self._pb_path != path:
                    return          # 已切歌, 丢弃结果
                if lrc:
                    pairs = parse_lrc(lrc)
                    times = [p[0] for p in pairs]
                    texts = [p[1] for p in pairs]
                    self.lyrics_panel.set_lyrics(
                        list(zip(times, texts)),
                        title=os.path.basename(path))
                    self.lyrics_panel.finish_fetch(True)
                    save_lrc(path, lrc)      # 落地 .lrc, 下次直接读
                else:
                    self.lyrics_panel.finish_fetch(False, "获取歌词失败，请稍后再试")

            self._ui_queue.put(apply)

        threading.Thread(target=worker, daemon=True).start()

    def _pb_toggle(self):
        if self._pb_ext or self._pb_path is None:
            return
        if not self._engine.st.get("ok"):
            messagebox.showinfo("提示", "内部播放器不可用，请用“外部”按钮。")
            return
        try:
            if self._engine.st["state"] == 3:
                self._engine.pause()
                self._pb_btn_play.set_glyph("\u25B6")
            else:
                self._engine.resume()
                self._pb_btn_play.set_glyph("\u23F8")
        except Exception as exc:  # noqa: BLE001
            print("播放切换失败:", exc)

    def _pb_prev_next(self, d):
        if not self._pb_playlist:
            return
        n = len(self._pb_playlist)
        if n <= 0:
            return
        # 手动上一首/下一首始终按列表顺序 ±1 (随机只影响自动切歌)
        self._pb_idx = (self._pb_idx + d) % n
        self._play_path(self._pb_playlist[self._pb_idx])

    # ------------------------------------------------------ 播放模式
    MODE_ICONS = ("\u23F9", "\U0001F501", "\U0001F502", "\U0001F500")
    MODE_NAMES = ("顺序播放", "列表循环", "单曲循环", "随机播放")

    def _pb_cycle_mode(self):
        self._pb_mode = (self._pb_mode + 1) % len(self.MODE_ICONS)
        self._pb_btn_mode.set_glyph(self.MODE_ICONS[self._pb_mode])
        self._save_settings()

    def _pb_auto_next(self):
        """一首歌自然播放结束后, 按播放模式决定下一首。"""
        if not self._pb_playlist:
            return
        n = len(self._pb_playlist)
        mode = self._pb_mode
        if mode == 2:                     # 单曲循环: 重播当前
            if 0 <= self._pb_idx < n:
                self._play_path(self._pb_playlist[self._pb_idx])
            return
        if mode == 0 and self._pb_idx >= n - 1:
            self._pb_btn_play.set_glyph("\u25B6")   # 顺序: 播完即停
            return
        if mode == 3:                     # 随机
            import random
            nxt = random.randrange(n)
            if n == 1:
                nxt = 0
            self._pb_idx = nxt
        else:                             # 列表循环: 回绕到下一首
            self._pb_idx = (self._pb_idx + 1) % n
        self._play_path(self._pb_playlist[self._pb_idx])

    def _pb_seek(self, v):
        # 程序化 set() 也会触发本回调 (ttk.Scale 特性), 必须忽略,
        # 否则 _poll_player 每 400ms 刷新进度都会重新 seek → 播放卡顿
        if self._pb_syncing:
            return
        if self._engine.st.get("ok") and not self._pb_ext and self._pb_dur > 0:
            try:
                self._engine.seek(v)
            except Exception:  # noqa: BLE001
                pass

    def _pb_on_vol(self, v):
        if not self._pb_ext:
            self._pb_vol_val = max(0.0, float(v))
            if self._pb_muted:
                self._pb_muted = False
                if self._pb_btn_mute is not None:
                    self._pb_btn_mute.set_glyph("\U0001F50A")
            try:
                self._engine.setvol(v)
            except Exception:  # noqa: BLE001
                pass
            self._save_settings()

    def _pb_toggle_mute(self):
        """静音/取消静音 (记忆音量)。"""
        if not self._pb_ext:
            if self._pb_muted:
                self._pb_muted = False
                self._engine.setvol(self._pb_vol_prev)
                self._pb_vol.set(self._pb_vol_prev)
                self._pb_btn_mute.set_glyph("\U0001F50A")
            else:
                self._pb_muted = True
                self._pb_vol_prev = int(self._pb_vol.get() or 50)
                self._engine.setvol(0)
                self._pb_btn_mute.set_glyph("\U0001F507")
            self._save_settings()

    def _poll_player(self):
        """每 400ms 从引擎状态 dict 刷新进度/时长 (不跨线程访问 winmm)。"""
        if self._pb_path and not self._pb_ext:
            st = self._engine.st
            if st.get("ok"):
                dur = float(st.get("dur") or 0.0)
                pos = float(st.get("pos") or 0.0)
                if dur > 0:
                    self._pb_dur = dur
                    if int(float(self._pb_progress.cget("to"))) != int(dur) + 1:
                        self._pb_progress.configure(to=int(dur) + 1)
                    if abs(pos - self._pb_last_set) >= 0.2:
                        try:
                            self._pb_syncing = True      # 阻止回调触发 seek
                            self._pb_progress.set(min(pos, dur))
                            self._pb_last_set = pos
                        except Exception:  # noqa: BLE001
                            pass
                        finally:
                            self._pb_syncing = False
                    self._pb_time.configure(
                        text="%s / %s" % (self._fmt(pos), self._fmt(dur)))
# 播放中时显示暂停图标, 否则显示播放图标
                try:
                    icon = ("\u23F8" if int(st.get("state") or 0) == 3
                            else "\u25B6")
                    if self._pb_btn_play._glyph != icon:
                        self._pb_btn_play.set_glyph(icon)
                except Exception:  # noqa: BLE001
                    pass
                # 播放结束 (state 3→stopped) → 按播放模式自动切歌
                st_now = int(st.get("state") or 0)
                if st_now == 3:
                    self._pb_was_playing = True
                elif self._pb_was_playing and st_now != 2:
                    self._pb_was_playing = False
                    try:
                        self._pb_auto_next()
                    except Exception:  # noqa: BLE001
                        pass
                self._pb_pos = pos
                # 歌词面板: 播放位置 → 动画高亮
                try:
                    self.lyrics_panel.set_position(pos * 1000)
                except Exception:  # noqa: BLE001
                    pass
        try:
            if self.root.winfo_exists():
                self.root.after(400, self._poll_player)
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def _fmt(t):
        t = int(t)
        return "%d:%02d" % (t // 60, t % 60)

    # ============================================================== 设置持久化
    def _load_settings(self):
        """读取 settings.json, 恢复播放模式/音量/静音 (不自动播放)。"""
        try:
            with open(self._settings_path, encoding="utf-8") as f:
                import json
                s = json.load(f)
        except Exception:  # noqa: BLE001
            return
        try:
            self._pb_mode = int(s.get("mode", 1)) % len(self.MODE_ICONS)
            self._pb_btn_mode.set_glyph(self.MODE_ICONS[self._pb_mode])
            vol = max(0, min(100, int(s.get("volume", 50))))
            self._pb_vol_val = vol
            self._pb_vol_prev = vol
            self._pb_vol.set(vol)
            self._engine.setvol(vol)
            self._pb_muted = bool(s.get("muted", False))
            if self._pb_muted:
                self._engine.setvol(0)
        except Exception:  # noqa: BLE001
            pass

    def _save_settings(self):
        """保存播放模式/音量/静音到 settings.json。"""
        import json
        try:
            data = {"mode": int(self._pb_mode),
                    "volume": int(self._pb_vol_val),
                    "muted": bool(self._pb_muted)}
            with open(self._settings_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:  # noqa: BLE001
            pass

# ============================================================== 快捷键
    def _bind_shortcuts(self):
        """空格=播放/暂停, ←→=±5s, ↑↓=音量 (搜索框输入时忽略)。"""
        def _in_box():
            try:
                f = self.root.focus_get()
            except Exception:  # noqa: BLE001
                return False
            if f is None:
                return False
            return f == self.box or f in self.box.winfo_children()

        self.root.bind("<space>", lambda e: self._pb_toggle()
                       if not _in_box() else None)
        self.root.bind("<Left>", lambda e: self._pb_seek_rel(-5)
                       if not _in_box() else None)
        self.root.bind("<Right>", lambda e: self._pb_seek_rel(5)
                       if not _in_box() else None)
        self.root.bind("<Up>", lambda e: self._pb_vol_rel(5)
                       if not _in_box() else None)
        self.root.bind("<Down>", lambda e: self._pb_vol_rel(-5)
                       if not _in_box() else None)

    def _pb_seek_rel(self, dt):
        if self._pb_ext or not self._pb_path:
            return
        pos = float(self._engine.st.get("pos") or 0.0)
        self._pb_seek(max(0, pos + dt))

    def _pb_vol_rel(self, d):
        if self._pb_ext:
            return
        v = max(0, min(100, int(self._pb_vol.get() or 50) + d))
        self._pb_vol.set(v)
        self._pb_on_vol(v)

    # ============================================================== 设置/托盘
    def on_settings(self):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="主题色", command=self.open_theme_dialog)
        menu.add_separator()
        menu.add_command(label="设置默认存储位置", command=self.open_storage_dialog)
        menu.add_separator()
        menu.add_command(label="反馈",
                         command=lambda: messagebox.showinfo(
                             "反馈", "仅作学习交流使用，请支持正版音乐。"))
        try:
            x = self.root.winfo_rootx() + 812
            y = self.root.winfo_rooty() + 46
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def open_theme_dialog(self):
        def change(hex_color):
            widgets.set_accent(hex_color)
            self._apply_accent()
        dialogs.ThemeDialog(self.root, change, current=widgets.ACCENT_HEX)

    def _apply_accent(self):
        """切换强调色后重刷主题相关控件。"""
        widgets.apply_tk_theme(self.root)
        widgets.refresh_all_theme()
        self._draw_logo()
        for item in self._nav.values():
            item.set_selected(item._sel)
        self._pb_btn_play.set_fill(widgets.ACCENT_HEX, widgets.ACCENT_DK_HEX)
        self.btn_search.set_fill(widgets.ACCENT_HEX, widgets.ACCENT_DK_HEX)

    def open_storage_dialog(self):
        dialogs.StorageDialog(self.root)

    def _toggle_lyrics(self):
        """切换歌词面板显示/隐藏。"""
        if self._lyrics_visible:
            self.lyrics_panel.lower()
            self.lyrics_panel.set_active(False)
            self._lyrics_visible = False
            self._pb_btn_lyr.configure(text="\u8bcd")
            {"home": self.show_home,
             "download": self.show_download_panel,
             "local": self.show_local_music}.get(self._cur_panel, self.show_home)()
        else:
            self.lyrics_panel.tkraise()
            self.playbar.tkraise()
            self._lyrics_visible = True
            self._pb_btn_lyr.configure(text="\u8bcd\u2713")
            self.lyrics_panel.set_active(True)

    def minimize(self):
        if dialogs.tray_available():
            self._to_tray()
            return
        self._taskbar_minimize()

    def _taskbar_minimize(self):
        """无托盘时最小化: macOS 到 Dock / Windows 到任务栏。

        无边框窗口直接 iconify 在多数平台上不可靠, 先临时加回系统
        装饰再最小化 (macOS 上 overrideredirect 切换失败则直接 iconify)。
        splash 型窗口 (macOS) 本身无边框, 无需切换装饰, 直接最小化即可。
        """
        if getattr(self, "_splash_mode", False):
            self._taskbar_min = (self.root.winfo_x(), self.root.winfo_y())
            try:
                self.root.iconify()
            except tk.TclError:
                pass
            return
        self._taskbar_min = (self.root.winfo_x(), self.root.winfo_y())
        self._minimizing = True
        try:
            self.root.overrideredirect(False)
            self.root.update_idletasks()   # 先让系统拿到带边框的新样式
            self.root.iconify()
        except tk.TclError:
            try:
                # macOS: 可能无法动态去掉 overrideredirect -> 直接最小化
                self.root.iconify()
            except tk.TclError:
                pass
            self._minimizing = False
            try:
                self.root.overrideredirect(True)
            except Exception:  # noqa: BLE001
                pass

    def _on_map(self, e):
        """从任务栏点击恢复: 去掉系统边框回到无边框, 并恢复到原位置。"""
        if getattr(self, "_minimizing", False):
            # 最小化瞬间自身触发的 Map 事件: 等真正回到 normal 再处理
            if self.root.state() != "normal":
                return
            self._minimizing = False
        pos = getattr(self, "_taskbar_min", None)
        if pos is None:
            return
        self._taskbar_min = None
        if not getattr(self, "_splash_mode", False):
            try:
                self.root.overrideredirect(True)
            except Exception:  # noqa: BLE001
                pass
        self.root.geometry("+%d+%d" % pos)
        self.root.tkraise()
        self.root.focus_force()

    def _to_tray(self):
        if not self.tray_active:
            self.tray_active = True
            self.tray_icon = dialogs.run_tray(os.path.join(PICTRUE, "logo.jpg"),
                                              self.root)
            if self.tray_icon is None:
                self.tray_active = False
                self._taskbar_minimize()
                return
        self.root.withdraw()

    def show_from_tray(self):
        self.root.deiconify()
        self.root.state("normal")
        self.root.tkraise()
        self.root.focus_force()   # 从托盘回来也确保窗口可接收键盘

    def exit_app(self):
        self._save_settings()
        if self.tray_icon is not None and self.tray_active:
            try:
                self.tray_icon.stop()
            except Exception:  # noqa: BLE001
                pass
        self.root.destroy()

    # ============================================================== 拖拽
    def _bind_drag(self, widget):
        widget.bind("<Button-1>", self._start_drag)
        widget.bind("<B1-Motion>", self._on_drag)

    def _start_drag(self, e):
        self.drag_off = (e.x_root - self.root.winfo_x(),
                         e.y_root - self.root.winfo_y())

    def _on_drag(self, e):
        x = e.x_root - self.drag_off[0]
        y = e.y_root - self.drag_off[1]
        self.root.geometry("+%d+%d" % (x, y))

    # ============================================================== 线程->UI
    def _poll_ui(self):
        """把工作线程投递的 UI 更新在 Tk 主线程执行, 防止跨线程 after 崩溃。"""
        try:
            for _ in range(200):
                fn = self._ui_queue.get_nowait()
                try:
                    fn()
                except Exception as exc:  # noqa: BLE001
                    print("UI 回调错误:", exc)
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(150, self._poll_ui)

    # ============================================================== 启动读取
    def _load_download_dir(self):
        try:
            folder = dialogs.DOWNLOAD_DIR
            if not os.path.isdir(folder):
                return
            rows = []
            for i, fn in enumerate(sorted(f for f in os.listdir(folder)
                                          if f.lower().endswith(".mp3"))):
                full = os.path.join(folder, fn)
                dur, artist = _probe_meta(full)
                self._dl_meta[full] = (dur, artist)
                size = widgets.fmt_size(os.path.getsize(full))
                rows.append((str(len(self.download_paths) + i + 1), fn,
                             artist, dur, size, ""))
                self.download_paths.append(full)
            if rows:
                # 不能跨线程直接 after, 只把工作投递到主线程队列
                self._ui_queue.put(lambda: self.download_list.set_rows(rows))
        except Exception as exc:  # noqa: BLE001
            print("读取下载目录失败:", exc)


if __name__ == "__main__":
    MainWindow()


