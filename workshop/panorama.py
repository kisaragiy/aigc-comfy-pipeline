#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/panorama.py — 全景拼接（B-panorama）v1.0
==================================================
核心生图操作：多张图拼接全景/长图。
方法：
  1. 多张图按序横向/纵向拼接
  2. 高度统一（contain 到最小高度）
  3. 可选 img2img 融合接缝（--refine）

用法:
  python -m agents workshop panorama <图1> <图2> [<图3>...] [--vertical] [--refine "描述"]
"""

import argparse, os, sys, time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent


def make_panorama(images, vertical=False, output=None, refine=None, seed=-1):
    """多图拼接全景。

    Args:
        images: [路径...]（>=2 张）
        vertical: True=纵向（长条漫），False=横向（全景）
        refine: 可选 img2img 融合接缝

    Returns:
        [输出路径...]
    """
    from PIL import Image
    from workshop.image_utils import open_image_safe

    if len(images) < 2:
        raise ValueError('至少需要 2 张图')
    for p in images:
        if not os.path.exists(p):
            raise FileNotFoundError(f'图片不存在: {p}')

    imgs = [open_image_safe(p).convert('RGB') for p in images]

    # 统一尺寸（contain 到最小高/宽）
    if vertical:
        w = min(i.width for i in imgs)
        imgs = [i.resize((w, int(i.height * w / i.width)), Image.LANCZOS) for i in imgs]
        canvas = Image.new('RGB', (w, sum(i.height for i in imgs)), (255, 255, 255))
        y = 0
        for i in imgs:
            canvas.paste(i, (0, y))
            y += i.height
        print(f'  🖼️ 纵向拼接 {len(imgs)} 张 → {canvas.width}x{canvas.height}')
    else:
        h = min(i.height for i in imgs)
        imgs = [i.resize((int(i.width * h / i.height), h), Image.LANCZOS) for i in imgs]
        canvas = Image.new('RGB', (sum(i.width for i in imgs), h), (255, 255, 255))
        x = 0
        for i in imgs:
            canvas.paste(i, (x, 0))
            x += i.width
        print(f'  🖼️ 横向拼接 {len(imgs)} 张 → {canvas.width}x{canvas.height}')

    out_path = output or str(PROJECT / 'outputs' / f"panorama_{time.strftime('%Y%m%d_%H%M%S')}.png")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    canvas.save(out_path)
    print(f'  ✅ 全景图: {out_path}')
    results = [out_path]

    # 可选融合接缝
    if refine:
        try:
            from workshop.img2img import img2img
            print(f'  ✨ 接缝融合: {refine}...')
            refined = img2img(out_path, refine, denoise=0.35, seed=seed,
                              output_dir=os.path.dirname(out_path))
            results.extend(refined)
        except Exception as e:
            print(f'  ⚠️ 融合失败: {str(e)[:80]}')

    return results


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop panorama', description='多图拼接全景/长图')
    ap.add_argument('images', nargs='+', help='图片路径（>=2 张）')
    ap.add_argument('--vertical', action='store_true', help='纵向拼接（长条漫）')
    ap.add_argument('--refine', default=None, help='接缝融合描述（img2img）')
    ap.add_argument('--output', default=None, help='输出路径')
    ap.add_argument('--seed', type=int, default=-1)
    args = ap.parse_args(argv)

    try:
        make_panorama(args.images, vertical=args.vertical, output=args.output,
                      refine=args.refine, seed=args.seed)
        return 0
    except Exception as e:
        print(f'❌ 全景拼接失败: {str(e)[:150]}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
