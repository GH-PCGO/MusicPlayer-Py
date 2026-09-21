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
    """网易云 track → (歌名, 歌手, 封面URL)。

    兼容两套字段: 旧 web 接口用 artists/album, v6/weapi 用 ar/al。
    """
    name = (t.get("name") or "").strip()
    ars = t.get("artists") or t.get("ar") or []
    artists = " / ".join(a.get("name", "") for a in ars if a.get("name"))
    alb = t.get("album") or t.get("al") or {}
    pic = alb.get("picUrl") or alb.get("picUrl_str") or ""
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


# ------------------------------------------------------------------ 歌单导入
def _https(url):
    """http 封面统一升到 https (安卓 WebView 不允许明文 http)。"""
    url = url or ""
    if url.startswith("http://"):
        return "https://" + url[7:]
    return url


def _user_session(cookie):
    """带用户 cookie 的独立 Session (不影响公开接口的模块级 Session)。

    cookie 为空时退化为匿名会话 —— 公开歌单同样可以直接读取。
    """
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA, "Referer": HOME})
    cookie = (cookie or "").strip()
    if cookie:
        if "=" not in cookie:                     # 允许只粘贴 MUSIC_U 的值
            cookie = "MUSIC_U=" + cookie
        sess.headers.update({"Cookie": cookie})
    return sess


def _auth_get(sess, url, timeout=20):
    resp = sess.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def user_profile(cookie):
    """校验 cookie → ``{uid, nickname, avatar}``; 无效时抛 ValueError。"""
    try:
        data = _auth_get(_user_session(cookie),
                         "https://music.163.com/api/nuser/account/get")
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ValueError("网络错误: %s" % exc)
    prof = data.get("profile") or {}
    uid = prof.get("userId")
    if not uid:
        raise ValueError("cookie 无效或已过期")
    return {"uid": uid, "nickname": prof.get("nickname") or "",
            "avatar": _https(prof.get("avatarUrl"))}


def user_playlists(cookie, uid=None):
    """当前账号的歌单 (含私有歌单 / 「我喜欢的音乐」) → list[dict]。"""
    sess = _user_session(cookie)
    if not uid:
        uid = user_profile(cookie)["uid"]
    out, offset = [], 0
    while True:
        data = _auth_get(sess, "https://music.163.com/api/user/playlist/"
                               "?uid=%s&limit=100&offset=%d" % (uid, offset))
        page = data.get("playlist") or []
        for p in page:
            pid = p.get("id")
            if not pid:
                continue
            out.append({
                "id": pid,
                "name": p.get("name") or "",
                "cover": _https(p.get("coverImgUrl")),
                "count": int(p.get("trackCount") or 0),
                "special": int(p.get("specialType") or 0) == 5,
                "creator": (p.get("creator") or {}).get("nickname") or "",
            })
        if not data.get("more") or not page or offset > 2000:
            break
        offset += len(page)
    return out


def playlist_songs_all(cookie, pid, limit=1000):
    """歌单全部歌曲 (超过 1000 首用 song/detail 补齐) → (歌单名, [(名, 歌手, 封面)])。"""
    sess = _user_session(cookie)
    data = _auth_get(sess, "https://music.163.com/api/v6/playlist/detail"
                           "?id=%s&n=%d&s=0" % (pid, max(1, limit)))
    pl = data.get("playlist") or {}
    name = pl.get("name") or ""
    tracks = pl.get("tracks") or []
    out = []
    for t in tracks:
        n, a, pic = _track_row(t)
        if n:
            out.append((n, a, _https(pic)))
    ids = [x.get("id") for x in (pl.get("trackIds") or []) if x.get("id")]
    if len(ids) > len(out):
        have = {t.get("id") for t in tracks}
        todo = [i for i in ids if i not in have]
        for i in range(0, len(todo), 200):
            chunk = todo[i:i + 200]
            try:
                dd = _auth_get(sess, "https://music.163.com/api/song/detail"
                                     "?ids=[%s]" % ",".join(str(x) for x in chunk))
            except Exception:  # noqa: BLE001
                continue
            for t in dd.get("songs") or []:
                n, a, pic = _track_row(t)
                if n:
                    out.append((n, a, _https(pic)))
            if len(out) >= limit:
                break
    return name, out[:limit]


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
