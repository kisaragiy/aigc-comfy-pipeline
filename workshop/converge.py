#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/converge.py — 意图逼近工作流 v1.0
==========================================
目标：把"描述→出图"的单次博弈变成多轮校准，收敛到"优秀画师商业图"。

核心思想（黑盒需求打法 × 图像意图）：
- 语言与画面之间存在鸿沟，prompt 永远是不完整编码
- 不追求一次猜中，追求快速收敛（猜错成本最小化）
- 每轮交付带"可修正接口"：用户指认方向，不描述抽象感觉

轮次:
  R1 锚点射击: 4 个风格锚点（动漫番剧/电影感/游戏原画/精致插画）各出候选
  R2 变体矩阵: 锁定锚点后，构图×光影 4 变体
  R3 微调:     细节修正（表情/姿势/服装/氛围）
  之后:        pick 进入收敛（小步变体），或 done 输出 best

用法:
  python -m agents workshop converge "银发少女，樱花树下，逆光" [--ref 参考图] [--model sdxl|flux]
  python -m agents workshop converge --pick 2 [--notes "头发要更长，色调偏冷"]
  python -m agents workshop converge --pick 3 [--notes "换夜景"]] [--round 3]
  python -m agents workshop converge --status
  python -m agents workshop converge --done
"""

import argparse, json, os, re, subprocess, sys, time, urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
STATE_PATH = PROJECT / 'workspace' / 'converge_state.json'
OUT_BASE = PROJECT / 'workspace' / 'converge'
os.makedirs(OUT_BASE, exist_ok=True)

# ── LLM (本地 ollama，零成本) ──
OLLAMA_CANDIDATES = ['http://127.0.0.1:11434', 'http://172.22.175.253:11434']
_OLLAMA = None

def _no_proxy_opener():
    """urllib 显式禁用代理（环境 http_proxy 会劫持内网 ollama）"""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))

def _ollama_base():
    global _OLLAMA
    if _OLLAMA:
        return _OLLAMA
    opener = _no_proxy_opener()
    for base in OLLAMA_CANDIDATES:
        try:
            opener.open(base + '/api/tags', timeout=3)
            _OLLAMA = base
            return base
        except Exception:
            continue
    _OLLAMA = ''
    return ''

def _llm(prompt, system='', timeout=180, model='qwen3:14b'):
    base = _ollama_base()
    if not base:
        return ''
    body = json.dumps({
        'model': model, 'prompt': prompt, 'system': system,
        'stream': False, 'think': False,
        'options': {'temperature': 0.7},
    }).encode()
    req = urllib.request.Request(base + '/api/generate', data=body,
                                 headers={'Content-Type': 'application/json'})
    resp = json.loads(_no_proxy_opener().open(req, timeout=timeout).read())
    return resp.get('response', '')

def _clean(text):
    """去 think 链/前后缀，兼容 qwen 输出"""
    text = re.sub(r'<think>[\s\S]*?</think>', '', text)
    text = re.sub(r'^(thinking|Thought|分析|思考)[:：]?[\s\S]*?\n', '', text, flags=re.I)
    return text.strip()

# ── 状态管理 ──

def load_state():
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {'round': 0, 'history': [], 'pick': None, 'notes': [], 'best': None}

def save_state(st):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding='utf-8')

# ── R1: 锚点射击 ──

STYLE_ANCHORS = [
    ('动漫番剧', 'high-quality anime series key visual, clean lineart, vibrant cel shading, detailed eyes, anime style'),
    ('电影感', 'cinematic movie still, dramatic lighting, shallow depth of field, film grain, cinematic composition'),
    ('游戏原画', 'AAA game character art, concept art quality, rich detail, dramatic rim light, game splash art'),
    ('精致插画', 'polished digital illustration, elegant color palette, delicate rendering, professional illustration'),
]

def _build_anchor_prompts(desc, ref_analysis=''):
    """用 LLM 把用户描述 × 4 风格锚点 融合成 4 个完整 prompt"""
    prompts = {}
    ref_note = f'\n参考图特征: {ref_analysis[:300]}' if ref_analysis else ''
    for name, style in STYLE_ANCHORS:
        out = _llm(f'''你是商业级插画师。用户想画: {desc}{ref_note}

请为"{name}"风格写一条完整英文绘图 prompt（1-2 句，包含: 主体特征/姿势/场景/光线/氛围/画风关键词）。
要求: 保持用户描述的核心主体不变，只换风格化表达。不要输出解释。''')
        out = _clean(out).strip().strip('"')
        if out:
            prompts[name] = out
    # 若 LLM 失败，fallback 模板
    for name, style in STYLE_ANCHORS:
        prompts.setdefault(name, f'{desc}, {style}, high quality, detailed, masterpiece')
    return prompts

# ── R2/R3: 变体生成 ──

DIMENSIONS_R2 = [
    ('特写', 'close-up shot, upper body, face focus'),
    ('半身', 'medium shot, waist-up, natural pose'),
    ('全身', 'full body shot, standing, dynamic pose'),
    ('场景', 'wide shot, environmental, character in scene'),
]
LIGHTINGS_R2 = [
    'soft golden hour lighting', 'cool moonlight, night atmosphere',
    'dramatic backlight, rim light', 'warm indoor lighting, cozy mood',
]

def _build_variant_prompts(base_prompt, notes=''):
    """R2: 构图×光影 4 变体。R3: notes 融合。"""
    prompts = []
    note = f'\n用户修正意见: {notes}' if notes else ''
    if notes:
        # R3 微调：让 LLM 把用户意见合入 prompt
        out = _llm(f'''用户对这张图不满意，意见: {notes}
原 prompt: {base_prompt}
请输出修正后的完整英文 prompt（保持风格与主体，应用用户意见）。只输出 prompt。''')
        out = _clean(out).strip().strip('"')
        if out:
            return [('微调', out)]
    for comp, comp_tag in DIMENSIONS_R2:
        for light in LIGHTINGS_R2[:1]:  # R2 每构图 1 光 → 4 张；若需 8 张改 [2]
            p = f'{base_prompt}, {comp_tag}, {light}'
            prompts.append((f'{comp}·{light.split(",")[0]}', p))
    return prompts[:4]

# ── 生成（调 create_from_nl） ──

def _generate(prompt, model_type, ref_path, out_dir, dry_run=False):
    """单 prompt 生成（复用 create_from_nl）。返回输出目录/图片路径"""
    from workshop.create import create_from_nl
    kw = dict(
        nl_text=prompt, count=1, model_type=model_type,
        output_dir=str(out_dir), prompt_ready=True,
        inspect=True, dry_run=dry_run, gallery_dir=str(out_dir / 'gallery'),
    )
    if ref_path:
        kw['ref_path'] = ref_path
    try:
        result = create_from_nl(**kw)
        return result
    except Exception as e:
        print(f'  ⚠️ 生成失败: {str(e)[:120]}')
        return None

# ── refcheck: 参考图 vs 生成图 细节对比 ──

REFCHECK_PROMPT = '''Compare the character in image 1 (reference) vs image 2 (generated).
Output ONLY a JSON array with EXACTLY these 8 items:
[{"item":"hair_color","ref":"...","gen":"...","verdict":"match|diff|missing"},
 {"item":"hair_style","ref":"...","gen":"...","verdict":"match|diff|missing"},
 {"item":"eye_color","ref":"...","gen":"...","verdict":"match|diff|missing"},
 {"item":"face_shape","ref":"...","gen":"...","verdict":"match|diff|missing"},
 {"item":"outfit","ref":"...","gen":"...","verdict":"match|diff|missing"},
 {"item":"accessory","ref":"...","gen":"...","verdict":"match|diff|missing"},
 {"item":"pose","ref":"...","gen":"...","verdict":"match|diff|missing"},
 {"item":"style","ref":"...","gen":"...","verdict":"match|diff|missing"}]
Rules:
1. Be precise about colors (e.g. "pink-purple gradient" not "pink") — this is the key to judging match
2. verdict is exactly one of: match / diff / missing
3. JSON array only, no other text.'''

_ITEM_CN = {'hair_color': '发色', 'hair_style': '发型', 'eye_color': '瞳色',
            'face_shape': '脸型', 'outfit': '服装', 'accessory': '饰品',
            'pose': '姿态', 'style': '整体风格'}

def refcheck(ref_img, gen_img, verbose=True):
    """双图 VLM 对比 → 细节差异清单 + 自动生成的修正意见。"""
    base = _ollama_base()
    if not base:
        print('⚠️ ollama 不可用')
        return []
    import base64 as b64
    def enc(p):
        from PIL import Image
        img = Image.open(p)
        if max(img.size) > 768:
            r = 768 / max(img.size)
            img = img.resize((int(img.width * r), int(img.height * r)), Image.LANCZOS)
        buf = __import__('io').BytesIO()
        img.save(buf, format='PNG')
        return b64.b64encode(buf.getvalue()).decode()
    try:
        body = json.dumps({
            'model': 'qwen3-vl:8b', 'stream': False, 'think': False,
            'options': {'temperature': 0.1},
            'prompt': REFCHECK_PROMPT,
            'images': [enc(ref_img), enc(gen_img)],
        }).encode()
        req = urllib.request.Request(base + '/api/generate', data=body,
                                     headers={'Content-Type': 'application/json'})
        resp = json.loads(_no_proxy_opener().open(req, timeout=240).read())
        out = resp.get('response', '')
    except Exception as e:
        print(f'⚠️ refcheck 调用失败: {str(e)[:80]}')
        return []
    m = re.search(r'\[[\s\S]*\]', out)
    if not m:
        print(f'⚠️ VLM 输出非 JSON: {out[:100]}')
        return []
    try:
        diffs = json.loads(m.group(0))
    except Exception:
        return []
    if verbose:
        for d in diffs:
            item = d.get('item', '')
            mark = {'match': '✅', 'diff': '❌', 'missing': '⬜'}.get(d.get('verdict'), '?')
            cn = _ITEM_CN.get(item, item)
            print(f"{mark} {cn}: 参考[{d.get('ref','')[:50]}] vs 生成[{d.get('gen','')[:50]}]")
    return diffs

def _diffs_to_notes(diffs):
    """差异清单 → 自然语言修正意见（直接可作 --notes）"""
    bad = [d for d in diffs if d.get('verdict') in ('diff', 'missing')]
    if not bad:
        return ''
    parts = []
    for d in bad[:6]:
        item = d.get('item', '')
        ref = d.get('ref', '')
        if item and ref:
            cn = _ITEM_CN.get(item, item)
            parts.append(f'{cn}要{ref}')
    return '，'.join(parts)

# ── CLI ──

def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop converge', description='意图逼近工作流')
    ap.add_argument('desc', nargs='*', help='图像描述（仅第一轮需要）')
    ap.add_argument('--ref', default=None, help='参考图路径（锚点捕获，比描述准）')
    ap.add_argument('--model', default='sdxl', choices=['sdxl', 'flux'])
    ap.add_argument('--pick', type=int, default=None, help='选中第 N 个候选进入下一轮')
    ap.add_argument('--notes', default='', help='修正意见（自然语言，LLM 融合进 prompt）')
    ap.add_argument('--round', type=int, default=None, help='指定目标轮次（默认自动推进）')
    ap.add_argument('--status', action='store_true', help='查看当前状态')
    ap.add_argument('--done', action='store_true', help='收敛完成，输出 best')
    ap.add_argument('--dry-run', action='store_true', help='只生成 prompt 不跑 ComfyUI')
    ap.add_argument('--refcheck', nargs=2, metavar=('REF', 'GEN'),
                    help='对比参考图与生成图，输出细节差异清单')
    ap.add_argument('--notes-from-diff', action='store_true',
                    help='refcheck 后自动把差异转成 --notes 修正意见')
    args = ap.parse_args(argv)

    st = load_state()

    if args.refcheck:
        diffs = refcheck(args.refcheck[0], args.refcheck[1])
        if args.notes_from_diff:
            notes = _diffs_to_notes(diffs)
            print(f'\n# 自动生成的修正意见: {notes}')
            print('# 用法: workshop converge --pick <序号> --notes "上面这句"')
        return

    if args.status:
        print(json.dumps({k: st[k] for k in ('round', 'pick', 'notes', 'best')},
                         ensure_ascii=False, indent=2))
        for i, h in enumerate(st.get('history', []), 1):
            mark = '◀' if st.get('pick') == i else ' '
            print(f'{mark} [{i}] R{h.get("round")} {h.get("name","")}: {h.get("prompt","")[:80]}')
            if h.get('images'):
                print(f'      → {", ".join(h["images"])}')
        return

    if args.done:
        print('# 收敛完成。best:', st.get('best'))
        print('# 状态保留在', STATE_PATH)
        return

    # 第一轮：需要描述
    if not st['history']:
        if not args.desc:
            print('第一轮需要描述: workshop converge "你的描述" [--ref 参考图]')
            return
        desc = ' '.join(args.desc)
        ref_analysis = ''
        if args.ref:
            try:
                from workshop.engine.ref import ref_analyze_to_prompt
                ref_analysis = ref_analyze_to_prompt(args.ref)
            except Exception as e:
                print(f'  ⚠️ 参考图分析失败(继续): {str(e)[:80]}')
        prompts = _build_anchor_prompts(desc, ref_analysis)
        st['round'] = 1
        st['desc'] = desc
        st['ref'] = args.ref
        st['history'] = []
        out_dir = OUT_BASE / 'r1_anchors'
        for i, (name, prompt) in enumerate(prompts.items(), 1):
            print(f'[{i}] 锚点·{name}')
            print(f'    {prompt}')
            if not args.dry_run:
                r = _generate(prompt, args.model, args.ref, out_dir / f'{i:02d}_{name}')
                st['history'].append({'round': 1, 'name': name, 'prompt': prompt,
                                      'images': _collect_images(out_dir / f'{i:02d}_{name}')})
            else:
                st['history'].append({'round': 1, 'name': name, 'prompt': prompt, 'images': []})
        st['round'] = 2
        save_state(st)
        print('\n# R1 完成。选一个方向: workshop converge --pick <序号> [--notes "微调意见"]')
        return

    # pick 推进轮次
    if args.pick is not None:
        idx = args.pick - 1
        if idx < 0 or idx >= len(st['history']):
            print(f'序号越界: 当前 {len(st["history"])} 个候选')
            return
        base = st['history'][idx]
        st['pick'] = args.pick
        st['notes'].append(args.notes or f'选中 R{base["round"]} 候选 {base["name"]}')
        st['round'] = base['round'] + 1
        prompts = _build_variant_prompts(base['prompt'], args.notes)
        out_dir = OUT_BASE / f'r{st["round"]}_variants'
        st['history'] = [h for h in st['history'] if h.get('round') == st['round'] - 1]  # 保留上一轮
        for i, (name, prompt) in enumerate(prompts, 1):
            print(f'[{i}] {name}')
            print(f'    {prompt}')
            if not args.dry_run:
                r = _generate(prompt, args.model, st.get('ref'), out_dir / f'{i:02d}')
                st['history'].append({'round': st['round'], 'name': name, 'prompt': prompt,
                                      'images': _collect_images(out_dir / f'{i:02d}')})
            else:
                st['history'].append({'round': st['round'], 'name': name, 'prompt': prompt, 'images': []})
        save_state(st)
        print(f'\n# R{st["round"]} 完成。继续: converge --pick <序号> [--notes] 或 --done')
        return

    print('用法: converge "描述" | converge --pick N [--notes] | converge --status | converge --done')

def _collect_images(d):
    if not d.exists():
        return []
    imgs = sorted(str(p) for p in d.rglob('*.png'))[:4]
    return imgs

if __name__ == '__main__':
    main()
