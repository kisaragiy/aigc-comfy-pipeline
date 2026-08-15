# -*- coding: utf-8 -*-
"""第五轮场景测试：idphoto / outfit / colorize"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_idphoto_colors():
    """证件照底色标准"""
    from workshop.idphoto import BG_COLORS
    assert "white" in BG_COLORS and "blue" in BG_COLORS and "red" in BG_COLORS
    # 标准证件蓝
    assert BG_COLORS["blue"] == (67, 142, 219)


def test_idphoto_sizes():
    """证件照规格"""
    from workshop.idphoto import SIZES
    w, h = SIZES["1inch"]
    assert (w, h) == (295, 413)  # 一寸标准


def test_idphoto_bbox():
    """人像 bbox 检测（非零区域）"""
    from workshop.idphoto import _person_bbox
    from PIL import Image
    import numpy as np
    img = Image.new("L", (100, 100), 0)
    arr = np.asarray(img).copy()  # 可写副本
    arr[20:60, 30:70] = 255  # 人像区域
    img = Image.fromarray(arr)
    tmp = Path(__file__).parent / "tmp_bbox.png"
    img.save(tmp)
    bbox = _person_bbox(str(tmp))
    tmp.unlink()
    assert bbox is not None
    min_x, min_y, max_x, max_y = bbox
    # 切片 [30:70] 的排他边界 → max 是 69，用容差
    assert min_x <= 30 and max_x >= 68 and min_y <= 20 and max_y >= 58


def test_idphoto_bbox_empty():
    """无人像 → None"""
    from workshop.idphoto import _person_bbox
    from PIL import Image
    img = Image.new("L", (50, 50), 0)
    tmp = Path(__file__).parent / "tmp_bbox2.png"
    img.save(tmp)
    assert _person_bbox(str(tmp)) is None
    tmp.unlink()


def test_outfit_model_prompts():
    """服装模特 prompt 完整"""
    from workshop.outfit import MODEL_PROMPTS
    assert "female" in MODEL_PROMPTS and "male" in MODEL_PROMPTS
    assert "modeling the outfit" in MODEL_PROMPTS["female"]


def test_colorize_uses_canny(tmp_path):
    """线稿上色用 Canny ControlNet"""
    from workshop.colorize import _build_colorize_wf
    from PIL import Image as PILImage
    # 真实临时图（读尺寸用）
    img = PILImage.new("RGB", (512, 512), (255, 255, 255))
    f = tmp_path / "lineart.png"
    img.save(f)
    wf = _build_colorize_wf(f.name, "prompt", "neg", 123)
    # 应有 Canny 节点和 ControlNetApply
    class_types = [v['class_type'] for v in wf.values()]
    assert "Canny" in class_types
    assert "ControlNetApply" in class_types
