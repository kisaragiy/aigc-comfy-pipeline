#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/layer.py — 分层绘制（背景/角色分离画再合成）v1.0
==========================================================
商业画师工作流的 AI 版：
角色层单独画（纯白背景，注意力集中）→ 背景层单独画（无角色干扰）
→ SAM 分割抠角色 → PIL 合成（缩放/定位/羽化）→ 分层可独立重画。

用法:
  python -m agents workshop layer "角色描述" --bg "背景描述"
      [--ref 参考图] [--model sdxl] [--scale 0.75] [--pos bottom-center]
      [--redo char|bg]   重画某一层（保留另一层）
"""

import argparse, json, os, re, shutil, sys, time, urllib.request
from pathlib import Path
from PIL import Image, ImageFilter

PROJECT = Path(__file__).resolve().parent.parent
COMFY = 'http://127.0.0.1:8188'
COMFY_INPUT = r'C:\DrawingLive\ComfyUI\input'
COMFY_OUTPUT = r'C:\DrawingLive\ComfyUI\output'
OUT_BASE = PROJECT / 'outputs'
STATE_PATH = PROJECT / 'workspace' / 'layer_state.json'

def _norm(p):
    p = os.path.expanduser(p)
    m = re.match(r'^/([a-zA-Z])/(.*)$', p)
    if m:
        p = m.group(1) + ':/' + m.group(2)
    return p

def _http():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))

def _submit(wf, timeout=400):
    body = json.dumps({'prompt': wf}).encode()
    req = urllib.request.Request(COMFY + '/prompt', data=body,
                                 headers={'Content-Type': 'application/json'})
    r = json.loads(_http().open(req, timeout=30).read())
    if 'error' in r:
        raise RuntimeError(str(r['error'])[:200])
    pid = r['prompt_id']
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            d = json.loads(_http().open(COMFY + f'/history/{pid}', timeout=5).read())
            if pid in d:
                files = []
                for node in d[pid].get('outputs', {}).values():
                    files += [img['filename'] for img in node.get('images', [])]
                if files:
                    return files
        except Exception:
            pass
        time.sleep(2)
    raise TimeoutError('生成超时')

# ── 统一风格基调（光照/色调一致，避免分层后违和） ──

def _style_base(desc, bg_desc):
    """LLM 提取统一的光照方向/色调基调 → (风格词, 角色prompt, 背景prompt)"""
    base = ''
    try:
        from agents.vlm_analyzer import _call_ollama_vl  # 可能不存在，用直连
    except Exception:
        pass
    # 直连 ollama 文本模型
    import urllib.request as _ur
    try:
        body = json.dumps({
            'model': 'qwen3:14b', 'stream': False, 'think': False,
            'prompt': f'''统一下面角色和背景的光照/色调，输出共同风格词（光源方向+色调+氛围，15字内英文）。
角色: {desc[:100]}
背景: {bg_desc[:100]}
只输出风格词。''',
        }).encode()
        req = _ur.Request('http://172.22.175.253:11434/api/generate', data=body,
                          headers={'Content-Type': 'application/json'})
        resp = json.loads(_ur.build_opener(_ur.ProxyHandler({})).open(req, timeout=60).read())
        base = resp.get('response', '').strip()[:60]
    except Exception:
        pass
    return base

def _translate_desc(desc, timeout=60):
    """中文描述 → 英文（SDXL 对中文理解差，实测中文直接生成走样）"""
    try:
        body = json.dumps({
            'model': 'qwen3:14b', 'stream': False, 'think': False,
            'prompt': f'''把下面的角色描述翻译成英文绘图 prompt（保留全部细节：发色/发型/瞳色/服装/表情）：
{desc[:150]}
只输出英文，不要解释。''',
        }).encode()
        req = urllib.request.Request('http://172.22.175.253:11434/api/generate', data=body,
                                     headers={'Content-Type': 'application/json'})
        resp = json.loads(urllib.request.build_opener(
            urllib.request.ProxyHandler({})).open(req, timeout=timeout).read())
        out = resp.get('response', '').strip()
        if out:
            return out[:300]
    except Exception:
        pass
    return desc

# ── 生成单层 ──

def _gen_layer(prompt, model_type, out_dir, seed, extra=''):
    from workshop.create import create_from_nl
    create_from_nl(
        prompt + ', ' + extra, count=1, model_type=model_type, seed=seed,
        prompt_ready=True, inspect=False, dry_run=False, output_dir=str(out_dir),
    )
    best = out_dir / 'best.png'
    return str(best) if best.exists() else None

# ── SAM 抠图 ──

def _sam_cutout(char_path, prompt='person'):
    """SAM2 文本定位分割 → 返回 mask 图路径（修复：旧 GroundingDinoSAMSegment 在
    transformers 新版崩溃 + 保存 IMAGE 而非 MASK；改用 SAM2Segment 输出 MASK_IMAGE）"""
    fname = os.path.basename(char_path)
    shutil.copy(char_path, os.path.join(COMFY_INPUT, fname))
    wf = {
        '1': {'class_type': 'LoadImage', 'inputs': {'image': fname}},
        '2': {'class_type': 'SAM2Segment',
              'inputs': {'image': ['1', 0], 'prompt': prompt,
                         'sam2_model': 'sam2.1_hiera_tiny',
                         'dino_model': 'GroundingDINO_SwinT_OGC (694MB)',
                         'device': 'Auto', 'threshold': 0.3, 'box_threshold': 0.3}},
        '3': {'class_type': 'SaveImage',
              'inputs': {'images': ['2', 2], 'filename_prefix': 'layer_mask'}},
    }
    files = _submit(wf, timeout=180)
    if not files:
        raise RuntimeError('SAM 分割无输出')
    src = os.path.join(COMFY_OUTPUT, files[0])
    mask_path = os.path.join(PROJECT, 'workspace', f'layer_mask_{int(time.time())}.png')
    shutil.copy(src, mask_path)
    return mask_path

# ── 语义分割抠图（easy humanSegmentation，替代坏掉的 SAM 节点） ──

def _human_segment(char_path, method='human_parsing_lip'):
    """easy humanSegmentation 人体语义分割 → 返回 mask 图路径"""
    fname = os.path.basename(char_path)
    shutil.copy(char_path, os.path.join(COMFY_INPUT, fname))
    wf = {
        '1': {'class_type': 'LoadImage', 'inputs': {'image': fname}},
        '2': {'class_type': 'easy humanSegmentation',
              'inputs': {'image': ['1', 0], 'method': method, 'confidence': 0.4,
                         'crop_multi': 0.0, 'mask_components': [0]}},
        '3': {'class_type': 'MaskToImage', 'inputs': {'mask': ['2', 1]}},
        '4': {'class_type': 'SaveImage',
              'inputs': {'images': ['3', 0], 'filename_prefix': 'layer_human_mask'}},
    }
    files = _submit(wf, timeout=240)
    if not files:
        raise RuntimeError('人体分割无输出')
    src = os.path.join(COMFY_OUTPUT, files[0])
    mask_path = os.path.join(PROJECT, 'workspace', f'layer_mask_{int(time.time())}.png')
    shutil.copy(src, mask_path)
    return mask_path

def _apply_mask_to_fg(char_path, mask_path, feather=3):
    """角色图 + mask 图 → RGBA（alpha=invert(mask)，黑=保留）。
    easy humanSegmentation 的 mask 语义: 白=背景 黑=人体"""
    img = Image.open(char_path).convert('RGB')
    mask = Image.open(mask_path).convert('L').resize(img.size, Image.LANCZOS)
    rgba = img.convert('RGBA')
    # invert: 黑(人体)→alpha 255 保留
    inv = Image.eval(mask, lambda v: 255 - v)
    if feather > 0:
        inv = inv.filter(ImageFilter.GaussianBlur(feather))
    rgba.putalpha(inv)
    return rgba

# ── 抠图：色度键（品红背景）──

def _cutout_magenta(char_path, feather=3, hue_dist=35, min_sat=0.25):
    """品红背景色度键抠图（HSV 色相距离，肤色安全）。
    品红色相≈300°，肤色≈25°——色相距离 60°+ 不会误切肤色。
    返回 RGBA 图"""
    import numpy as np
    img = Image.open(char_path).convert('RGB')
    hsv = img.convert('HSV')
    h_arr = np.asarray(hsv.getchannel('H'), dtype=np.float32) / 255.0 * 360.0
    s_arr = np.asarray(hsv.getchannel('S'), dtype=np.float32) / 255.0
    # 到品红(300°)的环形色相距离
    d1 = np.abs(h_arr - 300.0)
    d2 = 360.0 - d1
    dist_h = np.minimum(d1, d2)
    # 背景 = 色相接近品红 且 饱和度足够（品红背景是高饱和）
    is_bg = (dist_h < hue_dist) & (s_arr > min_sat)
    alpha = np.where(is_bg, 0, 255).astype(np.uint8)
    arr = np.asarray(img, dtype=np.uint8)
    rgba = np.dstack([arr, alpha])
    out = Image.fromarray(rgba, 'RGBA')
    if feather > 0:
        a = out.getchannel('A').filter(ImageFilter.GaussianBlur(feather))
        out.putalpha(a)
    return out

def _cutout_white(char_path, feather=3, threshold=230):
    """白底亮度阈值抠图（角色非浅色时可用）"""
    import numpy as np
    img = Image.open(char_path).convert('RGB')
    arr = np.asarray(img, dtype=np.float32)
    lum = arr.mean(axis=2)
    alpha = np.clip(255 - (lum - threshold) * 4, 0, 255).astype(np.uint8)
    rgba = np.dstack([arr.astype(np.uint8), alpha])
    out = Image.fromarray(rgba, 'RGBA')
    if feather > 0:
        a = out.getchannel('A').filter(ImageFilter.GaussianBlur(feather))
        out.putalpha(a)
    return out

def _cutout_adaptive(char_path, feather=3, threshold=45):
    """自适应背景色抠图：四角采样背景主色 → 色距阈值 alpha。
    纯 PIL 实现（不依赖 numpy——hermes venv numpy 损坏）。
    返回 RGBA 图"""
    img = Image.open(char_path).convert('RGB')
    w, h = img.size
    # 四角 8x8 区域平均色
    def corner_avg(x, y):
        px = img.crop((x, y, min(x + 8, w), min(y + 8, h)))
        sm = [0, 0, 0]
        cnt = 0
        for p in px.getdata():
            sm[0] += p[0]; sm[1] += p[1]; sm[2] += p[2]; cnt += 1
        return tuple(s // cnt for s in sm)
    corners = [corner_avg(0, 0), corner_avg(w - 8, 0),
               corner_avg(0, h - 8), corner_avg(w - 8, h - 8)]
    # 中位数背景色
    bg = tuple(sorted(c[i] for c in corners)[len(corners) // 2] for i in range(3))
    # 逐像素色距 → alpha
    alpha = Image.new('L', (w, h), 0)
    src = img.load()
    dst = alpha.load()
    for y in range(h):
        for x in range(w):
            r, g, b = src[x, y]
            dist = ((r - bg[0]) ** 2 + (g - bg[1]) ** 2 + (b - bg[2]) ** 2) ** 0.5
            dst[x, y] = 255 if dist > threshold else 0
    if feather > 0:
        alpha = alpha.filter(ImageFilter.GaussianBlur(feather))
    rgba = img.convert('RGBA')
    rgba.putalpha(alpha)
    return rgba, bg

# ── PIL 合成 ──

def _compose(bg_path, char_path, mask_path, scale=0.75, feather=3, pos='bottom-center'):
    bg = Image.open(bg_path).convert('RGB')
    fg = Image.open(char_path).convert('RGB')
    mask = Image.open(mask_path).convert('L')
    # 缩放角色到背景高度的 scale 倍
    target_h = int(bg.height * scale)
    ratio = target_h / fg.height
    new_size = (int(fg.width * ratio), target_h)
    fg = fg.resize(new_size, Image.LANCZOS)
    mask = mask.resize(new_size, Image.LANCZOS)
    # 羽化边缘
    if feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(feather))
    # 定位
    if pos == 'bottom-center':
        x = (bg.width - fg.width) // 2
        y = bg.height - fg.height
    elif pos == 'center':
        x = (bg.width - fg.width) // 2
        y = (bg.height - fg.height) // 2
    else:
        x, y = 0, bg.height - fg.height
    bg.paste(fg, (x, y), mask)
    return bg

def _compose_rgba(bg_path, fg_rgba_path, scale=0.75, feather=3, pos='bottom-center'):
    """背景 + RGBA 前景合成（前景自带 alpha）"""
    bg = Image.open(bg_path).convert('RGB')
    fg = Image.open(fg_rgba_path).convert('RGBA')
    target_h = int(bg.height * scale)
    ratio = target_h / fg.height
    fg = fg.resize((int(fg.width * ratio), target_h), Image.LANCZOS)
    if pos == 'bottom-center':
        x = (bg.width - fg.width) // 2
        y = bg.height - fg.height
    elif pos == 'center':
        x = (bg.width - fg.width) // 2
        y = (bg.height - fg.height) // 2
    else:
        x, y = 0, bg.height - fg.height
    bg.paste(fg, (x, y), fg)
    return bg

# ── 状态 ──

def _load_state():
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {}

def _save_state(st):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding='utf-8')

# ── CLI ──

def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop layer', description='分层绘制（角色/背景分离→SAM抠图→合成）')
    ap.add_argument('desc', nargs='*', help='角色描述（仅首次需要）')
    ap.add_argument('--bg', required=True, help='背景描述')
    ap.add_argument('--ref', default=None, help='角色参考图')
    ap.add_argument('--model', default='sdxl', choices=['sdxl', 'flux'])
    ap.add_argument('--scale', type=float, default=0.75, help='角色占背景高度比例（默认 0.75）')
    ap.add_argument('--pos', default='bottom-center', choices=['bottom-center', 'center', 'bottom-left'])
    ap.add_argument('--redo', choices=['char', 'bg'], default=None, help='只重画某一层')
    ap.add_argument('--seed', type=int, default=-1)
    ap.add_argument('--status', action='store_true')
    args = ap.parse_args(argv)

    st = _load_state()

    if args.status:
        print(json.dumps(st, ensure_ascii=False, indent=2))
        return

    if not args.desc and not st.get('char_prompt'):
        print('用法: layer "角色描述" --bg "背景描述" [--scale 0.75] [--redo char|bg]')
        return

    desc = ' '.join(args.desc) if args.desc else st['char_prompt']
    bg_desc = args.bg if args.bg else st.get('bg_prompt', '')
    if not bg_desc:
        print('需要 --bg 背景描述')
        return

    seed = args.seed if args.seed >= 0 else int(time.time()) % 2**31
    run_dir = OUT_BASE / f'layer_{time.strftime("%Y%m%d_%H%M%S")}'
    run_dir.mkdir(parents=True, exist_ok=True)

    # 1. 统一风格基调 + 英文翻译
    print('# 统一光照/色调基调...')
    style = _style_base(desc, bg_desc)
    if style:
        print(f'  风格词: {style}')
    else:
        style = 'consistent lighting, soft natural light'
        print(f'  风格词(默认): {style}')
    desc_en = _translate_desc(desc)
    if desc_en != desc:
        print(f'  角色描述(英文): {desc_en[:100]}')

    char_prompt = f'{desc_en}, full body, standing, plain solid background, solo'
    bg_prompt = f'{bg_desc}, no characters, {style}'

    # 2. 生成角色层/背景层（支持 --redo 单层重画）
    char_path = st.get('char_path')
    bg_path = st.get('bg_path')
    if args.redo != 'bg' and (args.redo == 'char' or not char_path or not os.path.exists(char_path)):
        print('# 生成角色层（白底）...')
        char_path = _gen_layer(char_prompt, args.model, run_dir / 'char', seed,
                               'solo, no background details')
        print(f'  → {char_path}')
    if args.redo != 'char' and (args.redo == 'bg' or not bg_path or not os.path.exists(bg_path)):
        print('# 生成背景层（无角色）...')
        bg_path = _gen_layer(bg_prompt, args.model, run_dir / 'bg', seed + 1,
                             'landscape orientation, wide shot, empty scene')
        print(f'  → {bg_path}')

    if not char_path or not bg_path or not os.path.exists(char_path) or not os.path.exists(bg_path):
        print('❌ 分层生成失败')
        return

    # 3. 抠图（自适应色距优先——SAM2/语义分割均有 transformers 兼容坑，纯 PIL 最稳）
    print('# 抠图（自适应色距）...')
    try:
        fg_rgba, bg_color = _cutout_adaptive(char_path)
        fg_rgba.save(run_dir / 'char_cutout.png')
        print(f'  → {run_dir / "char_cutout.png"}（背景色: {tuple(int(x) for x in bg_color)}）')
    except Exception as e:
        print(f'⚠️ 自适应抠图失败: {str(e)[:100]}，回退品红/白底')
        try:
            fg_rgba = _cutout_magenta(char_path)
            fg_rgba.save(run_dir / 'char_cutout.png')
            print(f'  品红抠图成功')
        except Exception as e2:
            print(f'❌ 抠图失败: {str(e2)[:80]}')
            return

    # 4. 合成
    print('# 合成...')
    composed = _compose_rgba(bg_path, str(run_dir / 'char_cutout.png'),
                             args.scale, feather=3, pos=args.pos)
    final = run_dir / 'final.png'
    composed.save(final)
    print(f'✅ 合成完成: {final}')
    print(f'  分层: 角色={char_path}')
    print(f'        背景={bg_path}')
    print(f'  调整: --scale {args.scale} 换大小 | --redo char/bg 重画单层')

    st.update({'char_prompt': desc, 'bg_prompt': bg_desc, 'char_path': char_path,
               'bg_path': bg_path, 'final': str(final), 'scale': args.scale})
    _save_state(st)

if __name__ == '__main__':
    main()
