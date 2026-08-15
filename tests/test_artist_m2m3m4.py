# -*- coding: utf-8 -*-
"""M2/M3/M4 画师工作流测试：倒置镜像检查 + 焦点引导 + 色彩统一"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workshop.finalcheck import _flip_variants
from workshop.colorgrade import colorgrade, _blend


@pytest.fixture
def sample_image():
    """偏色测试图（R 通道偏弱）"""
    from PIL import Image

    img = Image.new("RGB", (64, 64), (100, 200, 200))  # R 弱 G/B 强
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img.save(f.name)
        return f.name


def test_flip_variants_count(sample_image):
    """倒置/镜像变体应生成 2 张（base64）"""
    variants = _flip_variants(sample_image)
    assert len(variants) == 2


def test_flip_variants_are_valid_png(sample_image):
    """变体应为可解码 PNG"""
    import base64, io
    from PIL import Image

    for v in _flip_variants(sample_image):
        img = Image.open(io.BytesIO(base64.b64decode(v)))
        assert img.mode in ("RGB", "RGBA", "L")
        assert img.width == 64


def test_colorgrade_white_balance(sample_image):
    """自动白平衡应拉平偏色（R 增益 > 1，spread 变小）"""
    out = tempfile.mkdtemp()
    files = colorgrade(sample_image, output=str(Path(out) / "graded.png"))
    assert len(files) == 1 and os.path.exists(files[0])

    from PIL import Image, ImageStat
    orig = ImageStat.Stat(Image.open(sample_image).convert("RGB")).mean
    img = Image.open(files[0]).convert("RGB")
    graded = ImageStat.Stat(img).mean
    # 白平衡后 RGB spread 应变小（strength=0.5 半量：spread 减半）
    assert max(graded) - min(graded) < max(orig) - min(orig), \
        f"白平衡未生效: {orig} → {graded}"


def test_colorgrade_warm_shifts_red(sample_image):
    """暖色温应增强 R 通道"""
    out = tempfile.mkdtemp()
    f1 = colorgrade(sample_image, warm=0.3, output=str(Path(out) / "warm.png"))[0]
    f2 = colorgrade(sample_image, warm=None, output=str(Path(out) / "auto.png"))[0]

    from PIL import Image, ImageStat
    r1 = ImageStat.Stat(Image.open(f1).convert("RGB")).mean[0]
    r2 = ImageStat.Stat(Image.open(f2).convert("RGB")).mean[0]
    assert r1 > r2  # 暖色温 R 更高


def test_blend_interpolation():
    """插值函数：0=原图，1=全量"""
    assert _blend(100, 200, 0) == 100
    assert _blend(100, 200, 1) == 200
    assert _blend(100, 200, 0.5) == 150
