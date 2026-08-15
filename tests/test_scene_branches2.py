# -*- coding: utf-8 -*-
"""DFS 细节第二轮：印刷规格 / 证件照换装 / multi 参考图 / 漫画边框"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_merch_print_mode(tmp_path):
    """merch 印刷模式：出血线 + CMYK"""
    from workshop.merch import generate_merch
    import inspect
    src = inspect.getsource(generate_merch)
    assert "print_mode" in src
    assert "CMYK" in src
    assert "bleed" in src


def test_idphoto_outfit_flag():
    """idphoto 支持 outfit 换装"""
    from workshop.idphoto import idphoto
    import inspect
    assert "outfit" in inspect.signature(idphoto).parameters


def test_multi_ref_flags():
    """multi 支持 ref_a/ref_b 参考图"""
    from workshop.wallpaper import generate_multi
    import inspect
    params = inspect.signature(generate_multi).parameters
    assert "ref_a" in params
    assert "ref_b" in params


def test_border_styles():
    """漫画边框 3 样式"""
    from workshop.manga.manga import BORDER_STYLES
    assert "sharp" in BORDER_STYLES
    assert "round" in BORDER_STYLES
    assert "slash" in BORDER_STYLES


def test_border_draws(tmp_path):
    """边框绘制不遮内容（画布非全黑）"""
    from workshop.manga.manga import _draw_panel_border
    from PIL import Image
    img = Image.new("RGB", (300, 300), (255, 255, 255))
    # 先画个黑方块当内容
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    d.rectangle([50, 50, 150, 150], fill=(100, 100, 100))
    _draw_panel_border(img, 0, 0, 300, 300, "round")
    # 内容区域仍可见（非纯白/纯黑）
    px = img.getpixel((100, 100))
    assert px != (255, 255, 255)
    assert px != (0, 0, 0)
    # 边框区域有黑线
    assert img.getpixel((10, 150)) == (0, 0, 0)
