# -*- coding: utf-8 -*-
"""
歌词模块: 纯 Python ID3v2 USLT 注入 + KuWo/网易云歌词获取 + .lrc 保存

用法:
    from lyrics import embed_lyrics, fetch_lyrics
    lrc = fetch_lyrics(rid, title, artist)
    if lrc:
        embed_lyrics(mp3_path, lrc, title, artist)
        save_lrc(mp3_path, lrc)
"""
import os
import re

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


# ================================================================== ID3v2
def _syncsafe_encode(size):
    """整数 → synchsafe (4 bytes, 每字节 7 bit)。"""
    return bytes([
        (size >> 21) & 0x7F,
        (size >> 14) & 0x7F,
        (size >> 7) & 0x7F,
        size & 0x7F,
    ])


def _syncsafe_decode(data):
    """synchsafe 4 bytes → 整数。"""
    return (data[0] << 21) | (data[1] << 14) | (data[2] << 7) | data[3]


def _parse_frames(tag_data, version):
    """解析 tag 数据中的帧列表, 返回 (frames, padding_start)。"""
    frames = []
    pos = 0
    while pos < len(tag_data) - 10:
        fid = tag_data[pos:pos + 4]
        if fid[0] == 0 or not all(0x20 <= b < 0x7F for b in fid):
            break
        if version >= 0x04:
            fsize = _syncsafe_decode(tag_data[pos + 4:pos + 8])
        else:
            fsize = int.from_bytes(tag_data[pos + 4:pos + 8], "big")
        if pos + 10 + fsize > len(tag_data):
            break
        frames.append((fid, fsize, tag_data[pos + 8:pos + 10],
                        tag_data[pos + 10:pos + 10 + fsize]))
        pos += 10 + fsize
    return frames, pos


def _build_uslt_frame(lang="chi", desc="", lyrics=""):
    """构建一个 USLT 帧 (ID3v2.3/2.4 通用)。"""
    enc = lyrics.encode("utf-8")
    body = b"\x03" + lang.encode("ascii") + desc.encode("utf-8") + b"\x00" + enc + b"\x00"
    return b"USLT" + len(body).to_bytes(4, "big") + b"\x00\x00" + body


def _build_simple_frame(frame_id, text):
    """构建一个简单文本帧 (TIT2/TPE1 等)。"""
    enc = text.encode("utf-8")
    body = b"\x03" + enc  # 0x03 = UTF-8
    return frame_id.encode("ascii") + len(body).to_bytes(4, "big") + b"\x00\x00" + body


def embed_lyrics(path, lrc_text, title="", artist=""):
    """将 LRC 歌词嵌入 MP3 的 ID3v2 USLT 帧。

    如果文件已有 ID3v2 tag, 则移除旧 USLT 帧并插入新帧;
    如果无 tag, 则新建最小 ID3v2.3 tag (含 TIT2/TPE1/USLT)。
    header 尺寸必须按 synchsafe 编码 (v2.3/v2.4 皆然);
    帧尺寸: v2.3 用普通 32bit, v2.4 用 synchsafe。
    """
    with open(path, "rb") as f:
        data = f.read()

    has_tag = data[:3] == b"ID3"
    if has_tag:
        if len(data) < 10:
            has_tag = False
            tag_data = b""
            version = 0x03
            flags = 0
        else:
            version = data[3]
            flags = data[5]
            tag_size = _syncsafe_decode(data[6:10])
            tag_data = data[10:10 + tag_size]
    else:
        tag_data = b""
        version = 0x03
        flags = 0

    def frame_size_bytes(n):
        return _syncsafe_encode(n) if version >= 0x04 else \
            n.to_bytes(4, "big")

    frames, _ = _parse_frames(tag_data, version)

    new_frames = []
    new_frames.append(_build_uslt_frame("chi", "", lrc_text))
    if title:
        new_frames.append(_build_simple_frame("TIT2", title))
    if artist:
        new_frames.append(_build_simple_frame("TPE1", artist))

    for fid, fsize, fflags, fdata in frames:
        if fid in (b"USLT", b"TIT2", b"TPE1"):
            continue
        new_frames.append(fid + frame_size_bytes(fsize) + fflags + fdata)

    new_tag_data = b"".join(new_frames) + b"\x00" * 16
    header = (b"ID3" + bytes([version, 0x00, flags]) +
              _syncsafe_encode(len(new_tag_data)))

    if has_tag:
        audio = data[10 + tag_size:]
    else:
        audio = data
    with open(path, "wb") as f:
        f.write(header + new_tag_data + audio)
    return True


