# -*- coding: utf-8 -*-
"""生图细节第三轮：风格迁移 / 批量img2img / mask羽化 / 渐变融合 / 反推编辑"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_stylize_module():
    """风格迁移模块可导入"""
    from workshop.stylize import stylize
    import inspect
    params = inspect.signature(stylize).parameters
    assert "content_image" in params
    assert "style_image" in params


def test_stylize_missing_file():
    """风格迁移缺图报错"""
    from workshop.stylize import stylize
    with pytest.raises(FileNotFoundError):
        stylize("C:/nope.png", "C:/nope2.png")


def test_img2img_batch_flag():
    """img2img 支持批量目录"""
    from workshop.img2img import batch_img2img
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        r = batch_img2img(d, "测试", glob_pattern='*.png')
        assert r == []  # 空目录


def test_inpaint_feather_mask(tmp_path):
    """mask 羽化（边缘渐变）"""
    from workshop.inpaint import _make_box_mask
    from PIL import Image
    img = Image.new("RGB", (200, 200), (0, 0, 0))
    src = tmp_path / "s.png"
    img.save(src)
    out = tmp_path / "m.png"
    _make_box_mask(str(src), (50, 50, 150, 150), str(out), feather=10)
    m = Image.open(out).convert("L")
    # 中心全白
    assert m.getpixel((100, 100)) == 255
    # 边缘渐变（50 边界处应是中间值——羽化后非 0/255）
    edge = m.getpixel((50, 100))
    assert 0 < edge < 255


def test_blend_gradient(tmp_path):
    """渐变融合（左 A 右 B）"""
    from workshop.blend import blend_images
    from PIL import Image
    a = Image.new("RGB", (200, 100), (255, 0, 0))   # 红
    b = Image.new("RGB", (200, 100), (0, 0, 255))   # 蓝
    pa, pb = tmp_path / "a.png", tmp_path / "b.png"
    a.save(pa); b.save(pb)
    out = tmp_path / "g.png"
    results = blend_images(str(pa), str(pb), gradient=True, output=str(out))
    assert results
    img = Image.open(out).convert("RGB")
    # 左边缘偏红（A），右边缘偏蓝（B）
    left = img.getpixel((10, 50))
    right = img.getpixel((190, 50))
    assert left[0] > left[2]  # 左红
    assert right[2] > right[0]  # 右蓝


def test_interrogate_edit_flag():
    """反推支持 edit 修改组合"""
    from workshop.interrogate import main
    import inspect
    src = inspect.getsource(main)
    assert "args.edit" in src
    # recreate 分支也还在
    assert "args.recreate" in src
