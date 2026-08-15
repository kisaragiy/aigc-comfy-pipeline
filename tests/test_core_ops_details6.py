# -*- coding: utf-8 -*-
"""生图细节第六轮：高清修复管线 / 背景替换 / 变体选择 / 去水印 / 批量融合"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_enhance_module():
    """高清修复管线可导入"""
    from workshop.enhance import enhance
    import inspect
    params = inspect.signature(enhance).parameters
    assert "upscale" in params and "face" in params and "compare" in params


def test_enhance_missing_file():
    """高清修复缺图报错"""
    from workshop.enhance import enhance
    with pytest.raises(FileNotFoundError):
        enhance("C:/nope.png")


def test_bg_replace_module():
    """背景替换可导入"""
    from workshop.bg_replace import bg_replace
    import inspect
    params = inspect.signature(bg_replace).parameters
    assert "subject" in params and "compare" in params


def test_bg_replace_missing_file():
    """背景替换缺图报错"""
    from workshop.bg_replace import bg_replace
    with pytest.raises(FileNotFoundError):
        bg_replace("C:/nope.png", "海边")


def test_pick_best_single():
    """变体选择：单张直接返回"""
    from workshop.img2img import pick_best
    assert pick_best(["a.png"], "desc") == "a.png"
    assert pick_best([], "desc") is None


def test_watermark_flag():
    """inpaint 支持 --watermark"""
    from workshop.inpaint import main
    import inspect
    assert "watermark" in inspect.getsource(main)


def test_batch_blend_empty(tmp_path):
    """批量融合空目录 → 空结果"""
    from workshop.blend import batch_blend
    d2 = tmp_path / "b"
    d2.mkdir()
    assert batch_blend(str(tmp_path), str(d2)) == []
