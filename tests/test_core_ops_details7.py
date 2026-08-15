# -*- coding: utf-8 -*-
"""生图细节第七轮：批量修复 / 全景拼接 / 划痕修复 / 图片信息"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_enhance_batch_empty(tmp_path):
    """批量修复空目录 → 空结果"""
    from workshop.enhance import batch_enhance
    assert batch_enhance(str(tmp_path), upscale=2) == []


def test_panorama_requires_2():
    """全景拼接至少 2 张"""
    from workshop.panorama import make_panorama
    with pytest.raises(ValueError):
        make_panorama(["a.png"])


def test_panorama_missing():
    """全景拼接缺图报错"""
    from workshop.panorama import make_panorama
    with pytest.raises(FileNotFoundError):
        make_panorama(["C:/nope.png", "C:/nope2.png"])


def test_panorama_horizontal(tmp_path):
    """全景横向拼接"""
    from workshop.panorama import make_panorama
    from PIL import Image
    a = Image.new("RGB", (100, 80), (255, 0, 0))
    b = Image.new("RGB", (100, 80), (0, 0, 255))
    pa, pb = tmp_path / "a.png", tmp_path / "b.png"
    a.save(pa); b.save(pb)
    out = tmp_path / "p.png"
    results = make_panorama([str(pa), str(pb)], output=str(out))
    assert results
    img = Image.open(out)
    assert img.width == 200 and img.height == 80


def test_restore_scratch(tmp_path):
    """划痕修复（无划痕图也应能处理）"""
    from workshop.restore import _restore_scratch
    from PIL import Image
    img = Image.new("L", (100, 100), 128)
    src = tmp_path / "s.png"
    img.save(src)
    out = tmp_path / "o.png"
    _restore_scratch(str(src), str(out))
    assert os.path.exists(out)
    r = Image.open(out)
    assert r.size == (100, 100)


def test_info_basic(tmp_path):
    """图片信息查看"""
    from workshop.info import _get_info
    from PIL import Image
    img = Image.new("RGB", (64, 48), (0, 0, 0))
    p = tmp_path / "i.png"
    img.save(p)
    info = _get_info(str(p))
    assert info['尺寸'] == '64x48'
    assert info['格式'] == 'PNG'
