#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/compose.py — 构图先行（缩略图风暴）v1.0
================================================
画师流程的 AI 版: 先快速出 N 张"构图雏形"（不看细节只看布局）
→ 你选构图 → Canny 提取结构线 → ControlNet 引导精修出稿。

用法:
  python -m agents workshop compose "描述" [--n 6] [--model sdxl]
      # R0 构图风暴: 快速生成 N 张雏形
  python -m agents workshop compose --pick <序号> [--strength 0.6]
      # R1 精修: 选中雏形 → Canny 结构线 → ControlNet 精修
  python -m agents workshop compose --status
"""

import argparse, json, os, re, shutil, sys, time, urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
COMFY = 'http://127.0.0.1:8188'
COMFY_INPUT = r'C:\DrawingLive\ComfyUI\input'
COMFY_OUTPUT = r'C:\DrawingLive\ComfyUI\output'
OUT_BASE = PROJECT / 'outputs'
STATE_PATH = PROJECT / 'workspace' / 'compose_state.json'

def _norm(p):
    p = os.path.expanduser(p)
    m = re.match(r'^/([a-zA-Z])/(.*)$', p)
    if m:
        p = m.group(1) + ':/' + m.group(2)
    return p

def _http():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))

def _submit(wf, timeout=300):
    """提交工作流，等结果，返回输出文件列表"""
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

# ── R0: 构图风暴 ──

def _compose_sketches(desc, n, model_type, seed):
    """逐张快速生成 n 张构图雏形（每张独立目录，构图风暴要看到全部候选）。
    中文 desc 必须 LLM 翻译成英文（SDXL 对中文理解差，实测中文直喂必跑偏）"""
    from workshop.create import create_from_nl
    from workshop.layer import _translate_desc
    desc_en = _translate_desc(desc)
    if desc_en != desc:
        print(f'  雏形 prompt(英文): {desc_en[:120]}')
    base = OUT_BASE / f'compose_{time.strftime("%Y%m%d_%H%M%S")}'
    for i in range(n):
        s = seed + i if seed >= 0 else -1
        create_from_nl(
            desc_en, count=1, model_type=model_type, seed=s,
            prompt_ready=True, inspect=False, dry_run=False,
            output_dir=str(base / f'sketch_{i+1:02d}'),
        )
    return base

# ── R1: Canny 结构线提取 + ControlNet 精修 ──

def _canny_preprocess(img_path, low=0.4, high=0.8):
    """ComfyUI Canny 节点提取结构线（阈值 0-1 FLOAT）→ 返回 canny 图文件名"""
    import shutil as _sh
    fname = os.path.basename(img_path)
    dst = os.path.join(COMFY_INPUT, fname)
    if os.path.abspath(img_path) != os.path.abspath(dst):
        _sh.copy(img_path, dst)
    wf = {
        '1': {'class_type': 'LoadImage', 'inputs': {'image': fname}},
        '2': {'class_type': 'Canny',
              'inputs': {'image': ['1', 0], 'low_threshold': low, 'high_threshold': high}},
        '3': {'class_type': 'SaveImage',
              'inputs': {'images': ['2', 0], 'filename_prefix': 'compose_canny'}},
    }
    files = _submit(wf, timeout=120)
    if not files:
        raise RuntimeError('Canny 无输出')
    # 复制回 input（给 ControlNet 用）——文件名唯一化防 ComfyUI 缓存
    src = os.path.join(COMFY_OUTPUT, files[0])
    canny_name = f'compose_canny_{int(time.time())}.png'
    _sh.copy(src, os.path.join(COMFY_INPUT, canny_name))
    return canny_name

# ControlNet 模型映射（只用真实存在的 SDXL 模型）
CN_MODELS = {
    'lineart': 'controlnet-sd-xl-1.0-softedge-dexined.safetensors',
    'softedge': 'controlnet-sd-xl-1.0-softedge-dexined.safetensors',
    'depth': 'controlnet-depth-sdxl-1.0.safetensors',
    'openpose': 'OpenPoseXL2.safetensors',
}

def _build_sdxl_cn_wf(prompt, ref_name, cn_model, strength, negative, seed,
                      width=1024, height=1152, prefix='compose_final'):
    """SDXL + ControlNet 工作流（waiIllustriousSDXL_v160）"""
    wf = {}
    wf['1'] = {'class_type': 'CheckpointLoaderSimple',
               'inputs': {'ckpt_name': 'waiIllustriousSDXL_v160.safetensors'}}
    wf['2'] = {'class_type': 'CLIPTextEncode',
               'inputs': {'text': prompt, 'clip': ['1', 1]}}
    wf['3'] = {'class_type': 'CLIPTextEncode',
               'inputs': {'text': negative or 'worst quality, blurry, low quality', 'clip': ['1', 1]}}
    wf['4'] = {'class_type': 'LoadImage', 'inputs': {'image': ref_name}}
    wf['5'] = {'class_type': 'ControlNetLoader',
               'inputs': {'control_net_name': cn_model}}
    wf['6'] = {'class_type': 'ControlNetApply',
               'inputs': {'conditioning': ['2', 0], 'control_net': ['5', 0],
                          'image': ['4', 0], 'strength': strength}}
    wf['7'] = {'class_type': 'KSampler',
               'inputs': {'model': ['1', 0], 'positive': ['6', 0], 'negative': ['3', 0],
                          'latent_image': ['8', 0], 'seed': seed, 'steps': 28, 'cfg': 6.5,
                          'sampler_name': 'dpmpp_2m', 'scheduler': 'karras', 'denoise': 1.0}}
    wf['8'] = {'class_type': 'EmptyLatentImage',
               'inputs': {'width': width, 'height': height, 'batch_size': 1}}
    wf['9'] = {'class_type': 'VAEDecode', 'inputs': {'samples': ['7', 0], 'vae': ['1', 2]}}
    wf['10'] = {'class_type': 'SaveImage',
                'inputs': {'images': ['9', 0], 'filename_prefix': prefix}}
    return wf

def _refine(desc, sketch_path, control_type, strength, model, seed, negative):
    """选中雏形 → Canny → ControlNet 精修"""
    canny_name = _canny_preprocess(sketch_path)
    print(f'  结构线提取完成: {canny_name}')
    cn_model = CN_MODELS.get(control_type, CN_MODELS['lineart'])
    seed_actual = seed if seed >= 0 else int(time.time()) % 2**31
    wf = _build_sdxl_cn_wf(desc, canny_name, cn_model, strength, negative,
                           seed_actual, prefix='compose_final')
    print(f'  提交 ControlNet({control_type}: {cn_model}) 精修...')
    files = _submit(wf, timeout=600)
    out_dir = OUT_BASE / f'compose_final_{time.strftime("%Y%m%d_%H%M%S")}'
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for f in files:
        src = os.path.join(COMFY_OUTPUT, f)
        if os.path.exists(src):
            dst = out_dir / f
            shutil.copy(src, dst)
            saved.append(str(dst))
    return saved

# ── R1.5: 黑白光影稿（value study，画师流程 M1）──

def _value_study(img_path, out_dir, contrast=1.15, bright=0.0):
    """生成黑白光影稿：PIL 灰度 + 对比度微调（纯 CPU 零显存）。

    画师流程: 上色前先确认光影叙事（明暗结构/大气透视/焦点区域）。
    用法: compose --value <序号> → 输出 value_study.png 供用户确认光影，
          满意后 --pick 走彩色精修。
    返回保存路径列表。
    """
    from PIL import Image, ImageEnhance

    img = Image.open(img_path).convert('L')          # 灰度
    img = ImageEnhance.Contrast(img).enhance(contrast)  # 对比度微调
    if bright:
        img = ImageEnhance.Brightness(img).enhance(1.0 + bright)
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f'value_study_{time.strftime("%H%M%S")}.png'
    img.save(dst)
    print(f'  🎨 黑白光影稿: {dst}')
    print(f'  （明暗结构确认：主体亮部/背景暗部/焦点引导）')
    return [str(dst)]

def _value_study_workflow(img_path, out_dir, contrast=1.15):
    """（备用）ComfyUI 灰度工作流——VLM 评分用；默认用 PIL 零显存方案"""
    return _value_study(img_path, out_dir, contrast)

# ── 状态 ──

def _load_state():
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {'desc': '', 'sketches': [], 'pick': None, 'final': []}

def _save_state(st):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding='utf-8')

# ── CLI ──

def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop compose', description='构图先行（缩略图风暴）')
    ap.add_argument('desc', nargs='*', help='画面描述（仅 R0 需要）')
    ap.add_argument('--n', type=int, default=6, help='雏形数量（默认 6）')
    ap.add_argument('--model', default='sdxl', choices=['sdxl', 'flux'])
    ap.add_argument('--pick', type=int, default=None, help='选中构图进入精修')
    ap.add_argument('--value', type=int, default=None,
                    help='选中构图生成黑白光影稿（画师流程：上色前确认光影结构）')
    ap.add_argument('--type', default='lineart', choices=['lineart', 'softedge', 'depth', 'openpose'],
                    help='ControlNet 控制类型（默认 lineart=Canny 结构线）')
    ap.add_argument('--strength', type=float, default=0.6, help='ControlNet 强度')
    ap.add_argument('--contrast', type=float, default=1.15, help='光影稿对比度（默认 1.15）')
    ap.add_argument('--seed', type=int, default=-1)
    ap.add_argument('--negative', default='bad anatomy, bad hands, extra fingers, blurry, lowres, watermark')
    ap.add_argument('--status', action='store_true')
    args = ap.parse_args(argv)

    st = _load_state()

    if args.status:
        print(f"描述: {st['desc']}")
        for i, s in enumerate(st.get('sketches', []), 1):
            mark = '◀' if st.get('pick') == i else ' '
            print(f"{mark} [{i}] {s}")
        if st.get('final'):
            print('成稿:', st['final'])
        return

    if args.pick is not None or args.value is not None:
        pick_or_value = args.pick if args.pick is not None else args.value
        idx = pick_or_value - 1
        if idx < 0 or idx >= len(st['sketches']):
            print(f'序号越界: 共 {len(st["sketches"])} 张雏形')
            return
        sketch = st['sketches'][idx]
        st['pick'] = pick_or_value
        print(f'选中: [{pick_or_value}] {sketch}')
        if args.value is not None:
            # 光影稿模式：确认明暗结构（不精修，供用户判断）
            out_dir = OUT_BASE / f'compose_value_{time.strftime("%Y%m%d_%H%M%S")}'
            try:
                saved = _value_study(sketch, out_dir, contrast=args.contrast)
                print(f'\n✅ 光影稿完成: {saved}')
                print(f'  明暗结构 OK？→ compose --pick {pick_or_value} 走彩色精修')
                print(f'  明暗不满意？→ compose --value {pick_or_value} --contrast 1.3 调对比度')
            except Exception as e:
                print(f'❌ 光影稿失败: {str(e)[:150]}')
            return
        try:
            saved = _refine(st['desc'], sketch, args.type, args.strength,
                            args.model, args.seed, args.negative)
            st['final'] = saved
            _save_state(st)
            print(f'\n✅ 精修完成: {saved}')
            print(f'  不满意可换图: compose --pick <其他序号>；或改 --strength 重跑')
        except Exception as e:
            print(f'❌ 精修失败: {str(e)[:150]}')
        return

    if not args.desc:
        print('用法: compose "描述" | compose --pick N | compose --status')
        return

    desc = ' '.join(args.desc)
    print(f'# R0 构图风暴: {desc}（{args.n} 张雏形，只看布局不看细节）')
    try:
        _compose_sketches(desc, args.n, args.model, args.seed)
        # 收集雏形图
        dirs = sorted(OUT_BASE.glob('compose_*'), key=lambda p: p.stat().st_mtime, reverse=True)
        if dirs:
            latest = dirs[0]
            imgs = sorted(str(p) for p in latest.rglob('best.png'))
            st['desc'] = desc
            st['sketches'] = imgs
            st['pick'] = None
            _save_state(st)
            print(f'  雏形目录: {latest}')
            for i, im in enumerate(imgs, 1):
                print(f'  [{i}] {im}')
            print('\n# 选构图: compose --pick <序号> [--type lineart] [--strength 0.6]')
        else:
            print('  未找到雏形输出')
    except Exception as e:
        print(f'❌ R0 失败: {str(e)[:150]}')

if __name__ == '__main__':
    main()
