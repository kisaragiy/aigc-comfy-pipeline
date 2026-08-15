# -*- coding: utf-8 -*-
"""生图细节第二轮：反推闭环/批量 / 对比图 / inpaint 多区域 / outpaint 平铺 / blend 角色融合"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_interrogate_recreate_flag():
    """反推支持 --recreate 闭环"""
    from workshop.interrogate import main
    import inspect
    assert "recreate" in inspect.getsource(main)


def test_interrogate_batch(tmp_path):
    """批量反推（无图片 → 空结果）"""
    from workshop.interrogate import batch_interrogate
    r = batch_interrogate(str(tmp_path), fmt='sdxl')
    assert r == {}
    # prompts.txt 不应生成（无图）
    assert not (tmp_path / "prompts.txt").exists()


def test_compare_horizontal(tmp_path):
    """对比图（左右排）"""
    from workshop.compare import make_compare
    from PIL import Image
    a = Image.new("RGB", (100, 80), (255, 0, 0))
    b = Image.new("RGB", (120, 80), (0, 0, 255))
    pa, pb = tmp_path / "a.png", tmp_path / "b.png"
    a.save(pa); b.save(pb)
    out = tmp_path / "cmp.png"
    make_compare(str(pa), str(pb), output=str(out))
    img = Image.open(out)
    # 左右排：宽 = 100+120+6，高 = 80+40(标签)
    assert img.width == 226
    assert img.height == 120


def test_compare_vertical(tmp_path):
    """对比图（上下排）"""
    from workshop.compare import make_compare
    from PIL import Image
    a = Image.new("RGB", (100, 80), (255, 0, 0))
    b = Image.new("RGB", (100, 60), (0, 0, 255))
    pa, pb = tmp_path / "a.png", tmp_path / "b.png"
    a.save(pa); b.save(pb)
    out = tmp_path / "cmp_v.png"
    make_compare(str(pa), str(pb), output=str(out), vertical=True)
    img = Image.open(out)
    assert img.width == 100
    assert img.height == 80 + 60 + 40 + 6


def test_inpaint_multi_areas_flag():
    """inpaint 支持多区域 + 对比图"""
    from workshop.inpaint import inpaint
    import inspect
    src = inspect.getsource(inpaint)
    assert "areas" in src
    assert "compare" in src


def test_outpaint_tile_flag():
    """outpaint 支持 tile 平铺"""
    from workshop.outpaint import outpaint
    import inspect
    assert "tile" in inspect.signature(outpaint).parameters


def test_blend_char_fusion():
    """blend 角色融合（缺图报错）"""
    from workshop.blend import blend_images
    with pytest.raises(FileNotFoundError):
        blend_images("a.png", "b.png", char_face="C:/nope.png", char_outfit="C:/nope2.png")
