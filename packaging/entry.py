# -*- coding: utf-8 -*-
"""PyInstaller 冻结入口: 启动音乐下载器。"""
import os
import sys

# 源码运行时把 src 加入路径; 冻结后 musicplayer 已在包内
_here = os.path.dirname(os.path.abspath(__file__))
_src = os.path.join(os.path.dirname(_here), "src")
if os.path.isdir(_src) and _src not in sys.path:
    sys.path.insert(0, _src)

from musicplayer.app import main  # noqa: E402

if __name__ == "__main__":
    main()
