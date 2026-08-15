# -*- coding: utf-8 -*-
"""生图细节第五轮：批量风格化 / 目标尺寸扩图 / 反向重绘 / 组合管线"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_batch_stylize_empty(tmp_path):
    """批量风格化空目录 → 空结果"""
    from workshop.stylize import batch_stylize
    r = batch_stylize(str(tmp_path), "C:/style.png")
    assert r == []


def test_outpaint_target_size(tmp_path):
    """目标尺寸扩图（自动计算扩展量）"""
    from workshop.outpaint import outpaint
    import inspect
    assert "target_w" in inspect.signature(outpaint).parameters
    assert "target_h" in inspect.signature(outpaint).parameters


def test_inpaint_invert_wf():
    """反向重绘工作流含 InvertMask"""
    from workshop.inpaint import _build_inpaint_wf
    wf = _build_inpaint_wf("x.png", "m.png", "p", "n", 42, invert=True)
    types = [v['class_type'] for v in wf.values()]
    assert "InvertMask" in types
    # SetLatentNoiseMask 的 mask 指向 InvertMask 输出
    slnm = [v for v in wf.values() if v['class_type'] == 'SetLatentNoiseMask'][0]
    assert slnm['inputs']['mask'] == ['15', 0]


def test_inpaint_no_invert():
    """非反向：无 InvertMask"""
    from workshop.inpaint import _build_inpaint_wf
    wf = _build_inpaint_wf("x.png", "m.png", "p", "n", 42, invert=False)
    types = [v['class_type'] for v in wf.values()]
    assert "InvertMask" not in types


def test_img2img_pipeline_flag():
    """img2img 支持 --pipeline 组合管线"""
    from workshop.img2img import pipeline
    import inspect
    params = inspect.signature(pipeline).parameters
    assert "edit_desc" in params
    assert "compare" in params
