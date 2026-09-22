# -*- coding: utf-8 -*-
"""酷狗音乐歌单解析 (无需登录/密钥)。

两种链接, 走两条路:

1. **云歌单 / App 分享链接** (``gcid_xxx``)::

       https://m.kugou.com/songlist/gcid_3zostefjz2z03a/?...&iszlist=1

   分享页把歌单前 10 首内嵌在 ``window.$output`` 里 (给 SEO/首屏用), 后面
   的只在页面里放「查看更多歌曲 → 打开酷狗 App」的深链 (``kugou://...``),
   没有可用的 web 接口 (全量接口 cloudlist 需要 App 的设备/登录身份)。
   所以这里能拿到的就是前 10 首, 同时把真实总数带回去, 让上层明确提示用户。

2. **公开歌单 (数字 specialid)**::

       https://www.kugou.com/yy/special/single/125032.html
       https://m.kugou.com/plist/list/125032
       125032

   走公开的 ``special/song`` 接口, **可以翻页拿全**, 不需要任何签名。

曲目只用来"导入收藏夹" —— 播放仍走酷我音源 (webapp 里统一匹配 rid)。
"""
import json
import re

import requests

MOBILE_UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36")

# 分享链接可能是短链, 统一跟随跳转
TIMEOUT = 20

CDN = "http://mobilecdn.kugou.com/api/v3"


def is_kugou_link(text):
    """粗判是不是酷狗的歌单链接/gcid。"""
    t = (text or "").strip().lower()
    return ("kugou.com" in t or t.startswith("gcid_")
            or "songlist/gcid" in t or "/songlist/" in t
            or bool(re.search(r"(special/single|plist/list)/\d+", t)))


def special_id(link):
    """从链接里取数字歌单 id (公开歌单); 取不到返回 ""。"""
    t = (link or "").strip()
    m = (re.search(r"(?:special/single|plist/list)/(\d+)", t)
         or re.search(r"[?&#]specialid=(\d+)", t))
    if m:
        return m.group(1)
    if t.isdigit() and len(t) >= 4:
        return t
    return ""


def parse_songlist(link, limit=1000):
    """云歌单分享链接 → (歌单名, [(歌名, 歌手, 封面)], 真实总数)。

    分享页只内嵌前 10 首; 第 3 个返回值是歌单真实总数, 总数 > 返回数量
    就说明被截断了 (上层要提示用户)。解析不到时返回 ("", [], 0)。
    """
    html = _fetch(link)
    data = _extract_output(html)
    if not data:
        return "", [], 0
    info = data.get("info") or {}
    li = info.get("listinfo") or {}
    name = (li.get("name") or "").strip() or "酷狗歌单"
    try:
        total = int(li.get("count") or 0)
    except (TypeError, ValueError):
        total = 0
    out = []
    for s in info.get("songs") or []:
        title, artist, cover = _song_row(s)
        if title:
            out.append((title, artist, cover))
        if len(out) >= limit:
            break
    return name, out, max(total, len(out))


def fetch_special(sid, limit=1000, page_size=100):
    """公开歌单 (数字 id) → (歌单名, [(歌名, 歌手, 封面)], 总数); 自动翻页。"""
    sid = str(sid or "").strip()
    if not sid:
        return "", [], 0
    name = ""
    try:
        info = _get_json("%s/special/info?specialid=%s&version=9108&plat=0"
                         % (CDN, sid))
        name = ((info.get("data") or {}).get("specialname") or "").strip()
    except Exception:  # noqa: BLE001
        pass
    out, total, page = [], 0, 1
    while len(out) < limit:
        url = ("%s/special/song?specialid=%s&page=%d&pagesize=%d"
               "&version=9108&plat=0" % (CDN, sid, page, page_size))
        try:
            data = _get_json(url)
        except Exception:  # noqa: BLE001
            break
        d = data.get("data") or {}
        songs = d.get("info") or []
        try:
            total = int(d.get("total") or total or 0)
        except (TypeError, ValueError):
            total = total or 0
        if not songs:
            break
        for it in songs:
            row = _special_row(it)
            if row[0]:
                out.append(row)
        if len(songs) < page_size:
            break
        page += 1
        if page > 40:                     # 兜底: 最多 4000 首
            break
    return name or "酷狗歌单", out[:limit], max(total, len(out))


# ------------------------------------------------------------------ 内部
def _get_json(url):
    resp = requests.get(url, headers={"User-Agent": MOBILE_UA,
                                      "Referer": "https://m.kugou.com/"},
                        timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _special_row(it):
    """公开歌单里的单曲 → (歌名, 歌手, 封面)。"""
    name = (it.get("songname") or "").strip()
    artist = (it.get("singername") or it.get("author_name") or "").strip()
    raw = (it.get("filename") or "").strip()
    if not name and raw:
        if " - " in raw:
            left, right = raw.split(" - ", 1)
            artist = artist or left.strip()
            name = right.strip()
        else:
            name = raw
    if not artist and name and raw.startswith(name + " - "):
        artist = raw[len(name) + 3:].strip()
    return name, artist, ""
def _fetch(link):
    """取歌单分享页。

    实测: 只有「移动 UA + m.kugou.com」的页面才内嵌 window.$output;
    桌面 UA 或 www.kugou.com 会拿到不带曲目数据的桌面版, 所以这里统一把
    www 改写成 m., 并且候选都试一遍, 谁带 $output 就用谁。
    """
    link = (link or "").strip()
    if not link:
        return ""
    cands = []
    if link.startswith("http"):
        alt = re.sub(r"^https?://www\.kugou\.com/", "https://m.kugou.com/", link)
        if alt != link:
            cands.append(alt)          # m. 优先
        cands.append(link)
    else:
        # 只给了 gcid_xxx
        cands.append("https://m.kugou.com/songlist/%s/" % link)
    fallback = ""
    for u in cands:
        try:
            text = _get(u)
        except Exception:  # noqa: BLE001
            continue
        if "output" in text:
            return text
        fallback = fallback or text
    return fallback


def _get(url):
    resp = requests.get(url, headers={"User-Agent": MOBILE_UA,
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
