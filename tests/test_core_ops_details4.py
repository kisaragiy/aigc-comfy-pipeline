# -*- coding: utf-8 -*-
"""生图细节第四轮：批量inpaint / img2img保脸 / 循环扩图 / 触发词 / 参数记录"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_batch_inpaint_requires_area():
    """批量 inpaint 需要统一区域"""
    from workshop.inpaint import batch_inpaint
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(ValueError):
            batch_inpaint(d, "测试", area=None, box=None)


def test_batch_inpaint_empty_dir(tmp_path):
    """批量 inpaint 空目录 → 空结果"""
    from workshop.inpaint import batch_inpaint
    r = batch_inpaint(str(tmp_path), "测试", area="眼睛")
    assert r == []


def test_img2img_faceid_flag():
    """img2img 支持 faceid 保脸"""
    from workshop.img2img import img2img
    import inspect
    assert "faceid" in inspect.signature(img2img).parameters


def test_outpaint_iterations_flag():
    """outpaint 支持循环扩图"""
    from workshop.outpaint import outpaint
    import inspect
    assert "iterations" in inspect.signature(outpaint).parameters


def test_interrogate_lora_hint_flag():
    """反推支持 LoRA 触发词检测"""
    from workshop.interrogate import main
    import inspect
    assert "lora_hint" in inspect.getsource(main)


def test_img2img_save_params(tmp_path):
    """img2img 保存参数记录（不实际生成——只测 helper）"""
    from workshop.img2img import _save_params
    import json
    _save_params(tmp_path, {'op': 'img2img', 'denoise': 0.6, 'seeds': [1, 2]})
    p = tmp_path / 'params.json'
    assert p.exists()
    data = json.loads(p.read_text(encoding='utf-8'))
    assert data['denoise'] == 0.6
    assert data['seeds'] == [1, 2]
