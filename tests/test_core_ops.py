# -*- coding: utf-8 -*-
"""核心生图操作测试：反推 / img2img / inpaint / outpaint / blend"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_interrogate_formats():
    """反推格式模板"""
    from workshop.interrogate import FORMATS
    assert "natural" in FORMATS and "sdxl" in FORMATS and "tag" in FORMATS
    assert "comma-separated" in FORMATS["sdxl"].lower()
    assert "Danbooru" in FORMATS["tag"]


def test_interrogate_missing_file():
    """反推图片不存在 → 报错"""
    from workshop.interrogate import interrogate
    with pytest.raises(FileNotFoundError):
        interrogate("C:/nonexistent.png")


def test_img2img_wf_structure():
    """img2img 工作流含 VAEEncode + denoise"""
    from workshop.img2img import _build_img2img_wf
    wf = _build_img2img_wf("x.png", "prompt", "neg", 42, denoise=0.6)
    types = [v['class_type'] for v in wf.values()]
    assert "VAEEncode" in types
    # KSampler denoise
    sampler = [v for v in wf.values() if v['class_type'] == 'KSampler'][0]
    assert sampler['inputs']['denoise'] == 0.6


def test_inpaint_requires_mask():
    """inpaint 必须给 area 或 box"""
    from workshop.inpaint import inpaint
    # 用存在的文件（否则先报 FileNotFound）
    import tempfile
    from PIL import Image
    f = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    Image.new("RGB", (10, 10)).save(f.name)
    f.close()
    try:
        with pytest.raises(ValueError):
            inpaint(f.name, "改一下", area=None, box=None)
    finally:
        os.unlink(f.name)


def test_inpaint_box_mask(tmp_path):
    """矩形 mask 生成"""
    from workshop.inpaint import _make_box_mask
    from PIL import Image
    img = Image.new("RGB", (200, 200), (0, 0, 0))
    src = tmp_path / "src.png"
    img.save(src)
    out = tmp_path / "mask.png"
    name = _make_box_mask(str(src), (50, 50, 150, 150), str(out))
    assert name == "mask.png"
    m = Image.open(out).convert("L")
    assert m.getpixel((100, 100)) == 255  # 框内白
    assert m.getpixel((10, 10)) == 0      # 框外黑


def test_outpaint_expand_canvas(tmp_path):
    """扩图画布 + mask"""
    from workshop.outpaint import _expand_canvas
    from PIL import Image
    img = Image.new("RGB", (100, 100), (255, 0, 0))
    src = tmp_path / "src.png"
    img.save(src)
    exp, mask, bounds = _expand_canvas(str(src), right=50, bottom=50, out_path=str(tmp_path / "o"))
    assert os.path.exists(exp)
    e = Image.open(exp)
    assert e.size == (150, 150)  # 100+50
    m = Image.open(mask).convert("L")
    assert m.getpixel((125, 50)) == 255  # 右侧扩展区白
    assert m.getpixel((50, 50)) == 0     # 原图区黑


def test_blend_works(tmp_path):
    """图片融合（PIL 混合）"""
    from workshop.blend import blend_images
    from PIL import Image
    a = Image.new("RGB", (100, 100), (255, 0, 0))
    b = Image.new("RGB", (100, 100), (0, 0, 255))
    pa, pb = tmp_path / "a.png", tmp_path / "b.png"
    a.save(pa); b.save(pb)
    out = tmp_path / "blend.png"
    results = blend_images(str(pa), str(pb), weight=0.5, output=str(out))
    assert results
    img = Image.open(out).convert("RGB")
    r, g, bl = img.getpixel((50, 50))
    assert r > 100 and bl > 100  # 红蓝混合 → 紫
