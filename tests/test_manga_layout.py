# -*- coding: utf-8 -*-
"""E4 漫画布局自动匹配测试（业界对齐 AI Comic Factory parseLayoutFromStoryboards）"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workshop.manga.manga import _match_layout, _LAYOUT_TEMPLATES


def test_match_4_square_uses_grid2x2():
    """4 个方格 → grid2x2"""
    assert _match_layout(4, [1.0, 1.0, 1.0, 1.0]) == "grid2x2"


def test_match_4_with_big_wide_uses_L4():
    """4 格含大横格（比例差异大）→ L4"""
    assert _match_layout(4, [2.0, 1.0, 1.0, 1.0]) == "L4"


def test_match_4_with_tall_uses_L4_v():
    """4 格含竖格主导 → L4_v"""
    assert _match_layout(4, [0.6, 1.0, 1.0, 1.0]) == "L4_v"


def test_match_4_all_wide_uses_strip4():
    """4 格全横 → strip4（webtoon）"""
    assert _match_layout(4, [1.8, 1.8, 1.8, 1.8]) == "strip4"


def test_match_3_with_wide_uses_grid3():
    """3 格含横格 → grid3"""
    assert _match_layout(3, [1.5, 1.0, 1.0]) == "grid3"


def test_match_3_all_square_uses_strip3():
    """3 格全方 → strip3"""
    assert _match_layout(3, [1.0, 1.0, 1.0]) == "strip3"


def test_match_6_uses_grid6():
    """6 格 → grid6"""
    assert _match_layout(6, [1.0] * 6) == "grid6"


def test_match_unsupported_count_returns_empty():
    """不支持的格数（5）→ 空（回退固定网格）"""
    assert _match_layout(5, [1.0] * 5) == ""


def test_match_empty_ratios_fallback():
    """无比例信息 → 默认 grid2x2"""
    assert _match_layout(4, []) == "grid2x2"


def test_templates_have_valid_panels():
    """所有模板 panels 数与 cols*rows 容量匹配"""
    for name, tmpl in _LAYOUT_TEMPLATES.items():
        n = len(tmpl["panels"])
        capacity = tmpl["cols"] * tmpl["rows"]
        assert n <= capacity, f"{name}: {n} 格超过 {capacity} 容量"
        for wr, hr in tmpl["panels"]:
            assert wr > 0 and hr > 0
