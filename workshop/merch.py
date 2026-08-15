#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/merch.py — 周边设计（B-merch）v1.0
============================================
B站工房/周边变现场景（挂件/立牌/徽章/明信片）。
要点：
  - 透明底 PNG（印刷/电商用，去背景）
  - 常用周边尺寸（挂件 1:1 / 立牌 3:4 / 徽章 1:1 / 明信片 3:4）
  - 边缘留白（印刷裁切安全区）

用法:
  python -m agents workshop merch "描述" [--type sticker|standee|badge|postcard]
"""

import argparse, json, os, re, sys, time, urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent

# 周边类型 → (尺寸, 说明)
MERCH_TYPES = {
    "sticker": (1024, 1024, "挂件/贴纸 1:1 透明底"),
    "badge":   (1024, 1024, "徽章 1:1 圆形构图"),
    "standee": (896, 1152,  "立牌 3:4 全身角色"),
    "postcard": (1152, 896, "明信片 3:4 横版"),
}

# 透明底风格（印刷用：干净背景/主体居中/边缘留白）
_MERCH_STYLE = (
    "clean sticker design, character centered, transparent background style, "
    "white outline, simple flat background, sticker cutout style, "
    "merchandise design, print-ready, no text, no watermark"
)


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
               'inputs': {'images': ['6', 0], 'filename_prefix': 'merch'}}
    return wf


def _make_transparent_bg(image_path, output_path, threshold=235):
    """把接近白色的背景转透明（简易去背，周边印刷用）。

    注意：这是简易版（白色背景才可靠），复杂背景请用管线 fix --remove-bg。
    """
    from PIL import Image
    img = Image.open(image_path).convert('RGBA')
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r > threshold and g > threshold and b > threshold:
                px[x, y] = (r, g, b, 0)  # 白→透明
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path)
    return output_path


def generate_merch(desc, mtype='sticker', seed=-1, output=None, negative=None,
                   count=1, transparent=True, print_mode=False):
    """生成周边设计图。

    Args:
        mtype: 类型（sticker 贴纸/badge 徽章/standee 立牌/postcard 明信片）
        transparent: 透明底（白底转透明，保留原图）
        print_mode: 印刷模式（+3mm 出血线 + CMYK 色彩模式——印刷厂要求）

    Returns:
        [输出路径...]
    """
    if mtype not in MERCH_TYPES:
        print(f"⚠️ 未知类型 {mtype}，可选: {list(MERCH_TYPES.keys())}")
        return []
    width, height, _ = MERCH_TYPES[mtype]

    # 中文翻译
    try:
        from workshop.layer import _translate_desc
        desc_en = _translate_desc(desc)
    except Exception:
        desc_en = desc

    full_prompt = f"{desc_en}, {_MERCH_STYLE}"
    seed_actual = seed if seed >= 0 else int(time.time()) % 2**31
    wf = _build_wf(full_prompt, negative, seed_actual, width, height)
    print(f'  提交周边工作流 ({mtype} {width}x{height}, seed={seed_actual})...')
    files = _submit(wf, timeout=600)
    if not files:
        raise RuntimeError('周边无输出')

    COMFY_OUTPUT = r'C:\DrawingLive\ComfyUI\output'
    src = os.path.join(COMFY_OUTPUT, files[0])
    if not os.path.exists(src):
        raise RuntimeError(f'输出文件不存在: {src}')

    out_path = output or str(PROJECT / 'outputs' / f"merch_{mtype}_{time.strftime('%Y%m%d_%H%M%S')}.png")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    if transparent:
        # 透明底版本
        _make_transparent_bg(src, out_path)
        print(f'  🎨 周边完成（透明底）: {out_path}')
        # 同时保留原图（有背景版本，对比用）
        with open(src, 'rb') as f_in:
            data = f_in.read()
        orig_path = out_path.replace('.png', '_bg.png')
        with open(orig_path, 'wb') as f_out:
            f_out.write(data)
        print(f'  🎨 原图（含背景）: {orig_path}')
        result = [out_path, orig_path]
    else:
        with open(src, 'rb') as f_in, open(out_path, 'wb') as f_out:
            f_out.write(f_in.read())
        print(f'  🎨 周边完成: {out_path}')
        result = [out_path]

    # 印刷模式：+3mm 出血线 + CMYK 色彩模式（印刷厂要求，周边变现场景细节）
    if print_mode:
        try:
            from PIL import Image
            img = Image.open(out_path).convert('RGB')
            w, h = img.size
            # +3mm 出血（300dpi 下 3mm ≈ 35px，按比例：加 5% 边）
            bleed = int(min(w, h) * 0.05)
            canvas = Image.new('RGB', (w + bleed * 2, h + bleed * 2), (255, 255, 255))
            canvas.paste(img, (bleed, bleed))
            # CMYK 转换（印刷色彩模式）
            cmyk = canvas.convert('CMYK')
            print_path = out_path.replace('.png', '_print.tif')
            cmyk.save(print_path, format='TIFF', compression='tiff_lzw')
            print(f'  🖨️ 印刷版（+{bleed}px 出血/CMYK）: {print_path}')
            # 出血参考线（叠在原图上，供检查）
            guide = canvas.copy().convert('RGB')
            from PIL import ImageDraw
            gd = ImageDraw.Draw(guide)
            gd.rectangle([bleed, bleed, w + bleed - 1, h + bleed - 1],
                         outline=(255, 0, 0), width=2)
            guide_path = out_path.replace('.png', '_bleed_guide.png')
            guide.save(guide_path)
            print(f'  📏 出血参考线: {guide_path}')
            result.append(print_path)
            result.append(guide_path)
        except Exception as e:
            print(f'  ⚠️ 印刷模式失败: {str(e)[:100]}')

    return result


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop merch', description='周边设计（挂件/立牌/徽章/明信片）')
    ap.add_argument('desc', nargs='*', help='角色/内容描述')
    ap.add_argument('--type', choices=list(MERCH_TYPES.keys()), default='sticker',
                    help='类型: sticker(贴纸)/badge(徽章)/standee(立牌)/postcard(明信片)')
    ap.add_argument('--output', default=None, help='输出路径')
    ap.add_argument('--seed', type=int, default=-1)
    ap.add_argument('--no-transparent', action='store_true', help='不做透明底（保留背景）')
    ap.add_argument('--print', action='store_true', help='印刷模式（+出血线 CMYK，印刷厂规格）')
    args = ap.parse_args(argv)

    desc = ' '.join(args.desc)
    if not desc:
        print('用法: merch "描述" [--type sticker|badge|standee|postcard] [--print]')
        return 1
    try:
        generate_merch(desc, mtype=args.type, seed=args.seed, output=args.output,
                       transparent=not args.no_transparent, print_mode=args.print)
        return 0
    except Exception as e:
        print(f'❌ 周边生成失败: {str(e)[:150]}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
