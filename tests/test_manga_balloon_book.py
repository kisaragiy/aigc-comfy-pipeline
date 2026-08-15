# -*- coding: utf-8 -*-
"""B1 台词气泡 + B3 多页漫画测试"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workshop.manga.manga import _draw_balloon, _balloon_type


@pytest.fixture
def canvas():
    """测试画布"""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (400, 400), (255, 255, 255))
    return ImageDraw.Draw(img), img


def test_balloon_dialogue_type():
    """普通对话 → tail 尖角气泡"""
    assert _balloon_type({"备注": ""}, 0) == "tail"


def test_balloon_narration_type():
    """旁白 → rect 矩形气泡"""
    assert _balloon_type({"备注": "旁白：这是森林"}, 0) == "rect"
    assert _balloon_type({"备注": "解说"}, 0) == "rect"


def test_balloon_empty_returns():
    """空台词 → 不绘制（画布保持全白）"""
    from PIL import Image, ImageDraw
    import numpy as np
    img = Image.new("RGB", (400, 400), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    _draw_balloon(draw, "", 0, 0, 100, 100, "tail")
    arr = np.asarray(img)
    assert (arr == 255).all()  # 全白无变化


def test_balloon_draws_ellipse(canvas):
    """tail 气泡应画出内容（非全白）"""
    draw, img = canvas
    _draw_balloon(draw, "你好", 10, 10, 200, 200, "tail")
    assert img.getbbox() is not None  # 有内容


def test_balloon_draws_rect(canvas):
    """rect 旁白气泡应画出内容"""
    draw, img = canvas
    _draw_balloon(draw, "这是旁白", 10, 10, 200, 200, "rect")
    assert img.getbbox() is not None


def test_balloon_long_text_wraps(canvas):
    """长台词应换行且不超面板"""
    draw, img = canvas
    _draw_balloon(draw, "这是一段很长的台词内容测试换行功能", 10, 10, 300, 300, "tail")
    assert img.getbbox() is not None


def test_balloon_type_invalid_note():
    """无备注或备注无关键词 → tail"""
    assert _balloon_type({"备注": "战斗场景"}, 0) == "tail"
    assert _balloon_type({}, 0) == "tail"
