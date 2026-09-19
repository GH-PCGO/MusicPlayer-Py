# -*- coding: utf-8 -*-
"""安卓 MediaStore 发布: 把下载好的 mp3 复制进系统媒体库 ``Music/音乐下载器/``。

设计: **私有副本 + 媒体库发布**。下载仍写应用私有目录 (歌词/封面嵌入逻辑不变),
完成后另存一份到系统媒体库, 使文件管理器 / 系统音乐 App 可见; 删除时两边同删。

- 免存储权限: 应用对自己 insert 的媒体拥有完全读写权 (API 29+ 也是如此);
- 仅安卓 (Chaquopy 提供 ``java`` 桥) 可用; 桌面 / iPhone 无桥时 ``available()``
  返回 False, 所有调用安全降级为 no-op (下载只落私有目录)。
"""
import os

_ctx = None
_rel = "Music/音乐下载器"
_probe = None            # None=未探测; True/False=缓存结果


def set_context(ctx, rel=None):
    """由 MainActivity 注入 Android Context (Chaquopy JavaObject)。"""
    global _ctx, _rel, _probe
    _ctx = ctx
    if rel:
        _rel = rel
    _probe = None


def available():
    """安卓且 java 桥可用时返回 True。"""
    global _probe
    if _ctx is None:
        return False
    if _probe is not None:
        return _probe
    try:
        from java import jclass  # noqa: F401
        jclass("android.provider.MediaStore")
        _probe = True
    except Exception:  # noqa: BLE001
        _probe = False
    return _probe


def _media_cls():
    from java import jclass
    return jclass("android.provider.MediaStore$Audio$Media")


def _columns_cls():
    from java import jclass
    return jclass("android.provider.MediaStore$MediaColumns")


def publish(local_path, display_name, mime="audio/mpeg"):
    """把本地 mp3 复制进媒体库。成功返回 uri 字符串, 失败返回 None。"""
    if not available() or not local_path or not os.path.isfile(local_path):
        return None
    try:
        from java import jclass
        Media = _media_cls()
        Cols = _columns_cls()
        ContentValues = jclass("android.content.ContentValues")
        resolver = _ctx.getContentResolver()

        values = ContentValues()
        values.put(Cols.DISPLAY_NAME, display_name)
        values.put(Cols.MIME_TYPE, mime)
        values.put(Cols.RELATIVE_PATH, _rel)
        values.put(Cols.IS_PENDING, 1)
        uri = resolver.insert(Media.EXTERNAL_CONTENT_URI, values)
        if uri is None:
            return None
        try:
            out = resolver.openOutputStream(uri)
            try:
                with open(local_path, "rb") as f:
                    while True:
                        chunk = f.read(1 << 20)
                        if not chunk:
                            break
                        out.write(chunk)
            finally:
                out.close()
        except Exception:  # noqa: BLE001
            try:
                resolver.delete(uri, None, None)
            except Exception:  # noqa: BLE001
                pass
            return None
        done = ContentValues()
        done.put(Cols.IS_PENDING, 0)
        resolver.update(uri, done, None, None)
        return str(uri)
    except Exception:  # noqa: BLE001
        return None


def delete(display_name):
    """按显示名删除媒体库中本目录下的条目, 返回删除条数。"""
    if not available() or not display_name:
        return 0
    try:
        Media = _media_cls()
        resolver = _ctx.getContentResolver()
        selection = "RELATIVE_PATH LIKE ? AND DISPLAY_NAME=?"
        args = [_rel.rstrip("/") + "/%", display_name]
        return int(resolver.delete(Media.EXTERNAL_CONTENT_URI,
                                   selection, args))
    except Exception:  # noqa: BLE001
        return 0


def exists(display_name):
    """媒体库是否已存在同名文件。"""
    if not available() or not display_name:
        return False
    try:
        Media = _media_cls()
        resolver = _ctx.getContentResolver()
        selection = "RELATIVE_PATH LIKE ? AND DISPLAY_NAME=?"
        args = [_rel.rstrip("/") + "/%", display_name]
        cur = resolver.query(Media.EXTERNAL_CONTENT_URI, ["_id"],
                             selection, args, None)
        if cur is None:
            return False
        try:
            return bool(cur.moveToFirst())
        finally:
            cur.close()
    except Exception:  # noqa: BLE001
        return False
