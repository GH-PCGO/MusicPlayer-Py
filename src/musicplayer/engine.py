# -*- coding: utf-8 -*-
"""
跨平台音频播放引擎 (pygame.mixer 实现)

替代原 Windows 独占的 _MciEngine (winmm.mciSendString / waveOutSetVolume)。
- macOS / Windows / Linux 均可运行
- 进程内播放, 命令队列 + 状态 dict, 与主线程完全解耦
- 接口与原 _MciEngine 完全一致:  start / play / pause / resume /
  seek / setvol / stop, 状态:  st = {"ok","state","dur","pos","err"}
"""
import os
import queue
import subprocess
import sys
import threading

try:
    import pygame  # noqa: F401
    _HAS_PYGAME = True
except ImportError:  # pragma: no cover - 依赖缺失时降级
    _HAS_PYGAME = False

try:
    import mutagen  # noqa: F401
    _HAS_MUTAGEN = True
except ImportError:
    _HAS_MUTAGEN = False


def open_path(path):
    """跨平台调用系统默认应用打开文件/URL (替代 Windows 的 os.startfile)。

    macOS:   open 命令
    Windows: os.startfile
    Linux:   xdg-open
    """
    if not path:
        return False
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", path])
        elif sys.platform == "win32":
            os.startfile(path)  # noqa: S606
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception:  # noqa: BLE001
        return False


