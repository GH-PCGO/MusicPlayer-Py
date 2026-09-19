# -*- coding: utf-8 -*-
"""共享 Web 服务: 为移动端 WebView / iPhone Safari 提供搜索 / 播放 / 下载 /
本地音乐库 / 歌词 / 热榜歌单等 HTTP 接口。

纯标准库实现 (http.server), 复用桌面版纯逻辑 (kuwo / lyrics / netease)。
- 安卓端: 由 android/app/src/main/python/server.py 作为薄包装调用本模块
  (Chaquopy 已把 src/musicplayer 打进 APK), 绑定 127.0.0.1 供 WebView 访问;
- iPhone / 局域网: ``python -m musicplayer.webapp`` 绑定 0.0.0.0, 手机 Safari
  打开 ``http://<Mac 局域网IP>:8000/`` 即可使用。

接口:
  GET  /                     移动端页面 (www/index.html)
  GET  /static/<path>        静态资源 (www 目录)
  GET  /api/search?kw=&pn=   酷我搜索
  GET  /api/stream?rid=&br=  在线播放直链 (mobi.s 签名)
  GET  /api/lyrics           歌词 (LRC 原文 + 解析行)
  GET  /api/hot ✓  GET /api/playlists ✓  GET /api/playlist  网易云推荐
  GET  /api/mv/search?kw=    MV 搜索 (网易云 + B站 合并)
  GET  /api/mv/url?id=       网易云 MV 直链 mp4 (短时效, 现取)
  GET  /api/mv/embed?bvid=   B站 MV 内嵌播放地址
  GET  /api/library          本地下载的音乐库
  GET  /api/downloads        下载状态/进度/文件列表
  POST /api/download         开始下载到本地音乐库 (自动嵌歌词/封面)
  GET  /api/audio?name=      播放本地音乐 (支持 Range 拖动进度)
  GET  /api/audio_cover?name= 本地音乐内嵌封面
  DELETE /api/download?name= 删除本地音乐 (含同名 .lrc; 安卓同步删媒体库)
"""
import json
import mimetypes
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from musicplayer.kuwo import KuwoAPI
from musicplayer.lyrics import fetch_lyrics, parse_lrc, read_cover
from musicplayer import androidstorage
from musicplayer import bilibili
from musicplayer import netease
from musicplayer import paths

WEB_DIR = os.path.join(paths.ASSETS_DIR, "www")   # 默认包内前端, 可通过 set_web_dir 覆盖
_api = KuwoAPI()
_dl_lock = threading.Lock()
_dl_state = {}        # 文件名 → {"status": downloading/done/failed, "mb": 进度MB}
_mv_lock = threading.Lock()
_mv_cache = {}        # 关键词 → (时间戳, [MV 候选])  60s 缓存, 省去重复搜索
_SERVER = None        # 当前运行中的 ThreadingHTTPServer (start() 记录 / stop() 关闭)
_SERVER_LOCK = threading.Lock()

_QUALITY_CHAINS = {
    "320kmp3": ("320kmp3", "192kmp3", "128kmp3"),
    "192kmp3": ("192kmp3", "128kmp3"),
    "128kmp3": ("128kmp3",),
}


def set_web_dir(path):
    """安卓端把 www 从 APK assets 解压后注入; 其它情况用包内 assets/www。"""
    global WEB_DIR
    if path:
        WEB_DIR = path


# ---------------------------------------------------------------- 工具
def _resolve_url(rid, br):
    """按首选码率沿回落链解析在线播放地址。"""
    chain = _QUALITY_CHAINS.get(br or "320kmp3", _QUALITY_CHAINS["320kmp3"])
    last = None
    for b in chain:
        try:
            return _api._mobi_url(rid, b)
        except Exception as exc:  # noqa: BLE001
            last = exc
    raise IOError("解析播放地址失败: %s" % last)


def _file_size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def _duration_of(path):
    """本地 mp3 时长 (秒); 无 mutagen 时返回 0。"""
    try:
        import mutagen
        info = mutagen.File(path).info
        if info and getattr(info, "length", None):
            return float(info.length)
    except Exception:  # noqa: BLE001
        pass
    return 0.0


