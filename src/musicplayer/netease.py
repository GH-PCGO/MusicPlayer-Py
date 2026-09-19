# -*- coding: utf-8 -*-
"""网易云音乐公开接口 (无需登录/密钥)。

用途:
- 首页推荐: 热榜歌曲 / 推荐歌单 / 歌单内歌曲;
- 歌词抓取 (lyrics.py) 依赖同一域名;
- 「观看MV」: MV 搜索 (type=1004) + MV 详情直链 (brs, 240/480/720/1080)。

风控: music.163.com 对连续请求会返回 -462, 故统一走「先访问首页预热 cookie,
再带 Referer」的模块级 Session。
"""
import requests

UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36")

# 官方榜单歌单 id
HOT_PLAYLISTS = {
    "热歌榜": "3778678",
    "飙升榜": "19723756",
    "新歌榜": "3779629",
}

HOME = "https://music.163.com/"
MUSIC_PREFIX = "http://p1.music.126.net"      # 旧封面域名 → 统一升到 https

_session = requests.Session()
_session.headers.update({"User-Agent": UA})
_warmed = False


def _warm():
    """首次访问首页取 cookie 并设 Referer, 规避 -462。"""
    global _warmed
    if _warmed:
        return
    try:
        _session.get(HOME, timeout=15)
        _session.headers.update({"Referer": HOME})
    except Exception:  # noqa: BLE001
        return
    _warmed = True


def _get(url, timeout=15):
    _warm()
    resp = _session.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _track_row(t):
    """网易云 track → (歌名, 歌手, 封面URL)。"""
    name = (t.get("name") or "").strip()
    artists = " / ".join(a.get("name", "") for a in (t.get("artists") or [])
                         if a.get("name"))
    pic = (t.get("album") or {}).get("picUrl") or ""
    return name, artists, pic


def fetch_hot_songs(limit=20, list_id="3778678"):
    """热榜歌曲 → [(歌名, 歌手, 封面URL), ...]。"""
    data = _get("https://music.163.com/api/playlist/detail?id=%s" % list_id)
    tracks = (data.get("result") or {}).get("tracks") or []
    out = []
    for t in tracks:
        name, artist, pic = _track_row(t)
        if name:
            out.append((name, artist, pic))
        if len(out) >= limit:
            break
    return out


def fetch_recommend_playlists(limit=6):
    """推荐歌单 → [(id, 名称, 封面URL, 播放量), ...]。"""
    data = _get("https://music.163.com/api/personalized/playlist?limit=%d"
                % limit)
    out = []
    for p in data.get("result") or []:
        pid = p.get("id")
        if pid:
            out.append((pid, p.get("name") or "", p.get("picUrl") or "",
                        int(p.get("playCount") or 0)))
        if len(out) >= limit:
            break
    return out


def fetch_playlist_songs(playlist_id, limit=50):
    """歌单内歌曲 → (歌单名, [(歌名, 歌手, 封面URL), ...])。"""
    data = _get("https://music.163.com/api/playlist/detail?id=%s" % playlist_id)
    res = data.get("result") or {}
    name = res.get("name") or ""
    out = []
    for t in res.get("tracks") or []:
        n, a, pic = _track_row(t)
        if n:
            out.append((n, a, pic))
        if len(out) >= limit:
            break
    return name, out


# ------------------------------------------------------------------ MV
def _mv_cover(url):
    url = url or ""
    if url.startswith("http://p1.music.126.net"):
        return "https://" + url[7:]
    return url


def search_mv(keyword, limit=8):
    """MV 搜索 → [{source, id, name, artist, cover, dur, play}, ...]。

    使用公开 ``api/search/get`` (type=1004)。失败时返回空列表。
    """
    keyword = (keyword or "").strip()
    if not keyword:
        return []
    try:
        data = _get("https://music.163.com/api/search/get"
                    "?s=%s&type=1004&limit=%d&offset=0"
                    % (requests.utils.quote(keyword), limit))
    except Exception:  # noqa: BLE001
        return []
    mvs = (data.get("result") or {}).get("mvs") or []
    out = []
    for m in mvs:
        mid = m.get("id")
        if not mid:
            continue
        out.append({
            "source": "netease",
            "id": mid,
            "name": (m.get("name") or "").strip(),
            "artist": m.get("artistName") or "",
            "cover": _mv_cover(m.get("cover")),
            "dur": int((m.get("duration") or 0) / 1000),
            "play": int(m.get("playCount") or 0),
        })
        if len(out) >= limit:
            break
    return out


def mv_play_url(mvid, max_quality=1080):
    """MV 直链 mp4 (取 <= max_quality 的最高档)。

    返回 ``{url, quality}``; 拿不到返回 ``{url: "", quality: 0}``。
    注意签名 ``wsTime`` 短时效, 每次点播都应现取。
    """
    try:
        data = _get("https://music.163.com/api/mv/detail?id=%s" % mvid)
    except Exception:  # noqa: BLE001
        return {"url": "", "quality": 0}
    brs = (data.get("data") or {}).get("brs") or {}
    best = 0
    for q in sorted((int(k) for k in brs.keys()), reverse=True):
        if q <= max_quality and brs.get(str(q)):
            best = q
            break
    return {"url": brs.get(str(best), "") if best else "", "quality": best}
