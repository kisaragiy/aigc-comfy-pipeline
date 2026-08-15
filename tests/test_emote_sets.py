# -*- coding: utf-8 -*-
"""表情库来源域扩展测试：31 表情 4 预设 / adult 锚点 / 集合完整性"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_emote_library_size():
    """表情库 ≥ 30 个"""
    from workshop.emotes import EMOTE_MAP
    assert len(EMOTE_MAP) >= 30


def test_emote_sets_complete():
    """5 预设集存在且表情都在库中"""
    from workshop.emotes import EMOTE_MAP, EMOTE_SETS
    assert {'casual', 'galgame', 'manga', 'ecchi', 'horror'} <= set(EMOTE_SETS.keys())
    for name, emotes in EMOTE_SETS.items():
        for e in emotes:
            assert e in EMOTE_MAP, f'{name} 集 {e} 不在库中'


def test_horror_set():
    """猎奇向表情集（12魔器风格）"""
    from workshop.emotes import EMOTE_SETS
    h = set(EMOTE_SETS['horror'])
    assert len(h) >= 10
    for e in ('狂气', '病娇', '崩坏', '空洞', '怨念', '极黑'):
        assert e in h


def test_ecchi_adult_anchor():
    """核心色气向表情必须 adult 锚点"""
    from workshop.emotes import EMOTE_MAP
    for e in ('色气', '挑逗', '魅惑', '娇喘'):
        assert 'adult' in EMOTE_MAP[e], f'{e} 缺 adult 锚点'


def test_galgame_diff_expressions():
    """galgame 差分表情（心动/黑化/吃醋/流泪等）"""
    from workshop.emotes import EMOTE_SETS
    g = set(EMOTE_SETS['galgame'])
    for e in ('心动', '黑化', '吃醋', '流泪', '脸红', '嫌弃'):
        assert e in g


def test_manga_exaggerated():
    """漫画夸张表情（汗颜/石化/星星眼/炸毛）"""
    from workshop.emotes import EMOTE_SETS
    m = set(EMOTE_SETS['manga'])
    for e in ('汗颜', '石化', '星星眼', '炸毛', '流口水'):
        assert e in m


def test_all_emotes_have_emoji():
    """所有表情有 emoji（文件名用）"""
    from workshop.emotes import EMOTE_MAP, _emoji
    for e in EMOTE_MAP:
        assert _emoji(e) != '😐' or e in ('坏笑', '色气')  # 这两个故意用 😏


def test_emote_set_validation():
    """ecchi/galgame 集通过 generate_emotes 校验（count=0）"""
    from workshop.emotes import EMOTE_SETS, generate_emotes
    for name in ('ecchi', 'galgame', 'manga'):
        r = generate_emotes('成年角色' if name == 'ecchi' else '少女',
                            emotes=list(EMOTE_SETS[name]), count=0)
        assert r == []
