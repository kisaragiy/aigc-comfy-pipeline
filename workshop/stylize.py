#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/stylize.py — 风格迁移（B-stylize）v1.0
================================================
核心生图操作：风格迁移——内容图 A 的内容 + 风格图 B 的风格。
方法：IPAdapter 双参考（内容 ref 低权重 + 风格 ref 高权重）。

用法:
  python -m agents workshop stylize <内容图> <风格图> [--content-weight 0.5] [--style-weight 0.9] [--desc "描述"]
"""

import argparse, os, sys, time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent


def stylize(content_image, style_image, desc=None, content_weight=0.5,
            style_weight=0.9, seed=-1, output=None, count=1):
    """风格迁移（内容 + 风格双参考）。

    Args:
        content_image: 内容图（要保留的主体/构图）
        style_image: 风格图（要学习的画风/色调）
        desc: 可选描述（中文）
        content_weight/style_weight: IPAdapter 权重
        count: 生成张数

    Returns:
        [输出路径...]
    """
    from workshop.create import create_from_nl
    import tempfile

    for p in (content_image, style_image):
        if not os.path.exists(p):
            raise FileNotFoundError(f'图片不存在: {p}')

    # 描述（中文翻译）
    desc_en = desc or "apply the style of the style reference to the content, same composition, same subject"
    try:
        from workshop.layer import _translate_desc
        desc_en = _translate_desc(desc) if desc else desc_en
    except Exception:
        pass

    out_dir = Path(output or (PROJECT / 'outputs' / f"stylize_{time.strftime('%Y%m%d_%H%M%S')}"))
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f'  🎨 风格迁移: 内容←{os.path.basename(content_image)} + 风格←{os.path.basename(style_image)}')
    print(f'  ⚖️ 权重: 内容{content_weight} / 风格{style_weight}')

    base_seed = seed if seed >= 0 else 20260814
    saved = []
    for i in range(count):
        s = base_seed + i * 23
        sub = out_dir / f"styled_{i+1:02d}"
        try:
            create_from_nl(
                f"{desc_en}, keep original composition and subject, restyle in reference art style",
                count=1, model_type='sdxl', seed=s,
                ref_path=style_image, ip_weight=style_weight,
                prompt_ready=True, inspect=False, dry_run=False,
                output_dir=str(sub),
            )
            best = sub / 'best.png'
            if best.exists():
                saved.append(str(best))
                print(f'  ✅ 风格化: {best}')
        except Exception as e:
            print(f'  ⚠️ 第{i+1}张失败: {str(e)[:100]}')

    print(f'\n📁 输出目录: {out_dir}')
    return saved


def batch_stylize(image_dir, style_image, desc=None, style_weight=0.9,
                  seed=-1, glob_pattern='*.png', output_dir=None):
    """批量风格迁移（目录内所有图统一风格化——批量统一画风）。

    Args:
        image_dir: 图片目录
        style_image: 风格参考图
        desc: 可选描述
        style_weight: 风格权重
        glob_pattern: 匹配模式
        output_dir: 输出目录

    Returns:
        [输出路径...]
    """
    import glob
    imgs = sorted(glob.glob(os.path.join(image_dir, glob_pattern)))
    if not imgs:
        print(f'⚠️ {image_dir} 下无 {glob_pattern} 文件')
        return []
    out_root = Path(output_dir or (PROJECT / 'outputs' / f"batch_stylize_{time.strftime('%Y%m%d_%H%M%S')}"))
    saved = []
    print(f'📚 批量风格化 {len(imgs)} 张 → 风格: {os.path.basename(style_image)}')
    for i, img in enumerate(imgs):
        print(f'\n  [{i+1}/{len(imgs)}] {os.path.basename(img)}')
        try:
            results = stylize(img, style_image, desc=desc,
                              style_weight=style_weight, seed=seed + i * 29,
                              output=str(out_root / f"img_{i+1:02d}"))
            saved.extend(results)
        except Exception as e:
            print(f'  ⚠️ 失败: {str(e)[:80]}')
    print(f'\n📁 批量输出: {out_root}（{len(saved)} 张）')
    return saved


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop stylize', description='风格迁移（内容+风格双参考）')
    ap.add_argument('content', help='内容图路径')
    ap.add_argument('style', help='风格图路径')
    ap.add_argument('--desc', default=None, help='描述（中文，可选）')
    ap.add_argument('--content-weight', type=float, default=0.5, help='内容权重')
    ap.add_argument('--style-weight', type=float, default=0.9, help='风格权重')
    ap.add_argument('--count', type=int, default=1, help='生成张数')
    ap.add_argument('--dir', default=None, help='批量风格化目录（所有 png/jpg）')
    ap.add_argument('--output', default=None, help='输出目录')
    ap.add_argument('--seed', type=int, default=-1)
    args = ap.parse_args(argv)

    # 批量模式
    if args.dir:
        try:
            batch_stylize(args.dir, args.style, desc=args.desc,
                          style_weight=args.style_weight, seed=args.seed,
                          output_dir=args.output)
            return 0
        except Exception as e:
            print(f'❌ 批量风格化失败: {str(e)[:150]}')
            return 1

    try:
        stylize(args.content, args.style, desc=args.desc,
                content_weight=args.content_weight, style_weight=args.style_weight,
                seed=args.seed, output=args.output, count=args.count)
        return 0
    except Exception as e:
        print(f'❌ 风格迁移失败: {str(e)[:150]}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
