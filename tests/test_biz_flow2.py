# -*- coding: utf-8 -*-
"""商业图细节第二轮：文字合成 / 产品套图 / 多尺寸 / 社交 / 文字门禁"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_biztext_module():
    """文字合成可导入"""
    from workshop.biztext import add_text, POSITIONS
    assert "bottom-center" in POSITIONS
    import inspect
    params = inspect.signature(add_text).parameters
    assert "title" in params and "sub" in params and "font_size" in params


def test_biztext_missing():
    """文字合成缺图报错"""
    from workshop.biztext import add_text
    with pytest.raises(FileNotFoundError):
        add_text("C:/nope.png", "标题")


def test_biztext_works(tmp_path):
    """文字合成实际输出（中文标题）"""
    from workshop.biztext import add_text
    from PIL import Image
    img = Image.new("RGB", (400, 300), (50, 50, 120))
    src = tmp_path / "s.png"
    img.save(src)
    out = tmp_path / "o.png"
    add_text(str(src), "商业图标题", sub="副标题", pos="bottom-center",
             output=str(out))
    assert os.path.exists(out)
    r = Image.open(out)
    assert r.size == (400, 300)


def test_product_shots_complete():
    """产品主图 5 件套规格"""
    from workshop.biz import PRODUCT_SHOTS
    for s in ("white", "scene", "detail", "angle", "size"):
        assert s in PRODUCT_SHOTS


def test_variant_sizes():
    """多尺寸适配 5 规格"""
    from workshop.biz import VARIANT_SIZES
    assert len(VARIANT_SIZES) >= 5
    assert VARIANT_SIZES["cover16x9"][0] / VARIANT_SIZES["cover16x9"][1] == 16 / 9
    assert VARIANT_SIZES["social3x4"][1] > VARIANT_SIZES["social3x4"][0]


def test_make_variants(tmp_path):
    """多尺寸适配实际输出"""
    from workshop.biz import make_variants
    from PIL import Image
    img = Image.new("RGB", (800, 600), (200, 100, 50))
    src = tmp_path / "m.png"
    img.save(src)
    saved = make_variants(str(src), output_dir=str(tmp_path / "v"))
    assert len(saved) == 5
    for p in saved:
        assert os.path.exists(p)


def test_biztext_invalid_pos(tmp_path):
    """非法位置报错"""
    from workshop.biztext import add_text
    from PIL import Image
    img = Image.new("RGB", (50, 50))
    src = tmp_path / "s.png"
    img.save(src)
    with pytest.raises(ValueError):
        add_text(str(src), "标题", pos="nope")
