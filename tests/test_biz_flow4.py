# -*- coding: utf-8 -*-
"""商业图细节第四轮：批量文字/多行换行/海报模板/banner模板/VI扩展"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_biztext_batch_empty(tmp_path):
    """批量文字合成空目录 → 空结果"""
    from workshop.biztext import batch_add_text
    assert batch_add_text(str(tmp_path), "标题") == []


def test_biztext_wrap():
    """多行自动换行"""
    from workshop.biztext import _wrap_text
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (400, 100))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 40)
    lines = _wrap_text(draw, "这是一个很长很长很长很长很长的标题", font, 200)
    assert len(lines) >= 2


def test_biztext_batch_works(tmp_path):
    """批量文字合成（2 张）"""
    from workshop.biztext import batch_add_text
    from PIL import Image
    d = tmp_path / "imgs"; d.mkdir()
    for i in range(2):
        Image.new("RGB", (300, 200), (30, 40, 60)).save(str(d / f"i{i}.png"))
    out = tmp_path / "out"
    saved = batch_add_text(str(d), "系列标题", output_dir=str(out))
    assert len(saved) == 2
    for p in saved:
        assert os.path.exists(p)


def test_poster_templates():
    """海报模板 5 种"""
    from workshop.biz import POSTER_TEMPLATES
    for t in ("new_product", "recruit", "festival", "event", "thank"):
        assert t in POSTER_TEMPLATES


def test_banner_templates():
    """Banner 模板 4 种"""
    from workshop.biz import BANNER_TEMPLATES
    for t in ("sale", "new", "brand", "holiday"):
        assert t in BANNER_TEMPLATES


def test_vi_six_items():
    """VI 6 件套"""
    from workshop.biz import brand_vi
    import inspect
    src = inspect.getsource(brand_vi)
    for t in ("banner", "social"):
        assert t in src
