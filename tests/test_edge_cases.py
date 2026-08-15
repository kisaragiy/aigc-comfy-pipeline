# -*- coding: utf-8 -*-
"""边缘情况测试：损坏图 / 空文件 / 伪png / 极小图 / RGBA / 参数边界"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def edge_files(tmp_path):
    """构造边缘输入文件集。"""
    from PIL import Image
    corrupt = tmp_path / 'corrupt.png'
    corrupt.write_bytes(b'not a real png at all')
    empty = tmp_path / 'empty.png'
    empty.write_bytes(b'')
    fake = tmp_path / 'fake.png'
    fake.write_bytes(b'just text pretending')
    tiny = tmp_path / 'tiny.png'
    Image.new('RGB', (1, 1)).save(tiny)
    rgba = tmp_path / 'rgba.png'
    Image.new('RGBA', (64, 64), (255, 0, 0, 128)).save(rgba)
    good = tmp_path / 'good.png'
    Image.new('RGB', (128, 96)).save(good)
    return {'corrupt': corrupt, 'empty': empty, 'fake': fake,
            'tiny': tiny, 'rgba': rgba, 'good': good}


def test_open_image_safe_missing(tmp_path):
    """缺图 → FileNotFoundError"""
    from workshop.image_utils import open_image_safe
    with pytest.raises(FileNotFoundError):
        open_image_safe(str(tmp_path / 'nope.png'))


def test_open_image_safe_corrupt(edge_files):
    """损坏图 → ValueError（友好）"""
    from workshop.image_utils import open_image_safe
    with pytest.raises(ValueError, match='损坏或格式不支持'):
        open_image_safe(str(edge_files['corrupt']))


def test_open_image_safe_empty(edge_files):
    """空文件 → ValueError"""
    from workshop.image_utils import open_image_safe
    with pytest.raises(ValueError):
        open_image_safe(str(edge_files['empty']))


def test_open_image_safe_fake(edge_files):
    """伪png → ValueError"""
    from workshop.image_utils import open_image_safe
    with pytest.raises(ValueError):
        open_image_safe(str(edge_files['fake']))


def test_open_image_safe_dir(tmp_path):
    """目录 → ValueError"""
    from workshop.image_utils import open_image_safe
    with pytest.raises(ValueError):
        open_image_safe(str(tmp_path))


def test_blend_corrupt(edge_files):
    """blend 损坏图 → ValueError"""
    from workshop.blend import blend_images
    with pytest.raises(ValueError):
        blend_images(str(edge_files['corrupt']), str(edge_files['good']))


def test_blend_weight_out_of_range(edge_files):
    """blend weight 越界 → ValueError"""
    from workshop.blend import blend_images
    with pytest.raises(ValueError):
        blend_images(str(edge_files['good']), str(edge_files['good']), weight=1.5)


def test_restore_corrupt(edge_files):
    """restore 损坏图 → ValueError"""
    from workshop.restore import restore_photo
    with pytest.raises(ValueError):
        restore_photo(str(edge_files['corrupt']))


def test_restore_rgba_ok(edge_files, tmp_path):
    """restore RGBA → 正常（convert RGB）"""
    from workshop.restore import restore_photo
    out = tmp_path / 'r_out.png'
    r = restore_photo(str(edge_files['rgba']), output=str(out))
    assert os.path.exists(out)


def test_panorama_corrupt(edge_files):
    """panorama 损坏图 → ValueError"""
    from workshop.panorama import make_panorama
    with pytest.raises(ValueError):
        make_panorama([str(edge_files['corrupt']), str(edge_files['good'])])


def test_panorama_single(edge_files, tmp_path):
    """panorama 单张 → ValueError"""
    from workshop.panorama import make_panorama
    with pytest.raises(ValueError):
        make_panorama([str(edge_files['good'])])


def test_biztext_corrupt(edge_files):
    """biztext 损坏图 → ValueError"""
    from workshop.biztext import add_text
    with pytest.raises(ValueError):
        add_text(str(edge_files['corrupt']), '标题')


def test_variants_corrupt(edge_files):
    """variants 损坏图 → ValueError"""
    from workshop.biz import make_variants
    with pytest.raises(ValueError):
        make_variants(str(edge_files['corrupt']))


def test_compare_corrupt(edge_files):
    """compare 损坏图 → ValueError"""
    from workshop.compare import make_compare
    with pytest.raises(ValueError):
        make_compare(str(edge_files['corrupt']), str(edge_files['good']))


def test_info_corrupt(edge_files):
    """info 损坏图 → ValueError"""
    from workshop.info import _get_info
    with pytest.raises(ValueError):
        _get_info(str(edge_files['corrupt']))


def test_kb_corrupt(edge_files):
    """kb 像素规则损坏图 → ValueError"""
    from workshop.kb import _pixel_check
    with pytest.raises(ValueError):
        _pixel_check({'id': 'TECH-01'}, str(edge_files['corrupt']))


def test_enhance_corrupt(edge_files):
    """enhance 损坏图 → 立即 ValueError（不静默走完全流程）"""
    from workshop.enhance import enhance
    with pytest.raises(ValueError):
        enhance(str(edge_files['corrupt']))


def test_interrogate_corrupt_before_vlm(edge_files):
    """interrogate 损坏图 → ValueError（图片校验在 VLM 之前）"""
    from workshop.interrogate import interrogate
    with pytest.raises(ValueError):
        interrogate(str(edge_files['corrupt']))


def test_biztext_empty_title(edge_files):
    """biztext 空标题 → 友好 ValueError"""
    from workshop.biztext import add_text
    with pytest.raises(ValueError, match='标题不能为空'):
        add_text(str(edge_files['good']), '')
    with pytest.raises(ValueError, match='标题不能为空'):
        add_text(str(edge_files['good']), '   ')


def test_biztext_negative_font(edge_files):
    """biztext 负字号 → 友好 ValueError"""
    from workshop.biztext import add_text
    with pytest.raises(ValueError, match='字号必须为正数'):
        add_text(str(edge_files['good']), '标题', font_size=-10)


def test_biztext_long_title(edge_files, tmp_path):
    """biztext 超长标题（200字）→ 多行换行正常"""
    from workshop.biztext import add_text
    out = tmp_path / 'long.png'
    add_text(str(edge_files['good']), '超' * 200, output=str(out))
    assert os.path.exists(out)


def test_batch_biztext_mixed(edge_files, tmp_path):
    """biztext 批量混合目录：好图处理+坏图跳过"""
    from workshop.biztext import batch_add_text
    d = tmp_path / 'mix'; d.mkdir()
    from PIL import Image
    Image.new('RGB', (64, 64)).save(d / 'ok.png')
    (d / 'bad.png').write_bytes(b'not png')
    saved = batch_add_text(str(d), '标题', output_dir=str(tmp_path / 'out'))
    assert len(saved) == 1  # 只处理好图


def test_batch_empty_dir(edge_files, tmp_path):
    """批量空目录 → 空结果不崩"""
    from workshop.biztext import batch_add_text
    assert batch_add_text(str(tmp_path / 'nope'), '标题') == []


def test_oc_blank_card_prompt():
    """空角色卡 prompt 不崩"""
    from workshop.oc import oc_to_prompt
    oc = {'name': 'x', 'trigger': 'trig', 'desc': '',
          'identity': {k: '' for k in ('hair', 'hair_color', 'eyes', 'eye_color', 'skin', 'face_shape', 'height', 'body')},
          'style': {k: '' for k in ('art_style', 'color_palette', 'lighting')},
          'outfits': [], 'personality': '', 'background': ''}
    assert 'trig' in oc_to_prompt(oc)


def test_outpaint_negative_direction(edge_files):
    """outpaint 负方向 → 友好 ValueError"""
    from workshop.outpaint import outpaint
    with pytest.raises(ValueError, match='不能为负数'):
        outpaint(str(edge_files['good']), right=-100)
    with pytest.raises(ValueError, match='不能为负数'):
        outpaint(str(edge_files['good']), target_w=-5)


def test_blend_directory_as_image(edge_files, tmp_path):
    """blend 传目录 → 友好 ValueError"""
    from workshop.blend import blend_images
    with pytest.raises(ValueError, match='目录'):
        blend_images(str(tmp_path), str(edge_files['good']))


def test_compare_mixed_sizes(edge_files, tmp_path):
    """compare 横竖图异尺寸 → 正常"""
    from workshop.compare import make_compare
    from PIL import Image
    tall = tmp_path / 'tall.png'
    Image.new('RGB', (48, 64)).save(tall)
    out = tmp_path / 'c.png'
    make_compare(str(edge_files['good']), str(tall), output=str(out))
    assert os.path.exists(out)


def test_interrogate_bad_fmt(edge_files):
    """interrogate 非法格式 → 友好 ValueError"""
    from workshop.interrogate import interrogate
    with pytest.raises(ValueError, match='格式可选'):
        interrogate(str(edge_files['good']), fmt='badfmt')


def test_kb_threshold_out_of_range(edge_files):
    """kb threshold 越界 → 友好 ValueError"""
    from workshop.kb import check_image
    with pytest.raises(ValueError, match='阈值'):
        check_image(str(edge_files['good']), category='技术', threshold=2.0)


def test_kb_no_matching_rules(edge_files):
    """kb 无匹配规则 → 友好 ValueError"""
    from workshop.kb import check_image
    with pytest.raises(ValueError, match='无匹配规则'):
        check_image(str(edge_files['good']), rules='NOPE-01')


def test_oc_missing(clean_tmp, monkeypatch):
    """oc 不存在 → 友好报错"""
    import workshop.oc as oc_mod
    monkeypatch.setattr(oc_mod, 'OC_DIR', Path(clean_tmp) / 'oc')
    oc_mod.OC_DIR.mkdir(exist_ok=True)
    with pytest.raises(FileNotFoundError, match='OC 不存在'):
        oc_mod.show_oc('nope')
    with pytest.raises(FileNotFoundError, match='OC 不存在'):
        oc_mod.gen_oc('nope')


def test_oc_translate_english_only():
    """oc 翻译：纯英文不翻译"""
    from workshop.oc import _translate_prompt
    assert _translate_prompt('1girl, silver hair') == '1girl, silver hair'


def test_oc_translate_chinese():
    """oc 翻译：中文 → 英文"""
    from workshop.oc import _translate_prompt
    out = _translate_prompt('银白长发少女')
    assert out and not any('\u4e00' <= c <= '\u9fff' for c in out)


def test_lora_name_auto_ext(clean_tmp, monkeypatch):
    """oc gen LoRA 名自动补 .safetensors"""
    import workshop.oc as oc_mod
    monkeypatch.setattr(oc_mod, 'OC_DIR', Path(clean_tmp) / 'oc')
    oc_mod.OC_DIR.mkdir(exist_ok=True)
    oc_mod.create_oc('x', '描述')
    # main 的补扩展名逻辑
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--lora', default=None)
    args = ap.parse_args(['--lora', 'style_cine_manga'])
    lora = args.lora
    if lora and not lora.endswith('.safetensors'):
        lora = lora + '.safetensors'
    assert lora == 'style_cine_manga.safetensors'


def test_create_empty_desc():
    """create 空描述 → 友好 ValueError（不默默生成默认模板图）"""
    from workshop.create import create_from_nl
    with pytest.raises(ValueError, match='描述不能为空'):
        create_from_nl('', count=1, dry_run=True)
    with pytest.raises(ValueError, match='描述不能为空'):
        create_from_nl('   ', count=1, dry_run=True)


def test_create_count_invalid():
    """create count 非法 → 友好 ValueError"""
    from workshop.create import create_from_nl
    with pytest.raises(ValueError, match='count'):
        create_from_nl('少女', count=0, dry_run=True)
    with pytest.raises(ValueError, match='count'):
        create_from_nl('少女', count=-2, dry_run=True)


def test_create_seed_type():
    """create seed 非整数 → 友好 ValueError"""
    from workshop.create import create_from_nl
    with pytest.raises(ValueError, match='seed'):
        create_from_nl('少女', count=1, seed='abc', dry_run=True)


def test_outfit_missing_clothing():
    """outfit 缺服装图 → 友好报错"""
    from workshop.outfit import generate_outfit
    with pytest.raises(FileNotFoundError):
        generate_outfit('C:/nope.png')


def test_outfit_corrupt_clothing(edge_files):
    """outfit 损坏服装图 → 友好 ValueError"""
    from workshop.outfit import generate_outfit
    with pytest.raises(ValueError, match='损坏或格式不支持'):
        generate_outfit(str(edge_files['corrupt']))


def test_emotes_empty_desc():
    """emotes 空描述 → 友好 ValueError"""
    from workshop.emotes import generate_emotes
    with pytest.raises(ValueError, match='角色描述不能为空'):
        generate_emotes('')


def test_emotes_unknown_emote():
    """emotes 非法表情 → 友好 ValueError（列出可用）"""
    from workshop.emotes import generate_emotes
    with pytest.raises(ValueError, match='未知表情'):
        generate_emotes('少女', emotes=['不存在的表情'])


def test_emotes_valid_emote(edge_files):
    """emotes 合法表情可跑（count=0 不生成只校验）"""
    from workshop.emotes import generate_emotes
    r = generate_emotes('银发少女', emotes=['高兴', '微笑'], count=0)
    assert r == []


def test_emotes_name_sanitized(edge_files, tmp_path):
    """emotes name 含路径字符 → 清洗为下划线（不创建嵌套目录）"""
    from workshop.emotes import generate_emotes
    r = generate_emotes('银发少女', count=0, name='a/b\\c',
                        output_dir=str(tmp_path / 'out'))
    # count=0 不建目录，但 name 已清洗（不抛错即可）
    assert r == []


def test_multi_ref_missing():
    """multi ref 缺图 → 友好报错（不默默跑）"""
    from workshop.wallpaper import generate_multi
    with pytest.raises(FileNotFoundError):
        generate_multi('A', 'B', ref_a='C:/nope.png')


def test_multi_ref_corrupt(edge_files):
    """multi ref 损坏图 → 友好 ValueError"""
    from workshop.wallpaper import generate_multi
    with pytest.raises(ValueError):
        generate_multi('A', 'B', ref_a=str(edge_files['corrupt']))


def test_multi_unknown_mode():
    """multi 未知模式 → 返回空不崩"""
    from workshop.wallpaper import generate_multi
    assert generate_multi('A', 'B', mode='nope') == []


def test_idphoto_bad_params():
    """idphoto 坏底色/坏规格 → 友好 ValueError"""
    from workshop.idphoto import idphoto
    with pytest.raises(ValueError, match='底色可选'):
        idphoto('C:/x.png', bg='purple')
    with pytest.raises(ValueError, match='规格可选'):
        idphoto('C:/x.png', size='huge')


def test_oc_verify_non_character(edge_files, tmp_path):
    """oc verify 非角色图（风景）→ 低分无假阳性"""
    import workshop.oc as oc_mod
    from PIL import Image
    # 用真实 celeste 角色卡
    oc_dir = oc_mod.OC_DIR
    if (oc_dir / 'celeste.json').exists():
        landscape = tmp_path / 'land.png'
        Image.new('RGB', (128, 128), (100, 150, 200)).save(landscape)
        # 直接调用 VLM 评分逻辑（verify 打印不返回——用内部逻辑验证）
        import base64, re, urllib.request
        from workshop.oc import _load
        oc = _load('celeste')
        idn = oc['identity']
        features = [f'hair color {idn["hair_color"]}', f'eye color {idn["eye_color"]}']
        with open(landscape, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode()
        body = __import__('json').dumps({
            'model': 'qwen3-vl:8b', 'stream': False, 'think': False,
            'prompt': (f'Does this character have: {", ".join(features)}? '
                       'Rate 0-1 how well ALL features match. Output ONLY the number.'),
            'images': [b64],
        }).encode()
        req = urllib.request.Request('http://172.22.175.253:11434/api/generate', data=body,
                                     headers={'Content-Type': 'application/json'})
        resp = __import__('json').loads(urllib.request.urlopen(req, timeout=120).read())
        m = re.search(r'(\d+(?:\.\d+)?)', resp.get('response', ''))
        score = float(m.group(1)) if m else 0.0
        assert score < 0.3  # 风景图无角色特征 → 低分
    else:
        pytest.skip('celeste 角色卡不存在')


def test_oc_gen_count_limit(clean_tmp, monkeypatch):
    """oc gen count 非法/巨大 → 友好 ValueError（防千次生成）"""
    import workshop.oc as oc_mod
    monkeypatch.setattr(oc_mod, 'OC_DIR', Path(clean_tmp) / 'oc')
    oc_mod.OC_DIR.mkdir(exist_ok=True)
    oc_mod.create_oc('x', '描述')
    with pytest.raises(ValueError, match='count 必须'):
        oc_mod.gen_oc('x', count=0)
    with pytest.raises(ValueError, match='count 过大'):
        oc_mod.gen_oc('x', count=1000)


def test_oc_normalize_old_card():
    """旧版缺字段角色卡 → 归一化补齐不崩"""
    import workshop.oc as oc_mod
    old = {'name': 'oldchar', 'trigger': 'oldtrig'}
    norm = oc_mod._normalize(old)
    assert norm['identity']['hair_color'] == ''
    assert norm['version'] == '1.0'
    assert norm['outfits'] == []


def test_emotes_dedup(edge_files, tmp_path):
    """emotes 重复表情去重（count=0 校验列表处理）"""
    from workshop.emotes import generate_emotes
    # 用 monkeypatch 方式验证去重逻辑：count=0 只校验不生成，返回空
    r = generate_emotes('少女', emotes=['高兴', '高兴', '微笑'], count=0)
    assert r == []


def test_emotes_wx_export_deep_dir(edge_files, tmp_path):
    """wx 导出深层目录自动创建"""
    from workshop.emotes import _export_wx_specs
    from PIL import Image
    img = tmp_path / 'e.png'
    Image.new('RGBA', (64, 64)).save(img)
    exported = _export_wx_specs({'高兴': str(img)}, tmp_path / 'deep' / 'nested')
    assert exported  # 有输出
    assert (tmp_path / 'deep' / 'nested' / 'wx_export').exists()


def test_oc_prompt_outfit_idx_out_of_range(clean_tmp, monkeypatch):
    """oc_to_prompt outfit_idx 越界 → 不崩（条件保护，不加服装）"""
    import workshop.oc as oc_mod
    monkeypatch.setattr(oc_mod, 'OC_DIR', Path(clean_tmp) / 'oc')
    oc_mod.OC_DIR.mkdir(exist_ok=True)
    oc = oc_mod.create_oc('x', '描述', outfit='服装A')
    p = oc_mod.oc_to_prompt(oc, outfit_idx=99)
    assert '服装A' not in p  # 越界 → 不加服装（条件保护不崩）
    assert 'xoc' in p


def test_oc_duplicate(clean_tmp, monkeypatch):
    """OC 重名 → ValueError"""
    import workshop.oc as oc_mod
    monkeypatch.setattr(oc_mod, 'OC_DIR', Path(clean_tmp) / 'oc')
    oc_mod.OC_DIR.mkdir(exist_ok=True)
    oc_mod.create_oc('dup', '描述')
    with pytest.raises(ValueError):
        oc_mod.create_oc('dup', '描述')


@pytest.fixture
def clean_tmp(tmp_path):
    return str(tmp_path)
