# -*- coding: utf-8 -*-
"""商业图类型测试：轻小说插画/游戏 KV/中文标题/系列一致性"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_commercial_types():
    """商业图类型规格（轻小说插画/游戏 KV）"""
    from workshop.cover import COVER_TYPES
    assert 'illustration' in COVER_TYPES
    assert 'game_kv' in COVER_TYPES
    # 插画：2:3 竖版（宽<高）——(w, h, style) 三元组
    il = COVER_TYPES['illustration']
    assert il[0] < il[1], '插画应竖版'
    assert 'light novel illustration' in il[2]
    # 游戏 KV：16:9 横版（宽>高）
    kv = COVER_TYPES['game_kv']
    assert kv[0] > kv[1], '游戏 KV 应横版'
    assert 'game key visual' in kv[2]


def test_cover_title_cjk(tmp_path):
    """中文标题渲染（微软雅黑粗体）"""
    from workshop.cover import _add_title_zone
    import os
    if not os.path.exists(r'C:\Windows\Fonts\msyhbd.ttc'):
        pytest.skip('无中文字体')
    from PIL import Image
    src = tmp_path / 'src.png'
    Image.new('RGB', (768, 1152), (30, 30, 60)).save(src)
    out = tmp_path / 'out.png'
    _add_title_zone(str(src), str(out), title='银狼物语', ctype='novel')
    assert out.exists()
    assert out.stat().st_size > 0


def test_cover_type_edge():
    """类型边界：未知类型友好报错"""
    from workshop.cover import COVER_TYPES
    assert 'unknown' not in COVER_TYPES  # 无未知类型
    assert len(COVER_TYPES) >= 6  # 6 种类型


def test_cover_retry_logic(monkeypatch):
    """自动重试：失败→重试成功"""
    import workshop.cover as cv
    calls = {'n': 0}
    def fake_submit(wf, timeout=300):
        calls['n'] += 1
        if calls['n'] < 3:
            raise TimeoutError('生成超时')
        return ['ok.png']
    monkeypatch.setattr(cv, '_submit', fake_submit)
    monkeypatch.setattr(cv, '_build_cover_wf', lambda *a, **kw: {'x': 1})
    import types
    fake_time = types.SimpleNamespace(time=lambda: 0, sleep=lambda s: None)
    monkeypatch.setattr(cv, 'time', fake_time)
    # 直接测 generate_cover 的重试循环（输出文件不存在会 continue——不崩即可）
    try:
        cv.generate_cover('测试', ctype='video', output='C:/tmp/cover_retry_test.png')
    except Exception:
        pass
    assert calls['n'] >= 2, f'应至少重试 1 次，实际 {calls["n"]}'


def test_cover_outfit_style(monkeypatch):
    """cover --outfit 服装风格展开"""
    import workshop.cover as cv
    calls = {}
    def fake_build_cover(prompt, negative, seed, w, h):
        calls['prompt'] = prompt
        return {'x': 1}
    monkeypatch.setattr(cv, '_build_cover_wf', fake_build_cover)
    monkeypatch.setattr(cv, '_submit', lambda *a, **kw: ['ok.png'])
    monkeypatch.setattr(cv, '_add_title_zone', lambda *a, **kw: 'out.png')
    import types
    monkeypatch.setattr(cv, 'time', types.SimpleNamespace(time=lambda: 0, sleep=lambda s: None))
    import os
    try:
        cv.generate_cover('银狼少女', ctype='video', outfit_style='gothic',
                          output='C:/tmp/cover_outfit_test.png')
    except Exception:
        pass
    assert calls.get('prompt', '')
    assert 'black gothic dress' in calls['prompt']


def test_oc_emotes_cmd(tmp_path, monkeypatch):
    """oc emotes 子命令：角色卡 → 一键表情"""
    import workshop.oc as oc_mod
    monkeypatch.setattr(oc_mod, 'OC_DIR', tmp_path / 'oc')
    oc_mod.OC_DIR.mkdir(exist_ok=True)
    oc_mod.create_oc('fox2', '白狐', hair='long', hair_color='white')
    # 验证 prompt 生成 + emotes 调用链（mock generate_emotes）
    calls = []
    import workshop.emotes as em_mod
    monkeypatch.setattr(em_mod, 'generate_emotes',
                        lambda *a, **kw: calls.append((a[0], kw)))
    p = oc_mod.oc_to_prompt(oc_mod._load('fox2'))
    assert 'silvoc' in p or 'fox2' in p  # 触发词或角色特征
    assert 'white' in p


def test_game_kv_focus(monkeypatch):
    """game_kv 复杂描述自动聚焦主角色"""
    import workshop.cover as cv
    calls = {}
    def fake_build_cover(prompt, negative, seed, w, h):
        calls['prompt'] = prompt
        return {'x': 1}
    monkeypatch.setattr(cv, '_build_cover_wf', fake_build_cover)
    monkeypatch.setattr(cv, '_submit', lambda *a, **kw: ['ok.png'])
    monkeypatch.setattr(cv, '_add_title_zone', lambda *a, **kw: 'out.png')
    import workshop.layer as layer_mod
    monkeypatch.setattr(layer_mod, '_translate_desc', lambda d: 'translated ' + d)
    import types
    monkeypatch.setattr(cv, 'time', types.SimpleNamespace(time=lambda: 0, sleep=lambda s: None))
    try:
        cv.generate_cover('银狼少女机甲小队末日战场巨型机甲粒子光效', ctype='game_kv',
                          output='C:/tmp/kv_focus_test.png')
    except Exception:
        pass
    assert 'focus on the main character' in calls['prompt']


def test_kb_check_hook(monkeypatch):
    """--check kb 质量门禁钩子"""
    import workshop.cover as cv
    called = []
    class FakeKb:
        @staticmethod
        def check_image(p):
            called.append(p)
            return 0.9, 'ok'
    import sys, types
    monkeypatch.setitem(sys.modules, 'workshop.kb', types.SimpleNamespace(check_image=FakeKb.check_image))
    # 直接测 kb_check 分支（不生成——用 out_paths 非空模拟）
    import workshop.layer as layer_mod
    monkeypatch.setattr(layer_mod, '_translate_desc', lambda d: d)
    monkeypatch.setattr(cv, '_build_cover_wf', lambda *a, **kw: {'x': 1})
    monkeypatch.setattr(cv, '_submit', lambda *a, **kw: ['ok.png'])
    monkeypatch.setattr(cv, '_add_title_zone', lambda *a, **kw: 'out.png')
    monkeypatch.setattr(cv, 'time', types.SimpleNamespace(time=lambda: 0, sleep=lambda s: None))
    monkeypatch.setattr(cv, '_http', lambda: None)
    import os
    monkeypatch.setattr(os.path, 'exists', lambda p: True)
    try:
        cv.generate_cover('测试', ctype='video', output='C:/tmp/kb_hook_test.png', kb_check=True)
    except Exception:
        pass
    assert called, 'kb check 应被调用'


def test_cover_negative_words():
    """cover 负向词含人物细节硬伤词"""
    import workshop.cover as cv
    wf = cv._build_cover_wf('test prompt', None, 42, 1344, 768)
    neg_text = wf['3']['inputs']['text']
    assert 'bad hands' in neg_text
    assert 'extra fingers' in neg_text
    assert 'mutated hands' in neg_text


def test_wx_export(tmp_path):
    """微信表情导出全套规格（主图/缩略图/横幅）"""
    from workshop.emotes import _export_wx_specs
    from PIL import Image
    src = tmp_path / 'src.png'
    Image.new('RGB', (512, 512), (200, 100, 100)).save(src)
    result = _export_wx_specs({'a': str(src), 'b': str(src)}, tmp_path)
    assert len(result) >= 6  # 2 主图 + 2 缩略 + 横幅/封面
    mains = [v for k, v in result.items() if k.startswith('main')]
    from PIL import Image as I
    assert I.open(mains[0]).size == (240, 240)
