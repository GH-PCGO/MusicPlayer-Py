# -*- coding: utf-8 -*-
"""酷狗音乐歌单分享链接解析 (无需登录/密钥)。

酷狗 App 分享出来的歌单链接形如::

    https://m.kugou.com/songlist/gcid_3zostefjz2z03a/?...&iszlist=1

这个页面会把整份歌单以 JSON 内嵌在 ``window.$output`` 里 (给 SEO/首屏用),
所以带移动端 UA 取一次页面就能拿到全部曲目, 不需要任何签名参数。

注意: 这里的曲目只用来"导入收藏夹" —— 播放仍然走酷我音源 (webapp 里统一
匹配 rid), 所以拿到 (歌名, 歌手) 就够了。
"""
import json
import re

import requests

MOBILE_UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36")

# 分享链接可能是短链, 统一跟随跳转
TIMEOUT = 20


def is_kugou_link(text):
    """粗判是不是酷狗的歌单链接/gcid。"""
    t = (text or "").strip().lower()
    return ("kugou.com" in t or t.startswith("gcid_")
            or "songlist/gcid" in t or "/songlist/" in t)


def parse_songlist(link, limit=1000):
    """酷狗歌单链接 → (歌单名, [(歌名, 歌手, 封面URL), ...])。

    只认 gcid 云歌单/分享页这种格式; 解析不到时返回 ("", [])。
    """
    html = _fetch(link)
    data = _extract_output(html)
    if not data:
        return "", []
    info = data.get("info") or {}
    li = info.get("listinfo") or {}
    name = (li.get("name") or "").strip() or "酷狗歌单"
    out = []
    for s in info.get("songs") or []:
        title, artist, cover = _song_row(s)
        if title:
            out.append((title, artist, cover))
        if len(out) >= limit:
            break
    return name, out


# ------------------------------------------------------------------ 内部
def _fetch(link):
    link = (link or "").strip()
    if not link:
        return ""
    if not link.startswith("http"):
        # 只给了 gcid_xxx
        link = "https://m.kugou.com/songlist/%s/" % link
    resp = requests.get(link, headers={"User-Agent": MOBILE_UA,
                                       "Referer": "https://m.kugou.com/"},
                        timeout=TIMEOUT)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text


def _extract_output(html):
    """从页面里抠出 window.$output 的 JSON 对象。"""
    key = "window." + chr(36) + "output"
    i = html.find(key)
    if i < 0:
        return None
    start = html.find("{", i)
    if start < 0:
        return None
    depth = 0
    for k in range(start, len(html)):
        ch = html[k]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start:k + 1])
                except ValueError:
                    return None
    return None


def _song_row(s):
    """酷狗单曲 → (歌名, 歌手, 封面)。

    酷狗的 ``name`` 通常是 "歌手 - 歌名" (也可能正好等于歌名), 歌手另在
    ``singerinfo`` 里; 两边都拿来互相校正, 尽量还原干净的歌名。
    """
    raw = (s.get("name") or "").strip()
    artists = [x.get("name") for x in (s.get("singerinfo") or [])
               if x.get("name")]
    artist = " / ".join(artists)
    title = raw
    if artist and raw.startswith(artist):
        title = raw[len(artist):].lstrip(" -—_·")
    elif " - " in raw:
        left, right = raw.split(" - ", 1)
        if not artist:
            artist = left.strip()
        title = right.strip()
    title = (title or raw).strip()
    # 有些条目会带 "歌名 (Live)" 之类后缀, 保留原样交给匹配器判断
    cover = (s.get("cover") or "").replace("{size}", "480")
    if cover.startswith("http://"):
        cover = "https://" + cover[7:]
    return title, artist, cover