def _build_apic_frame(mime, image_bytes, desc="", pic_type=3):
    """构建一个 APIC 附件图片帧 (encoding=0 Latin-1 描述, 兼容性最好)。

    pic_type: 3 = 正面专辑封面 (Front cover), 大多数播放器识别。
    """
    body = (b"\x00" + mime.encode("latin-1", errors="replace") + b"\x00" +
            bytes([pic_type]) +
            desc.encode("latin-1", errors="replace") + b"\x00" +
            bytes(image_bytes))
    return b"APIC" + len(body).to_bytes(4, "big") + b"\x00\x00" + body


def embed_cover(path, image_bytes, mime="image/jpeg"):
    """将封面图嵌入 MP3 的 ID3v2 APIC 帧 (保留 USLT/TIT2/TPE1 等现有帧)。

    若无 ID3v2 标签则新建; 已有 APIC 帧则替换 (避免重复封面)。
    """
    if not image_bytes:
        return False
    with open(path, "rb") as f:
        data = f.read()

    has_tag = data[:3] == b"ID3" and len(data) >= 10
    if has_tag:
        version = data[3]
        flags = data[5]
        tag_size = _syncsafe_decode(data[6:10])
        tag_data = data[10:10 + tag_size]
    else:
        version, flags, tag_size, tag_data = 0x03, 0, 0, b""

    def frame_size_bytes(n):
        return _syncsafe_encode(n) if version >= 0x04 else \
            n.to_bytes(4, "big")

    frames, _ = _parse_frames(tag_data, version)
    apic = _build_apic_frame(mime, image_bytes)

    new_frames = [apic]
    for fid, fsize, fflags, fdata in frames:
        if fid in (b"APIC",):
            continue                      # 去掉旧封面
        new_frames.append(fid + frame_size_bytes(fsize) + fflags + fdata)

    new_tag_data = b"".join(new_frames) + b"\x00" * 16
    header = (b"ID3" + bytes([version, 0x00, flags]) +
              _syncsafe_encode(len(new_tag_data)))

    if has_tag:
        audio = data[10 + tag_size:]
    else:
        audio = data
    with open(path, "wb") as f:
        f.write(header + new_tag_data + audio)
    return True


def read_uslt(path):
    """读取 MP3 文件中的 USLT 歌词, 返回 (歌词文本, 语言) 或 (None, None)。"""
    with open(path, "rb") as f:
        header = f.read(10)
    if len(header) < 10 or header[:3] != b"ID3":
        return None, None


def read_cover(path):
    """读取 MP3 内嵌封面 (ID3v2 APIC 帧), 返回 PIL Image 或 None。"""
    try:
        import io
        from PIL import Image
    except Exception:  # noqa: BLE001
        return None
    try:
        with open(path, "rb") as f:
            header = f.read(10)
        if len(header) < 10 or header[:3] != b"ID3":
            return None
        ver = header[3]
        tag_size = _syncsafe_decode(header[6:10])
        with open(path, "rb") as f:
            f.seek(10)
            tag_data = f.read(tag_size)
        frames, _ = _parse_frames(tag_data, ver)
        for fid, fsize, fflags, fdata in frames:
            if fid == b"APIC" and fdata:
                try:
                    enc = fdata[0]
                    i = 1
                    while i < len(fdata) and fdata[i] != 0:
                        i += 1
                    j = i + 2                    # 跳过 MIME\0 和图片类型
                    if enc in (1, 2):            # UTF-16 描述: 双字节 00 结尾
                        while j + 1 < len(fdata) and not (fdata[j] == 0 and
                                                           fdata[j + 1] == 0):
                            j += 2
                        j += 2
                    else:                        # ISO-8859-1 / UTF-8 描述
                        while j < len(fdata) and fdata[j] != 0:
                            j += 1
                        j += 1
                    img = Image.open(io.BytesIO(fdata[j:]))
                    img.load()
                    return img
                except Exception:  # noqa: BLE001
                    continue
    except Exception:  # noqa: BLE001
        pass
    return None
    ver = header[3]
    tag_size = _syncsafe_decode(header[6:10])
    f = open(path, "rb")
    f.seek(10)
    tag_data = f.read(tag_size)
    f.close()
    frames, _ = _parse_frames(tag_data, ver)
    for fid, fsize, fflags, fdata in frames:
        if fid == b"USLT" and fdata:
            enc_byte = fdata[0]
            lang = fdata[1:4].decode("ascii", errors="replace")
            rest = fdata[4:]
            parts = rest.split(b"\x00", 1)
            if len(parts) == 2:
                lyrics = parts[1]
            else:
                lyrics = rest
            try:
                if enc_byte == 0:
                    return lyrics.decode("latin-1"), lang
                elif enc_byte == 1:
                    return lyrics.decode("utf-16"), lang
                elif enc_byte == 2:
                    return lyrics.decode("utf-16-be"), lang
                else:
                    return lyrics.decode("utf-8"), lang
            except Exception:
                return lyrics.decode("utf-8", errors="replace"), lang
    return None, None