class MciEngine:
    """Windows 原生 MCI 播放引擎 (winmm.mciSendString): 无需 pygame 等第三方库。

    仅在 pygame 缺失且系统为 Windows 时由 default_engine() 选用。
    接口与 CrossPlatformEngine 完全一致: start/play/pause/resume/seek/
    setvol/stop, 状态 st = {"ok","state","dur","pos","err"}。
    """

    ALIAS = "appplay"

    def __init__(self):
        self.cmds = queue.Queue()
        self.st = {"ok": False, "state": 0, "dur": 0.0, "pos": 0.0,
                   "err": ""}
        self._t = None

    def start(self):
        if self._t is not None:
            return
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def _run(self):
        import ctypes
        mci = ctypes.windll.winmm.mciSendStringW

        def send(cmd):
            buf = ctypes.create_unicode_buffer(512)
            r = mci(cmd, buf, 512, 0)
            return r, buf.value

        try:
            r, _ = send("open new type waveaudio alias _test")
            if r == 0:
                send("close _test")
            self.st["ok"] = True
        except Exception as exc:  # noqa: BLE001
            self.st["err"] = str(exc)
            return

        current_path = None
        loaded_path = None

        while True:
            try:
                cmd = self.cmds.get(timeout=0.25)
            except queue.Empty:
                cmd = None
            try:
                if cmd is not None:
                    kind = cmd.get("kind")
                    if kind == "play":
                        if current_path:
                            send("close %s" % self.ALIAS)
                        path = cmd["path"]
                        r, _ = send('open "%s" alias %s type mpegvideo'
                                    % (path, self.ALIAS))
                        if r == 0:
                            send("set %s time format milliseconds"
                                 % self.ALIAS)
                            send("play %s" % self.ALIAS)
                            current_path = path
                            loaded_path = None      # 需重新取时长
                        else:
                            self.st["err"] = "MCI open failed: %d" % r
                    elif kind == "pause":
                        send("pause %s" % self.ALIAS)
                    elif kind == "resume":
                        send("play %s" % self.ALIAS)
                    elif kind == "seek":
                        ms = int(float(cmd["v"]) * 1000)
                        send("seek %s to %d" % (self.ALIAS, ms))
                        send("play %s" % self.ALIAS)
                    elif kind == "setvol":
                        vol = int(float(cmd["v"]))
                        vol16 = max(0, min(65535, vol * 65535 // 100))
                        ctypes.windll.winmm.waveOutSetVolume(
                            0, vol16 | (vol16 << 16))
                    elif kind == "stop":
                        send("stop %s" % self.ALIAS)
                        current_path = None
                        loaded_path = None
                        self.st["dur"] = 0.0
                    elif kind == "shutdown":
                        break
            except Exception as exc:  # noqa: BLE001
                self.st["err"] = str(exc)
            # 状态轮询: 仅在已加载曲目时执行
            if current_path:
                try:
                    _, mode = send("status %s mode" % self.ALIAS)
                    mode = mode.lower().strip()
                    self.st["state"] = (3 if mode == "playing" else
                                        2 if mode == "paused" else
                                        1 if mode == "stopped" else 0)
                    _, pos_s = send("status %s position" % self.ALIAS)
                    self.st["pos"] = float(pos_s) / 1000.0 if pos_s else 0.0
                    if loaded_path != current_path:
                        _, len_s = send("status %s length" % self.ALIAS)
                        if len_s:
                            self.st["dur"] = float(len_s) / 1000.0
                        loaded_path = current_path
                except Exception:  # noqa: BLE001
                    pass

    def play(self, path):
        self.cmds.put({"kind": "play", "path": path})

    def pause(self):
        self.cmds.put({"kind": "pause"})

    def resume(self):
        self.cmds.put({"kind": "resume"})

    def seek(self, v):
        self.cmds.put({"kind": "seek", "v": v})

    def setvol(self, v):
        self.cmds.put({"kind": "setvol", "v": v})

    def stop(self):
        self.cmds.put({"kind": "stop"})

    def shutdown(self):
        self.cmds.put({"kind": "shutdown"})


def default_engine():
    """按平台选择引擎。

    - pygame 可用 → CrossPlatformEngine (macOS/Windows/Linux)
    - pygame 缺失且 Windows → MciEngine (winmm, 零依赖)
    - 其他平台无 pygame → CrossPlatformEngine (将提示缺少 pygame)
    """
    if _HAS_PYGAME:
        return CrossPlatformEngine()
    if sys.platform == "win32":
        return MciEngine()
    return CrossPlatformEngine()


class CrossPlatformEngine:
    """pygame.mixer 播放引擎: 进程内播放, 命令队列驱动。

    state 对照: 0 未知 / 1 已停止 / 2 暂停 / 3 播放中。
    """

    def __init__(self):
        self.cmds = queue.Queue()
        self.st = {"ok": False, "state": 0, "dur": 0.0, "pos": 0.0,
                   "err": ""}
        self._t = None
        self._current = None      # 当前已播放的路径
        self._paused = False      # 暂停标记
        self._pos_at_pause = 0.0  # 暂停时的位置 (秒)
        self._start_offset = 0.0  # 本次播放的起始位置 (seek 用), 秒

    # ------------------------------------------------------------ 启动
    def start(self):
        if self._t is not None:
            return
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    # ------------------------------------------------------------ 内部线程
    def _run(self):
        if not _HAS_PYGAME:
            self.st["err"] = "缺少 pygame 库，请执行 pip install pygame"
            self._drain_only()
            return
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2,
                              buffer=2048)
            self.st["ok"] = True
        except Exception as exc:  # noqa: BLE001
            self.st["err"] = "音频初始化失败: %s" % exc
            self._drain_only()
            return

        try:
            pygame.mixer.music.set_endevent()  # 不依赖事件, 用轮询
        except Exception:  # noqa: BLE001
            pass

        while True:
            try:
                cmd = self.cmds.get(timeout=0.2)
            except queue.Empty:
                cmd = None

            if cmd is not None:
                self._handle(cmd)
                if cmd.get("kind") == "shutdown":
                    break
            self._poll_state()

        try:
            pygame.mixer.music.stop()
        except Exception:  # noqa: BLE001
            pass

    def _drain_only(self):
        """初始化失败时: 只消费命令不播放, 避免队列无限堆积。"""
        while True:
            try:
                cmd = self.cmds.get(timeout=0.2)
            except queue.Empty:
                continue
            if cmd.get("kind") == "shutdown":
                break

    def _handle(self, cmd):
        kind = cmd.get("kind")
        try:
            if kind == "play":
                path = cmd["path"]
                pygame.mixer.music.load(path)
                pygame.mixer.music.play()
                self._current = path
                self._paused = False
                self._pos_at_pause = 0.0
                self._start_offset = 0.0
                self.st["state"] = 3
                self.st["dur"] = self._duration(path)
                self.st["pos"] = 0.0
            elif kind == "pause":
                if self._paused:
                    return
                self._pos_at_pause = self._current_pos()
                self._paused = True
                self.st["state"] = 2
                pygame.mixer.music.pause()
            elif kind == "resume":
                if not self._paused:
                    return
                self._paused = False
                self.st["state"] = 3
                pygame.mixer.music.unpause()
            elif kind == "seek":
                v = max(0.0, float(cmd.get("v") or 0.0))
                if self._current:
                    # pygame 无独立 seek: 从目标位置重新开始播放;
                    # get_pos() 从 start 点起算, 需用 _start_offset 补偿
                    pygame.mixer.music.load(self._current)
                    pygame.mixer.music.play(start=v)
                    self._start_offset = v
                    self._paused = False
                    self._pos_at_pause = v
                    self.st["state"] = 3
                    self.st["pos"] = v
            elif kind == "setvol":
                vol = max(0.0, min(1.0, float(cmd.get("v") or 0.0) / 100.0))
                pygame.mixer.music.set_volume(vol)
            elif kind == "stop":
                pygame.mixer.music.stop()
                self._current = None
                self._paused = False
                self._pos_at_pause = 0.0
                self._start_offset = 0.0
                self.st["dur"] = 0.0
                self.st["pos"] = 0.0
                self.st["state"] = 0
        except Exception as exc:  # noqa: BLE001
            self.st["err"] = str(exc)

    def _current_pos(self):
        """返回当前播放位置 (秒), 补偿 seek 起始偏移。"""
        try:
            if self._paused:
                return self._pos_at_pause
            t = pygame.mixer.music.get_pos()
            if t < 0:
                return self._start_offset
            return t / 1000.0 + self._start_offset
        except Exception:  # noqa: BLE001
            return 0.0

    def _duration(self, path):
        """获取音频时长 (秒)。优先 mutagen, 回落 pygame Sound。"""
        if _HAS_MUTAGEN:
            try:
                import mutagen
                info = mutagen.File(path).info
                if info and getattr(info, "length", None):
                    return float(info.length)
            except Exception:  # noqa: BLE001
                pass
        try:
            return float(pygame.mixer.Sound(path).get_length())
        except Exception:  # noqa: BLE001
            return 0.0

    def _poll_state(self):
        """轮询播放状态写入 st dict (主线程只读)。"""
        if not self._current:
            return
        try:
            dur = float(self.st.get("dur") or 0.0)

            if self._paused:
                self.st["state"] = 2
                self.st["pos"] = self._pos_at_pause
                return
            if pygame.mixer.music.get_busy():
                self.st["state"] = 3
                t = pygame.mixer.music.get_pos()
                self.st["pos"] = t / 1000.0 + self._start_offset if t >= 0 \
                    else self._start_offset
            else:
                # 轨道已加载但未在播放 → 播放结束
                self.st["state"] = 1
                self.st["pos"] = dur
        except Exception as exc:  # noqa: BLE001
            self.st["err"] = str(exc)

    # ------------------------------------------------------------ 对外接口
    def play(self, path):
        self.cmds.put({"kind": "play", "path": path})

    def pause(self):
        self.cmds.put({"kind": "pause"})

    def resume(self):
        self.cmds.put({"kind": "resume"})

    def seek(self, v):
        self.cmds.put({"kind": "seek", "v": v})

    def setvol(self, v):
        self.cmds.put({"kind": "setvol", "v": v})

    def stop(self):
        self.cmds.put({"kind": "stop"})

    def shutdown(self):
        self.cmds.put({"kind": "shutdown"})