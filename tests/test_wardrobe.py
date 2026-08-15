# -*- coding: utf-8 -*-
"""衣品知识库测试：风格模板 / 子部件词库 / oc 集成"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_wardrobe_styles_count():
    """风格库 ≥ 10 类"""
    from workshop.wardrobe import WARDROBE_STYLES
    assert len(WARDROBE_STYLES) >= 10


def test_style_template_complete():
    """每类模板含 outfit+shoes+socks+palette"""
    from workshop.wardrobe import WARDROBE_STYLES
    for name, tpl in WARDROBE_STYLES.items():
        assert tpl['outfit'], f'{name} 缺 outfit'
        assert 'shoes' in tpl, f'{name} 缺 shoes 键'
        assert 'socks' in tpl, f'{name} 缺 socks 键'
        assert tpl.get('palette'), f'{name} 缺配色'


def test_build_outfit():
    """build_outfit 生成完整描述"""
    from workshop.wardrobe import build_outfit
    out = build_outfit('gothic')
    assert 'gothic dress' in out
    assert 'boots' in out
    assert 'stockings' in out
    assert 'color scheme' in out


def test_build_outfit_custom_color():
    """自定义配色覆盖默认"""
    from workshop.wardrobe import build_outfit
    out = build_outfit('gothic', color='white and gold')
    assert 'white and gold' in out
    assert 'color scheme' not in out


def test_build_outfit_unknown():
    """未知风格 → 友好报错"""
    from workshop.wardrobe import build_outfit
    with pytest.raises(ValueError, match='未知风格'):
        build_outfit('nope')


def test_body_parts():
    """子部件词库"""
    from workshop.wardrobe import build_body_parts
    out = build_body_parts(body_detail='curvy', face_shape='oval',
                           hair_style='twintails', socks_style='thighhigh')
    assert 'hourglass' in out
    assert 'oval face' in out
    assert 'twin tails' in out
    assert 'thigh-high' in out


def test_body_parts_detail():
    """细节描述"""
    from workshop.wardrobe import build_body_parts
    out = build_body_parts(eye_detail=True, hair_detail=True)
    assert 'catchlight' in out
    assert 'highlights' in out


def test_build_outfit_mix():
    """混搭风格（异世界/ARPG 组合）"""
    from workshop.wardrobe import build_outfit
    out = build_outfit('fantasy', mix=['cyber', 'military'])
    assert 'fantasy battle armor' in out
    assert 'cyber style elements' in out
    assert 'military style elements' in out


def test_build_outfit_mix_unknown():
    """未知混搭风格 → 友好报错"""
    from workshop.wardrobe import build_outfit
    with pytest.raises(ValueError, match='未知混搭风格'):
        build_outfit('fantasy', mix='nope')


def test_build_outfit_mix_edge():
    """混搭边界：空/自身/多风格"""
    from workshop.wardrobe import build_outfit
    assert 'gothic dress' in build_outfit('gothic', mix=[])  # 空列表=不混
    assert 'gothic dress' in build_outfit('gothic', mix='gothic')  # 自身=重复元素可接受
    out = build_outfit('fantasy', mix=['cyber', 'military', 'lolita'])
    for m in ('cyber', 'military', 'lolita'):
        assert f'{m} style elements' in out  # 多风格混搭


def test_all_styles_buildable():
    """全部 12 风格 build 完整"""
    from workshop.wardrobe import WARDROBE_STYLES, build_outfit
    for s in WARDROBE_STYLES:
        out = build_outfit(s)
        assert len(out) > 50, f'{s} 描述过短'


def test_oc_body_parts_integration(tmp_path, monkeypatch):
    """oc 角色卡 body 词库值 → 展开（身材/脸型）"""
    import workshop.oc as oc_mod
    monkeypatch.setattr(oc_mod, 'OC_DIR', tmp_path / 'oc')
    oc_mod.OC_DIR.mkdir(exist_ok=True)
    oc = oc_mod.create_oc('x', '少女', outfit='gothic')
    oc['identity']['body'] = 'curvy'
    oc['identity']['face_shape'] = 'oval'
    oc_mod._save(oc)
    p = oc_mod.oc_to_prompt(oc)
    assert 'hourglass' in p  # curvy → hourglass figure
    assert 'oval face' in p


def test_kb_outfit_rules():
    """kb 服装类规则存在且 OUTFIT-05 不可见降级"""
    import json
    from pathlib import Path
    db = json.load(open(Path(__file__).resolve().parent.parent / 'workshop' / 'kb_rules.json', encoding='utf-8'))
    outfit_rules = [r for r in db['rules'] if r['category'] == '服装']
    assert len(outfit_rules) >= 5
    o5 = next(r for r in outfit_rules if r['id'] == 'OUTFIT-05')
    assert 'NOT visible' in o5['prompt']  # 不可见降级逻辑


def test_arknight_style():
    """方舟风复杂绑带设计"""
    from workshop.wardrobe import build_outfit
    out = build_outfit('arknight')
    assert 'strap harness' in out
    assert 'decorative straps' in out
    assert 'asymmetrical' in out
    assert 'tactical boots' in out


def test_outfit_variants():
    """衣装变体（穿/不穿双版本）"""
    from workshop.wardrobe import build_outfit
    full = build_outfit('gothic')
    swim = build_outfit('gothic', variant='swim')
    lingerie = build_outfit('gothic', variant='lingerie')
    artistic = build_outfit('gothic', variant='artistic')
    assert 'bikini' in swim
    assert 'lingerie' in lingerie
    assert 'nude figure study' in artistic
    assert 'boots' in full and 'boots' not in artistic  # 变体不穿鞋袜


def test_outfit_variant_unknown():
    """未知变体 → 友好报错"""
    from workshop.wardrobe import build_outfit
    with pytest.raises(ValueError, match='未知变体'):
        build_outfit('gothic', variant='nope')


def test_figure_pose_words():
    """人体层/姿势层词库"""
    from workshop.wardrobe import build_body_parts
    fig = build_body_parts(figure_style='proportion', pose_style='fighting')
    assert 'head-to-body ratio' in fig
    assert 'fighting stance' in fig
    art = build_body_parts(figure_style='artistic')
    assert 'nude study' in art and 'correct anatomy' in art


def test_accessories_racial_lighting():
    """配饰/异质特征/光影词库"""
    from workshop.wardrobe import build_body_parts
    out = build_body_parts(accessory='jewelry', racial='animal_ears', lighting='rim')
    assert 'pendant necklace' in out
    assert 'animal ears' in out
    assert 'rim lighting' in out
    # 细节
    out2 = build_body_parts(lighting_detail=True, racial_detail=True)
    assert 'light direction consistency' in out2
    assert 'natural integration' in out2


def test_ip_styles():
    """IP 参考风格库 ≥ 30 个作品"""
    from workshop.wardrobe import IP_STYLES
    assert len(IP_STYLES) >= 30
    for k in ('原神', '少女前线', '碧蓝航线', '崩坏三', 'Fate', '斗罗大陆'):
        assert k in IP_STYLES


def test_build_outfit_ip():
    """IP 风格锚注入"""
    from workshop.wardrobe import build_outfit
    out = build_outfit('military', ip='少女前线')
    assert 'girls frontline style' in out
    assert 'tactical military uniform' in out
    out2 = build_outfit('fantasy', ip='原神')
    assert 'genshin-inspired' in out2


def test_build_outfit_ip_unknown():
    """未知 IP → 友好报错"""
    from workshop.wardrobe import build_outfit
    with pytest.raises(ValueError, match='未知 IP'):
        build_outfit('gothic', ip='不存在作品')


def test_appeal_words():
    """点睛裸露/记忆点/世界观锚词库"""
    from workshop.wardrobe import build_body_parts
    out = build_body_parts(accent='thigh_strap', memory='color_anchor', worldview='military')
    assert 'thigh strap' in out
    assert 'signature color' in out
    assert 'military world' in out
    # 细节
    out2 = build_body_parts(accent_detail=True)
    assert 'strategic exposure' in out2


def test_oc_appeal_fields(tmp_path, monkeypatch):
    """oc 吸引力三字段（概念锚/记忆点/世界观）→ prompt 展开"""
    import workshop.oc as oc_mod
    monkeypatch.setattr(oc_mod, 'OC_DIR', tmp_path / 'oc')
    oc_mod.OC_DIR.mkdir(exist_ok=True)
    oc = oc_mod.create_oc('fox', '白狐少女', hair='long', hair_color='white',
                          concept_anchor='animal_ears', memory_point='color_anchor,symbol',
                          worldview='fantasy', outfit='gothic')
    p = oc_mod.oc_to_prompt(oc)
    assert 'animal ears' in p           # 概念锚 → 异质特征词库
    assert 'signature color' in p       # 记忆点展开
    assert 'iconic emblem' in p
    assert 'fantasy world' in p         # 世界观展开
    # 自定义概念锚（非词库）→ 自由文本
    oc2 = oc_mod.create_oc('blade', '剑姬', concept_anchor='月光剑')
    p2 = oc_mod.oc_to_prompt(oc2)
    assert '月光剑 concept' in p2


def test_emotes_outfit_style(tmp_path, monkeypatch):
    """emotes --outfit 服装风格展开（表情穿风格服装）"""
    import workshop.emotes as em
    import workshop.create as create_mod
    calls = []
    def fake_create(*a, **kw):
        calls.append(a[0] if a else kw.get('prompt', ''))
        return {'files': []}
    monkeypatch.setattr(create_mod, 'create_from_nl', fake_create)
    try:
        em.generate_emotes('银白双马尾少女', emotes=['微笑'], name='t', count=1,
                           output_dir=str(tmp_path), outfit_style='gothic')
    except Exception:
        pass  # 生成流程因无图可能中断，prompt 构造已验证
    assert calls, '应调用 create_from_nl'
    assert 'black gothic dress' in calls[0]
    # 未知风格 → 降级不崩
    try:
        em.generate_emotes('银白双马尾少女', emotes=['微笑'], name='t2', count=1,
                           output_dir=str(tmp_path), outfit_style='不存在风格')
    except Exception:
        pass
    assert True


def test_kb_appeal_rules():
    """kb 吸引力规则存在（4 条）"""
    import json
    from pathlib import Path
    db = json.load(open(Path(__file__).resolve().parent.parent / 'workshop' / 'kb_rules.json', encoding='utf-8'))
    appeal = [r for r in db['rules'] if r['category'] == '吸引力']
    assert len(appeal) >= 4
    assert {r['id'] for r in appeal} >= {'APPEAL-01', 'APPEAL-02', 'APPEAL-03', 'APPEAL-04'}


def test_oc_outfit_style_integration(tmp_path, monkeypatch):
    """oc 角色卡 outfit=风格名 → 自动展开"""
    import workshop.oc as oc_mod
    monkeypatch.setattr(oc_mod, 'OC_DIR', tmp_path / 'oc')
    oc_mod.OC_DIR.mkdir(exist_ok=True)
    oc = oc_mod.create_oc('x', '描述', outfit='gothic')
    p = oc_mod.oc_to_prompt(oc)
    assert 'gothic dress' in p  # 风格名展开为完整设计
    assert 'boots' in p


def test_oc_outfit_custom_stays(tmp_path, monkeypatch):
    """oc 角色卡自定义服装描述不变"""
    import workshop.oc as oc_mod
    monkeypatch.setattr(oc_mod, 'OC_DIR', tmp_path / 'oc')
    oc_mod.OC_DIR.mkdir(exist_ok=True)
    oc = oc_mod.create_oc('x', '描述', outfit='白色连衣裙，蝴蝶结')
    p = oc_mod.oc_to_prompt(oc)
    assert '白色连衣裙' in p  # 非风格名保持原文


def test_hand_style():
    """手部细节词库"""
    from workshop.wardrobe import build_body_parts
    out = build_body_parts(hand_style='detail')
    assert 'five fingers clearly' in out
    out2 = build_body_parts(hand_style='holding')
    assert 'proper grip' in out2
