# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置: 应用本体 (onedir, 无控制台窗口)。

用法: pyinstaller --clean -y packaging/MusicPlayer.spec
产物: dist/MusicPlayer/MusicPlayer.exe (+ _internal/)
"""
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))
SRC = os.path.join(ROOT, "src")
ASSETS = os.path.join(SRC, "musicplayer", "assets")
ICON = os.path.join(SPECPATH, "app.ico")

# 设计稿源文件不随包发布 (仅运行时资源)
SKIP_FILES = {"透明背景logo.jpeg", "透明背景logo.png"}


def _assets_datas(src, dst):
    out = []
    for root, _dirs, files in os.walk(src):
        for fn in files:
            if fn in SKIP_FILES:
                continue
            rel = os.path.relpath(root, src)
            target = dst if rel == "." else os.path.join(dst, rel)
            out.append((os.path.join(root, fn), target))
    return out


a = Analysis(
    [os.path.join(SPECPATH, "entry.py")],
    pathex=[SRC],
    binaries=[],
    datas=_assets_datas(ASSETS, "musicplayer/assets"),
    hiddenimports=["PIL._tkinter_finder"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "numpy", "scipy", "matplotlib", "pygame",
              "pystray", "mutagen"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MusicPlayer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=ICON if os.path.exists(ICON) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="MusicPlayer",
)
