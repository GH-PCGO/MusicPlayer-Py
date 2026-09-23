# -*- coding: utf-8 -*-
"""路径解析: 资产目录与数据目录 (下载目录 / 设置文件)。

支持两种布局:
- 源码布局 ``<root>/src/musicplayer`` → 数据目录取项目根 ``<root>``；
- 已安装布局 (site-packages) → 数据目录取用户主目录 ``~/MusicPlayer``。
"""
import os

PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(PKG_DIR)

if os.path.basename(_PARENT) == "src":
    ROOT_DIR = os.path.dirname(_PARENT)          # 源码布局
    DATA_DIR = ROOT_DIR
else:
    ROOT_DIR = _PARENT                           # 已安装
    DATA_DIR = os.path.join(os.path.expanduser("~"), "MusicPlayer")

# 资源 (图片)
ASSETS_DIR = os.path.join(PKG_DIR, "assets")
PICTRUE = os.path.join(ASSETS_DIR, "Pictrue")

# 数据 (下载歌曲 / 设置)
DOWNLOAD_DIR = os.path.join(DATA_DIR, "music")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")


def set_download_dir(path):
    """重设下载目录 (iOS 容器 Documents 等), 并保证目录存在。"""
    global DOWNLOAD_DIR
    os.makedirs(path, exist_ok=True)
    DOWNLOAD_DIR = path
    return DOWNLOAD_DIR
