# -*- coding: utf-8 -*-
"""条漫（webtoon 竖排）模式测试"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workshop.manga.manga import _match_layout, _LAYOUT_TEMPLATES


def test_match_webtoon_prefer():
    """prefer=webtoon 强制条漫"""
    assert _match_layout(4, [1.0] * 4, prefer="webtoon") == "webtoon"
    assert _match_layout(6, [1.0] * 6, prefer="webtoon") == "webtoon6"


def test_webtoon_template_structure():
    """条漫模板：1 列竖排 + 每格竖比"""
    t = _LAYOUT_TEMPLATES["webtoon"]
    assert t["cols"] == 1
    assert t["rows"] == 4
    for wr, hr in t["panels"]:
        assert hr > wr  # 竖格（高>宽）


def test_webtoon6_template():
    """6 格条漫模板存在且结构正确"""
    t = _LAYOUT_TEMPLATES["webtoon6"]
    assert t["cols"] == 1
    assert len(t["panels"]) == 6


def test_auto_still_works():
    """auto 模式不受影响（方格仍 grid2x2）"""
    assert _match_layout(4, [1.0] * 4) == "grid2x2"