# ============================================================ 歌词获取
def fetch_lrc_kuwo(rid, session=None, timeout=10):
    """从酷我 mobi.s 获取 LRC 歌词 (纯文本)。"""
    sess = session or requests.Session()
    urls = [
        "http://mobi.kuwo.cn/mobi.s?f=web&source=&from=web&type=getlrc&rid=%s" % rid,
        "http://mobi.kuwo.cn/mobi.s?f=web&source=&from=web&type=getlrcwithtime&rid=%s" % rid,
    ]
    for url in urls:
        try:
            r = sess.get(url, timeout=timeout, headers={"User-Agent": UA})
            if r.status_code == 200 and r.text.strip():
                text = r.text.strip()
                if text.startswith("<?xml") or "<data>" in text[:200]:
                    match = re.search(r"<!\[CDATA\[(.*?)\]\]>", text, re.DOTALL)
                    if match:
                        return match.group(1).strip()
                elif len(text) > 10 and any(c in text for c in ["[0", "[1", "[2", "[3", "[4", "[5"]):
                    return text
        except Exception:
            pass
    return None


def fetch_lrc_netease(title, artist="", session=None, timeout=10):
    """从网易云音乐公开 API 获取 LRC 歌词 (无 API Key)。"""
    sess = session or requests.Session()
    try:
        search_url = "https://music.163.com/api/search/get/web"
        params = {"s": title, "type": 1, "limit": 20, "csrf_token": ""}
        r = sess.get(search_url, params=params, timeout=timeout,
                     headers={"User-Agent": UA, "Referer": "https://music.163.com/"})
        data = r.json()
        songs = (data.get("result") or {}).get("songs") or []
    except Exception:
        return None
    if not songs:
        return None
    tl = title.strip().lower()
    candidates = {}   # id -> 分数
    for song in songs:
        name = (song.get("name") or "").strip().lower()
        artists = " ".join(a.get("name", "") for a in (song.get("artists") or []))
        score = 0
        if name == tl:
            score += 2
        elif tl in name:
            score += 1
        if artist and artist.lower() in artists.lower():
            score += 2
        if song.get("id") and (score not in candidates or score > 0):
            candidates[song["id"]] = max(candidates.get(song["id"], 0), score)
    best_id = max(candidates, key=candidates.get) if candidates else None
    if best_id is None:
        best_id = songs[0]["id"]
    try:
        lrc_url = "https://music.163.com/api/song/lyric"
        r2 = sess.get(lrc_url, params={"id": best_id, "lv": 1, "tv": 0},
                       timeout=timeout,
                       headers={"User-Agent": UA, "Referer": "https://music.163.com/"})
        lrc_data = r2.json()
        lrc = (lrc_data.get("lrc") or {}).get("lyric")
        return lrc if lrc and len(lrc.strip()) > 10 else None
    except Exception:
        return None


