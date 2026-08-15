#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/wallpaper.py — 壁纸/头像生成（B-wall）v1.0
====================================================
B站高频生图场景：手机壁纸(9:16)/头像(1:1)/桌面壁纸(16:9)。
要点：
  - 手机壁纸：竖构图 + 主体在上 2/3（底部留给图标）
  - 头像：方形构图 + 脸部/上半身特写居中
  - 桌面壁纸：横构图 + 主体偏侧（留出任务栏/图标区）

用法:
  python -m agents workshop wallpaper "描述" [--type phone|avatar|desktop]
"""

import argparse, json, os, re, sys, time, urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent

# 类型 → (尺寸, 构图强调, 文件名)
TYPES = {
    "phone": (768, 1344, "vertical composition, phone wallpaper, subject in upper two-thirds, empty space at bottom for icons, full body or upper body"),
    "avatar": (1024, 1024, "square avatar, face and upper body centered, close-up portrait, clean background"),
    "desktop": (1344, 768, "horizontal composition, desktop wallpaper, subject slightly off-center, scenic background"),
    "live_bg": (1344, 768, "live stream background, empty scene, no characters, atmospheric environment, cozy room or virtual stage, anime scenery"),
}

# 多人同框构图（B站 67K 热度：CP/同框是二创核心）
MULTI_COMPOSE = {
    "couple": "two characters together, standing side by side, looking at each other, romantic atmosphere, both in frame clearly",
    "group": "three characters together, group shot, all visible clearly, dynamic interaction",
    "battle": "two characters facing off, combat stance, dynamic action, both in frame",
}


def _http():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _submit(wf, timeout=300):
    COMFY = 'http://127.0.0.1:8188'
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


def _build_wf(prompt, negative, seed, width, height):
    wf = {}
    wf['1'] = {'class_type': 'CheckpointLoaderSimple',
               'inputs': {'ckpt_name': 'waiIllustriousSDXL_v160.safetensors'}}
    wf['2'] = {'class_type': 'CLIPTextEncode',
               'inputs': {'text': prompt, 'clip': ['1', 1]}}
    wf['3'] = {'class_type': 'CLIPTextEncode',
               'inputs': {'text': negative or 'worst quality, blurry, low quality, watermark, text', 'clip': ['1', 1]}}
    wf['4'] = {'class_type': 'EmptyLatentImage',
               'inputs': {'width': width, 'height': height, 'batch_size': 1}}
    wf['5'] = {'class_type': 'KSampler',
               'inputs': {'model': ['1', 0], 'positive': ['2', 0], 'negative': ['3', 0],
                          'latent_image': ['4', 0], 'seed': seed, 'steps': 26, 'cfg': 6.5,
                          'sampler_name': 'dpmpp_2m', 'scheduler': 'karras', 'denoise': 1.0}}
    wf['6'] = {'class_type': 'VAEDecode', 'inputs': {'samples': ['5', 0], 'vae': ['1', 2]}}
    wf['7'] = {'class_type': 'SaveImage',
               'inputs': {'images': ['6', 0], 'filename_prefix': 'wallpaper'}}
    return wf


def generate_wallpaper(desc, wtype='phone', seed=-1, output=None, negative=None, count=1,
                       dynamic=False, dark=False, notch=False):
    """生成壁纸/头像。

    Args:
        dynamic: 动态壁纸（生成图后接 I2V 微动——B站 73K 热度场景）
        dark: 深色模式增强（底部 1/3 渐变暗化，图标可见——手机壁纸细节）
        notch: 刘海安全区（顶部 8% 渐变留空——全面屏细节）

    Returns:
        [输出路径...]
    """
    if wtype not in TYPES:
        print(f"⚠️ 未知类型 {wtype}，可选: {list(TYPES.keys())}")
        return []
    width, height, compose = TYPES[wtype]

    # 中文翻译
    try:
        from workshop.layer import _translate_desc
        desc_en = _translate_desc(desc)
    except Exception:
        desc_en = desc

    full_prompt = f"{desc_en}, {compose}, high quality anime illustration, detailed, beautiful"
    base_seed = seed if seed >= 0 else int(time.time()) % 2**31
    out_paths = []
    for i in range(count):
        s = base_seed + i * 7
        wf = _build_wf(full_prompt, negative, s, width, height)
        print(f'  提交 {wtype} 工作流 ({width}x{height}, seed={s})...')
        files = _submit(wf, timeout=600)
        if not files:
            print('  ⚠️ 无输出')
            continue
        COMFY_OUTPUT = r'C:\DrawingLive\ComfyUI\output'
        src = os.path.join(COMFY_OUTPUT, files[0])
        if not os.path.exists(src):
            print(f'  ⚠️ 文件不存在: {src}')
            continue
        out_path = output or str(PROJECT / 'outputs' / f"wallpaper_{wtype}_{time.strftime('%Y%m%d_%H%M%S')}_{i+1}.png")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(src, 'rb') as f_in, open(out_path, 'wb') as f_out:
            f_out.write(f_in.read())

        # 深色模式/刘海安全区（手机壁纸细节，PIL 叠加渐变）
        if dark or notch:
            from PIL import Image as PImage, ImageDraw as PDraw
            img = PImage.open(out_path).convert('RGBA')
            overlay = PImage.new('RGBA', img.size, (0, 0, 0, 0))
            od = PDraw.Draw(overlay)
            w_img, h_img = img.size
            if dark:
                # 底部 1/3 渐变暗化（图标区）
                grad_h = int(h_img * 0.33)
                for j in range(grad_h):
                    alpha = int(160 * (j / grad_h) ** 1.5)  # 底部最暗
                    od.line([(0, h_img - grad_h + j), (w_img, h_img - grad_h + j)],
                            fill=(0, 0, 0, alpha))
            if notch:
                # 顶部 8% 渐变暗化（刘海/状态栏安全区）
                notch_h = int(h_img * 0.08)
                for j in range(notch_h):
                    alpha = int(120 * (1 - j / notch_h))
                    od.line([(0, j), (w_img, j)], fill=(0, 0, 0, alpha))
            img = PImage.alpha_composite(img, overlay).convert('RGB')
            img.save(out_path)
            if dark:
                print(f'  🌙 深色模式增强（底部图标区暗化）')
            if notch:
                print(f'  📱 刘海安全区优化（顶部渐变）')

        print(f'  🎨 {wtype}: {out_path}')
        out_paths.append(out_path)

        # 动态壁纸：I2V 微动（denoise 0.4 保持画面，帧少 24fps）
        if dynamic:
            try:
                from workshop.video.video import generate_video
                print('  🎬 生成动态壁纸（I2V 微动）...')
                vres = generate_video(
                    f"{full_prompt}, gentle motion, subtle animation, floating particles",
                    ref_image=out_path, frames=24, fps=12,
                    width=width, height=height, denoise=0.4,
                    seed=s, prefix=f"live_wall_{wtype}",
                    timeout=900,
                )
                vpath = vres.get('video_path') or vres.get('output')
                if vpath:
                    print(f'  🎬 动态壁纸: {vpath}')
                    out_paths.append(str(vpath))
            except Exception as e:
                print(f'  ⚠️ 动态壁纸失败: {str(e)[:120]}')
    return out_paths


def generate_multi(desc_a, desc_b=None, mode="couple", seed=-1, output=None,
                   negative=None, count=1, ref_a=None, ref_b=None):
    """多人同框生成（B站 67K 热度：CP/同框二创）。

    desc_a: 角色A描述；desc_b: 角色B描述（可空，用 mode 补全）
    mode: couple(双人CP)/group(三人)/battle(对决)
    ref_a/ref_b: 角色A/B 参考图（IPAdapter——防角色漂移，多人一致性细节）

    Returns:
        [输出路径...]
    """
    if mode not in MULTI_COMPOSE:
        print(f"⚠️ 未知模式 {mode}，可选: {list(MULTI_COMPOSE.keys())}")
        return []
    # 参考图前置校验（缺图/损坏 → 立即友好报错）
    from workshop.image_utils import open_image_safe
    for ref, label in ((ref_a, 'ref_a'), (ref_b, 'ref_b')):
        if ref:
            open_image_safe(ref)  # 缺图 FileNotFoundError / 损坏 ValueError
    compose = MULTI_COMPOSE[mode]

    # 中文翻译两个角色描述
    try:
        from workshop.layer import _translate_desc
        a_en = _translate_desc(desc_a) if desc_a else "a character"
        b_en = _translate_desc(desc_b) if desc_b else "another character"
    except Exception:
        a_en = desc_a or "a character"
        b_en = desc_b or "another character"

    full_prompt = f"{a_en}, {b_en}, {compose}, high quality anime illustration, detailed, beautiful"
    base_seed = seed if seed >= 0 else int(time.time()) % 2**31
    out_paths = []
    for i in range(count):
        s = base_seed + i * 7

        # 双角色参考图模式（IPAdapter 防漂移）
        if ref_a or ref_b:
            from workshop.create import create_from_nl
            sub = Path(output or str(PROJECT / 'outputs' / f"multi_{mode}_{time.strftime('%Y%m%d_%H%M%S')}_{i+1}"))
            sub.mkdir(parents=True, exist_ok=True)
            try:
                create_from_nl(
                    full_prompt, count=1, model_type='sdxl', seed=s,
                    ref_path=ref_a, ip_weight=0.8,
                    prompt_ready=True, inspect=False, dry_run=False,
                    output_dir=str(sub),
                )
                best = sub / 'best.png'
                if best.exists():
                    out_paths.append(str(best))
                    print(f'  🎨 多人同框(ref): {best}')
            except Exception as e:
                print(f'  ⚠️ 失败: {str(e)[:100]}')
            continue

        wf = _build_wf(full_prompt, negative, s, 1344, 768)
        print(f'  提交多人同框 ({mode}, seed={s})...')
        files = _submit(wf, timeout=600)
        if not files:
            print('  ⚠️ 无输出')
            continue
        COMFY_OUTPUT = r'C:\DrawingLive\ComfyUI\output'
        src = os.path.join(COMFY_OUTPUT, files[0])
        if not os.path.exists(src):
            print(f'  ⚠️ 文件不存在: {src}')
            continue
        out_path = output or str(PROJECT / 'outputs' / f"multi_{mode}_{time.strftime('%Y%m%d_%H%M%S')}_{i+1}.png")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(src, 'rb') as f_in, open(out_path, 'wb') as f_out:
            f_out.write(f_in.read())
        print(f'  🎨 多人同框: {out_path}')
        out_paths.append(out_path)
    return out_paths


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop wallpaper', description='壁纸/头像生成')
    ap.add_argument('desc', nargs='*', help='内容描述')
    ap.add_argument('--type', choices=list(TYPES.keys()), default='phone',
                    help='类型: phone(手机壁纸9:16)/avatar(头像1:1)/desktop(桌面16:9)/live_bg(直播背景)')
    ap.add_argument('--output', default=None, help='输出路径')
    ap.add_argument('--seed', type=int, default=-1)
    ap.add_argument('--count', type=int, default=1, help='生成张数')
    ap.add_argument('--dynamic', action='store_true', help='动态壁纸（I2V 微动）')
    ap.add_argument('--dark', action='store_true', help='深色模式（底部图标区暗化）')
    ap.add_argument('--notch', action='store_true', help='刘海安全区（顶部渐变留空）')
    args = ap.parse_args(argv)

    desc = ' '.join(args.desc)
    if not desc:
        print('用法: wallpaper "描述" [--type phone|avatar|desktop] [--count N] [--dynamic] [--dark] [--notch]')
        return 1
    try:
        generate_wallpaper(desc, wtype=args.type, seed=args.seed,
                           output=args.output, count=args.count, dynamic=args.dynamic,
                           dark=args.dark, notch=args.notch)
        return 0
    except Exception as e:
        print(f'❌ 失败: {str(e)[:150]}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
