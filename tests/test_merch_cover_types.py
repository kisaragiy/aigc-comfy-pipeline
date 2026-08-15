# -*- coding: utf-8 -*-
"""N1-N3 新增场景测试：cover 多类型 / merch 周边"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_cover_types_exist():
    """cover 支持 video/live/novel 三类型"""
    from workshop.cover import COVER_TYPES
    assert "video" in COVER_TYPES and "live" in COVER_TYPES and "novel" in COVER_TYPES


def test_cover_novel_vertical():
    """小说封面 2:3 竖版"""
    from workshop.cover import COVER_TYPES
    w, h, style = COVER_TYPES["novel"]
    assert h > w  # 竖版
    assert "vertical" in style


def test_cover_live_widescreen():
    """直播封面 16:9 横版"""
    from workshop.cover import COVER_TYPES
    w, h, style = COVER_TYPES["live"]
    assert w > h  # 横版


def test_merch_types_exist():
    """merch 支持 sticker/badge/standee/postcard"""
    from workshop.merch import MERCH_TYPES
    for t in ["sticker", "badge", "standee", "postcard"]:
        assert t in MERCH_TYPES, f"缺 {t}"


def test_merch_standee_vertical():
    """立牌 3:4 竖版（全身角色）"""
    from workshop.merch import MERCH_TYPES
    w, h, _ = MERCH_TYPES["standee"]
    assert h > w


def test_transparent_bg_white_to_alpha(tmp_path):
    """白色背景转透明"""
    from workshop.merch import _make_transparent_bg
    from PIL import Image
    # 白底图 + 彩色中心
    img = Image.new("RGB", (100, 100), (255, 255, 255))
    for y in range(30, 70):
        for x in range(30, 70):
            img.putpixel((x, y), (255, 0, 0))
    src = tmp_path / "src.png"
    out = tmp_path / "out.png"
    img.save(src)
    _make_transparent_bg(str(src), str(out))
    out_img = Image.open(out).convert("RGBA")
    # 角落透明
    assert out_img.getpixel((5, 5))[3] == 0
    # 中心不透明
    assert out_img.getpixel((50, 50))[3] == 255
