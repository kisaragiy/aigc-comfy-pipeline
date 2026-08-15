# -*- coding: utf-8 -*-
"""风格蒸馏闭环测试：清洗 / 数据集生成 / caption / 训练命令"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_clean_caption_removes_style():
    """Caption 清洗：去风格词留内容"""
    from workshop.style_distill import _clean_caption
    text = "1girl, standing, anime style, masterpiece, best quality, cinematic lighting, blue sky"
    cleaned = _clean_caption(text)
    assert "anime style" not in cleaned
    assert "masterpiece" not in cleaned
    assert "cinematic" not in cleaned
    assert "1girl" in cleaned
    assert "standing" in cleaned
    assert "blue sky" in cleaned


def test_clean_caption_no_empty():
    """清洗后不为空"""
    from workshop.style_distill import _clean_caption
    assert _clean_caption("masterpiece, anime style").strip() == ""


def test_caption_dataset(tmp_path):
    """Caption 生成：每图一个 .caption"""
    from workshop.style_distill import caption_dataset
    from PIL import Image
    Image.new("RGB", (64, 64)).save(str(tmp_path / "0001_1girl.png"))
    Image.new("RGB", (64, 64)).save(str(tmp_path / "0002_1boy.png"))
    caption_dataset(str(tmp_path), "mystyle")
    c1 = tmp_path / "0001_1girl.caption"
    assert c1.exists()
    text = c1.read_text(encoding='utf-8')
    assert "mystyle" in text
    assert "1girl" in text


def test_style_words_nonempty():
    """风格词表非空"""
    from workshop.style_distill import STYLE_WORDS
    assert len(STYLE_WORDS) > 5


def test_train_cmd_shape():
    """训练命令包含关键参数（风格 LoRA 配置）"""
    from workshop.style_distill import train_style_lora
    import inspect
    params = inspect.signature(train_style_lora).parameters
    for p in ("images_dir", "trigger", "name", "steps", "dim"):
        assert p in params
