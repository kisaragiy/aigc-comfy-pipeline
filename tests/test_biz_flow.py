# -*- coding: utf-8 -*-
"""商业图流程测试：biz 8 主题 / 规格表 / 无文字铁律 / 批量"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_biz_topics_complete():
    """商业图 8 主题规格表"""
    from workshop.biz import BIZ_TOPICS
    for t in ("avatar", "cover", "poster", "dashboard", "mockup", "banner", "logo", "product"):
        assert t in BIZ_TOPICS
        assert "size" in BIZ_TOPICS[t]
        assert "constraint" in BIZ_TOPICS[t]


def test_biz_styles():
    """品牌风格预设"""
    from workshop.biz import BIZ_STYLES
    for s in ("default", "tech", "minimal", "luxury", "fresh", "warm"):
        assert s in BIZ_STYLES


def test_biz_invalid_topic():
    """非法主题报错"""
    from workshop.biz import biz_generate
    with pytest.raises(ValueError):
        biz_generate("nope", "test")


def test_biz_wf_structure():
    """qwen-image 工作流结构"""
    from workshop.biz import _build_biz_wf
    wf = _build_biz_wf("测试", 1024, 1024, 42)
    types = [v['class_type'] for v in wf.values()]
    assert "UnetLoaderGGUF" in types
    assert "CLIPLoader" in types
    assert "VAELoader" in types
    # CLIPLoader 用 qwen_image 类型
    cl = [v for v in wf.values() if v['class_type'] == 'CLIPLoader'][0]
    assert cl['inputs']['type'] == 'qwen_image'


def test_biz_no_text_rule():
    """无文字铁律（默认 prompt 含无文字约束）"""
    from workshop.biz import biz_generate
    import inspect
    src = inspect.getsource(biz_generate)
    assert "不要出现任何文字" in src or "no text" in src.lower()


def test_biz_ratio_sizes():
    """尺寸规格符合商业标准"""
    from workshop.biz import BIZ_TOPICS
    assert BIZ_TOPICS["banner"]["size"][0] / BIZ_TOPICS["banner"]["size"][1] > 2.0  # 21:9
    assert BIZ_TOPICS["avatar"]["size"][0] == BIZ_TOPICS["avatar"]["size"][1]  # 1:1
    assert BIZ_TOPICS["poster"]["size"][1] > BIZ_TOPICS["poster"]["size"][0]  # 竖版
