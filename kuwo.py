# -*- coding: utf-8 -*-
"""
Kuwo (酷我音乐) API 客户端
类比原 Java 项目中的 Search.java / Function.saveMusicFile
提供: 搜索 -> rid 《歌名》 歌手 行 ; 在线播放链接; 下载 mp3

官方"修复"后:
- www.kuwo.cn 系 csrf 接口 (web 搜索/playUrl/www.kuwo.cn/url) 全部返回
  "The request is illegal!" (csrf 改由 JS 生成 Hm_token->Cross 头)；
- antiserver 直连 (Search.apiDownlowd) 只返回 ~11s 试听片段。
所以下载改为 mobi.s 车载签名接口 convert_url_with_sign (伪装车载版客户端),
可拿到完整全曲, 320k 优先、128k 回落; 搜索仍走 search.kuwo.cn/r.s。
"""
import os
import random
import re
import threading
import time
import urllib.parse

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

SEARCH_URL = ("http://search.kuwo.cn/r.s?all={kw}&ft=music&itemset=web_2013"
              "&client=kt&pn={pn}&rn={rn}&rformat=json&encoding=utf8"
              "&mobi=1&vipver=MUSIC_8.0.3.0")

# 原版两步 csrf 流程 (备用链路)
SEARCH_COOKIE_URL = "http://www.kuwo.cn/search/list?key={kw}"
SEARCH_WEB_URL = ("http://www.kuwo.cn/api/www/search/searchMusicBykeyWord"
                  "?key={kw}&pn={pn}&rn={rn}&httpsStatus=1&reqId=f3d0e9c0-b4aa-11eb-abcd-233be870dd07")

# antiserver 直连 (原项目 apiDownlowd, 现仅返回 ~11s 试听, 作最后兜底)
ANTI_URL = ("http://antiserver.kuwo.cn/anti.s?useless=/resource/&format=mp3"
            "&rid=MUSIC_{rid}&response=res&type=convert_url&")

# mobi.s 车载签名下载 (convert_url_with_sign), 返回完整 mp3 地址
MOBI_URL = "https://mobi.kuwo.cn/mobi.s"
MOBI_SOURCE = "kwplayercar_ar_6.0.0.9_B_jiakong_vh.apk"


