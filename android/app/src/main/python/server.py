# -*- coding: utf-8 -*-
"""Android 端服务器: 复用 musicplayer.webapp (Chaquopy 已把 src 打入 APK)。

MainActivity 调用本模块的 set_web_dir() 注入解压后的 www, 再 start() 启动
127.0.0.1 上的 HTTP 服务供 WebView 访问。
"""
import os
import sys

# 桌面调试 (python android/app/src/main/python/server.py) 时把项目 src 加入搜索路径;
# 在 Chaquopy 中运行 (作为 server 模块) 时 musicplayer 已随包, 不会执行本分支。
if __name__ == "__main__" and not any(
        os.path.isdir(os.path.join(p, "musicplayer"))
        for p in sys.path if p):
    _here = os.path.dirname(os.path.abspath(__file__))
    _root = os.path.abspath(os.path.join(_here, *([".."] * 5)))
    sys.path.insert(0, os.path.join(_root, "src"))

import musicplayer.webapp as webapp  # noqa: E402
from musicplayer import androidstorage  # noqa: E402


def set_web_dir(path):
    webapp.set_web_dir(path)


def set_android_storage(context, rel="Music/音乐下载器"):
    """MainActivity 注入 Android Context, 下载完成后发布到系统媒体库。

    桌面调试时 context 可为 None → androidstorage 自动降级为 no-op。
    """
    androidstorage.set_context(context, rel)


def start(port=8760):
    """绑定 127.0.0.1 (仅本机 WebView), 返回实际端口。"""
    return webapp.start(port=port, host="127.0.0.1")


if __name__ == "__main__":
    _here = os.path.dirname(os.path.abspath(__file__))
    webapp.set_web_dir(os.path.join(_here, "..", "assets", "www"))
    port = start(8760)
    print("server on http://127.0.0.1:%d/  (www=%s)"
          % (port, webapp.WEB_DIR), flush=True)
    import time
    while True:
        time.sleep(1)