def _fmt_size(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return "%.1f %s" % (n, unit) if unit != "B" else "%d B" % int(n)
        n /= 1024.0
    return "-"


def _fmt_dur(sec):
    s = int(float(sec or 0))
    if s <= 0:
        return ""
    m, s = divmod(s, 60)
    return "%d:%02d" % (m, s)


def _scan_library():
    """扫描本地音乐库 (下载目录) 的 mp3。"""
    folder = paths.DOWNLOAD_DIR
    items = []
    if os.path.isdir(folder):
        for fn in sorted(f for f in os.listdir(folder)
                         if f.lower().endswith(".mp3")):
            full = os.path.join(folder, fn)
            items.append({"name": fn,
                          "size": _fmt_size(_file_size(full)),
                          "dur": _fmt_dur(_duration_of(full)),
                          "bytes": _file_size(full)})
    return items


def _resolve_rid(title, artist):
    """无 rid 时按「歌手 歌名」在酷我搜索解析 rid (首页热歌只有歌名/歌手)。"""
    title = (title or "").strip()
    if not title:
        return ""
    artist = (artist or "").split(" / ")[0].strip()
    kw = (artist + " " + title) if artist else title
    try:
        items = _api.search(kw, page=1)
    except Exception:  # noqa: BLE001
        return ""
    return str(items[0][0]) if items else ""


def _search_mv(kw, limit=8):
    """并发搜索网易云 + B站 MV, 合并返回; 结果缓存 60s。"""
    kw = (kw or "").strip()
    if not kw:
        return []
    now = time.time()
    with _mv_lock:
        hit = _mv_cache.get(kw)
        if hit and now - hit[0] < 60:
            return hit[1]
    out = []

    def collect(fn):
        try:
            out.extend(fn())
        except Exception:  # noqa: BLE001
            pass

    threads = [
        threading.Thread(target=collect,
                         args=(lambda: netease.search_mv(kw, limit),)),
        threading.Thread(target=collect,
                         args=(lambda: bilibili.search_mv(kw, limit),)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(20)
    with _mv_lock:
        _mv_cache[kw] = (now, out)
    return out


def _start_download(rid, title, artist, cover, br="320kmp3"):
    """后台线程下载到本地音乐库; 名称统一《歌名》.mp3。

    完成后 (安卓) 另存一份到系统媒体库 Music/音乐下载器/。
    """
    display = "《%s》.mp3" % (title or "未知")
    full = os.path.join(paths.DOWNLOAD_DIR, display)

    def worker():
        with _dl_lock:
            _dl_state[display] = {"status": "downloading", "mb": 0.0}

        def on_progress(n):
            with _dl_lock:
                st = _dl_state.get(display)
                if st:
                    st["mb"] = n / (1024.0 * 1024.0)

        _api.download(rid, display, paths.DOWNLOAD_DIR,
                      on_done=lambda p: _finish_download(display, p is not None),
                      on_progress=on_progress,
                      title=title or "", artist=artist or "",
                      cover=cover or "", br=br)

    def _finish_download(disp, ok):
        with _dl_lock:
            _dl_state[disp] = {"status": "done" if ok else "failed",
                               "mb": 0.0}
        if ok:
            # 私有目录已含歌词/封面; 再发布一份到系统媒体库 (无桥时 no-op)
            androidstorage.publish(full, disp)

    threading.Thread(target=worker, daemon=True).start()
    return display


# ---------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"  # 支持 Range/206 必须 1.1 (keep-alive)

    def log_message(self, *args):  # 静音访问日志
        pass

    # ------------------------------------------------------------ 基础
    def _headers(self, code, ctype, length=None, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        if length is not None:
            self.send_header("Content-Length", str(length))
        if extra:
            for k, v in extra.items():
                self.send_header(k, str(v))
        self.end_headers()

    def _send(self, code, ctype, body, extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self._headers(code, ctype, len(body), extra)
        if self.command != "HEAD":
            try:
                self.wfile.write(body)
            except Exception:  # noqa: BLE001
                pass

    def _json(self, obj, code=200):
        self._send(code, "application/json; charset=utf-8",
                   json.dumps(obj, ensure_ascii=False))

    def _static(self, rel):
        base = WEB_DIR or os.path.join(paths.ASSETS_DIR, "www")
        path = os.path.normpath(os.path.join(base, rel))
        if (not path.startswith(os.path.normpath(base))
                or not os.path.isfile(path)):
            return self._json({"error": "not found"}, 404)
        ctype, _enc = mimetypes.guess_type(path)
        if rel.endswith(".js"):
            ctype = "application/javascript; charset=utf-8"
        elif rel.endswith(".css"):
            ctype = "text/css; charset=utf-8"
        elif rel.endswith(".html"):
            ctype = "text/html; charset=utf-8"
        try:
            with open(path, "rb") as f:
                data = f.read()
            self._send(200, ctype or "application/octet-stream", data)
        except OSError:
            self._json({"error": "not found"}, 404)

    def _send_local_file(self, name):
        """对本地 mp3 支持 Range (iOS Safari 拖动进度条必需)。"""
        base = os.path.normpath(paths.DOWNLOAD_DIR)
        full = os.path.normpath(os.path.join(base, name))
        if (not full.startswith(base) or not os.path.isfile(full)
                or not name.lower().endswith((".mp3", ".lrc"))):
            return self._json({"error": "not found"}, 404)
        size = os.path.getsize(full)
        ctype = ("audio/mpeg" if name.lower().endswith(".mp3")
                 else "text/plain; charset=utf-8")
        rng = self.headers.get("Range")
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng or "")
            if not m:
                return self._json({"error": "bad range"}, 416)
            start = int(m.group(1)) if m.group(1) else 0
            end = int(m.group(2)) if m.group(2) else size - 1
            if start > end or start >= size:
                return self._json({"error": "range not satisfiable"}, 416)
            end = min(end, size - 1)
            n = end - start + 1
            extra = {"Content-Range": "bytes %d-%d/%d" % (start, end, size),
                     "Accept-Ranges": "bytes"}
            self._headers(206, ctype, n, extra)
            if self.command != "HEAD":
                try:
                    with open(full, "rb") as f:
                        f.seek(start)
                        left = n
                        while left > 0:
                            chunk = f.read(min(65536, left))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            left -= len(chunk)
                except Exception:  # noqa: BLE001
                    pass
            return
        extra = {"Accept-Ranges": "bytes"}
        self._send_file(full, ctype, extra)

    def _send_file(self, full, ctype, extra=None):
        size = os.path.getsize(full)
        self._headers(200, ctype, size, extra)
        if self.command != "HEAD":
            try:
                with open(full, "rb") as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------ 路由
    def do_GET(self):
        try:
            u = urlparse(self.path)
            q = parse_qs(u.query)
            p = u.path

            if p in ("/", "/index.html"):
                return self._static("index.html")
            if p.startswith("/static/"):
                return self._static(p[len("/static/"):])

            if p == "/api/search":
                kw = (q.get("kw") or [""])[0].strip()
                pn = max(1, int((q.get("pn") or ["1"])[0]))
                if not kw:
                    return self._json({"items": []})
                items = _api.search(kw, page=pn)
                out = [{"rid": r, "name": n, "artist": a,
                        "cover": KuwoAPI.cover_url(c)}
                       for r, n, a, c in items]
                return self._json({"items": out})

            if p == "/api/stream":
                rid = (q.get("rid") or [""])[0]
                if not rid:
                    return self._json({"error": "no rid"}, 400)
                br = (q.get("br") or ["320kmp3"])[0]
                return self._json({"url": _resolve_url(rid, br)})

            if p == "/api/lyrics":
                rid = (q.get("rid") or [""])[0]
                title = (q.get("title") or [""])[0]
                artist = (q.get("artist") or [""])[0]
                lrc = ""
                try:
                    lrc = fetch_lyrics(rid, title, artist,
                                       session=_api._session) or ""
                except Exception:  # noqa: BLE001
                    lrc = ""
                lines = parse_lrc(lrc) if lrc else []
                return self._json({"lrc": lrc,
                                   "lines": [list(x) for x in lines]})

            if p == "/api/hot":
                limit = min(50, max(1, int((q.get("limit") or ["20"])[0])))
                rows = netease.fetch_hot_songs(limit)
                return self._json({"items": [
                    {"name": n, "artist": a, "cover": c} for n, a, c in rows]})

            if p == "/api/playlists":
                limit = min(20, max(1, int((q.get("limit") or ["6"])[0])))
                rows = netease.fetch_recommend_playlists(limit)
                return self._json({"items": [
                    {"id": i, "name": n, "cover": c, "count": cnt}
                    for i, n, c, cnt in rows]})

            if p == "/api/playlist":
                pid = (q.get("id") or [""])[0]
                if not pid:
                    return self._json({"error": "no id"}, 400)
                limit = min(100, max(1, int((q.get("limit") or ["50"])[0])))
                name, rows = netease.fetch_playlist_songs(pid, limit)
                return self._json({"name": name, "items": [
                    {"name": n, "artist": a, "cover": c} for n, a, c in rows]})

            if p == "/api/mv/search":
                kw = (q.get("kw") or [""])[0].strip()
                limit = min(15, max(1, int((q.get("limit") or ["8"])[0])))
                if not kw:
                    return self._json({"items": []})
                return self._json({"items": _search_mv(kw, limit)})

            if p == "/api/mv/url":
                mid = (q.get("id") or [""])[0]
                if not mid:
                    return self._json({"error": "no id"}, 400)
                return self._json(netease.mv_play_url(mid))

            if p == "/api/mv/embed":
                bvid = (q.get("bvid") or [""])[0]
                if not bvid:
                    return self._json({"error": "no bvid"}, 400)
                return self._json({"url": bilibili.embed_url(bvid)})

            if p == "/api/library":
                return self._json({"items": _scan_library(),
                                   "folder": paths.DOWNLOAD_DIR})

            if p == "/api/downloads":
                with _dl_lock:
                    states = dict(_dl_state)
                items = _scan_library()
                for it in items:
                    st = states.get(it["name"])
                    if st:
                        it["status"] = st["status"]
                        it["mb"] = st.get("mb", 0.0)
                    else:
                        it["status"] = "done"
                        it["mb"] = it.get("bytes", 0) / (1024.0 * 1024.0)
                return self._json({"items": items})

            if p == "/api/audio":
                name = (q.get("name") or [""])[0]
                if not name:
                    return self._json({"error": "no name"}, 400)
                return self._send_local_file(name)

            if p == "/api/audio_cover":
                name = (q.get("name") or [""])[0]
                full = os.path.normpath(os.path.join(paths.DOWNLOAD_DIR, name))
                if (not full.startswith(os.path.normpath(paths.DOWNLOAD_DIR))
                        or not os.path.isfile(full)):
                    return self._json({"error": "not found"}, 404)
                try:
                    img = read_cover(full)
                except Exception:  # noqa: BLE001
                    img = None
                if not img:
                    return self._json({"error": "no cover"}, 404)
                try:
                    if not isinstance(img, bytes):
                        import io
                        buf = io.BytesIO()
                        img.save(buf, format="JPEG")
                        img = buf.getvalue()
                except Exception:  # noqa: BLE001
                    img = None
                if not img:
                    return self._json({"error": "no cover"}, 404)
                return self._send(200, "image/jpeg", img)

            return self._json({"error": "not found"}, 404)
        except Exception as exc:  # noqa: BLE001
            return self._json({"error": str(exc)}, 500)

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        try:
            u = urlparse(self.path)
            if u.path != "/api/download":
                return self._json({"error": "not found"}, 404)
            try:
                n = int(self.headers.get("Content-Length") or 0)
                data = json.loads(self.rfile.read(n).decode("utf-8"))
            except Exception:  # noqa: BLE001
                return self._json({"error": "bad json"}, 400)
            title = data.get("title", "")
            artist = data.get("artist", "")
            rid = str(data.get("rid") or "").strip()
            if not rid:
                rid = _resolve_rid(title, artist)   # 首页热歌等无 rid 时现解析
            if not rid:
                return self._json({"error": "未找到可下载的音源"}, 404)
            br = data.get("br") or "320kmp3"
            if br not in _QUALITY_CHAINS:
                br = "320kmp3"
            os.makedirs(paths.DOWNLOAD_DIR, exist_ok=True)
            display = _start_download(rid, title, artist,
                                      data.get("cover", ""), br=br)
            return self._json({"name": display, "ok": True})
        except Exception as exc:  # noqa: BLE001
            return self._json({"error": str(exc)}, 500)

    def do_DELETE(self):
        try:
            u = urlparse(self.path)
            q = parse_qs(u.query)
            name = (q.get("name") or [""])[0]
            if not name:
                return self._json({"error": "no name"}, 400)
            base = os.path.normpath(paths.DOWNLOAD_DIR)
            full = os.path.normpath(os.path.join(base, name))
            if not full.startswith(base):
                return self._json({"error": "bad path"}, 400)
            with _dl_lock:
                st = _dl_state.get(name)
                if st and st["status"] == "downloading":
                    return self._json({"error": "downloading"}, 409)
            removed = []
            for f in (full, os.path.join(base,
                                         os.path.splitext(name)[0] + ".lrc")):
                if os.path.isfile(f) and f.startswith(base):
                    try:
                        os.remove(f)
                        removed.append(os.path.basename(f))
                    except OSError:
                        pass
            _dl_state.pop(name, None)
            androidstorage.delete(name)      # 安卓: 同步删媒体库条目
            return self._json({"ok": True, "removed": removed})
        except Exception as exc:  # noqa: BLE001
            return self._json({"error": str(exc)}, 500)

    def do_OPTIONS(self):
        self._headers(204, "text/plain")


# ---------------------------------------------------------------- 启动
def start(port=8760, host="127.0.0.1"):
    """启动本地 HTTP 服务 (阻塞线程), 返回实际端口。"""
    global _SERVER
    srv = None
    for p in range(port, port + 20):
        try:
            srv = ThreadingHTTPServer((host, p), Handler)
            break
        except OSError:
            continue
    if srv is None:
        raise RuntimeError("无法绑定端口 %s:%d" % (host, port))
    with _SERVER_LOCK:
        if _SERVER is not None:
            try:
                _SERVER.shutdown()
                _SERVER.server_close()
            except Exception:  # noqa: BLE001
                pass
        _SERVER = srv
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1]


def stop():
    """停止当前服务 (幂等)。"""
    global _SERVER
    with _SERVER_LOCK:
        srv, _SERVER = _SERVER, None
    if srv is not None:
        try:
            srv.shutdown()
        except Exception:  # noqa: BLE001
            pass
        try:
            srv.server_close()
        except Exception:  # noqa: BLE001
            pass


def is_running():
    """服务是否在运行。"""
    with _SERVER_LOCK:
        return _SERVER is not None and _SERVER.server_address[1] is not None \
            and threading.active_count() > 0


def current_port():
    """当前服务端口 (未运行返回 None)。"""
    with _SERVER_LOCK:
        return _SERVER.server_address[1] if _SERVER else None


def lan_ip():
    """局域网 IP (macOS/跨平台, 供手机访问)。"""
    s = None
    try:
        s = __import__("socket").socket(__import__("socket").AF_INET,
                                        __import__("socket").SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:  # noqa: BLE001
        return "127.0.0.1"
    finally:
        if s:
            s.close()


def _lan_ip():
    return lan_ip()


def main():
    """iPhone/局域网模式: 绑定 0.0.0.0, 打印手机访问地址。

    用法: ``python -m musicplayer.webapp`` 或 ``python run_iphone.py``
    """
    os.makedirs(paths.DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(paths.DATA_DIR, exist_ok=True)
    port = int(os.environ.get("MUSICPLAYER_PORT", "8000"))
    start(port, host="0.0.0.0")
    ip = _lan_ip()
    print("=" * 46)
    print("  音乐下载器 · 手机访问模式已启动")
    print("  请让 iPhone 与电脑连接同一 Wi-Fi, 用 Safari 打开:")
    print()
    print("      http://%s:%d/" % (ip, port))
    print()
    print("  (本机预览: http://127.0.0.1:%d/)  Ctrl+C 退出" % port)
    print("=" * 46)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()