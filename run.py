# -*- coding: utf-8 -*-
"""便捷启动脚本 (无需安装即可运行): ``python run.py``。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "src"))

from musicplayer.app import main  # noqa: E402

if __name__ == "__main__":
    main()
