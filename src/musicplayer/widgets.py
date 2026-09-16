# -*- coding: utf-8 -*-
"""
自定义组件 (类比原 Java 的 MyMusicPanel / SearchPanel / SlidePanel / MyJcheckBox)
优化后的渲染方案 (P0~P2):
- 面板背景: 背景图等比 cover 铺底 (不再拉伸变形)
- 列表: 连续背景切片 + 高不透明白底 + 深色文字 (选中=主题蓝底白字);
  顶部列头 (序号/歌名/歌手/时长), 行高加大留出内边距
- 推荐格: 连续 cover 背景 + 圆角白卡 + 1:1 裁切封面 + 歌名
- ttk 主题统一 (按钮/复选框/下拉框/滚动条/滑杆)
"""
import base64
import io as _io
import os
import re
import sys
import tkinter as tk
import tkinter.ttk as ttk

from PIL import Image, ImageDraw, ImageFont

from .paths import PICTRUE

# 共享主题背景 (对应原 MyMusicPanel.path / SearchPanel.path)
MAIN_BG = os.path.join(PICTRUE, "logo.jpg")
SEARCH_BG = os.path.join(PICTRUE, "logo.jpg")

# 全局字号 (macOS 苹方 / Windows 微软雅黑)
FONT_FAMILY = "PingFang SC" if sys.platform == "darwin" else "微软雅黑"
DEFAULT_SIZE = 13
ROW_H = 46
HEADER_H = 44

# ---------------------------------------------------------------- 浅色极简配色令牌
ACCENT_HEX = "#1DB954"            # 音乐绿 (强调)
BORDER_HEX = "#E7E9EE"            # 边框浅灰
ACCENT_DK_HEX = "#17A34A"         # 深一点 (hover/按下)
ACCENT_SOFT_HEX = "#E7F8EE"       # 浅色底 (选中行)
ACCENT_TXT_HEX = "#0F9D4A"        # 强调上的深字
ACCENT = (29, 185, 84, 255)       # 同上的 RGB
ACCENT_DK = (23, 163, 74, 255)
ACCENT_SOFT = (231, 248, 238, 255)
_SEL_BG = (29, 185, 84, 255)      # 选中行: 强调绿底
_ROW_FILL = (255, 255, 255, 255)  # 普通行: 纯白
_HEAD_FILL = (248, 249, 251, 255)  # 列头: 极浅灰
_TEXT_FG = (31, 36, 48, 255)      # 主文字: 深墨
_TEXT_ON_FG = (255, 255, 255, 255)  # 强调底上的白字
_SUB_FG = (107, 114, 128, 255)    # 次级信息灰
_MUTE_FG = (156, 163, 175, 255)   # 更淡的文字/占位
_CHECK_FG = (29, 185, 84, 255)    # 勾选绿
_LINE_FG = (231, 233, 238, 255)   # 分隔线
_BAR_BG = (255, 255, 255, 255)    # 底部播放条白底
_BORDER = (231, 233, 238, 255)    # 边框
_BG_APP = (247, 248, 250, 255)    # 内容区底
_HOVER = (243, 244, 246, 255)     # 行 hover 浅灰
_DANGER = (229, 72, 77, 255)      # 危险 (关闭)


def _shift_hex(hex_color, factor):
    """颜色明暗调整: factor>1 变亮, <1 变暗。"""
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), \
        int(hex_color[5:7], 16)
    r = max(0, min(255, int(r * factor)))
    g = max(0, min(255, int(g * factor)))
    b = max(0, min(255, int(b * factor)))
    return "#%02x%02x%02x" % (r, g, b)


def set_accent(hex_color):
    """切换强调色 (主题预设), 更新全部令牌; 调用方需重刷主题。"""
    global ACCENT_HEX, ACCENT_DK_HEX, ACCENT_SOFT_HEX, ACCENT_TXT_HEX
    global ACCENT, ACCENT_DK, ACCENT_SOFT
    global _SEL_BG, _CHECK_FG
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), \
        int(hex_color[5:7], 16)
    ACCENT_HEX = hex_color
    ACCENT = (r, g, b, 255)
    ACCENT_DK_HEX = _shift_hex(hex_color, 0.82)
    ACCENT_SOFT_HEX = "#%02x%02x%02x" % (int(255 - (255 - r) * 0.93),
                                         int(255 - (255 - g) * 0.93),
                                         int(255 - (255 - b) * 0.93))
    ACCENT_TXT_HEX = _shift_hex(hex_color, 0.55)
    ACCENT_DK = tuple(int(_shift_hex(hex_color, 0.82)[i:i + 2], 16)
                      for i in (1, 3, 5)) + (255,)
    ACCENT_SOFT = (int(255 - (255 - r) * 0.93),
                   int(255 - (255 - g) * 0.93),
                   int(255 - (255 - b) * 0.93), 255)
    _SEL_BG = ACCENT
    _CHECK_FG = ACCENT

_img_cache = {}
_cover_cache = {}
_cover_photo_cache = {}
_font_cache = {}

# 需要随换肤一起重绘的组件
_theme_widgets = []


def register(w):
    if w not in _theme_widgets:
        _theme_widgets.append(w)


def refresh_all_theme():
    for w in list(_theme_widgets):
        try:
            w.refresh()
        except Exception:  # noqa: BLE001
            pass


_HAS_IMAGETK = None


def to_photo(img):
    """把 PIL 图像转成 tk.PhotoImage (优先 ImageTk, 缺失时回落 base64 PNG)。"""
    global _HAS_IMAGETK
    if _HAS_IMAGETK is None:
        try:
            from PIL import ImageTk  # noqa: F401
            _HAS_IMAGETK = True
        except Exception:  # noqa: BLE001
            _HAS_IMAGETK = False
    if _HAS_IMAGETK:
        try:
            from PIL import ImageTk
            return ImageTk.PhotoImage(img)
        except Exception:  # noqa: BLE001
            pass
    buf = _io.BytesIO()
    img.save(buf, format="PNG")
    return tk.PhotoImage(data=base64.b64encode(buf.getvalue()).decode("ascii"))


