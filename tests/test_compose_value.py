# -*- coding: utf-8 -*-
"""M1 黑白光影稿（value study）测试"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workshop.compose import _value_study


@pytest.fixture
def sample_image():
    """生成一张测试图（渐变，有明暗结构）"""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (64, 64), (200, 200, 200))
    d = ImageDraw.Draw(img)
    d.rectangle([8, 8, 24, 24], fill=(30, 30, 30))     # 暗部
    d.rectangle([40, 40, 56, 56], fill=(240, 240, 240))  # 亮部
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img.save(f.name)
        return f.name


def test_value_study_creates_grayscale(sample_image):
    """光影稿应生成且为灰度图"""
    out = tempfile.mkdtemp()
    files = _value_study(sample_image, Path(out))
    assert len(files) == 1
    assert os.path.exists(files[0])

    from PIL import Image
    img = Image.open(files[0])
    assert img.mode == "L"  # 灰度


def test_value_study_contrast_changes(sample_image):
    """对比度参数应影响输出（默认 1.15 vs 0.5）"""
    out1, out2 = tempfile.mkdtemp(), tempfile.mkdtemp()
    f1 = _value_study(sample_image, Path(out1), contrast=1.15)[0]
    f2 = _value_study(sample_image, Path(out2), contrast=0.5)[0]

    from PIL import Image
    import numpy as np
    a1 = np.asarray(Image.open(f1).convert("L"), dtype=int)
    a2 = np.asarray(Image.open(f2).convert("L"), dtype=int)
    # 高对比 → 暗部更暗、亮部更亮（方差更大）
    assert a1.std() > a2.std()


def test_value_study_brightness(sample_image):
    """亮度参数应生效"""
    out1, out2 = tempfile.mkdtemp(), tempfile.mkdtemp()
    f1 = _value_study(sample_image, Path(out1), bright=0.0)[0]
    f2 = _value_study(sample_image, Path(out2), bright=0.5)[0]

    from PIL import Image
    import numpy as np
    m1 = np.asarray(Image.open(f1).convert("L"), dtype=int).mean()
    m2 = np.asarray(Image.open(f2).convert("L"), dtype=int).mean()
    assert m2 > m1  # 更亮