def fetch_lrc_qq(title, artist="", session=None, timeout=10):
    """从 QQ 音乐公开接口获取 LRC 歌词 (无需登录)。返回完整 LRC。"""
    sess = session or requests.Session()
    headers = {"Referer": "https://y.qq.com/", "User-Agent": UA}
    key = ("%s %s" % (artist, title)) if artist else title
    try:
        r = sess.get("https://c.y.qq.com/soso/fcgi-bin/client_search_cp",
                     params={"w": key, "format": "json", "p": 1, "n": 10,
                             "t": 0, "aggr": 1, "lossless": 0, "cr": 1,
                             "g_tk": 5381},
                     headers=headers, timeout=timeout)
        songs = ((r.json().get("data") or {}).get("song") or {}).get("list") or []
    except Exception:
        return None
    if not songs:
        return None
    beta = None
    tl = title.strip().lower()
    for s in songs:
        name = (s.get("songname") or "").strip().lower()
        singers = "".join(x.get("name", "") for x in (s.get("singer") or []))
        if tl and name == tl and (not artist or artist.lower() in singers.lower()):
            beta = s.get("songmid")
            break
        if beta is None and tl and tl in name and \
                (not artist or artist.lower() in singers.lower()):
            beta = s.get("songmid")
    if beta is None:
        beta = songs[0].get("songmid")
    if not beta:
        return None
    import base64 as _b64
    import time as _t
    try:
        rl = sess.get("https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg",
                      params={"format": "json", "songmid": beta, "_": 1,
                              "pcachetime": int(_t.time()), "g_tk": 5381},
                      headers=headers, timeout=timeout)
        d = rl.json()
        lyr = d.get("lyric")
        if not lyr:
            return None
        text = _b64.b64decode(lyr).decode("utf-8")
        return text if len(text.strip()) > 10 else None
    except Exception:
        return None


def fetch_lyrics(rid, title="", artist="", session=None, timeout=10):
    """多源获取歌词: 酷我 → QQ音乐 → 网易云。返回 LRC 文本或 None。"""
    for fn in (lambda: fetch_lrc_kuwo(rid, session=session, timeout=timeout),
               lambda: fetch_lrc_qq(title, artist, session=session,
                                    timeout=timeout),
               lambda: fetch_lrc_netease(title, artist, session=session,
                                         timeout=timeout)):
        try:
            lrc = fn()
        except Exception:  # noqa: BLE001
            lrc = None
        if lrc:
            return lrc
    return None


# ============================================================ .lrc 保存
def save_lrc(mp3_path, lrc_text):
    """在 mp3 同目录保存同名 .lrc 文件。"""
    if not lrc_text:
        return None
    base = os.path.splitext(mp3_path)[0]
    lrc_path = base + ".lrc"
    try:
        with open(lrc_path, "w", encoding="utf-8") as f:
            f.write(lrc_text)
        return lrc_path
    except Exception:
        return None


def lrc_to_plain(lrc_text):
    """LRC → 纯文本 (去掉时间标签/元数据行, 每句一行)。用于 USLT 嵌入。"""
    if not lrc_text:
        return ""
    lines = []
    for line in lrc_text.splitlines():
        s = re.sub(r"^\[[\d:.]+\]", "", line.strip()).strip()
        if not s or re.match(r"\[(ti|ar|al|by|offset|length|total):", s,
                             re.I):
            continue                      # 跳过空行与 [ti:]/[ar:] 等元数据行
        if s not in lines:
            lines.append(s)
    return "\n".join(lines) if lines else lrc_text.strip()


# ============================================================ LRC 解析 (歌词面板)
def parse_lrc(lrc_text):
    """LRC → 排序后的 [(ms, text), ...] 列表, 供歌词面板逐句定位。

    支持标准 LRC 时间标签 [mm:ss.xx]，同句多时间标签取最早值。
    """
    if not lrc_text:
        return []
    out = []
    for line in lrc_text.splitlines():
        times = []
        rest = line
        for m in re.finditer(r"\[(\d{1,3}):(\d{2})(?:\.(\d{1,3}))?\]", line):
            minute = int(m.group(1))
            sec = int(m.group(2))
            ms_str = (m.group(3) or "0").ljust(3, "0")[:3]
            ms = minute * 60000 + sec * 1000 + int(ms_str)
            times.append(ms)
            rest = rest[m.end():]
        text = rest.strip()
        if text:
            for t in times:
                out.append((t, text))
    out.sort(key=lambda x: x[0])
    # 合并同时间同文本的重复行
    dedup = []
    for t, txt in out:
        if not dedup or dedup[-1][0] != t or dedup[-1][1] != txt:
            dedup.append((t, txt))
    return dedup


