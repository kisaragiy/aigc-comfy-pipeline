# -*- coding: utf-8 -*-
"""生图细节第八轮：restore 组合 / 批量背景替换 / 批量信息 / 批量对比"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_restore_combo_scratch_upscale(tmp_path):
    """restore 组合：划痕+超分同时用"""
    from workshop.restore import restore_photo
    from PIL import Image
    img = Image.new("L", (40, 40), 128)
    src = tmp_path / "s.png"
    img.save(src)
    out = tmp_path / "o.png"
    restore_photo(str(src), output=str(out), scratch=True, upscale=2)
    assert os.path.exists(out)
    r = Image.open(out)
    # 划痕(40) → 超分2x(80)
    assert r.size == (80, 80)


def test_restore_combo_color_upscale(tmp_path):
    """restore 组合：上色+超分"""
    from workshop.restore import restore_photo
    from PIL import Image
    img = Image.new("L", (30, 30), 100)
    src = tmp_path / "s.png"
    img.save(src)
    out = tmp_path / "o.png"
    restore_photo(str(src), output=str(out), color=True, upscale=2)
    assert os.path.exists(out)
    r = Image.open(out)
    assert r.size == (60, 60)
    assert r.mode == "RGB"  # 上色后 RGB


def test_bg_replace_batch_empty(tmp_path):
    """批量背景替换空目录 → 空结果"""
    from workshop.bg_replace import batch_bg_replace
    assert batch_bg_replace(str(tmp_path), "海边") == []


def test_info_batch(tmp_path):
    """批量图片信息"""
    from workshop.info import batch_info
    from PIL import Image
    Image.new("RGB", (10, 10)).save(str(tmp_path / "a.png"))
    rows = batch_info(str(tmp_path))
    assert len(rows) == 1
    assert rows[0][1] == "10x10"


def test_compare_batch_empty(tmp_path):
    """批量对比空目录 → 空结果"""
    from workshop.compare import batch_compare
    d2 = tmp_path / "b"
    d2.mkdir()
    assert batch_compare(str(tmp_path), str(d2)) == []


def test_compare_batch_works(tmp_path):
    """批量对比（2 对）"""
    from workshop.compare import batch_compare
    from PIL import Image
    d1 = tmp_path / "a"; d1.mkdir()
    d2 = tmp_path / "b"; d2.mkdir()
    for i in range(2):
        Image.new("RGB", (50, 40), (255, 0, 0)).save(str(d1 / f"i{i}.png"))
        Image.new("RGB", (50, 40), (0, 0, 255)).save(str(d2 / f"i{i}.png"))
    out = tmp_path / "out"
    saved = batch_compare(str(d1), str(d2), output_dir=str(out))
    assert len(saved) == 2
    for p in saved:
        assert os.path.exists(p)
