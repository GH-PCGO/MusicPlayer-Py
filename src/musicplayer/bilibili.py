# -*- coding: utf-8 -*-
"""B 站 MV 搜索 (免登录), 供「观看MV」功能使用。

搜索接口有风控: 直接请求可能返回验证页 (HTML 而非 JSON), 需先访问
``www.bilibili.com`` 取得 ``buvid3``/``b_nut`` cookie 并带上 ``Referer``,
之后 ``x/web-interface/search/type`` 便能稳定返回 JSON。

只做「搜索拿 bvid」: 播放交给 WebView 内嵌 ``player.bilibili.com`` iframe,
无需解析直链/签名。
"""
import re

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

HOME = "https://www.bilibili.com/"
SEARCH_API = "https://api.bilibili.com/x/web-interface/search/type"
EMBED_URL = ("https://player.bilibili.com/player.html?bvid=%s"
             "&page=1&autoplay=1&danmaku=0&high_quality=1&as_wide=1")

_session = requests.Session()
_session.headers.update({"User-Agent": UA, "Referer": HOME})
_warmed = False

_TAG = re.compile(r"<[^>]+>")
_DUR = re.compile(r"(\d+):(\d+)")


def _warm():
    """首次访问首页取 buvid3/b_nut cookie (风控必需), 只做一次。"""
    global _warmed
    if _warmed:
        return
    try:
        _session.get(HOME, timeout=15)
    except Exception:  # noqa: BLE001
        return
    _warmed = True


def _clean(text):
    """去掉搜索结果标题里的 <em class="keyword"> 高亮标签。"""
    return _TAG.sub("", text or "").strip()


def _cover(pic):
    pic = pic or ""
    if pic.startswith("//"):
        return "https:" + pic
    if pic.startswith("http://"):
        return "https://" + pic[7:]
    return pic


def _dur_seconds(text):
    m = _DUR.search(text or "")
    if not m:
        return 0
    return int(m.group(1)) * 60 + int(m.group(2))


def search_mv(keyword, limit=8):
    """按关键词搜 B 站视频 → MV 候选列表。

    返回 ``[{source, bvid, name, artist, cover, dur, play}, ...]``;
    失败 (风控/网络) 时返回空列表, 由调用方降级。
    """
    keyword = (keyword or "").strip()
    if not keyword:
        return []
    _warm()
    try:
        resp = _session.get(SEARCH_API, timeout=15, params={
            "search_type": "video", "keyword": keyword, "page": 1})
        resp.raise_for_status()
        data = resp.json()
    except Exception:  # noqa: BLE001
        return []
    if data.get("code") != 0:
        return []
    result = (data.get("data") or {}).get("result") or []
    out = []
    for v in result:
        bvid = v.get("bvid")
        if not bvid:
            continue
        out.append({
            "source": "bili",
            "bvid": bvid,
            "name": _clean(v.get("title")),
            "artist": v.get("author") or "",
            "cover": _cover(v.get("pic")),
            "dur": _dur_seconds(v.get("duration")),
            "play": int(v.get("play") or 0),
        })
        if len(out) >= limit:
            break
    return out


def embed_url(bvid):
    """B 站内嵌播放地址 (供 WebView iframe)。"""
    return EMBED_URL % bvid