def load_image(path, width=None, height=None):
    """加载并缩放图片 (拉伸), 带缓存, 用于菜单/图标等固定尺寸贴图。"""
    key = (path, width, height)
    if key in _img_cache:
        return _img_cache[key]
    img = Image.open(path)
    if width and height:
        img = img.resize((width, height), Image.LANCZOS)
    elif width:
        ratio = width / img.width
        img = img.resize((width, int(img.height * ratio)), Image.LANCZOS)
    ph = to_photo(img)
    _img_cache[key] = ph
    return ph


def cover_crop(img, w, h):
    """等比缩放并居中裁切填满 (w,h), 不变形。"""
    src = img.convert("RGB")
    iw, ih = src.size
    scale = max(w / iw, h / ih)
    nw = max(int(iw * scale), w)
    nh = max(int(ih * scale), h)
    src = src.resize((nw, nh), Image.LANCZOS)
    x = (nw - w) // 2
    y = (nh - h) // 2
    return src.crop((x, y, x + w, y + h))


def cover_image(path, width, height):
    """背景等比 cover 裁切到 (width,height) 的 PIL 图, 带缓存。"""
    key = (path, width, height)
    img = _cover_cache.get(key)
    if img is None:
        img = cover_crop(Image.open(path), width, height).convert("RGBA")
        _cover_cache[key] = img
    return img


def cover_photo(path, width, height):
    key = (path, width, height)
    ph = _cover_photo_cache.get(key)
    if ph is None:
        ph = to_photo(cover_image(path, width, height))
        _cover_photo_cache[key] = ph
    return ph


def round_cover_photo(img, size, radius=8):
    """把 PIL 图等比裁切 + 圆角 → tk.PhotoImage (播放条封面用)。"""
    img = cover_crop(img, size, size).convert("RGBA")
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1],
                                           radius=radius, fill=255)
    out.paste(img, (0, 0), mask)
    return to_photo(out)


