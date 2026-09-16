# -*- coding: utf-8 -*-
"""一键打包 Windows 可安装程序。

步骤:
  1. 由 assets/Pictrue/logo.jpg 生成 packaging/app.ico (多尺寸)
  2. PyInstaller 打包应用本体 -> dist/MusicPlayer/
  3. PyInstaller 打包安装程序 (内嵌 payload) -> dist/MusicPlayerSetup.exe

用法: python packaging/build.py          (在项目根执行)
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "packaging")
ICON = os.path.join(PKG, "app.ico")
LOGO = os.path.join(ROOT, "src", "musicplayer", "assets", "Pictrue",
                    "logo.jpg")


def gen_icon():
    if os.path.exists(ICON):
        print("[1/3] 图标已存在:", ICON)
        return
    try:
        from PIL import Image
        img = Image.open(LOGO).convert("RGBA")
        # 居中裁成正方形后缩放到多尺寸
        side = min(img.size)
        left = (img.width - side) // 2
        top = (img.height - side) // 2
        img = img.crop((left, top, left + side, top + side))
        sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                 (128, 128), (256, 256)]
        img.save(ICON, sizes=sizes)
        print("[1/3] 生成图标:", ICON)
    except Exception as exc:  # noqa: BLE001
        print("[1/3] 生成图标失败 (将不使用图标):", exc)


def run_pyinstaller(spec):
    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm",
           spec]
    print("[..] %s" % " ".join(cmd))
    r = subprocess.run(cmd, cwd=ROOT)
    return r.returncode == 0


def main():
    gen_icon()
    # 清理旧产物
    for d in (os.path.join(ROOT, "build"),
              os.path.join(ROOT, "dist")):
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)

    print("[2/3] 打包应用本体 ...")
    if not run_pyinstaller(os.path.join(PKG, "MusicPlayer.spec")):
        print("应用打包失败"); return 1
    app_dir = os.path.join(ROOT, "dist", "MusicPlayer")
    if not os.path.isfile(os.path.join(app_dir, "MusicPlayer.exe")):
        print("未生成 MusicPlayer.exe"); return 1

    print("[3/3] 打包安装程序 ...")
    if not run_pyinstaller(os.path.join(PKG, "installer.spec")):
        print("安装程序打包失败"); return 1
    setup = os.path.join(ROOT, "dist", "MusicPlayerSetup.exe")
    if not os.path.isfile(setup):
        print("未生成 MusicPlayerSetup.exe"); return 1

    size_mb = os.path.getsize(setup) / 1024.0 / 1024.0
    print("\n完成!")
    print("  程序目录 : %s" % app_dir)
    print("  安装程序 : %s  (%.1f MB)" % (setup, size_mb))
    return 0


if __name__ == "__main__":
    sys.exit(main())
