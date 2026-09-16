# -*- coding: utf-8 -*-
"""Android 端本地 HTTP 服务: 为 WebView 提供搜索 / 播放直链 / 歌词 / 静态页面。

纯标准库实现 (http.server), 只依赖桌面版复用的 musicplayer.kuwo / lyrics。
"""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

# 桌面调试 (python android/app/src/main/python/server.py) 时把项目 src 加入搜索路径;
# 在 Chaquopy 中运行 (作为 server 模块) 时 musicplayer 已随包, 不会执行本分支。
if __name__ == "__main__" and not any(
        os.path.isdir(os.path.join(p, "musicplayer"))
        for p in sys.path if p):
    _here = os.path.dirname(os.path.abspath(__file__))
    _root = os.path.abspath(os.path.join(_here, *([".."] * 5)))
    sys.path.insert(0, os.path.join(_root, "src"))

from musicplayer.kuwo import KuwoAPI
from musicplayer.lyrics import fetch_lyrics, parse_lrc

WEB_DIR = None          # 由 MainActivity 通过 set_web_dir() 传入 (解压后的 www 目录)
_api = KuwoAPI()

_MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".json": "application/json; charset=utf-8",
    ".woff2": "font/woff2",
}

_QUALITY_CHAINS = {
    "320kmp3": ("320kmp3", "192kmp3", "128kmp3"),
    "192kmp3": ("192kmp3", "128kmp3"),
    "128kmp3": ("128kmp3",),
}


def set_web_dir(path):
    global WEB_DIR
    WEB_DIR = path


def _resolve_url(rid, br):
    """按首选码率沿回落链解析出可直接播放的 mp3 地址。"""
    chain = _QUALITY_CHAINS.get(br or "320kmp3", _QUALITY_CHAINS["320kmp3"])
    last = None
    for b in chain:
        try:
            return _api._mobi_url(rid, b)
        except Exception as exc:  # noqa: BLE001
            last = exc
    raise IOError("解析播放地址失败: %s" % last)


class Handler(BaseHTTPRequestHandler):

    def log_message(self, *args):  # 静音访问日志
        pass

    # ------------------------------------------------------------ 工具
    def _send(self, code, ctype, body):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except Exception:  # noqa: BLE001
            pass

    def _json(self, obj, code=200):
        self._send(code, "application/json; charset=utf-8",
                   json.dumps(obj, ensure_ascii=False))

    def _static(self, rel):
        base = WEB_DIR
        if not base:
            base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
        path = os.path.normpath(os.path.join(base, rel))
        if not path.startswith(os.path.normpath(base)) or not os.path.isfile(path):
            return self._json({"error": "not found"}, 404)
        ext = os.path.splitext(path)[1].lower()
        with open(path, "rb") as f:
            data = f.read()
        self._send(200, _MIME.get(ext, "application/octet-stream"), data)

    # ------------------------------------------------------------ 路由
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        p = u.path
        try:
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
                url = _resolve_url(rid, br)
                return self._json({"url": url})

            if p == "/api/lyrics":
                rid = (q.get("rid") or [""])[0]
                title = (q.get("title") or [""])[0]
                artist = (q.get("artist") or [""])[0]
                lrc = ""
                try:
                    lrc = fetch_lyrics(rid, title, artist, session=_api._session) or ""
                except Exception:  # noqa: BLE001
                    lrc = ""
                lines = parse_lrc(lrc) if lrc else []
                return self._json({"lrc": lrc,
                                   "lines": [list(x) for x in lines]})

            return self._json({"error": "not found"}, 404)
        except Exception as exc:  # noqa: BLE001
            return self._json({"error": str(exc)}, 500)


def start(port=8760):
    """启动本地服务 (阻塞在 daemon 线程), 返回实际端口。"""
    srv = None
    for p in range(port, port + 20):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", p), Handler)
            break
        except OSError:
            continue
    if srv is None:
        raise RuntimeError("无法绑定本地端口")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1]


if __name__ == "__main__":
    # 桌面调试: python android/app/src/main/python/server.py
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    # here = <root>/android/app/src/main/python, 向上 5 级到项目根
    root = os.path.abspath(os.path.join(here, *([".."] * 5)))
    sys.path.insert(0, os.path.join(root, "src"))
    WEB_DIR = os.path.join(here, "..", "assets", "www")
    port = start(8760)
    print("server on http://127.0.0.1:%d/  (www=%s)" % (port, WEB_DIR), flush=True)
    import time
    while True:
        time.sleep(1)