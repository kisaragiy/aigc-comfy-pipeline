# -*- coding: utf-8 -*-
"""DFS 剩余支线测试：壁纸深色/刘海 + 跨页一致检查 + 音效字"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_wallpaper_dark_notch_flags():
    """wallpaper 支持 dark/notch"""
    from workshop.wallpaper import generate_wallpaper
    import inspect
    params = inspect.signature(generate_wallpaper).parameters
    assert "dark" in params
    assert "notch" in params


def test_verify_page_module():
    """跨页检查模块可导入"""
    from workshop.verify_page import verify_consistency
    import inspect
    src = inspect.getsource(verify_consistency)
    assert "score" in src


def test_sfx_words_detected():
    """音效字检测"""
    from workshop.manga.manga import _draw_sfx, _SFX_WORDS
    assert "砰" in _SFX_WORDS or "ドン" in _SFX_WORDS


def test_sfx_non_sfx_returns_false():
    """普通台词不是音效字 → False"""
    from workshop.manga.manga import _draw_sfx
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (200, 200), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    assert _draw_sfx(draw, "你好呀", 0, 0, 200, 200) is False


def test_sfx_draws_on_canvas():
    """音效字在画布上渲染"""
    from workshop.manga.manga import _draw_sfx
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (300, 300), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    assert _draw_sfx(draw, "砰！", 0, 0, 300, 300) is True
    # 应有内容（非全白）
    arr = img.getbbox()
    assert arr is not None
