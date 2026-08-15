#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/oc.py — 原创角色库（B-oc）v1.0
========================================
原创 OC 设计（艺术地基）：角色卡管理 + 角色图生成 + 一致性验证。
原创性铁律：不基于任何现有 IP 角色——所有特征从零设计。

用法:
  python -m agents workshop oc list                    # 列出所有 OC
  python -m agents workshop oc create <名称> --desc "..."  # 创建角色卡
  python -m agents workshop oc show <名称>             # 查看角色卡
  python -m agents workshop oc gen <名称> [--scene "..."]  # 生成角色图（角色卡→prompt）
  python -m agents workshop oc verify <名称>           # 一致性验证（多张图 vs 参考）
"""

import argparse, json, os, sys, time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
OC_DIR = Path(__file__).resolve().parent / 'oc_library'
OC_DIR.mkdir(exist_ok=True)

# 角色卡字段模板
OC_TEMPLATE = {
    "name": "",
    "trigger": "",
    "desc": "",
    "identity": {  # 身份核心（LoRA 必须锁定的特征）
        "hair": "", "hair_color": "", "eyes": "", "eye_color": "",
        "skin": "", "face_shape": "", "height": "", "body": "",
        # 吸引力设计（CHAR-APPEAL 五原则落地）
        "concept_anchor": "",  # 概念锚拟人（武器/花/兽/星——拟人化来源）
        "memory_point": "",  # 记忆点（silhouette/color_anchor/symbol/hair_sign/weapon/accessory/animal）
        "worldview": "",  # 世界观锚（fantasy/military/sci-fi/school/ancient/modern/postapoc/myth）
    },
    "style": {  # 画风（角色专属风格描述）
        "art_style": "", "color_palette": "", "lighting": "",
    },
    "outfits": [],  # 服装列表
    "personality": "",  # 性格（影响表情/姿势 prompt）
    "background": "",  # 背景故事
    "created": "",
    "version": "1.0",
}


def _ts():
    return time.strftime('%Y-%m-%d %H:%M')


def _normalize(oc):
    """角色卡字段归一化（旧版/缺字段 → 默认值补齐，向后兼容）。"""
    default = json.loads(json.dumps(OC_TEMPLATE))
    for k, v in default.items():
        if k not in oc:
            oc[k] = v
        elif isinstance(v, dict) and isinstance(oc[k], dict):
            for k2, v2 in v.items():
                if k2 not in oc[k]:
                    oc[k][k2] = v2
    return oc


def _load(name):
    p = OC_DIR / f'{name}.json'
    if not p.exists():
        raise FileNotFoundError(f'OC 不存在: {name}（可用: {list_oc_names()}）')
    with open(p, encoding='utf-8') as f:
        return _normalize(json.load(f))


def _save(oc):
    with open(OC_DIR / f"{oc['name']}.json", 'w', encoding='utf-8') as f:
        json.dump(oc, f, ensure_ascii=False, indent=2)


def list_oc_names():
    return sorted(p.stem for p in OC_DIR.glob('*.json'))


def list_oc():
    names = list_oc_names()
    if not names:
        print('📭 OC 库为空——用 `oc create <名称> --desc "..."` 创建')
        return
    print(f'\n👤 原创角色库（{len(names)} 个 OC）')
    for n in names:
        try:
            oc = _load(n)
            print(f'  - {n}: {oc.get("identity", {}).get("hair_color", "")}发 '
                  f'{oc.get("identity", {}).get("eye_color", "")}瞳 '
                  f'[{oc.get("trigger", "")}] {oc.get("desc", "")[:40]}')
        except Exception:
            print(f'  - {n}: (读取失败)')


def create_oc(name, desc, hair='', hair_color='', eyes='', eye_color='',
              outfit='', trigger=None, art_style='',
              concept_anchor='', memory_point='', worldview=''):
    """创建角色卡（吸引力三字段：概念锚拟人/记忆点/世界观）。"""
    if name in list_oc_names():
        raise ValueError(f'OC 已存在: {name}')
    oc = json.loads(json.dumps(OC_TEMPLATE))  # 深拷贝
    oc['name'] = name
    oc['trigger'] = trigger or f'{name[:4].lower()}oc'
    oc['desc'] = desc
    oc['identity']['hair'] = hair
    oc['identity']['hair_color'] = hair_color
    oc['identity']['eyes'] = eyes
    oc['identity']['eye_color'] = eye_color
    oc['identity']['concept_anchor'] = concept_anchor
    oc['identity']['memory_point'] = memory_point
    oc['identity']['worldview'] = worldview
    oc['style']['art_style'] = art_style
    if outfit:
        oc['outfits'].append(outfit)
    oc['created'] = _ts()
    _save(oc)
    print(f'✅ OC 创建: {name}（触发词: {oc["trigger"]}）')
    return oc


def show_oc(name):
    oc = _load(name)
    print(f'\n👤 {oc["name"]}（v{oc["version"]}）触发词: {oc["trigger"]}')
    print(f'  描述: {oc["desc"]}')
    idn = oc['identity']
    print(f'  身份: {idn["hair_color"]}{idn["hair"]} / {idn["eye_color"]}{idn["eyes"]} / '
          f'{idn["skin"] or "默认"}肤 / {idn["height"] or "?"}cm')
    if idn.get('concept_anchor'):
        print(f'  概念锚: {idn["concept_anchor"]}')
    if idn.get('memory_point'):
        print(f'  记忆点: {idn["memory_point"]}')
    if idn.get('worldview'):
        print(f'  世界观: {idn["worldview"]}')
    print(f'  画风: {oc["style"]["art_style"] or "（未设）"}')
    if oc['outfits']:
        print(f'  服装: {"; ".join(oc["outfits"])}')
    if oc['personality']:
        print(f'  性格: {oc["personality"]}')
    if oc['background']:
        print(f'  背景: {oc["background"]}')
    return oc


def oc_to_prompt(oc, scene='', outfit_idx=0):
    """角色卡 → 生成 prompt（身份核心 + 画风 + 场景）。"""
    idn = oc['identity']
    parts = [oc['trigger'], '1girl' if '女' in oc.get('desc', '') or 'girl' in oc.get('desc', '').lower() else '1boy']
    # 子部件词库集成：identity 值是词库名（如 body='curvy'）→ 展开描述
    try:
        from workshop.wardrobe import BODY_PARTS, build_body_parts
        _body_map = {'body': 'body_detail', 'face_shape': 'face_shape',
                     'eyes': 'eye_style', 'hair': 'hair_style'}
        _dict_map = {'body': 'body', 'face_shape': 'face', 'eyes': 'eyes', 'hair': 'hair'}
        _kw = {}
        for _k, _kwk in _body_map.items():
            _v = idn.get(_k, '')
            if _v in BODY_PARTS.get(_dict_map[_k], {}):
                _kw[_kwk] = _v
        if _kw:
            parts.append(build_body_parts(**_kw))
    except ImportError:
        pass
    if idn['hair_color']:
        parts.append(f'{idn["hair_color"]} hair')
    if idn['hair']:
        parts.append(idn['hair'])
    if idn['eye_color']:
        parts.append(f'{idn["eye_color"]} eyes')
    # 吸引力设计展开（CHAR-APPEAL 五原则：记忆点/世界观/概念锚拟人）
    try:
        from workshop.wardrobe import MEMORY_POINTS, WORLDVIEW_ANCHORS, RACIAL_FEATURES
        if idn.get('memory_point'):
            for _m in str(idn['memory_point']).split(','):
                _m = _m.strip()
                if _m in MEMORY_POINTS:
                    parts.append(MEMORY_POINTS[_m])
        if idn.get('worldview') and idn['worldview'] in WORLDVIEW_ANCHORS:
            parts.append(WORLDVIEW_ANCHORS[idn['worldview']])
        if idn.get('concept_anchor'):
            _c = idn['concept_anchor'].strip()
            if _c in RACIAL_FEATURES:
                parts.append(RACIAL_FEATURES[_c])
            else:
                parts.append(f'{_c} concept, {_c} motifs integrated into design')
    except ImportError:
        pass
    if oc['style']['art_style']:
        parts.append(oc['style']['art_style'])
    if oc['outfits'] and outfit_idx < len(oc['outfits']):
        outfit = oc['outfits'][outfit_idx]
        # 衣品词库集成：outfit 是风格名（如 gothic/lolita）→ 展开完整设计描述
        try:
            from workshop.wardrobe import WARDROBE_STYLES, build_outfit
            if outfit in WARDROBE_STYLES:
                outfit = build_outfit(outfit)
        except ImportError:
            pass
        parts.append(outfit)
    if scene:
        parts.append(scene)
    return ', '.join(p for p in parts if p)


def _translate_prompt(text):
    """中文 prompt → 英文 tag（SDXL 需要；含 CJK 才翻译）。"""
    import re
    if not re.search(r'[\u4e00-\u9fff]', text):
        return text
    try:
        import json as _json
        import urllib.request
        body = _json.dumps({
            'model': 'qwen3.5:9b', 'stream': False, 'think': False,
            'prompt': (f'Translate this image prompt to English danbooru-style tags. '
                       f'Keep existing English words. Output ONLY the translation.\n{text}'),
        }).encode()
        req = urllib.request.Request('http://172.22.175.253:11434/api/generate', data=body,
                                     headers={'Content-Type': 'application/json'})
        resp = _json.loads(urllib.request.urlopen(req, timeout=120).read())
        out = resp.get('response', '').strip()
        return out if out else text
    except Exception:
        return text  # 翻译失败用原文（SDXL 对中文 tag 容忍度低但至少有内容）


def gen_oc(name, scene='', count=1, seed=-1, output_dir=None, lora=None,
           lora_weight=0.9):
    """生成角色图（角色卡 → prompt → SDXL，可选自有风格 LoRA）。"""
    oc = _load(name)
    # count 上限校验（误传巨大 count 会触发长时间批量生成）
    if count is None or count < 1:
        raise ValueError(f'count 必须 >= 1（当前: {count}）')
    if count > 50:
        raise ValueError(f'count 过大（{count}）——单次最多 50 张，分批生成')
    prompt = oc_to_prompt(oc, scene)
    prompt_en = _translate_prompt(prompt)
    print(f'🎨 生成 {name}（{count} 张）prompt: {prompt_en[:80]}...')
    out_root = Path(output_dir or (PROJECT / 'outputs' / f"oc_{name}_{time.strftime('%Y%m%d_%H%M%S')}"))
    out_root.mkdir(parents=True, exist_ok=True)
    saved = []
    for i in range(count):
        try:
            if lora:
                from workshop.style_distill import _gen_sdxl_lora
                out = str(out_root / f'{name}_{i+1:02d}.png')
                _gen_sdxl_lora(prompt_en, out, seed + i * 17 if seed > 0 else int(time.time()) % 99999 + i,
                               lora_name=lora, lora_weight=lora_weight)
            else:
                from workshop.style_distill import _gen_sdxl
                out = str(out_root / f'{name}_{i+1:02d}.png')
                _gen_sdxl(prompt_en, out, seed + i * 17 if seed > 0 else int(time.time()) % 99999 + i)
            saved.append(out)
        except Exception as e:
            print(f'  ⚠️ 第{i+1}张失败: {str(e)[:80]}')
    print(f'📁 输出: {out_root}（{len(saved)} 张）')
    return saved


def verify_oc(name, images, threshold=0.6):
    """一致性验证：多张图 vs 角色卡特征（VLM 逐特征核对）。"""
    oc = _load(name)
    idn = oc['identity']
    features = []
    if idn['hair_color']:
        features.append(f'hair color {idn["hair_color"]}')
    if idn['eye_color']:
        features.append(f'eye color {idn["eye_color"]}')
    if idn['hair']:
        features.append(f'hairstyle {idn["hair"]}')
    if not features:
        print('  ⚠️ 角色卡无身份特征，无法验证')
        return
    feat_str = ', '.join(features)
    print(f'🔍 一致性验证: {name}（特征: {feat_str}）')
    try:
        import base64, re, urllib.request
        for img in images:
            with open(img, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode()
            body = json.dumps({
                'model': 'qwen3-vl:8b', 'stream': False, 'think': False,
                'prompt': (f'Does this character have: {feat_str}? '
                           'Rate 0-1 how well ALL features match. Output ONLY the number.'),
                'images': [b64],
            }).encode()
            req = urllib.request.Request('http://172.22.175.253:11434/api/generate', data=body,
                                         headers={'Content-Type': 'application/json'})
            resp = json.loads(urllib.request.urlopen(req, timeout=120).read())
            m = re.search(r'(\d+(?:\.\d+)?)', resp.get('response', ''))
            score = float(m.group(1)) if m else 0.0
            ok = score >= threshold
            print(f'  {"✅" if ok else "❌"} {os.path.basename(img)}: {score:.2f}')
    except Exception as e:
        print(f'  ⚠️ 验证失败: {str(e)[:100]}')


def verify_consistency_paths(images, threshold=0.6):
    """系列一致性：首张做锚，VLM 对比其余（同角色/同风格？）。

    Returns:
        (ok, detail)
    """
    import base64, re
    try:
        with open(images[0], 'rb') as f:
            anchor_b64 = base64.b64encode(f.read()).decode()
    except Exception as e:
        return False, f'锚图读取失败: {str(e)[:50]}'
    scores = []
    for img in images[1:]:
        try:
            with open(img, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode()
            body = json.dumps({
                'model': 'qwen3-vl:8b', 'stream': False, 'think': False,
                'prompt': ('Two images: first is anchor, second is candidate. '
                           'Are they the same character with consistent style? '
                           'Rate 0-1 (1=same character/style). Output ONLY the number.'),
                'images': [anchor_b64, b64],
            }).encode()
            req = urllib.request.Request('http://172.22.175.253:11434/api/generate', data=body,
                                         headers={'Content-Type': 'application/json'})
            resp = json.loads(urllib.request.urlopen(req, timeout=120).read())
            m = re.search(r'(\d+(?:\.\d+)?)', resp.get('response', ''))
            score = float(m.group(1)) if m else 0.0
            scores.append(score)
        except Exception as e:
            scores.append(0.0)
    avg = sum(scores) / len(scores) if scores else 0.0
    ok = avg >= threshold
    detail = f'系列一致性 {avg:.2f}（vs 锚图，阈值 {threshold}）'
    return ok, detail


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop oc', description='原创角色库（OC 设计/生成/验证）')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p_list = sub.add_parser('list', help='列出所有 OC')
    p_create = sub.add_parser('create', help='创建角色卡')
    p_create.add_argument('name')
    p_create.add_argument('--desc', required=True, help='角色描述')
    p_create.add_argument('--hair', default='', help='发型')
    p_create.add_argument('--hair-color', default='', help='发色')
    p_create.add_argument('--eyes', default='', help='眼型')
    p_create.add_argument('--eye-color', default='', help='瞳色')
    p_create.add_argument('--outfit', default='', help='初始服装（风格名如 gothic 自动展开）')
    p_create.add_argument('--trigger', default=None, help='触发词')
    p_create.add_argument('--art-style', default='', help='画风')
    p_create.add_argument('--concept', default='', help='概念锚拟人（白狐/剑/蔷薇/星——拟人化来源）')
    p_create.add_argument('--memory', default='', help='记忆点（silhouette/color_anchor/symbol/hair_sign/weapon/accessory/animal，逗号分隔）')
    p_create.add_argument('--worldview', default='', help='世界观（fantasy/military/sci-fi/school/ancient/modern/postapoc/myth）')

    p_show = sub.add_parser('show', help='查看角色卡')
    p_show.add_argument('name')

    p_gen = sub.add_parser('gen', help='生成角色图')
    p_gen.add_argument('name')
    p_gen.add_argument('--scene', default='', help='场景描述')
    p_gen.add_argument('--count', type=int, default=1)
    p_gen.add_argument('--seed', type=int, default=-1)
    p_gen.add_argument('--output', default=None)
    p_gen.add_argument('--lora', default=None, help='自有风格 LoRA 名（如 style_cine_manga）')
    p_gen.add_argument('--lora-weight', type=float, default=0.9)

    p_verify = sub.add_parser('verify', help='一致性验证')
    p_verify.add_argument('name')
    p_verify.add_argument('images', nargs='+', help='图片路径')

    p_emotes = sub.add_parser('emotes', help='一键表情（角色卡身份 → 表情包）')
    p_emotes.add_argument('name')
    p_emotes.add_argument('--set', default=None, help='表情集预设（normal/sweet/mischief/ecchi/action）')
    p_emotes.add_argument('--count', type=int, default=1)
    p_emotes.add_argument('--outfit', default=None, help='服装风格名（wardrobe：gothic 等）')
    p_emotes.add_argument('--output', default=None, help='输出目录')

    args = ap.parse_args(argv)

    try:
        if args.cmd == 'list':
            list_oc()
        elif args.cmd == 'create':
            create_oc(args.name, args.desc, args.hair, args.hair_color,
                      args.eyes, args.eye_color, args.outfit, args.trigger,
                      args.art_style, args.concept, args.memory, args.worldview)
        elif args.cmd == 'show':
            show_oc(args.name)
        elif args.cmd == 'gen':
            # LoRA 名自动补 .safetensors（ComfyUI LoraLoader 需要完整文件名）
            lora_name = args.lora
            if lora_name and not lora_name.endswith('.safetensors'):
                lora_name = lora_name + '.safetensors'
            gen_oc(args.name, args.scene, args.count, args.seed, args.output,
                   lora=lora_name, lora_weight=args.lora_weight)
        elif args.cmd == 'verify':
            verify_oc(args.name, args.images)
        elif args.cmd == 'emotes':
            # 角色卡身份 → 一键表情（emotes 联动）
            oc_ = _load(args.name)
            prompt = oc_to_prompt(oc_)
            from workshop.emotes import generate_emotes, EMOTE_SETS
            generate_emotes(prompt, name=args.name, count=args.count,
                            output_dir=args.output, outfit_style=args.outfit,
                            emotes=list(EMOTE_SETS[args.set]) if args.set and args.set in EMOTE_SETS else None)
        return 0
    except Exception as e:
        print(f'❌ oc 失败: {str(e)[:150]}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
