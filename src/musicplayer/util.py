# -*- coding: utf-8 -*-
"""通用工具函数 (无 UI 依赖)。"""

# 多歌手分隔符 (酷我标签常见 "\u300b"/"/" 等)
ARTIST_SEP = (" / ", "/", "\uff0f", "\u3001", "\u300b", "\u300d",
              ";", "\uff1b", "&", "|", "\u00b7", "feat.", "Feat.", ",")


def split_artists(artist):
    """把多歌手串拆成单独歌手列表。

    例如 ``'We Talk\u300b 陈奕迅'`` → ``['We Talk', '陈奕迅']``。
    """
    s = str(artist or "").strip()
    if not s:
        return []
    parts = [s]
    for sep in ARTIST_SEP:
        nxt = []
        for p in parts:
            nxt.extend(p.split(sep))
        parts = nxt
    out = []
    for p in parts:
        p = p.strip()
        if p and p not in out:
            out.append(p)
    return out
