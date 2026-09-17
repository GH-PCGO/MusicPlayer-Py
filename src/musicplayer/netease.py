# -*- coding: utf-8 -*-
"""网易云音乐公开接口 (无需登录/密钥)。

用于首页推荐: 热榜歌曲 / 推荐歌单 / 歌单内歌曲。
歌词抓取 (lyrics.py) 也依赖同一域名, 该域在桌面与安卓均可访问。
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


def _get(url, timeout=15):
    resp = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
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