class KuwoAPI:
    """酷我音乐搜索 / 播放 / 下载。"""

    def __init__(self, timeout=15):
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": UA})
        self.timeout = timeout
        self._csrf = None
        self._cookie = None

    # ------------------------------------------------------------------ 搜索
    COVER_BASE = "http://img1.kuwo.cn/star/albumcover/"

    @staticmethod
    def cover_url(short):
        """web_albumpic_short 相对路径 → 完整封面 URL。"""
        return KuwoAPI.COVER_BASE + short if short else ""

    def search(self, keyword, page=1, rn=30):
        """按关键词 + 页码搜索, 返回 [(rid, name, artist, cover_short), ...]。"""
        try:
            items = self._search_classic(keyword, page)
            if items:
                return items
        except Exception as exc:  # noqa: BLE001
            print("经典搜索接口不可用(%s), 尝试 web csrf 链路" % exc)
        items = self.search_web(keyword, page)
        if not items:
            raise IOError("搜索无结果")
        return items

    def _search_classic(self, keyword, page=1, rn=30):
        """search.kuwo.cn 兼容接口。"""
        kw = urllib.parse.quote(keyword)
        pn = max(page - 1, 0)
        url = SEARCH_URL.format(kw=kw, pn=pn, rn=rn)
        resp = self._session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        abslist = data.get("abslist") or []
        result = []
        for item in abslist:
            rid = str(item.get("MUSICRID") or "").replace("MUSIC_", "")
            name = item.get("NAME") or item.get("SONGNAME") or "未知歌曲"
            artist = item.get("ARTIST") or ""
            cover = item.get("web_albumpic_short") or ""
            result.append((rid, name, artist, cover))
        return result

    def _warm_csrf(self, keyword):
        """原版第一步: 访问 search/list 拿 Set-Cookie 里的 csrf token。"""
        if self._csrf and self._cookie:
            return
        url = SEARCH_COOKIE_URL.format(kw=urllib.parse.quote(keyword))
        resp = self._session.get(url, timeout=self.timeout)
        cookie_line = resp.headers.get("Set-Cookie") or ""
        m = re.search(r"kw_token=([^;]+)", cookie_line)
        if not m:
            return
        self._csrf = m.group(1)
        self._cookie = "kw_token=" + m.group(1)

    def search_web(self, keyword, page=1, rn=30):
        """原版两步 csrf 搜索 (www.kuwo.cn web api)。"""
        self._warm_csrf(keyword)
        kw = urllib.parse.quote(keyword)
        pn = max(page - 1, 0)
        url = SEARCH_WEB_URL.format(kw=kw, pn=pn, rn=rn)
        headers = {}
        if self._csrf and self._cookie:
            headers.update({"csrf": self._csrf, "cookie": self._cookie,
                            "Referer": SEARCH_COOKIE_URL.format(kw=kw)})
        resp = self._session.get(url, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            return []
        listing = (data.get("data") or {}).get("list") or []
        result = []
        for item in listing:
            rid = str(item.get("rid") or "")
            name = item.get("name") or "未知歌曲"
            artist = item.get("artist") or ""
            cover = item.get("pic") or item.get("albumpic") or \
                item.get("web_albumpic_short") or ""
            result.append((rid, name, artist, cover))
        return result

    @staticmethod
    def format_row(item, index=0):
        """与原项目 GetSearchArray 的 listdata 格式一致: <rid> 《<歌名>》 <歌手>"""
        rid, name, artist = item[:3]
        return "{rid} 《{name}》 {artist}".format(rid=rid, name=name, artist=artist)

    @staticmethod
    def display_name(row):
        """列表显示片段: 《歌名》.mp3  (UI 层再加序号 n, 对应原 Function.splitPath2)"""
        m = re.search(r"《([^》]+)》", row)
        name = m.group(1) if m else "未知歌曲"
        return "《" + name + "》.mp3"

    @staticmethod
    def artist_name(row):
        """列表列头'歌手'列显示: 取 <rid> 《歌名》 之后的部分。"""
        parts = row.split(" ", 2)
        return parts[2] if len(parts) > 2 else ""

    @staticmethod
    def song_name(row):
        m = re.search(r"《([^》]+)》", row)
        return m.group(1) if m else "未知歌曲"

    @staticmethod
    def row_rid(row):
        return row.split(" ", 1)[0]

    # ------------------------------------------------------------ 播放/下载
    def _mobi_url(self, rid, br):
        """mobi.s 车载签名接口: 返回完整 mp3 播放/下载地址。br 如 320kmp3/128kmp3。"""
        user = "C_APK_guanwang_%d%d" % (int(time.time() * 1e9),
                                        random.randint(0, 999999))
        params = {"f": "web", "source": MOBI_SOURCE, "from": "PC",
                  "type": "convert_url_with_sign", "br": br,
                  "rid": str(rid), "user": user}
        resp = self._session.get(MOBI_URL, params=params, timeout=self.timeout)
        resp.raise_for_status()
        try:
            data = resp.json().get("data") or {}
        except ValueError:
            data = {}
        url = data.get("url") or ""
        if not url:
            raise IOError("mobi.s 未返回播放地址(br=%s)" % br)
        return url

    def _mobi_stream(self, rid):
        """优先 320k, 失败回落 128k, 返回 (mp3流, 实际码率参数)。"""
        for br in ("320kmp3", "128kmp3"):
            try:
                url = self._mobi_url(rid, br)
                stream = self._session.get(url, timeout=self.timeout,
                                           stream=True)
                stream.raise_for_status()
                return stream, br
            except Exception:  # noqa: BLE001
                continue
        return None, None

    def get_play_url(self, rid):
        """返回可直接播放的 mp3 完整地址 (mobi.s 签名接口)。"""
        return self._mobi_url(rid, "320kmp3")

    def _anti(self, rid):
        """antiserver 兜底: 返回音频流响应 (仅试听片段)。"""
        url = ANTI_URL.format(rid=rid)
        resp = self._session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp

    def download(self, rid, filename, folder, on_done=None,
                 on_progress=None, title="", artist="", cover=None):
        """下载完整 mp3 到 folder, 支持回调 (线程中执行)。文件名保持《歌名》.mp3。

        on_done(path):   完成回调 (失败时 path=None)。
        on_progress(bytes_done): 分块进度回调 (已写入字节数)。
        cover(url): 封面图片 URL, 下载完成后写入 ID3v2 APIC 帧 (播放条/系统播放器
           均可显示头像)。下载完成后自动嵌入 ID3v2 歌词 (WMP 可显示) 并保存
           同名 .lrc 文件。
        """
        def worker():
            path = None
            try:
                os.makedirs(folder, exist_ok=True)
                stream, _br = self._mobi_stream(rid)   # 主链路: 完整全曲
                if stream is None:
                    stream = self._anti(rid)           # 兜底: antiserver 试听
                path = os.path.join(folder, filename)
                total = 0
                with open(path, "wb") as f:
                    for chunk in stream.iter_content(1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            total += len(chunk)
                            if on_progress:
                                try:
                                    on_progress(total)
                                except Exception:  # noqa: BLE001
                                    pass
                try:
                    from lyrics import (fetch_lyrics, embed_lyrics,
                                        embed_cover, save_lrc, lrc_to_plain)
                    name = title or os.path.splitext(filename)[0]
                    lrc = fetch_lyrics(rid, name, artist,
                                       session=self._session)
                    if lrc:
                        plain = lrc_to_plain(lrc)      # USLT 用纯文本
                        if plain:
                            embed_lyrics(path, plain, name, artist)
                        save_lrc(path, lrc)
                    if cover:                           # 嵌入封面 APIC 帧
                        try:
                            r = self._session.get(cover, timeout=10)
                            if r.status_code == 200 and r.content:
                                mime = (r.headers.get("Content-Type")
                                        or "image/jpeg").split(";")[0]
                                embed_cover(path, r.content,
                                            mime or "image/jpeg")
                        except Exception as exc:  # noqa: BLE001
                            print("封面嵌入失败 %s: %s" % (filename, exc))
                except Exception as exc:  # noqa: BLE001
                    print("歌词嵌入失败 %s: %s" % (filename, exc))
            except Exception as exc:  # noqa: BLE001
                print("下载失败 %s: %s" % (filename, exc))
                path = None
            if on_done:
                try:
                    on_done(path)
                except Exception:  # noqa: BLE001
                    pass
        threading.Thread(target=worker, daemon=True).start()
        return None