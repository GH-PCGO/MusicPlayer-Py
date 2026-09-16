# -*- coding: utf-8 -*-
"""核心纯逻辑单元测试 (无需网络 / 显示)。

运行: pytest  或  python -m pytest tests
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from musicplayer.lyrics import (  # noqa: E402
    _syncsafe_encode, _syncsafe_decode, parse_lrc, lrc_to_plain)
from musicplayer.util import split_artists  # noqa: E402


def test_syncsafe_roundtrip():
    for n in (0, 1, 127, 128, 445, 940, 100000, 0x0FFFFFFF):
        assert _syncsafe_decode(_syncsafe_encode(n)) == n


def test_syncsafe_encode_bytes():
    assert _syncsafe_encode(940) == bytes([0, 0, 7, 44])


def test_parse_lrc_basic():
    lrc = "[00:10.00]第一行\n[00:14.50]第二行\n[00:18.00]第三行\n"
    pairs = parse_lrc(lrc)
    assert [t for t, _ in pairs] == [10000, 14500, 18000]
    assert [s for _, s in pairs] == ["第一行", "第二行", "第三行"]


def test_parse_lrc_multi_timestamp_and_meta():
    lrc = "[ti:歌名]\n[ar:歌手]\n[00:01.00][00:05.00]重复行\n"
    pairs = parse_lrc(lrc)
    assert pairs == [(1000, "重复行"), (5000, "重复行")]


def test_lrc_to_plain_strips_meta():
    lrc = "[ti:七里香]\n[ar:周杰伦]\n[00:06.00]窗外的麻雀\n[00:10.00]雨下整夜\n"
    plain = lrc_to_plain(lrc)
    lines = plain.splitlines()
    assert lines == ["窗外的麻雀", "雨下整夜"]


def test_split_artists():
    assert split_artists("We Talk\u300b 陈奕迅") == ["We Talk", "陈奕迅"]
    assert split_artists("陈奕迅&王菲") == ["陈奕迅", "王菲"]
    assert split_artists("周杰伦") == ["周杰伦"]
    assert split_artists("") == []
    assert split_artists("A / B / A") == ["A", "B"]


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print("  [PASS]", fn.__name__)
        except Exception:
            failed += 1
            print("  [FAIL]", fn.__name__)
            traceback.print_exc()
    print("TESTS-OK" if not failed else "%d TEST(S) FAILED" % failed)
    sys.exit(1 if failed else 0)
