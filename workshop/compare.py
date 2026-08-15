#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/compare.py — 前后对比图（B-compare）v1.0
==================================================
B站超火展示形式：原图 vs 结果并排对比（修图/重绘/扩图前后）。
PIL 纯本地：并排拼接 + 中间分隔线 + 可选标注。

用法:
  python -m agents workshop compare <原图> <结果图> [--output 对比.png] [--vertical]
"""

import argparse, os, sys, time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent


def make_compare(before, after, output=None, vertical=False, labels=True,
                 label_a='原图', label_b='结果'):
    """并排对比图（原图 vs 结果）。

    Args:
        before: 原图路径
        after: 结果图路径
        vertical: True=上下排，False=左右排
        labels: 是否标注

    Returns:
        输出路径
    """
    from PIL import Image, ImageDraw, ImageFont

    for p in (before, after):
        if not os.path.exists(p):
            raise FileNotFoundError(f'图片不存在: {p}')

    from workshop.image_utils import open_image_safe
    a = open_image_safe(before).convert('RGB')
    b = open_image_safe(after).convert('RGB')

    # 统一尺寸（contain 到相同区域）
    if vertical:
        # 上下：宽度统一
        w = max(a.width, b.width)
        a2 = Image.new('RGB', (w, a.height), (0, 0, 0))
        a2.paste(a, ((w - a.width) // 2, 0))
        b2 = Image.new('RGB', (w, b.height), (0, 0, 0))
        b2.paste(b, ((w - b.width) // 2, 0))
        label_h = 40 if labels else 0
        canvas = Image.new('RGB', (w, a.height + b.height + label_h + 6), (255, 255, 255))
        y = 0
        if labels:
            d = ImageDraw.Draw(canvas)
            try:
                font = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 24)
            except OSError:
                font = ImageFont.load_default()
            for text, img, yy in ((label_a, a2, label_h), (label_b, b2, label_h + a.height + 6)):
                d.text((20, yy + 6), text, fill=(0, 0, 0), font=font)
            y = label_h
        canvas.paste(a2, (0, y))
        canvas.paste(b2, (0, y + a.height + 6))
    else:
        # 左右：高度统一
        h = max(a.height, b.height)
        a2 = Image.new('RGB', (a.width, h), (0, 0, 0))
        a2.paste(a, (0, (h - a.height) // 2))
        b2 = Image.new('RGB', (b.width, h), (0, 0, 0))
        b2.paste(b, (0, (h - b.height) // 2))
        label_h = 40 if labels else 0
        canvas = Image.new('RGB', (a.width + b.width + 6, h + label_h), (255, 255, 255))
        if labels:
            d = ImageDraw.Draw(canvas)
            try:
                font = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 24)
            except OSError:
                font = ImageFont.load_default()
            d.text((20, 8), label_a, fill=(0, 0, 0), font=font)
            d.text((a.width + 26, 8), label_b, fill=(0, 0, 0), font=font)
        canvas.paste(a2, (0, label_h))
        canvas.paste(b2, (a.width + 6, label_h))

    out_path = output or str(PROJECT / 'outputs' / f"compare_{time.strftime('%Y%m%d_%H%M%S')}.png")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    canvas.save(out_path)
    print(f'  🖼️ 对比图: {out_path} ({canvas.width}x{canvas.height})')
    return out_path


def batch_compare(dir_before, dir_after, glob_pattern='*.png', output_dir=None,
                  vertical=False):
    """批量对比（目录配对——原图目录 vs 结果目录同名文件）。

    Args:
        dir_before: 原图目录
        dir_after: 结果目录
        glob_pattern: 匹配模式
        output_dir: 输出目录
        vertical: 上下排

    Returns:
        [输出路径...]
    """
    import glob
    imgs_before = sorted(glob.glob(os.path.join(dir_before, glob_pattern)))
    imgs_after = sorted(glob.glob(os.path.join(dir_after, glob_pattern)))
    if not imgs_before or not imgs_after:
        print(f'⚠️ 目录图片不足（before:{len(imgs_before)} after:{len(imgs_after)}）')
        return []
    out_root = Path(output_dir or (PROJECT / 'outputs' / f"batch_compare_{time.strftime('%Y%m%d_%H%M%S')}"))
    out_root.mkdir(parents=True, exist_ok=True)
    saved = []
    n = min(len(imgs_before), len(imgs_after))
    print(f'📚 批量对比 {n} 对...')
    for i in range(n):
        try:
            out = str(out_root / f"cmp_{i+1:02d}.png")
            make_compare(imgs_before[i], imgs_after[i], output=out, vertical=vertical)
            saved.append(out)
        except Exception as e:
            print(f'  ⚠️ 第{i+1}对失败: {str(e)[:80]}')
    print(f'\n📁 批量输出: {out_root}（{len(saved)} 张）')
    return saved


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop compare', description='前后对比图（原图vs结果）')
    ap.add_argument('before', help='原图路径')
    ap.add_argument('after', help='结果图路径')
    ap.add_argument('--output', default=None, help='输出路径')
    ap.add_argument('--vertical', action='store_true', help='上下排（默认左右）')
    ap.add_argument('--no-labels', action='store_true', help='不标注')
    ap.add_argument('--label-a', default='原图', help='左侧标注')
    ap.add_argument('--label-b', default='结果', help='右侧标注')
    ap.add_argument('--dir-before', default=None, help='批量对比：原图目录')
    ap.add_argument('--dir-after', default=None, help='批量对比：结果目录')
    ap.add_argument('--output', default=None, help='输出路径/目录')
    args = ap.parse_args(argv)

    # 批量模式
    if args.dir_before and args.dir_after:
        try:
            batch_compare(args.dir_before, args.dir_after,
                          output_dir=args.output, vertical=args.vertical)
            return 0
        except Exception as e:
            print(f'❌ 批量对比失败: {str(e)[:150]}')
            return 1

    try:
        make_compare(args.before, args.after, output=args.output,
                     vertical=args.vertical, labels=not args.no_labels,
                     label_a=args.label_a, label_b=args.label_b)
        return 0
    except Exception as e:
        print(f'❌ 对比图失败: {str(e)[:150]}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