def placeholder_cover(size=48, radius=8):
    """主题色圆角 + 音符占位封面 (无真实封面时用)。"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius,
                        fill=ACCENT)
    f = _font(size // 2, bold=True)
    try:
        d.text((size // 2, size // 2 + 1), "\u266A", font=f,
               fill=(255, 255, 255, 255), anchor="mm")
    except Exception:  # noqa: BLE001
        pass
    return to_photo(img)


def _font(size, bold=False):
    size = max(int(size), 1)
    key = (size, bold)
    f = _font_cache.get(key)
    if f is not None:
        return f
    if sys.platform == "darwin":      # macOS 字体路径
        cands = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/System/Library/Fonts/Supplemental/Songti.ttc",
        ]
    else:                             # Windows 微软雅黑
        windir = os.environ.get("WINDIR", "C:/Windows")
        name = "msyhbd.ttc" if bold else "msyh.ttc"
        cands = [os.path.join(windir, "Fonts", name)]
    for ttc in cands:
        try:
            f = ImageFont.truetype(ttc, size)
            _font_cache[key] = f
            return f
        except Exception:  # noqa: BLE001
            continue
    try:
        f = ImageFont.truetype("arial.ttf", size)
    except Exception:  # noqa: BLE001
        f = ImageFont.load_default()
    _font_cache[key] = f
    return f


def _clip(d, s, f, maxw):
    """截断到最大显示宽度, 超长加省略号。"""
    if not s:
        return ""
    s = str(s)
    if d.textlength(s, font=f) <= maxw:
        return s
    while s and d.textlength(s + "…", font=f) > maxw:
        s = s[:-1]
    return s + "…"


def header_image(width, height, cols):
    """列头: 极浅灰底 + 下边框 + 各列标题 (微软雅黑加粗)。cols=[(title, x, align)]。"""
    img = Image.new("RGBA", (width, height), _HEAD_FILL)
    d = ImageDraw.Draw(img)
    f = _font(13, bold=True)
    for title, x, align in cols:
        if align == "r":
            w0 = int(d.textlength(title, font=f))
            xx = x - w0
        else:
            xx = x
        d.text((xx, (height + 1 - 13) // 2), title, font=f, fill=_SUB_FG)
    d.line([(0, height - 1), (width, height - 1)], fill=_BORDER, width=1)
    return img


def compose_row(base, n, title, artist="", dur="", checked=False,
                with_check=False, hover=False, fsize=13):
    """一行: 白/绿底 + 复选框 + 分列文字 (序号/歌名/歌手/时长)。"""
    w, h = base.size
    img = base.convert("RGBA")
    overlay = Image.new("RGBA", (w, h),
                        _SEL_BG if checked else (_HOVER if hover else _ROW_FILL))
    img = Image.alpha_composite(img, overlay)
    d = ImageDraw.Draw(img)
    if with_check:
        size = 15
        x0, y0 = 14, h // 2 - size + 1
        if checked:
            d.rounded_rectangle([x0, y0, x0 + size, y0 + size], radius=4,
                                fill=(255, 255, 255), outline=(255, 255, 255))
            d.line([(x0 + 4, y0 + size // 2), (x0 + size // 2, y0 + size - 3)],
                   fill=_CHECK_FG, width=2)
            d.line([(x0 + size // 2, y0 + size - 3), (x0 + size - 4, y0 + 4)],
                   fill=_CHECK_FG, width=2)
        else:
            d.rounded_rectangle([x0, y0, x0 + size, y0 + size], radius=4,
                                outline=(180, 186, 196, 255), width=1,
                                fill=(255, 255, 255))
    fill = _TEXT_ON_FG if checked else _TEXT_FG
    num_x, title_x, artist_x = 44, 78, 700
    f = _font(fsize)
    d.text((num_x, (h - fsize) // 2), _clip(d, n, f, 68), font=f, fill=fill)
    tf = _font(fsize, bold=True)
    d.text((title_x, (h - fsize) // 2), _clip(d, title, tf, 560 - 128),
           font=tf, fill=fill)
    if artist or dur:
        sf = _font(12)
        part = "  ".join(x for x in (artist, dur) if x)
        part = _clip(d, part, sf, 700 - 560)
        d.text((700 - int(d.textlength(part, font=sf)), (h - 12) // 2),
               part, font=sf, fill=_SUB_FG if not checked else _TEXT_ON_FG)
    return to_photo(img)


# 下载管理列表列头: 序号/歌名/歌手/时长/大小/状态
DOWNLOAD_HEADER_COLS = (("序号", 44, "l"), ("歌名", 78, "l"),
                        ("歌手", 480, "r"), ("时长", 560, "r"),
                        ("大小", 660, "r"), ("状态", 775, "r"))


def compose_dl_row(base, n, title, cells, hover=False, fsize=13):
    """下载管理多列行: 序号 + 歌名 + 右对齐各列。

    cells: [(text, right_x, fg), ...] 按右边界对齐绘制 (歌手/时长/大小/状态)。
    """
    w, h = base.size
    img = base.convert("RGBA")
    overlay = Image.new("RGBA", (w, h), _HOVER if hover else _ROW_FILL)
    img = Image.alpha_composite(img, overlay)
    d = ImageDraw.Draw(img)

    f = _font(fsize)
    d.text((44, (h - fsize) // 2), _clip(d, n, f, 44), font=f, fill=_TEXT_FG)

    tf = _font(fsize, bold=True)
    if cells and cells[0][1]:
        title_right = max(cells[0][1] - 16, 200)
    else:
        title_right = 560
    d.text((78, (h - fsize) // 2),
           _clip(d, title, tf, title_right - 78), font=tf, fill=_TEXT_FG)

    sf = _font(12)
    for text, xx, fg in cells:
        t = str(text or "")
        if not t:
            continue
        t2 = _clip(d, t, sf, 130)
        d.text((xx - int(d.textlength(t2, font=sf)), (h - 12) // 2),
               t2, font=sf, fill=fg)
    return to_photo(img)


def fmt_size(nbytes):
    """字节数 -> 可读大小 (B/KB/MB/GB)。"""
    try:
        b = float(nbytes)
    except Exception:  # noqa: BLE001
        return ""
    if b <= 0:
        return "-"
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return "%d %s" % (int(b), unit) if unit == "B" \
                else "%.1f %s" % (b, unit)
        b /= 1024.0
    return "%.1f GB" % b


def fmt_duration(sec):
    """秒数 -> mm:ss 或 h:mm:ss。无效返回空串。"""
    try:
        s = int(float(sec))
    except Exception:  # noqa: BLE001
        return ""
    if s <= 0:
        return ""
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return "%d:%02d:%02d" % (h, m, s)
    return "%d:%02d" % (m, s)


def row_parts(row):
    """把行数据规范成 (序号, 歌名, 歌手, 时长)。兼容 str 或元组。"""
    if not isinstance(row, str):
        row = list(row)
        if len(row) < 4:
            row += [""] * (4 - len(row))
        return tuple(row[:4])
    m = re.match(r"^(\d+)(.*)$", row)
    if m:
        return m.group(1), m.group(2), "", ""
    return "", row, "", ""


# ============================================================== ttk 主题
def apply_tk_theme(root):
    """统一原生控件观感 (按钮/复选框/下拉框/滚动条/滑杆) — 浅色极简。"""
    s = ttk.Style(root)
    try:
        s.theme_use("clam")
    except Exception:  # noqa: BLE001
        pass
    try:
        s.configure(".", font=(FONT_FAMILY, 11))
        # ---- 普通按钮: 白底细边 ----
        s.configure("TButton", background="#FFFFFF", foreground="#1F2430",
                    bordercolor="#E4E7EC", focusthickness=0,
                    focuscolor="#FFFFFF", relief="flat", padding=(14, 4))
        s.map("TButton",
              background=[("pressed", "#E9EBEF"), ("active", "#F3F4F6")],
              bordercolor=[("active", "#D4D8DE")])
        # ---- 主按钮: 音乐绿 ----
        s.configure("Accent.TButton", background=ACCENT_HEX,
                    foreground="#FFFFFF", bordercolor=ACCENT_HEX,
                    focusthickness=0, focuscolor=ACCENT_HEX, relief="flat",
                    padding=(14, 4))
        s.map("Accent.TButton",
              background=[("pressed", "#14803A"), ("active", "#17A34A")],
              bordercolor=[("active", "#17A34A")])
        # ---- 幽灵按钮: 无底细边 (播放条用) ----
        s.configure("Ghost.TButton", background="#FFFFFF",
                    foreground="#5A6472", bordercolor="#E4E7EC",
                    focusthickness=0, focuscolor="#FFFFFF", relief="flat",
                    padding=(6, 2))
        s.map("Ghost.TButton",
              background=[("pressed", "#E9EBEF"), ("active", "#F3F4F6")],
              bordercolor=[("active", "#D4D8DE")])
        s.configure("TCheckbutton", background="#FFFFFF", foreground="#1F2430",
                    indicatormargin=6, focusthickness=0)
        s.map("TCheckbutton", background=[("active", "#FFFFFF")])
        s.configure("TCombobox", fieldbackground="#FFFFFF",
                    background="#FFFFFF", foreground="#1F2430",
                    arrowsize=13, padding=(10, 5), relief="flat")
        s.map("TCombobox",
              fieldbackground=[("readonly", "#FFFFFF")],
              selectbackground=[("readonly", "#FFFFFF")])
        # ---- 细窄滚动条 ----
        s.configure("Vertical.TScrollbar", background="#E0E3E8",
                    troughcolor="#F7F8FA", bordercolor="#F7F8FA",
                    arrowcolor="#9AA3B0", arrowsize=9, width=10)
        s.map("Vertical.TScrollbar",
              background=[("active", "#C9CDD4")])
        s.configure("Horizontal.TScrollbar", background="#E0E3E8",
                    troughcolor="#F7F8FA", bordercolor="#F7F8FA",
                    arrowcolor="#9AA3B0", arrowsize=9)
        s.map("Horizontal.TScrollbar", background=[("active", "#C9CDD4")])
        s.configure("TScale", background="#F7F8FA",
                    troughcolor="#E7E9EE", bordercolor="#E7E9EE",
                    lightcolor="#E7E9EE", darkcolor="#E7E9EE")
        s.configure("TEntry", fieldbackground="#FFFFFF",
                    foreground="#1F2430", bordercolor="#E4E7EC",
                    padding=(10, 6), insertcolor="#1F2430")
        s.map("TEntry", fieldbackground=[("readonly", "#F7F8FA")],
              bordercolor=[("readonly", "#E4E7EC")])
    except Exception:  # noqa: BLE001
        pass


# ============================================================== 面板/轮播
class BgLabel(tk.Label):
    """顶部列头条目 (参数兼容旧用法); 渲染浅灰底 + 标题。"""

    def __init__(self, master, text, width, height, **kw):
        super().__init__(master, **kw)
        self._bgtext = text
        self._bgw, self._bgh = width, height
        self._draw()
        register(self)

    def _draw(self):
        ph = to_photo(header_image(self._bgw, self._bgh,
                                   [(self._bgtext, 12, "l")]))
        self.configure(image=ph)
        self.image = ph

    def refresh(self):
        self._draw()


class ImagePanel(tk.Frame):
    """带纯色底的面板 (浅色极简: 不再使用背景图)。"""

    _kind = "main"

    def __init__(self, master, kind="main", **kw):
        super().__init__(master, **kw)
        self._kind = kind
        self._photo = None
        self._bg_label = tk.Label(self, bg="#FFFFFF" if kind == "main"
                                  else "#F7F8FA")
        self._bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        self._bg_label.lower()
        self.configure(bg="#FFFFFF" if kind == "main" else "#F7F8FA")
        self.bind("<Configure>", lambda e: self._redraw())
        register(self)

    def refresh(self):
        self._redraw()

    def _redraw(self):
        pass


class Carousel(tk.Frame):
    """轮播图面板, 3 秒换一张, 等价于 SlidePanel (url1->url2->url3 循环)。"""

    def __init__(self, master, width=800, height=200, interval=3000, **kw):
        super().__init__(master, **kw)
        self.width, self.height = width, height
        self.interval = interval
        self._images = [
            os.path.join(PICTRUE, "url1.jpg"),
            os.path.join(PICTRUE, "url2.jpg"),
            os.path.join(PICTRUE, "url3.jpg"),
        ]
        self._index = 0
        self._label = tk.Label(self)
        self._label.place(x=0, y=0, relwidth=1, relheight=1)
        self._draw()

    def _draw(self):
        name = self._images[self._index % len(self._images)]
        self._index += 1
        try:
            self._label.configure(image=load_image(name, self.width, self.height))
            self._label.image = self._label.cget("image")
        except Exception:  # noqa: BLE001
            pass

    def start(self):
        def tick():
            self._draw()
            self._label.after(self.interval, tick)
        self._label.after(self.interval, tick)


# ============================================================== 滚动列表
def _wheel_units(event):
    """把不同平台的滚轮事件 delta 归一化为滚动行数。

    Windows/Linux: 每格 ±120; macOS: 鼠标滚轮 ±1 级小整数 /
    触控板像素级 (常 ±10~±300), 折算成每 ~40 像素滚 1 行。
    """
    if sys.platform == "darwin":
        d = event.delta
        if abs(d) < 2:
            n = 1 if d else 0
        else:
            n = max(1, int(abs(d) / 40))
        return -n if d > 0 else n
    d = event.delta
    return -int(d / 120) if d else 0


class _BgCanvasList(tk.Frame):
    """滚动列表基类: 顶部列头 + 白/绿底行 (hover 浅灰, 选中=音乐绿)。"""

    HEADER_COLS = (("序号", 44, "l"), ("歌名", 78, "l"),
                   ("歌手", 700, "r"), ("时长", 778, "r"))

    def __init__(self, master, width=800, height=500, row_h=ROW_H,
                 header=HEADER_COLS, on_scroll_end=None, **kw):
        super().__init__(master, **kw)
        self.width, self.height = width, height
        self.row_h = row_h
        self.on_scroll_end = on_scroll_end   # 滚到接近底部时回调 (无限滚动)
        self._bottom_fired = False
        self._row_w = width - 14   # 左右空出滚动条, 避免选中高亮钻到条下
        self.pack_propagate(False)

        self._header_ph = to_photo(
            header_image(width, HEADER_H, header))
        self._header_lbl = tk.Label(self, image=self._header_ph)
        self._header_lbl.image = self._header_ph
        self._header_lbl.place(x=0, y=0, width=width, height=HEADER_H)

        body_h = max(height - HEADER_H, 10)
        self.canvas = tk.Canvas(self, width=self._row_w, height=body_h,
                                highlightthickness=0, bg="#FFFFFF")
        self.canvas.place(x=0, y=HEADER_H, width=self._row_w, height=body_h)
        self.sb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.sb.set)
        self.sb.place(x=self._row_w, y=HEADER_H, width=14, height=body_h)

        self._photos = {}
        self._rows = []
        self._bg = None
        self._rb_pending = False
        self._hover_idx = None
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", self._on_leave)
        register(self)

    # ------------------------------------------------------------------
    def refresh(self):
        self._rebuild()

    def _on_motion(self, event):
        idx = self._index_at(event.y)
        if idx != self._hover_idx:
            old = self._hover_idx
            self._hover_idx = idx
            if old is not None:
                self._rerender(old)
            if idx is not None:
                self._rerender(idx)

    def _on_leave(self, _e):
        if self._hover_idx is not None:
            old = self._hover_idx
            self._hover_idx = None
            self._rerender(old)

    def _schedule_rebuild(self):
        """批量 add 时合并重绘 (60ms 防抖)。"""
        if self._rb_pending:
            return
        self._rb_pending = True
        self._rebuild()
        self.after(60, self._flush_rebuild)

    def _flush_rebuild(self):
        self._rb_pending = False
        self._rebuild()

    def _wheel(self, event):
        self.canvas.yview_scroll(_wheel_units(event), "units")
        self._maybe_load_more()

    def _maybe_load_more(self):
        """滚到接近底部且数据源允许时, 触发 on_scroll_end 加载下一页。"""
        if not self.on_scroll_end or self._bottom_fired:
            return
        try:
            frac = float(self.canvas.yview()[1])
        except Exception:  # noqa: BLE001
            return
        if frac >= 0.95:
            self._bottom_fired = True
            try:
                self.on_scroll_end()
            except Exception:  # noqa: BLE001
                pass
        else:
            self._bottom_fired = False

    def _rebuild(self):
        self.canvas.delete("row")
        self._photos = {}
        n = max(len(self._rows), self.height // self.row_h + 1)
        self._bg = None   # 纯色设计, 无需背景切片
        for i in range(n):
            row = self._rows[i] if i < len(self._rows) else None
            self._render(i, row)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _render(self, i, row):
        photo = self._make_photo(i, row)
        self._photos[i] = photo
        self.canvas.create_image(0, i * self.row_h, image=photo, anchor="nw",
                                 tags=("row", "row_%d" % i))

    def _rerender(self, i):
        self.canvas.delete("row_%d" % i)
        self._render(i, self._rows[i] if i < len(self._rows) else None)

    def _slices(self, i):
        return Image.new("RGBA", (self._row_w, self.row_h), _ROW_FILL)

    def _empty_photo(self, i):
        img = self._slices(i).convert("RGBA")
        d = ImageDraw.Draw(img)
        if self._rows or i != 0:
            return to_photo(img)
        f = _font(13)
        t = "暂无歌曲，请先扫描或下载"
        tw = int(d.textlength(t, font=f))
        d.text(((_row_w - tw) // 2, (self.row_h - 13) // 2), t, font=f,
               fill=_MUTE_FG)
        return to_photo(img)

    def _make_photo(self, i, row):  # pragma: no cover - 子类实现
        raise NotImplementedError

    def _index_at(self, y):
        y = self.canvas.canvasy(y)
        if y < 0:
            return None
        idx = int(y // self.row_h)
        return idx if 0 <= idx < len(self._rows) else None

    def items(self):
        return list(self._rows)


class ImageList(_BgCanvasList):
    """普通歌曲列表 (下载列表 / 本地列表), 双击播放。"""

    def __init__(self, master, width=800, height=500, row_h=ROW_H,
                 header=_BgCanvasList.HEADER_COLS, on_double=None, **kw):
        super().__init__(master, width=width, height=height, row_h=row_h,
                         header=header, **kw)
        self.on_double = on_double
        self.selected_index = None      # 单击选中的行 (顶部操作按钮用)
        self.canvas.bind("<Button-1>", self._select)
        self.canvas.bind("<Double-Button-1>", self._double)

    def _make_photo(self, i, row):
        if row is None:
            return self._empty_photo(i)
        n, title, artist, dur = row_parts(row)
        return compose_row(self._slices(i), n, title, artist, dur,
                           checked=False,
                           hover=(i == self._hover_idx or
                                  i == self.selected_index))

    def _select(self, event):
        idx = self._index_at(event.y)
        if idx is None:
            return
        self.selected_index = idx
        self._rerender(idx)

    def _double(self, event):
        idx = self._index_at(event.y)
        if idx is None:
            return
        if self.on_double:
            self.on_double(idx)

    def set_rows(self, rows):
        self._rows = list(rows)
        self._rebuild()

    def append_rows(self, rows):
        if not rows:
            return
        start = len(self._rows)
        self._rows.extend(rows)
        self._bottom_fired = False
        self._rebuild()

    def update_row(self, i, row):
        if 0 <= i < len(self._rows):
            self._rows[i] = row
            self._rerender(i)

    def add(self, text):
        self._rows.append(text)
        self._schedule_rebuild()


class ImageCheckList(_BgCanvasList):
    """带复选框的搜索列表, 单击切换选中 (选中=主题蓝底白字 + 勾选)。"""

    def __init__(self, master, width=800, height=300, row_h=ROW_H,
                 header=_BgCanvasList.HEADER_COLS, on_select=None,
                 on_double=None, **kw):
        super().__init__(master, width=width, height=height, row_h=row_h,
                         header=header, **kw)
        self.on_select = on_select
        self.on_double = on_double
        self._checked = set()
        self.canvas.bind("<Button-1>", self._click)
        if self.on_double:
            self.canvas.bind("<Double-Button-1>", self._double)

    def _double(self, event):
        idx = self._index_at(event.y)
        if idx is None:
            return
        if self.on_double:
            self.on_double(idx)

    def _make_photo(self, i, row):
        if row is None:
            return self._empty_photo(i)
        n, title, artist, dur = row_parts(row)
        return compose_row(self._slices(i), n, title, artist, dur,
                           checked=i in self._checked,
                           hover=(i == self._hover_idx), with_check=True)

    def _click(self, event):
        idx = self._index_at(event.y)
        if idx is None:
            return
        if idx in self._checked:
            self._checked.discard(idx)
        else:
            self._checked.add(idx)
        self._rerender(idx)
        if self.on_select:
            self.on_select()

    def set_data(self, rows):
        self._rows = list(rows)
        self._checked = set()
        self._bottom_fired = False
        self._rebuild()

    def append_rows(self, rows):
        if not rows:
            return
        self._rows.extend(rows)
        self._bottom_fired = False
        self._rebuild()

    def checked_indices(self):
        return sorted(self._checked)

    def check_all(self, state):
        if state:
            self._checked = set(range(len(self._rows)))
        else:
            self._checked.clear()
        self._rebuild()
        if self.on_select:
            self.on_select()


# ============================================================== 推荐格
class RecommendGrid(tk.Frame):
    """首页推荐网格: 连续 cover 背景 + 圆角白卡 + 1:1 封面 + 歌名 + 滚动提示。"""

    SONGS = ["一路向北", "大风吹", "下辈子不一定还能遇见你", "半生雪", "少年",
             "潮汐", "烟雨人间", "雾里", "晴天", "奔赴星空",
             "稻香", "虞兮叹", "青花瓷", "起风了", "难渡",
             "夜曲", "刺客", "霍元甲", "谪仙", "听妈妈的话"]

    CELL_W, CELL_H, GAP = 185, 190, 15
    ROWS, COLS = 5, 4

    def __init__(self, master, on_click, width=800, viewport=300, **kw):
        super().__init__(master, **kw)
        self.on_click = on_click
        self.width = width
        self.viewport = viewport
        self.pack_propagate(False)
        self.canvas = tk.Canvas(self, width=width, height=viewport,
                                highlightthickness=0, bg="#F7F8FA")
        self.canvas.place(x=0, y=0, width=width, height=viewport)
        self.sb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.sb.set)
        self.sb.place(x=width - 14, y=0, width=14, height=viewport)
        self.canvas.bind("<MouseWheel>", self._wheel)
        self._photos = []
        self._art = [os.path.join(PICTRUE, "L%d.jpg" % (i + 1))
                     for i in range(len(self.SONGS))]
        self._drawn = False
        # 不在构造时绘制 (20 张卡片合成较慢), 由主窗口在首帧后调用 draw_deferred

    def refresh(self):
        self._drawn = False
        self._draw()

    def draw_deferred(self):
        """首帧之后再绘制推荐卡片, 避免阻塞窗口显示 (启动优化)。"""
        if not self._drawn:
            self._draw()

    def _wheel(self, event):
        self.canvas.yview_scroll(_wheel_units(event), "units")

    def _cell(self, art_path, text):
        """透明卡: 圆角白卡 + 内缩 1:1 封面 + 底部固定歌名区 (无双层圆角打架)。"""
        w, h = self.CELL_W, self.CELL_H
        pad = 10
        text_h = 34
        cover_radius = 10
        card_radius = 14
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([pad, pad, w - pad - 1, h - pad - 1],
                            radius=card_radius,
                            fill=(255, 255, 255, 255), outline=_BORDER,
                            width=1)
        # 封面区域: 内缩于卡片, 圆角略小于卡片
        cx0, cy0 = pad + 8, pad + 8
        cx1, cy1 = w - pad - 8, h - pad - text_h
        a = min(cx1 - cx0, cy1 - cy0)
        ax = cx0 + (cx1 - cx0 - a) // 2
        ay = cy0 + (cy1 - cy0 - a) // 2
        try:
            art = cover_crop(Image.open(art_path), a, a)
            mask = Image.new("L", (a, a), 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, a - 1, a - 1],
                                                   radius=cover_radius,
                                                   fill=255)
            img.paste(art, (ax, ay), mask)
            d = ImageDraw.Draw(img)
        except Exception:  # noqa: BLE001
            pass
        # 歌名: 固定文字区, 垂直居中
        f = _font(13, bold=True)
        t = _clip(d, text, f, w - 2 * (pad + 9))
        tw = int(d.textlength(t, font=f))
        ty = cy1 + (text_h - 13) // 2
        d.text(((w - tw) // 2, ty), t, font=f, fill=_TEXT_FG)
        return to_photo(img)

    def _draw(self):
        self.canvas.delete("all")
        self._photos = []
        self._drawn = True
        total_h = self.ROWS * self.CELL_H + (self.ROWS - 1) * self.GAP + 30
        pad_x = (self.width - (self.COLS * self.CELL_W + (self.COLS - 1) * self.GAP)) // 2
        for i, name in enumerate(self.SONGS):
            r, c = i // self.COLS, i % self.COLS
            x0 = pad_x + c * (self.CELL_W + self.GAP)
            y0 = 15 + r * (self.CELL_H + self.GAP)
            photo = self._cell(self._art[i], name)
            self._photos.append(photo)
            tag = "cell_%d" % i
            self.canvas.create_image(x0, y0, image=photo, anchor="nw",
                                     tags=(tag,))
            self.canvas.tag_bind(tag, "<Button-1>",
                                 lambda e, n=name: self.on_click(n))
            self.canvas.tag_bind(tag, "<Enter>",
                                 lambda e: self.canvas.configure(cursor="hand2"))
            self.canvas.tag_bind(tag, "<Leave>",
                                 lambda e: self.canvas.configure(cursor=""))
        self.canvas.configure(scrollregion=(0, 0, self.width, total_h))


# ============================================================ 歌词面板
class ProgressBar(tk.Canvas):
    """简约进度条: 浅灰轨道 + 音乐绿填充 + 白色圆点, 点击/拖动 seek。"""

    def __init__(self, master, width=300, height=18, command=None,
                 bg="#FFFFFF"):
        super().__init__(master, width=width, height=height, bg=bg,
                         highlightthickness=0, cursor="hand2")
        # 注意: tk.Canvas 内部会占用 self._w / self._h (存放控件路径名),
        # 因此基准尺寸另存 _cw / _ch, 未完成布局时用它兜底。
        self._cw, self._ch = width, height
        self._value = 0.0
        self._maxv = 100.0
        self._command = command
        self._drag = False
        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._move)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Configure>", lambda e: self._draw())
        self._draw()

    def set(self, value):
        self._value = max(0.0, float(value))
        self._draw()

    def get(self):
        return self._value

    def configure(self, **kw):
        if "to" in kw:
            self._maxv = max(1.0, float(kw["to"] or 1))
            self._draw()

    def cget(self, k):
        if k == "to":
            return self._maxv
        raise tk.TclError("unknown option %r" % k)

    def _frac(self, e):
        w = self.winfo_width()
        if w <= 1:
            w = self._cw
        if w <= 1:
            return 0.0
        return max(0.0, min(1.0, e.x / w))

    def _press(self, e):
        self._drag = True
        self._update(e)

    def _move(self, e):
        if self._drag:
            self._update(e)

    def _release(self, _e):
        self._drag = False

    def _update(self, e):
        self._value = self._frac(e) * self._maxv
        self._draw()
        if self._command:
            self._command(self._value)

    def _draw(self):
        self.delete("all")
        # 控件尚未完成布局时 winfo_width() 返回 1 (非 0), 不能靠 `or` 兜底,
        # 否则恢复会话时按 1px 宽度绘制 → 进度条填充几乎为 0
        w = self.winfo_width()
        if w <= 1:
            w = self._cw
        h = self.winfo_height()
        if h <= 1:
            h = self._ch
        y = h // 2
        r = 3
        frac = (self._value / self._maxv) if self._maxv else 0.0
        self.create_rectangle(0, y - r, w, y + r, fill="#E7E9EE",
                              outline="", width=0)
        if frac > 0.01:
            fx = max(4.0, w * frac)
            self.create_rectangle(0, y - r, fx, y + r,
                                  fill=ACCENT_HEX, outline="", width=0)
        tx = w * frac
        self.create_oval(tx - 5, y - 5, tx + 5, y + 5, fill="#FFFFFF",
                         outline=ACCENT_HEX, width=2)


def _lerp_color(c1, c2, t):
    """两个 hex 颜色按 t ∈ [0,1] 线性插值, 返回 '#rrggbb'。"""
    t = max(0.0, min(1.0, t))
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return "#%02x%02x%02x" % (r, g, b)


class LyricsPanel(tk.Frame):
    """QQ 音乐风格歌词面板: 居中高亮 + 渐隐 + 缩放 + 丝滑滚动动画。

    对外方法:
        set_lyrics(timed_lines, title, artist)  timed_lines=[(ms, text),...]
        set_position(ms)   更新当前时间 (ms)
        clear(msg)         清空歌词, 显示提示文字
    """

    _BG      = "#F7F8FA"
    _ACCENT  = "#1DB954"      # 以下三项由 _sync_theme() 跟随强调色
    _GLOW    = "#DDF6E6"
    _CUR_TXT = "#0F9D4A"
    _DIM     = "#9AA3B0"
    _DEEP    = "#6B7280"
    _TITLE   = "#1F2430"
    _SUB     = "#6B7280"
    _LINE_H  = 40
    _FONT_CUR = (FONT_FAMILY, 20, "bold")
    _FONT_FAR = (FONT_FAMILY, 13)

    def _sync_theme(self):
        """把当前行的高亮色同步为当前强调色 (换肤后调用)。"""
        self._ACCENT = ACCENT_HEX
        self._GLOW = ACCENT_SOFT_HEX
        self._CUR_TXT = ACCENT_TXT_HEX

    def refresh(self):
        """换肤回调: 重新着色并重绘歌词。"""
        self._sync_theme()
        if self._lines:
            self._draw_frame()
        else:
            self._draw_blank()

    def __init__(self, master, width=800, height=600, **kw):
        super().__init__(master, bg=self._BG, **kw)
        self._W, self._H = width, height
        self._sync_theme()

        # ---- 顶部标题栏 ----
        self._title_var = tk.StringVar(value="")
        self._artist_var = tk.StringVar(value="")
        self._hdr = tk.Frame(self, bg=self._BG)
        self._hdr.place(x=0, y=0, width=width, height=70)
        tk.Label(self._hdr, textvariable=self._title_var,
                 bg=self._BG, fg=self._TITLE,
                 font=(FONT_FAMILY, 15, "bold")).place(relx=0.5, y=20, anchor="center")
        tk.Label(self._hdr, textvariable=self._artist_var,
                 bg=self._BG, fg=self._SUB,
                 font=(FONT_FAMILY, 11)).place(relx=0.5, y=48, anchor="center")
        tk.Frame(self._hdr, bg=BORDER_HEX, height=1).place(
            x=24, y=68, relwidth=1.0, width=width - 48)

        # ---- 画布歌词 ----
        self._canvas = tk.Canvas(self, bg=self._BG, highlightthickness=0,
                                 width=width, height=height - 70)
        self._canvas.place(x=0, y=70, width=width, height=height - 70)

        # ---- 获取歌词按钮 (无歌词时显示) ----
        self._fetch_cb = None
        self._fetching = False
        self._fetch_btn = ttk.Button(self, text="获取歌词",
                                     command=self._on_fetch,
                                     style="Accent.TButton",
                                     takefocus=False, cursor="hand2")

        # ---- 内部状态 ----
        self._lines = []        # [(ms, text), ...]  已按时间排序
        self._view_pos = 5.0    # 当前可视中心 (行索引浮点), 初始偏上
        self._target_pos = 5.0
        self._anim_id = None
        self._last_tick = 0.0
        self._cur_idx = -1
        self._blank_msg = ""
        self._active = False    # 面板可见时才运行动画, 避免后台 30fps 空转
        register(self)          # 换肤时随 refresh_all_theme() 重新着色

    # ---------------------------------------------------------- 对外接口
    def set_fetch_callback(self, cb):
        """设置「获取歌词」回调: 无歌词时按钮点击后执行。"""
        self._fetch_cb = cb

    def _show_fetch_btn(self, on):
        if on:
            bw, bh = 132, 34
            bx = (self._W - bw) // 2
            by = 70 + (self._H - 70) // 2 + 26
            self._fetch_btn.place(x=bx, y=by, width=bw, height=bh)
        else:
            self._fetch_btn.place_forget()

    def _on_fetch(self):
        if self._fetching or not self._fetch_cb:
            return
        self._fetching = True
        self._fetch_btn.configure(text="获取中...", state="disabled")
        try:
            self._fetch_cb()
        except Exception:  # noqa: BLE001
            self.finish_fetch(False, "获取歌词失败，请稍后再试")

    def finish_fetch(self, ok, msg=None):
        """获取结束: 失败时恢复按钮; 成功时由 set_lyrics 收起按钮。"""
        self._fetching = False
        self._fetch_btn.configure(text="获取歌词", state="normal")
        if not ok:
            self._blank_msg = msg or "获取歌词失败，请稍后再试"
            self._draw_blank()
            self._show_fetch_btn(True)

    def set_active(self, visible):
        """面板显示/隐藏: 只有可见时才启动动画, 隐藏即停 (省 CPU)。"""
        self._active = bool(visible)
        if self._active:
            if self._lines:
                self._start_anim()
        else:
            self._stop_anim()

    def set_lyrics(self, timed_lines, title="", artist=""):
        """传入 parse_lrc 返回的 [(ms, text), ...] 列表。"""
        self._lines = list(timed_lines) if timed_lines else []
        self._title_var.set(title)
        self._artist_var.set(artist)
        self._cur_idx = -1
        self._blank_msg = ""
        self._view_pos = 5.0
        self._target_pos = 5.0
        if not self._lines:
            self._blank_msg = "暂无歌词"
            self._draw_blank()
        else:
            self._draw_frame()
        self._show_fetch_btn(not self._lines)
        if self._active:
            self._start_anim()

    def set_position(self, ms):
        """播放位置 (ms), 更新目标行。"""
        if not self._lines:
            return
        t = max(0.0, float(ms))
        lo, hi = 0, len(self._lines) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self._lines[mid][0] <= t:
                lo = mid
            else:
                hi = mid - 1
        self._target_pos = float(lo)

    def clear(self, msg="暂无歌词"):
        """清空歌词并显示提示文字 (无歌词时提供「获取歌词」按钮)。"""
        self._lines = []
        self._cur_idx = -1
        self._blank_msg = msg
        self._title_var.set("")
        self._artist_var.set("")
        self._draw_blank()
        self._stop_anim()
        self._show_fetch_btn(True)

    def set_static(self, texts, title=""):
        """无时间轴的纯文本歌词: 静态列表显示 (无高亮滚动)。"""
        self._lines = []
        self._title_var.set(title)
        self._artist_var.set("")
        self._blank_msg = ""
        self._show_fetch_btn(False)
        self._stop_anim()
        c = self._canvas
        c.delete("all")
        lines = [t for t in (texts or []) if t.strip()]
        step = 30
        top = 20
        for i, t in enumerate(lines):
            y = top + i * step
            c.create_text(self._W // 2, y, text=t,
                          fill=self._DIM, font=(FONT_FAMILY, 12), anchor="center")

    # ---------------------------------------------------------- 动画
    def _start_anim(self):
        if self._anim_id is not None:
            return
        self._last_tick = __import__("time").monotonic()
        self._tick()

    def _stop_anim(self):
        if self._anim_id is not None:
            try:
                self.after_cancel(self._anim_id)
            except Exception:  # noqa: BLE001
                pass
            self._anim_id = None

    def _tick(self):
        now = __import__("time").monotonic()
        dt = now - self._last_tick
        self._last_tick = now
        # 指数缓动 (spring-like ease-out)
        speed = 10.0
        alpha = 1.0 - __import__("math").exp(-speed * dt)
        diff = self._target_pos - self._view_pos
        if abs(diff) < 0.001:
            self._view_pos = self._target_pos
        else:
            self._view_pos += diff * alpha
        self._draw_frame()
        self._anim_id = self.after(33, self._tick)   # ~30 fps

    # ---------------------------------------------------------- 绘制
    def _draw_blank(self):
        c = self._canvas
        c.delete("all")
        c.create_text(self._W // 2, (self._H - 70) // 2,
                      text=self._blank_msg or "暂无歌词",
                      fill=self._DIM, font=(FONT_FAMILY, 15), anchor="center")

    def _draw_frame(self):
        c = self._canvas
        c.delete("all")
        if not self._lines:
            return
        canvas_h = self._H - 70
        cy = int(canvas_h * 0.46)     # 活动行略偏上 (QQ 音乐式, 下方留出未来行)
        line_h = self._LINE_H
        margin = 56                    # 上下边缘渐隐区宽度
        lo = max(0, int(self._view_pos) - 12)
        hi = min(len(self._lines) - 1, int(self._view_pos) + 12)
        for i in range(lo, hi + 1):
            dist = abs(i - self._view_pos)
            w = max(0.0, 1.0 - dist / 4.5)   # 距中心渐隐权重
            y = cy + (i - self._view_pos) * line_h
            # 边缘渐隐权重: 越贴近画布上下边越淡, 彻底消除贴边裁切线
            edge = 1.0
            if y < margin:
                edge = max(0.0, y / margin)
            elif y > canvas_h - margin:
                edge = max(0.0, (canvas_h - y) / margin)
            if dist < 0.5:
                # --- 真正的当前行: 浅绿光晕 + 深绿加粗 ---
                glow_font = (FONT_FAMILY, 24, "bold")
                c.create_text(self._W // 2 + 1, y + 2,
                              text=self._lines[i][1],
                              font=glow_font,
                              fill=self._GLOW,
                              anchor="center")
                c.create_text(self._W // 2, y,
                              text=self._lines[i][1],
                              fill=self._CUR_TXT,
                              font=(FONT_FAMILY, 22, "bold"),
                              anchor="center")
            else:
                sz = int(12 + 8 * w)
                fill = _lerp_color(self._DIM, self._DEEP, w * w)
                if w > 0.45:
                    fill = _lerp_color(self._DEEP, self._TITLE,
                                       (w - 0.45) * 0.35)
                # 向背景色混合实现淡出 (Tk 无真实 alpha, 用颜色逼近)
                fill = _lerp_color(fill, self._BG, 1.0 - edge)
                c.create_text(self._W // 2, y,
                              text=self._lines[i][1],
                              fill=fill,
                              font=(FONT_FAMILY, sz, "normal"),
                              anchor="center")

    def destroy(self):
        self._stop_anim()
        super().destroy()