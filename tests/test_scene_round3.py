# -*- coding: utf-8 -*-
"""N4 动态表情 + 多人同框 + 直播背景 + 动态壁纸 测试"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_wallpaper_live_bg_type():
    """直播背景类型（16:9 无角色场景）"""
    from workshop.wallpaper import TYPES
    w, h, style = TYPES["live_bg"]
    assert w > h  # 横版
    assert "no characters" in style  # 无角色场景


def test_multi_modes_exist():
    """多人同框 3 模式"""
    from workshop.wallpaper import MULTI_COMPOSE
    assert "couple" in MULTI_COMPOSE and "group" in MULTI_COMPOSE and "battle" in MULTI_COMPOSE


def test_multi_prompt_has_both_chars():
    """多人同框 prompt 包含两个角色 + 构图"""
    from workshop.wallpaper import MULTI_COMPOSE
    # 验证 couple 构图描述包含双人要素
    assert "two characters" in MULTI_COMPOSE["couple"]
    assert "three characters" in MULTI_COMPOSE["group"]
    assert "two characters" in MULTI_COMPOSE["battle"]


def test_multi_module_imports():
    """multi 子命令可导入"""
    from workshop.multi import main
    import inspect
    assert "couple" in inspect.getsource(main)


def test_emotes_gif_flag():
    """emotes 支持 gif 参数"""
    from workshop.emotes import generate_emotes
    import inspect
    src = inspect.getsource(generate_emotes)
    assert "gif" in src and "GIF" in src


def test_wallpaper_dynamic_flag():
    """wallpaper 支持 dynamic（动态壁纸）"""
    from workshop.wallpaper import generate_wallpaper
    import inspect
    src = inspect.getsource(generate_wallpaper)
    assert "dynamic" in src
