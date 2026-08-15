# -*- coding: utf-8 -*-
"""审美知识库测试：规则加载 / 像素检查 / 分类 / 阈值"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_rules_load():
    """规则库加载且完整"""
    from workshop.kb import _load_rules
    db = _load_rules()
    assert db['version'] == '1.0'
    rules = db['rules']
    assert len(rules) >= 18
    # 六大类齐全
    cats = {r['category'] for r in rules}
    assert {'构图', '色彩', '光影', '造型', '技术', '风格'} <= cats
    # id 唯一
    ids = [r['id'] for r in rules]
    assert len(ids) == len(set(ids))


def test_rule_format():
    """规则格式完整"""
    from workshop.kb import _load_rules
    for r in _load_rules()['rules']:
        assert r['type'] in ('vlm', 'pixel')
        assert 'prompt' in r and r['prompt']
        assert 'weight' in r and r['weight'] > 0
        assert 'enabled' in r


def test_pixel_resolution(tmp_path):
    """像素规则：分辨率检查"""
    from workshop.kb import _pixel_check
    from PIL import Image
    img = Image.new('RGB', (1024, 768))
    p = tmp_path / 'big.png'
    img.save(p)
    assert _pixel_check({'id': 'TECH-01'}, str(p)) == 1.0
    img2 = Image.new('RGB', (256, 256))
    p2 = tmp_path / 'small.png'
    img2.save(p2)
    assert _pixel_check({'id': 'TECH-01'}, str(p2)) < 1.0


def test_pixel_light(tmp_path):
    """像素规则：过曝死黑检查"""
    from workshop.kb import _pixel_check
    from PIL import Image
    import numpy as np
    # 正常图
    arr = np.full((100, 100), 128, dtype=np.uint8)
    p = tmp_path / 'n.png'
    Image.fromarray(arr).save(p)
    assert _pixel_check({'id': 'LIGHT-03'}, str(p)) > 0.9
    # 半张死黑图
    arr2 = np.full((100, 100), 128, dtype=np.uint8)
    arr2[:50, :] = 0
    p2 = tmp_path / 'd.png'
    Image.fromarray(arr2).save(p2)
    assert _pixel_check({'id': 'LIGHT-03'}, str(p2)) < 0.9


def test_check_missing_file():
    """缺图报错"""
    from workshop.kb import check_image
    with pytest.raises(FileNotFoundError):
        check_image('C:/nope.png')


def test_check_category_filter(tmp_path):
    """类别过滤"""
    from workshop.kb import check_image
    from PIL import Image
    img = Image.new('RGB', (800, 600), (100, 100, 100))
    p = tmp_path / 'i.png'
    img.save(p)
    # 只跑像素规则（技术类）——不触发 VLM 网络
    total, results = check_image(str(p), category='技术', threshold=0.3)
    assert results
    assert all(r['category'] == '技术' for r in results)