# ============================================================ MP3 元数据 (纯 Python)
def _decode_id3_text(fdata):
    """解码 ID3v2 文本帧 body → str。"""
    if not fdata:
        return ""
    enc = fdata[0]
    raw = fdata[1:]
    try:
        if enc == 0:
            return raw.decode("latin-1").split("\x00")[0].strip()
        if enc == 1:
            return raw.decode("utf-16").split("\x00")[0].strip()
        if enc == 2:
            return raw.decode("utf-16-be").split("\x00")[0].strip()
        return raw.decode("utf-8", errors="replace").split("\x00")[0].strip()
    except Exception:  # noqa: BLE001
        try:
            return raw.decode("utf-8", errors="replace").split("\x00")[0].strip()
        except Exception:  # noqa: BLE001
            return ""


def read_id3_tags(path):
    """纯 Python 读取 ID3v2 标题/歌手, 返回 (title, artist)。无标签返回 ("","")。"""
    title = artist = ""
    try:
        with open(path, "rb") as f:
            header = f.read(10)
            if len(header) < 10 or header[:3] != b"ID3":
                return "", ""
            ver = header[3]
            size = _syncsafe_decode(header[6:10])
            tag_data = f.read(size)
        frames, _ = _parse_frames(tag_data, ver)
        for fid, _fs, _ff, fdata in frames:
            if fid == b"TIT2":
                title = _decode_id3_text(fdata)
            elif fid == b"TPE1":
                artist = _decode_id3_text(fdata)
        return title, artist
    except Exception:  # noqa: BLE001
        return "", ""


_V1L3_BITRATE = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224,
                 256, 320, 0]
_V2L3_BITRATE = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144,
                 160, 0]
_SR = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000],
       0: [11025, 12000, 8000]}


def mp3_duration(path):
    """纯 Python 估算 MP3 时长 (秒)。支持 ID3v2 跳过与 Xing/Info VBR 帧数。"""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            data = f.read(10)
            start = 0
            if len(data) >= 10 and data[:3] == b"ID3":
                start = 10 + _syncsafe_decode(data[6:10])
            f.seek(start)
            buf = f.read(4096)
        if len(buf) < 4:
            return 0.0
        i = 0
        while i < len(buf) - 4:
            if buf[i] == 0xFF and (buf[i + 1] & 0xE0) == 0xE0:
                break
            i += 1
        if i >= len(buf) - 4:
            return 0.0
        h = buf[i:i + 4]
        ver_bits = (h[1] >> 3) & 0x03        # 3=MPEG1, 2=MPEG2, 0=MPEG2.5
        layer_bits = (h[1] >> 1) & 0x03
        br_idx = (h[2] >> 4) & 0x0F
        sr_idx = (h[2] >> 2) & 0x03
        padding = (h[2] >> 1) & 0x01
        channel = (h[3] >> 6) & 0x03
        if ver_bits == 1 or layer_bits != 1 or br_idx in (0, 15) or sr_idx == 3:
            return 0.0
        if ver_bits == 3:                    # MPEG1 Layer III
            bitrate = _V1L3_BITRATE[br_idx] * 1000
            spf, sr = 1152, _SR[3][sr_idx]
            side = 17 if channel == 3 else 32
            flen = 144 * bitrate // sr + padding
        else:                                # MPEG2 / 2.5 Layer III
            bitrate = _V2L3_BITRATE[br_idx] * 1000
            spf, sr = 576, _SR[ver_bits][sr_idx]
            side = 9 if channel == 3 else 17
            flen = 72 * bitrate // sr + padding
        if not bitrate or not sr or flen <= 4:
            return 0.0
        # Xing/Info VBR 头: 帧头 4 + 可选 CRC 2 + side info
        off = i + 4 + side
        if i + 4 + side + 12 <= len(buf):
            tag = buf[off:off + 4]
            if tag in (b"Xing", b"Info"):
                flags = int.from_bytes(buf[off + 4:off + 8], "big")
                if flags & 0x01:
                    frames = int.from_bytes(buf[off + 8:off + 12], "big")
                    if frames > 0:
                        return frames * spf / float(sr)
        audio_bytes = max(0, size - start)
        return audio_bytes * 8.0 / bitrate
    except Exception:  # noqa: BLE001
        return 0.0


def read_meta(path):
    """读取 (标题, 歌手, 时长秒): 优先 ID3 标签; 时长由 MP3 帧估算。"""
    title, artist = read_id3_tags(path)
    dur = mp3_duration(path)
    return title, artist, dur
