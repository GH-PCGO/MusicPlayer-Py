# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置: 安装程序 (单文件, 内嵌 payload)。

用法: pyinstaller --clean -y packaging/installer.spec
前置: 已执行 MusicPlayer.spec 生成 dist/MusicPlayer/
产物: dist/MusicPlayerSetup.exe
"""
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))
APP_DIR = os.path.join(ROOT, "dist", "MusicPlayer")
ICON = os.path.join(SPECPATH, "app.ico")

a = Analysis(
    [os.path.join(SPECPATH, "installer.py")],
    pathex=[],
    binaries=[],
    datas=[(APP_DIR, "payload"), (ICON, ".")],
    hiddenimports=[],
    excludes=["numpy", "scipy", "matplotlib", "pygame", "pystray",
              "mutagen", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MusicPlayerSetup",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    icon=ICON if os.path.exists(ICON) else None,
)
