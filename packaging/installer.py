# -*- coding: utf-8 -*-
"""音乐下载器 Windows 安装程序 (自包含, 无需 Inno/NSIS)。

由 PyInstaller 打包成单文件 ``MusicPlayerSetup.exe``, 内部 payload/ 目录
携带应用本体。运行后:
  - 复制程序到安装目录 (默认 %LOCALAPPDATA%\\Programs\\MusicPlayer)
  - 创建 桌面 / 开始菜单 快捷方式
  - 写入 HKCU 卸载信息 + 生成 uninstall.bat (控制面板可卸载)

也支持命令行: ``MusicPlayerSetup.exe --uninstall`` 静默卸载。
"""
import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_NAME = "音乐下载器"
APP_ID = "MusicPlayer-Py"
APP_VERSION = "1.0.0"
EXE_NAME = "MusicPlayer.exe"
UNINSTALL_KEY = (r"Software\Microsoft\Windows\CurrentVersion\Uninstall\\"
                 + APP_ID)

APP_FONT = ("Microsoft YaHei", 10)
_TITLE_FONT = ("Microsoft YaHei", 16, "bold")


# --------------------------------------------------------------------- 路径
def _payload_dir():
    """定位待安装的应用文件目录。"""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        p = os.path.join(base, "payload")
        if os.path.isdir(p):
            return p
    # 开发环境: packaging/payload 或 dist/MusicPlayer
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, "payload"),
                 os.path.join(os.path.dirname(here), "dist", "MusicPlayer")):
        if os.path.isdir(cand):
            return cand
    return None


def _default_dir():
    local = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(local, "Programs", "MusicPlayer")


def _desktop_lnk():
    return os.path.join(os.path.expanduser("~"), "Desktop", APP_NAME + ".lnk")


def _startmenu_lnk():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Microsoft", "Windows", "Start Menu", "Programs",
                        APP_NAME + ".lnk")


# --------------------------------------------------------------------- 快捷方式
def _make_shortcut(lnk_path, target, workdir, args=""):
    """用 WScript.Shell 创建 .lnk (无需 pywin32)。"""
    ps = (
        "$w=New-Object -ComObject WScript.Shell;"
        "$s=$w.CreateShortcut('%s');"
        "$s.TargetPath='%s';$s.WorkingDirectory='%s';$s.Arguments='%s';"
        "$s.IconLocation='%s';$s.Save()"
        % (lnk_path.replace("'", "''"), target.replace("'", "''"),
           workdir.replace("'", "''"), args, target.replace("'", "''"))
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       creationflags=0x08000000, check=False)
        return os.path.exists(lnk_path)
    except Exception:  # noqa: BLE001
        return False


# --------------------------------------------------------------------- 安装/卸载
def _write_uninstall_bat(install_dir):
    bat = os.path.join(install_dir, "uninstall.bat")
    content = (
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        'del "%s" >nul 2>nul\r\n' % _desktop_lnk()
        + 'del "%s" >nul 2>nul\r\n' % _startmenu_lnk()
        + 'reg delete "%s" /f >nul 2>nul\r\n' % UNINSTALL_KEY.replace(
            "Software", "HKCU\\Software", 1)
        + 'copy /y "%~f0" "%TEMP%\\mp_uninstall.bat" >nul\r\n'
        + 'start "" cmd /c "%TEMP%\\mp_uninstall.bat" _run\r\n'
        + "exit /b\r\n"
        ":_run\r\n"
        "timeout /t 2 /nobreak >nul\r\n"
        'rmdir /s /q "%s" >nul 2>nul\r\n' % install_dir
        + 'del "%TEMP%\\mp_uninstall.bat" >nul 2>nul\r\n'
    )
    with open(bat, "w", encoding="utf-8") as f:
        f.write(content)
    return bat


def _register_uninstall(install_dir, size_kb):
    import winreg
    key_path = "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\" \
        + APP_ID
    try:
        k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
        exe = os.path.join(install_dir, EXE_NAME)
        winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
        winreg.SetValueEx(k, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
        winreg.SetValueEx(k, "Publisher", 0, winreg.REG_SZ, "GH-PCGO")
        winreg.SetValueEx(k, "InstallLocation", 0, winreg.REG_SZ, install_dir)
        winreg.SetValueEx(k, "DisplayIcon", 0, winreg.REG_SZ, exe)
        winreg.SetValueEx(k, "UninstallString", 0, winreg.REG_SZ,
                          '"%s"' % os.path.join(install_dir, "uninstall.bat"))
        winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "NoRepair", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "EstimatedSize", 0, winreg.REG_DWORD, size_kb)
        winreg.CloseKey(k)
        return True
    except Exception:  # noqa: BLE001
        return False


