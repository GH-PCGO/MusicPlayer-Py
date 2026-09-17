# -*- coding: utf-8 -*-
"""iPhone / 局域网访问: python run_iphone.py

把 `src` 加入搜索路径后启动共享 Web 服务 (绑定 0.0.0.0)。
手机与电脑连同一 Wi-Fi, 用 Safari 打开打印出的地址。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from musicplayer import webapp  # noqa: E402

if __name__ == "__main__":
    webapp.main()