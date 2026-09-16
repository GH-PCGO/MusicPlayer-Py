# -*- coding: utf-8 -*-
"""
设置相关窗口及系统托盘 (类比原 ChangeBackground / StorageLocation / ReadLocalMusic)
优化 (P0-4/P1-5/P1-6):
- 卡片式容器 + 定宽按钮 + 输入框内边距; 背景盖一层低饱和遮罩
- 换肤缩略图等比 cover 裁切 (不拉伸畸变) + 圆角白卡
- 全部使用 ttk 控件, 跟随统一主题
"""
import os
import queue
import sys
import threading
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import filedialog, messagebox

from PIL import Image, ImageDraw

from .widgets import PICTRUE, MAIN_BG, SEARCH_BG, FONT_FAMILY, load_image, \
    to_photo, cover_crop, ACCENT_HEX, ACCENT_DK_HEX, ACCENT_TXT_HEX, \
    ACCENT_SOFT_HEX
from .paths import DOWNLOAD_DIR

# 换肤窗口里的 5 个选择 (与原 ChangeBackground.java 坐标/尺寸一致):
#   b1 (40,60) b2 (300,60) b3 (40,540) b4 (300,540) b5 (600,60), 均 220x330
BG_CHOICES = [
    ("background1.jpg", 40, 60),
    ("background2.jpg", 300, 60),
    ("background3.jpg", 40, 540),
    ("logo.jpg", 300, 540),
    ("background5.jpg", 600, 60),
]


def _dimmed(path, w, h, alpha=70):
    """背景图 cover 铺底 + 深色遮罩, 让前景不乱。"""
    cov = cover_crop(Image.open(path), w, h).convert("RGBA")
    mask = Image.new("RGBA", (w, h), (15, 18, 24, alpha))
    return to_photo(Image.alpha_composite(cov, mask))


def _thumb(path, w, h, margin=6, radius=8):
    """等比 cover 缩略图 + 圆角白卡 + 浅投影 (不拉伸畸变)。"""
    img = Image.open(path).convert("RGB")
    art = cover_crop(img, w - 2 * margin, h - 2 * margin)
    art_mask = Image.new("L", art.size, 0)
    ImageDraw.Draw(art_mask).rounded_rectangle([0, 0, art.size[0] - 1,
                                                art.size[1] - 1],
                                               radius=radius, fill=255)
    card = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    card.paste(art, (margin, margin), art_mask)
    box_w, box_h = w + 10, h + 10
    out = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    d.rounded_rectangle([5, 7, 5 + w - 1, 7 + h - 1], radius=14,
                        fill=(20, 26, 38, 45))
    out.alpha_composite(card, (5, 5))
    return to_photo(out)


