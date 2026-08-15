# -*- coding: utf-8 -*-
"""原创 OC 库测试：角色卡 CRUD / prompt 构建 / 验证"""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def clean_lib(tmp_path, monkeypatch):
    """隔离 OC 库目录"""
    import workshop.oc as oc_mod
    monkeypatch.setattr(oc_mod, 'OC_DIR', tmp_path / 'oc_library')
    oc_mod.OC_DIR.mkdir(exist_ok=True)
    return oc_mod


def test_create_and_load(clean_lib):
    """创建角色卡 + 加载"""
    oc_mod = clean_lib
    oc = oc_mod.create_oc('testchar', '少女', hair='长发', hair_color='银白',
                          eyes='凤眼', eye_color='紫', outfit='白色连衣裙')
    assert oc['name'] == 'testchar'
    assert oc['trigger'] == 'testoc'
    loaded = oc_mod._load('testchar')
    assert loaded['identity']['hair_color'] == '银白'
    assert loaded['outfits'] == ['白色连衣裙']


def test_list(clean_lib):
    """列出 OC"""
    oc_mod = clean_lib
    oc_mod.create_oc('a', '描述A')
    oc_mod.create_oc('b', '描述B')
    assert oc_mod.list_oc_names() == ['a', 'b']


def test_duplicate_rejected(clean_lib):
    """重复创建报错"""
    oc_mod = clean_lib
    oc_mod.create_oc('dup', '描述')
    with pytest.raises(ValueError):
        oc_mod.create_oc('dup', '描述')


def test_missing_show(clean_lib):
    """不存在报错"""
    oc_mod = clean_lib
    with pytest.raises(FileNotFoundError):
        oc_mod.show_oc('nope')


def test_prompt_build(clean_lib):
    """角色卡 → prompt"""
    oc_mod = clean_lib
    oc = oc_mod.create_oc('promptchar', '少女', hair='双马尾', hair_color='黑',
                          eyes='圆眼', eye_color='蓝', art_style='赛璐璐')
    prompt = oc_mod.oc_to_prompt(oc, scene='海边')
    assert oc['trigger'] in prompt
    assert '黑 hair' in prompt
    assert '蓝 eyes' in prompt
    assert '海边' in prompt
    assert '赛璐璐' in prompt


def test_prompt_with_outfit(clean_lib):
    """服装索引"""
    oc_mod = clean_lib
    oc = oc_mod.create_oc('o', '男孩', outfit='校服')
    oc['outfits'].append('便服')
    oc_mod._save(oc)
    p1 = oc_mod.oc_to_prompt(oc, outfit_idx=0)
    p2 = oc_mod.oc_to_prompt(oc, outfit_idx=1)
    assert '校服' in p1 and '便服' in p2
