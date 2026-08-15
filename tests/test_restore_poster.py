# -*- coding: utf-8 -*-
"""第四轮场景测试：poster 海报 + restore 老照片修复"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_cover_poster_type():
    """poster 类型（A4 竖版）"""
    from workshop.cover import COVER_TYPES
    assert "poster" in COVER_TYPES
    w, h, style = COVER_TYPES["poster"]
    assert h > w  # 竖版
    assert "A4" in style or "vertical" in style


def test_cover_subtitle_supported():
    """generate_cover 支持 subtitle 参数"""
    from workshop.cover import generate_cover
    import inspect
    assert "subtitle" in inspect.signature(generate_cover).parameters


def test_restore_basic_works(tmp_path):
    """老照片修复：去噪+锐化+对比度"""
    from workshop.restore import _restore_basic
    from PIL import Image
    # 造一张噪点图
    import random
    img = Image.new("RGB", (200, 200), (120, 120, 120))
    px = img.load()
    for i in range(5000):
        x, y = random.randint(0, 199), random.randint(0, 199)
        v = random.randint(0, 255)
        px[x, y] = (v, v, v)
    src = tmp_path / "noisy.png"
    out = tmp_path / "restored.png"
    img.save(src)
    _restore_basic(str(src), str(out))
    assert out.exists()


def test_restore_color_mode(tmp_path):
    """上色模式（暖色调）"""
    from workshop.restore import _restore_basic
    from PIL import Image
    # 黑白图
    img = Image.new("RGB", (100, 100), (200, 200, 200))
    src = tmp_path / "bw.png"
    out = tmp_path / "colored.png"
    img.save(src)
    _restore_basic(str(src), str(out), color=True)
    assert out.exists()
    # 暖色调 → R 应 >= B（偏暖）
    out_img = Image.open(out).convert("RGB")
    r, g, b = out_img.getpixel((50, 50))
    assert r >= b  # 暖色


def test_restore_upscale(tmp_path):
    """超分 2x"""
    from workshop.restore import _restore_upscale
    from PIL import Image
    img = Image.new("RGB", (100, 100), (100, 100, 100))
    src = tmp_path / "small.png"
    out = tmp_path / "big.png"
    img.save(src)
    _restore_upscale(str(src), str(out), factor=2)
    out_img = Image.open(out)
    assert out_img.size == (200, 200)


def test_restore_missing_file():
    """照片不存在 → 报错"""
    from workshop.restore import restore_photo
    with pytest.raises(FileNotFoundError):
        restore_photo("C:/nonexistent/photo.png")
