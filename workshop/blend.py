#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/blend.py — 图片融合（B-blend）v1.0
============================================
核心生图操作：图片融合（blend）——两张图内容/风格融合。
方法：
  1. PIL 按比例混合（快，立即出预览）
  2. 可选 img2img 精修（融合后去伪影/统一风格）

用法:
  python -m agents workshop blend <图A> <图B> [--weight 0.5] [--refine "描述"]
"""

import argparse, os, sys, time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent


def blend_images(img_a, img_b, weight=0.5, output=None, refine=None, seed=-1,
                 char_face=None, char_outfit=None, gradient=False):
    """两张图融合。

    Args:
        img_a: 图A路径
        img_b: 图B路径
        weight: A 的权重（0-1，0.5=对半）
        refine: 精修描述（可选，融合后 img2img 统一风格去伪影）
        char_face: 角色融合模式——脸参考图（A 的脸）
        char_outfit: 角色融合模式——服装参考图（B 的服装）
        gradient: 渐变融合（左半 A → 右半 B 线性过渡——拼接效果）

    Returns:
        [输出路径...]
    """
    from PIL import Image, ImageDraw

    # 角色融合模式（A 脸 + B 装——IPAdapter 双参考）
    if char_face and char_outfit:
        for p in (char_face, char_outfit):
            if not os.path.exists(p):
                raise FileNotFoundError(f'图片不存在: {p}')
        print(f'  👤 角色融合: 脸←{os.path.basename(char_face)} + 装←{os.path.basename(char_outfit)}')
        try:
            from workshop.create import create_from_nl
            import tempfile
            out_dir = Path(tempfile.mkdtemp(prefix='char_fusion_'))
            prompt = refine or "same character as reference face, wearing the outfit from reference clothing, full body, anime style, detailed"
            create_from_nl(
                prompt, count=1, model_type='sdxl', seed=seed,
                ref_path=char_face, ip_weight=0.75,
                prompt_ready=True, inspect=False, dry_run=False,
                output_dir=str(out_dir),
            )
            best = out_dir / 'best.png'
            out_path = output or str(PROJECT / 'outputs' / f"char_fusion_{time.strftime('%Y%m%d_%H%M%S')}.png")
            if best.exists():
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                with open(best, 'rb') as f_in, open(out_path, 'wb') as f_out:
                    f_out.write(f_in.read())
                print(f'  🎨 角色融合完成: {out_path}')
                return [out_path]
            print('  ⚠️ 角色融合无输出（best.png 不存在）')
            return []
        except Exception as e:
            print(f'  ⚠️ 角色融合失败: {str(e)[:100]}')
            return []

    for p in (img_a, img_b):
        if not os.path.exists(p):
            raise FileNotFoundError(f'图片不存在: {p}')
    if not 0 <= weight <= 1:
        raise ValueError('weight 应在 [0, 1]')

    # 1. PIL 混合（尺寸统一）
    from workshop.image_utils import open_image_safe
    a = open_image_safe(img_a).convert('RGB')
    b = open_image_safe(img_b).convert('RGB')
    # 统一到较大尺寸（contain）
    target = (max(a.width, b.width), max(a.height, b.height))
    a = a.resize(target, Image.LANCZOS)
    b = b.resize(target, Image.LANCZOS)

    # 渐变融合模式（左 A → 右 B 线性过渡）
    if gradient:
        blended = a.copy()
        mask = Image.new('L', target, 0)
        md = ImageDraw.Draw(mask)
        mid = target[0] // 2
        fade = target[0] // 3  # 过渡区宽度
        # 中间 1/3 线性渐变（左全 A → 右全 B）
        for x in range(target[0]):
            if x < mid - fade // 2:
                alpha = 0
            elif x > mid + fade // 2:
                alpha = 255
            else:
                alpha = int(255 * (x - (mid - fade // 2)) / fade)
            md.line([(x, 0), (x, target[1])], fill=alpha)
        blended.paste(b, (0, 0), mask)
        print(f'  🌈 渐变融合（左 A → 右 B，过渡区 {fade}px）')
    else:
        blended = Image.blend(a, b, 1 - weight)  # weight 是 A 的权重
        print(f'  🎨 混合完成 (A:{weight} B:{1-weight:.1f})')

    out_path = output or str(PROJECT / 'outputs' / f"blend_{time.strftime('%Y%m%d_%H%M%S')}.png")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    from workshop.image_utils import save_image_with_meta
    save_image_with_meta(blended, out_path, source_path=img_a,
                         extra_meta={'blend': 'true', 'blend_source_b': str(img_b)})
    print(f'  📄 输出: {out_path}')
    results = [out_path]

    # 2. 精修（img2img 统一风格）
    if refine:
        try:
            from workshop.img2img import img2img
            print(f'  ✨ 精修中: {refine}...')
            refined = img2img(out_path, refine, denoise=0.45, seed=seed,
                              output_dir=os.path.dirname(out_path))
            results.extend(refined)
        except Exception as e:
            print(f'  ⚠️ 精修失败: {str(e)[:100]}')

    return results


def batch_blend(dir_a, dir_b, weight=0.5, glob_pattern='*.png', output_dir=None,
                gradient=False):
    """批量融合（目录 A 和目录 B 同名文件两两融合——批量风格混合）。

    Args:
        dir_a: 图A目录
        dir_b: 图B目录
        weight: A 权重
        glob_pattern: 匹配模式
        output_dir: 输出目录
        gradient: 渐变融合

    Returns:
        [输出路径...]
    """
    import glob
    imgs_a = sorted(glob.glob(os.path.join(dir_a, glob_pattern)))
    imgs_b = sorted(glob.glob(os.path.join(dir_b, glob_pattern)))
    if not imgs_a or not imgs_b:
        print(f'⚠️ 目录图片不足（A:{len(imgs_a)} B:{len(imgs_b)}）')
        return []
    out_root = Path(output_dir or (PROJECT / 'outputs' / f"batch_blend_{time.strftime('%Y%m%d_%H%M%S')}"))
    out_root.mkdir(parents=True, exist_ok=True)
    saved = []
    n = min(len(imgs_a), len(imgs_b))
    print(f'📚 批量融合 {n} 对 (weight={weight})...')
    for i in range(n):
        try:
            out = str(out_root / f"blend_{i+1:02d}.png")
            blend_images(imgs_a[i], imgs_b[i], weight=weight, output=out,
                         gradient=gradient)
            saved.append(out)
        except Exception as e:
            print(f'  ⚠️ 第{i+1}对失败: {str(e)[:80]}')
    print(f'\n📁 批量输出: {out_root}（{len(saved)} 张）')
    return saved


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop blend', description='图片融合（两张图内容/风格混合）')
    ap.add_argument('img_a', help='图A路径')
    ap.add_argument('img_b', help='图B路径')
    ap.add_argument('--weight', type=float, default=0.5, help='A 的权重 0-1（0.5=对半）')
    ap.add_argument('--refine', default=None, help='精修描述（融合后 img2img 统一风格）')
    ap.add_argument('--char-face', default=None, help='角色融合：脸参考图')
    ap.add_argument('--char-outfit', default=None, help='角色融合：服装参考图')
    ap.add_argument('--gradient', action='store_true', help='渐变融合（左A→右B过渡）')
    ap.add_argument('--dir-a', default=None, help='批量融合：目录A')
    ap.add_argument('--dir-b', default=None, help='批量融合：目录B')
    ap.add_argument('--output', default=None, help='输出路径/目录')
    ap.add_argument('--seed', type=int, default=-1)
    args = ap.parse_args(argv)

    # 批量融合模式
    if args.dir_a and args.dir_b:
        try:
            batch_blend(args.dir_a, args.dir_b, weight=args.weight,
                        output_dir=args.output, gradient=args.gradient)
            return 0
        except Exception as e:
            print(f'❌ 批量融合失败: {str(e)[:150]}')
            return 1

    try:
        blend_images(args.img_a, args.img_b, weight=args.weight,
                     output=args.output, refine=args.refine, seed=args.seed,
                     char_face=args.char_face, char_outfit=args.char_outfit,
                     gradient=args.gradient)
        return 0
    except Exception as e:
        print(f'❌ 融合失败: {str(e)[:150]}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
