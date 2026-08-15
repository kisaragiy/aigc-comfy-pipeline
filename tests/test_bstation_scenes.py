# -*- coding: utf-8 -*-
"""B站主流生图场景模块测试：cover/emotes/wallpaper"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_cover_module_imports():
    """cover 模块可导入且有核心函数"""
    from workshop.cover import generate_cover, _COVER_STYLE, _TITLE_ZONE
    assert "16:9" in _COVER_STYLE or "widescreen" in _COVER_STYLE
    assert len(_TITLE_ZONE) == 4  # 留白区 4 坐标


def test_cover_style_high_impact():
    """封面风格应含高冲击力要素"""
    from workshop.cover import _COVER_STYLE
    for kw in ["high impact", "subject", "dramatic", "contrast"]:
        assert kw in _COVER_STYLE, f"缺 {kw}"


def test_emotes_default_list():
    """表情包默认表情库存在且映射完整"""
    from workshop.emotes import DEFAULT_EMOTES, EMOTE_MAP
    assert len(DEFAULT_EMOTES) >= 6
    for e in DEFAULT_EMOTES:
        assert e in EMOTE_MAP, f"{e} 缺英文映射"


def test_emotes_emoji_map():
    """每个表情都有 emoji"""
    from workshop.emotes import EMOTE_MAP, _emoji
    for e in EMOTE_MAP:
        assert _emoji(e) != "😐" or e == "无语"  # 无语是 😐


def test_wallpaper_types():
    """壁纸类型定义完整（尺寸+构图）"""
    from workshop.wallpaper import TYPES
    assert "phone" in TYPES and "avatar" in TYPES and "desktop" in TYPES
    # 手机壁纸竖构图
    pw, ph, _ = TYPES["phone"]
    assert ph > pw
    # 头像方形
    aw, ah, _ = TYPES["avatar"]
    assert aw == ah
    # 桌面横构图
    dw, dh, _ = TYPES["desktop"]
    assert dw > dh


def test_character_sheet_flag():
    """character 支持 --sheet 参数（三视图）"""
    from workshop.character import main
    import inspect
    src = inspect.getsource(main)
    assert "--sheet" in src