def _center_over(win, w, h, master=None):
    """把窗口居中到 master (主窗口) 之上; 无 master 时居中屏幕, 并防跑出屏。"""
    win.update_idletasks()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    try:
        if master is not None and master.winfo_exists() and \
                master.winfo_ismapped():
            mx, my = master.winfo_rootx(), master.winfo_rooty()
            mw, mh = master.winfo_width(), master.winfo_height()
        else:
            mx, my, mw, mh = 0, 0, sw, sh
    except Exception:  # noqa: BLE001
        mx, my, mw, mh = 0, 0, sw, sh
    x = max(0, min(mx + (mw - w) // 2, sw - w))
    y = max(0, min(my + (mh - h) // 2, sh - h))
    win.geometry("+%d+%d" % (x, y))


class ThemeDialog(tk.Toplevel):
    """主题色选择窗口: 5 个预设强调色 (简约卡片)。"""

    COLORS = [
        ("音乐绿", "#1DB954"),
        ("清爽蓝", "#3B82F6"),
        ("品牌紫", "#7C3AED"),
        ("暖阳橙", "#F59E0B"),
        ("珊瑚红", "#EF4444"),
    ]

    def __init__(self, master, on_change, current=None):
        super().__init__(master)
        self.title("主题色")
        self.geometry("520x320")
        self.resizable(False, False)
        self.on_change = on_change
        self.configure(bg="#FFFFFF")

        tk.Label(self, text="选择主题色", font=(FONT_FAMILY, 18, "bold"),
                 bg="#FFFFFF", fg="#1F2430").place(x=24, y=20)

        card = tk.Frame(self, bg="#F7F8FA", highlightthickness=1,
                        highlightbackground="#E7E9EE")
        card.place(x=24, y=66, width=472, height=180)

        n = len(self.COLORS)
        slot = 92
        start_x = (472 - (n * slot - 12)) // 2
        for i, (name, color) in enumerate(self.COLORS):
            x = start_x + i * slot
            c = tk.Canvas(card, width=80, height=120, bg="#F7F8FA",
                          highlightthickness=0, cursor="hand2")
            c.place(x=x, y=30)
            active = (current or "").lower() == color.lower()
            ring = 4 if active else 0
            c.create_oval(6 - ring, 6 - ring, 74 + ring, 74 + ring,
                          outline="#D4D8DE", width=1 if not active else 2)
            c.create_oval(12, 12, 68, 68, fill=color, outline="")
            c.create_text(40, 100, text=name, fill="#6B7280",
                          font=(FONT_FAMILY, 11))
            c.bind("<Button-1>", lambda e, col=color: self._pick(col))
        tk.Label(self, text="设置后立即生效", font=(FONT_FAMILY, 10),
                 bg="#FFFFFF", fg="#9AA3B0").place(x=24, y=262)

        self.center()

    def center(self):
        _center_over(self, 520, 320, self.master)

    def _pick(self, color):
        if self.on_change:
            self.on_change(color)
        self.destroy()


class StorageDialog(tk.Toplevel):
    """设置默认存储位置窗口 (卡片式)。"""

    def __init__(self, master):
        super().__init__(master)
        self.title("存储位置")
        self.geometry("520x300")
        self.resizable(False, False)
        self.configure(bg="#FFFFFF")

        tk.Label(self, text="设置默认存储位置", font=(FONT_FAMILY, 18, "bold"),
                 bg="#FFFFFF", fg="#1F2430").place(x=24, y=20)

        card = tk.Frame(self, bg="#F7F8FA", highlightthickness=1,
                        highlightbackground="#E7E9EE")
        card.place(x=24, y=70, width=472, height=120)

        tk.Label(card, text="存储位置：", font=(FONT_FAMILY, 12),
                 bg="#F7F8FA", fg="#5A6472").place(x=20, y=42)
        self.entry = ttk.Entry(card, font=(FONT_FAMILY, 11), state="readonly")
        self.entry.place(x=106, y=36, width=240, height=36)
        ttk.Button(card, text="选择...", command=self._choose,
                   style="Accent.TButton").place(x=360, y=36, width=92, height=36)
        self._set_dir(DOWNLOAD_DIR)

        self.center()

    def center(self):
        _center_over(self, 520, 300, self.master)

    def _set_dir(self, path):
        show = path if len(path) <= 40 else "…" + path[-(len(path) - 37):]
        self.entry.configure(state="normal")
        self.entry.delete(0, "end")
        self.entry.insert(0, show)
        self.entry.configure(state="readonly")

    def _choose(self):
        folder = filedialog.askdirectory(title="选择存储目录")
        if folder:
            global DOWNLOAD_DIR
            DOWNLOAD_DIR = folder
            self._set_dir(folder)


class LocalScanDialog(tk.Toplevel):
    """本地音乐扫描窗口 (视觉重做 + macOS 焦点修复)。

    - 无边框浮层: macOS 用 -type splash (可正常接收点击/焦点),
      其余平台 overrideredirect。
    - 关闭/销毁时自动把焦点还给主窗口, 避免 macOS 上"关掉后点不动主界面"。
    """

    def __init__(self, master, on_file):
        super().__init__(master)
        self.title("本地音乐")
        self.geometry("640x300")
        self.resizable(False, False)
        self.on_file = on_file
        self._dir = None
        self._scanning = False
        self._stop = False
        self._found = 0

        if sys.platform == "darwin":
            try:
                self.attributes("-type", "splash")
            except tk.TclError:  # pragma: no cover - 极老 Tk 兜底
                self.overrideredirect(True)
        else:
            self.overrideredirect(True)
        self.protocol("WM_DELETE_WINDOW", self._hide)
        self.configure(bg="#FFFFFF")

        # 顶部绿色强调条
        tk.Frame(self, bg=ACCENT_HEX, height=5).place(x=0, y=0, width=640)

        # 头部: 绿圆音符图标 + 标题/副标题
        icon = tk.Canvas(self, width=46, height=46, bg="#FFFFFF",
                         highlightthickness=0)
        icon.place(x=26, y=20)
        icon.create_oval(1, 1, 45, 45, fill=ACCENT_HEX, outline="")
        icon.create_text(23, 24, text="\u266A", fill="#FFFFFF",
                         font=(FONT_FAMILY, 22, "bold"))
        tk.Label(self, text="扫描本地音乐", bg="#FFFFFF", fg="#1F2430",
                 font=(FONT_FAMILY, 18, "bold")).place(x=84, y=20)
        tk.Label(self, text="选择文件夹，把里面的 MP3 一键加入本地音乐",
                 bg="#FFFFFF", fg="#9AA3B0",
                 font=(FONT_FAMILY, 11)).place(x=84, y=52)

        # 文件夹选择卡片
        card = tk.Frame(self, bg="#F7F8FA", highlightthickness=1,
                        highlightbackground="#E7E9EE")
        card.place(x=26, y=86, width=588, height=92)
        tk.Label(card, text="文件夹", bg="#F7F8FA", fg="#5A6472",
                 font=(FONT_FAMILY, 11)).place(x=20, y=12)
        self.text = ttk.Entry(card, font=(FONT_FAMILY, 11), state="readonly")
        self.text.place(x=20, y=38, width=424, height=34)
        self.btn_choose = ttk.Button(card, text="选择...", command=self._choose,
                                     style="Accent.TButton")
        self.btn_choose.place(x=456, y=36, width=112, height=36)

        # 状态区 (扫描进度/提示)
        self.status = tk.Label(self, text="请选择文件夹开始扫描",
                               bg="#FFFFFF", fg="#9AA3B0",
                               font=(FONT_FAMILY, 12), anchor="w")
        self.status.place(x=28, y=194, width=580)
        self.now = tk.Label(self, text="", bg="#FFFFFF", fg="#5A6472",
                            font=(FONT_FAMILY, 11), anchor="w")
        self.now.place(x=28, y=222, width=580)

        # 底部按钮
        self.btn_scan = ttk.Button(self, text="\u25B6 开始扫描", command=self._scan,
                                   style="Accent.TButton")
        self.btn_scan.place(x=378, y=260, width=112, height=34)
        self.btn_ok = ttk.Button(self, text="完成", command=self._hide,
                                 style="TButton")
        self.btn_ok.place(x=502, y=260, width=112, height=34)
        self.bind("<Return>", lambda e: self._hide())
        self.bind("<Escape>", lambda e: self._hide())
        self.bind("<Destroy>", self._on_destroy)

        # 工作线程只往队列投递, 由主线程 after 轮询刷新 (Tk 非线程安全)
        self._scan_queue = queue.SimpleQueue()
        self.after(100, self._drain)

        self.center()

    def center(self):
        _center_over(self, 640, 300, self.master)

    def _refocus_master(self):
        """关闭后把点击/键盘焦点还给主窗口。"""
        try:
            m = self.master
            if m is not None and m.winfo_exists():
                m.lift()
                m.focus_force()
        except Exception:  # noqa: BLE001
            pass

    def _on_destroy(self, event):
        if event.widget is self:
            self._refocus_master()

    def _choose(self):
        folder = filedialog.askdirectory(title="选择文件夹")
        if folder:
            self._dir = folder
            self.text.configure(state="normal")
            self.text.delete(0, "end")
            self.text.insert(0, folder)
            self.text.configure(state="readonly")
            self.status.configure(text="文件夹已选择，点击「开始扫描」")
            self.status.configure(fg=ACCENT_TXT_HEX)

    def _scan(self):
        if self.text.get().strip() == "":
            self.status.configure(text="请先选择文件路径！")
            self.status.configure(fg="#EF4444")
            return
        if self._scanning:
            return
        self._scanning = True
        self._found = 0
        self.btn_scan.configure(state="disabled")
        self.status.configure(text="正在扫描文件…", fg="#1F2430")
        root = self.text.get().strip()
        threading.Thread(target=self._walk, args=(root,), daemon=True).start()

    def _web(self, fn):
        """工作线程投递 UI 更新到队列, 由主线程 _drain 执行。"""
        self._scan_queue.put(fn)

    def _drain(self):
        """主线程轮询: 执行扫描线程投递的 UI 更新。"""
        try:
            while True:
                fn = self._scan_queue.get_nowait()
                self._apply(fn)
        except queue.Empty:
            pass
        try:
            if self.winfo_exists():
                self.after(100, self._drain)
        except Exception:  # noqa: BLE001
            pass

    def _apply(self, fn):
        if fn is None:
            self.status.configure(text="正在扫描文件…")
        elif fn is True:
            self.status.configure(text="扫描完成！新发现 %d 首歌曲" % self._found,
                                  fg=ACCENT_TXT_HEX)
            self.now.configure(text="")
            self.btn_scan.configure(state="normal")
        else:
            self._found += 1
            self.now.configure(text=fn)
            self.on_file(fn)

    def _walk(self, root):
        try:
            for dirpath, _dirnames, filenames in os.walk(root):
                for fn in filenames:
                    if self._stop:
                        return
                    if fn.lower().endswith(".mp3"):
                        full = os.path.join(dirpath, fn)
                        self._web(None)
                        self._web(full)
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._scanning = False
            self._stop = False
            self._web(True)
            self.after(0, lambda: self.btn_scan.configure(state="normal"))

    def _hide(self):
        self.withdraw()
        self._refocus_master()


class QueueDialog(tk.Toplevel):
    """播放队列浮层: 显示队列、双击跳播、清空、关闭。"""

    def __init__(self, master, app, on_play, on_clear):
        super().__init__(master)
        self.title("播放队列")
        self.geometry("360x440")
        self.resizable(False, False)
        self.configure(bg="#FFFFFF")
        self._app = app
        self._on_play = on_play
        self._on_clear = on_clear

        tk.Label(self, text="播放队列", font=(FONT_FAMILY, 16, "bold"),
                 bg="#FFFFFF", fg="#1F2430").place(x=18, y=14)

        self._list = tk.Listbox(self, bg="#FFFFFF", fg="#1F2430",
                                font=(FONT_FAMILY, 11), bd=0,
                                highlightthickness=0, selectbackground="#E7F8EE",
                                selectforeground="#0F9D4A", activestyle="none")
        self._list.place(x=16, y=52, width=328, height=330)
        self._list.bind("<Double-Button-1>", self._pick)
        sb = ttk.Scrollbar(self, orient="vertical",
                           command=self._list.yview)
        self._list.configure(yscrollcommand=sb.set)
        sb.place(x=344, y=52, width=10, height=330)

        ttk.Button(self, text="清空", command=self._clear,
                   style="TButton").place(x=90, y=396, width=90, height=32)
        ttk.Button(self, text="关闭", command=self.destroy,
                   style="TButton").place(x=192, y=396, width=90, height=32)

        self.refresh()
        _center_over(self, 360, 440, self.master)

    def refresh(self):
        self._list.delete(0, "end")
        for i, item in enumerate(self._app._queue):
            self._list.insert("end", "%d. %s" % (i + 1,
                                                 item.get("title", "?")))
        if not self._app._queue:
            self._list.insert("end", "（队列为空）")

    def _pick(self, _e):
        sel = self._list.curselection()
        if sel and sel[0] < len(self._app._queue):
            self._on_play(sel[0])

    def _clear(self):
        self._on_clear()


def tray_available():
    try:
        import pystray  # noqa: F401
        return True
    except ImportError:
        return False


def run_tray(icon_image_path, master):
    """系统托盘 (可选 pystray)。返回 tray 线程对象; 不可用时返回 None。"""
    if not tray_available():
        return None
    import pystray
    from PIL import Image
    from threading import Thread

    icon_image = Image.open(icon_image_path).resize((64, 64))

    def on_open(icon, item):
        icon.stop()
        master.after(0, master.show_from_tray)

    def on_quit(icon, item):
        icon.stop()
        master.after(0, master.exit_app)

    menu = pystray.Menu(
        pystray.MenuItem("打开主界面", on_open, default=True),
        pystray.MenuItem("退出", on_quit),
    )
    icon = pystray.Icon("music_player", icon_image, "音乐下载器", menu)

    def worker():
        icon.run()

    t = Thread(target=worker, daemon=True)
    t.start()
    return icon