def do_install(src_dir, dst_dir, desktop=True, startmenu=True,
               on_log=None):
    """复制文件 + 建快捷方式 + 写卸载信息。返回 (ok, message)。"""
    import shutil

    def log(msg):
        if on_log:
            on_log(msg)

    if not src_dir or not os.path.isdir(src_dir):
        return False, "未找到安装包内容 (payload)"
    try:
        log("正在复制文件到 %s ..." % dst_dir)
        os.makedirs(dst_dir, exist_ok=True)
        for item in os.listdir(src_dir):
            s = os.path.join(src_dir, item)
            d = os.path.join(dst_dir, item)
            if os.path.isdir(s):
                if os.path.isdir(d):
                    shutil.rmtree(d, ignore_errors=True)
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)
        exe = os.path.join(dst_dir, EXE_NAME)
        if desktop:
            log("创建桌面快捷方式 ...")
            _make_shortcut(_desktop_lnk(), exe, dst_dir)
        if startmenu:
            log("创建开始菜单快捷方式 ...")
            _make_shortcut(_startmenu_lnk(), exe, dst_dir)
        log("写入卸载信息 ...")
        total = 0
        for root, _dirs, files in os.walk(dst_dir):
            for fn in files:
                try:
                    total += os.path.getsize(os.path.join(root, fn))
                except OSError:
                    pass
        _write_uninstall_bat(dst_dir)
        _register_uninstall(dst_dir, total // 1024)
        log("安装完成")
        return True, dst_dir
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def do_uninstall(install_dir):
    """静默卸载: 删快捷方式/注册表/安装目录。"""
    import winreg
    for lnk in (_desktop_lnk(), _startmenu_lnk()):
        try:
            if os.path.exists(lnk):
                os.remove(lnk)
        except OSError:
            pass
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                         "Software\\Microsoft\\Windows\\CurrentVersion\\"
                         "Uninstall\\" + APP_ID)
    except OSError:
        pass
    bat = os.path.join(install_dir, "uninstall.bat")
    if os.path.exists(bat):
        subprocess.Popen(["cmd", "/c", bat], creationflags=0x08000000)
    return True


# --------------------------------------------------------------------- UI
class InstallerApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("%s 安装程序 v%s" % (APP_NAME, APP_VERSION))
        self.root.resizable(False, False)
        self.root.configure(bg="#FFFFFF")
        try:
            self.root.iconbitmap(os.path.join(getattr(sys, "_MEIPASS", ""),
                                              "app.ico"))
        except Exception:  # noqa: BLE001
            pass
        self._center(580, 300)
        self._build()
        self.root.mainloop()

    def _center(self, w, h):
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry("%dx%d+%d+%d" % (w, h, x, y))

    def _build(self):
        tk.Label(self.root, text="安装 %s" % APP_NAME, bg="#FFFFFF",
                 fg="#1F2430", font=_TITLE_FONT).place(x=24, y=18)
        tk.Label(self.root, text="选择安装位置，然后点击“开始安装”。",
                 bg="#FFFFFF", fg="#6B7280", font=APP_FONT).place(x=24, y=54)

        tk.Label(self.root, text="安装位置：", bg="#FFFFFF", fg="#5A6472",
                 font=APP_FONT).place(x=24, y=96)
        self.path_var = tk.StringVar(value=_default_dir())
        entry = ttk.Entry(self.root, textvariable=self.path_var,
                          font=APP_FONT)
        entry.place(x=104, y=92, width=392, height=30)
        entry.xview_moveto(1.0)          # 显示路径尾部
        ttk.Button(self.root, text="浏览...", command=self._browse
                   ).place(x=504, y=92, width=72, height=30)

        self.desktop_var = tk.BooleanVar(value=True)
        self.startmenu_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.root, text="创建桌面快捷方式",
                        variable=self.desktop_var).place(x=24, y=138)
        ttk.Checkbutton(self.root, text="创建开始菜单快捷方式",
                        variable=self.startmenu_var).place(x=24, y=168)

        self.status = tk.Label(self.root, text="", bg="#FFFFFF",
                               fg="#6B7280", font=("Microsoft YaHei", 9),
                               anchor="w")
        self.status.place(x=24, y=206, width=536)

        self.btn = ttk.Button(self.root, text="开始安装",
                              command=self._install)
        self.btn.place(x=362, y=240, width=100, height=36)
        ttk.Button(self.root, text="退出", command=self.root.destroy
                   ).place(x=472, y=240, width=82, height=36)

    def _browse(self):
        d = filedialog.askdirectory(title="选择安装目录",
                                    initialdir=self.path_var.get() or None)
        if d:
            self.path_var.set(os.path.join(d, "MusicPlayer"))

    def _log(self, msg):
        self.status.configure(text=msg)
        self.root.update_idletasks()

    def _install(self):
        dst = self.path_var.get().strip()
        if not dst:
            messagebox.showwarning("提示", "请选择安装位置")
            return
        src = _payload_dir()
        self.btn.configure(state="disabled")
        ok, res = do_install(src, dst, self.desktop_var.get(),
                             self.startmenu_var.get(), on_log=self._log)
        if ok:
            if messagebox.askyesno("安装完成",
                                   "安装成功！\n是否立即运行？"):
                try:
                    os.startfile(os.path.join(dst, EXE_NAME))
                except Exception:  # noqa: BLE001
                    pass
            self.root.destroy()
        else:
            messagebox.showerror("安装失败", res)
            self.btn.configure(state="normal")


def main():
    if "--uninstall" in sys.argv:
        # 从注册表读取安装目录或使用默认
        do_uninstall(_default_dir())
        return
    InstallerApp()


if __name__ == "__main__":
    main()
