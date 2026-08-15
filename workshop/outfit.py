#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/outfit.py — 服装上身图（B-outfit）v1.0
================================================
B站 122K 热度：平铺服装图 → 模特上身展示（电商/服装设计）。
用 IPAdapter 参考图（服装图作为 ref）+ 模特 prompt → 生成上身效果。

用法:
  python -m agents workshop outfit <服装图> [--desc "连衣裙"] [--model female|male]
"""

import argparse, os, sys, time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent

# 模特 prompt（IPAdapter 参考服装 → 上身）
MODEL_PROMPTS = {
    "female": "an elegant young woman modeling the outfit, full body, fashion photography, studio lighting, clean background, looking at camera, stylish pose",
    "male": "a handsome young man modeling the outfit, full body, fashion photography, studio lighting, clean background, looking at camera, stylish pose",
}


def generate_outfit(clothing_image, desc=None, model='female', count=1,
                    output_dir=None, seed=-1, ip_weight=0.85):
    """平铺服装 → 模特上身展示。

    Args:
        clothing_image: 服装图路径（平铺/挂拍）
        desc: 服装描述（可选，辅助 prompt）
        model: female/male 模特
        count: 生成张数
        output_dir: 输出目录

    Returns:
        [输出路径...]
    """
    from workshop.create import create_from_nl
    from workshop.image_utils import open_image_safe

    # 服装图校验（缺图/损坏 → 立即友好报错，不默默跑完全流程）
    open_image_safe(clothing_image)

    out_dir = Path(output_dir or (PROJECT / 'outputs' / f"outfit_{time.strftime('%Y%m%d_%H%M%S')}"))
    out_dir.mkdir(parents=True, exist_ok=True)

    # 中文翻译服装描述
    desc_en = desc or "this outfit"
    try:
        from workshop.layer import _translate_desc
        desc_en = _translate_desc(desc) if desc else "this outfit"
    except Exception:
        pass

    prompt = f"{desc_en}, {MODEL_PROMPTS[model]}"
    print(f'  👗 服装参考: {clothing_image}')
    print(f'  💃 模特: {model} | prompt: {prompt[:80]}...')

    base_seed = seed if seed >= 0 else 20260814
    saved = []
    for i in range(count):
        s = base_seed + i * 7
        sub = out_dir / f"model_{i+1:02d}"
        try:
            create_from_nl(
                prompt, count=1, model_type='sdxl', seed=s,
                ref_path=clothing_image, ip_weight=ip_weight,
                prompt_ready=True, inspect=False, dry_run=False,
                output_dir=str(sub),
            )
            best = sub / 'best.png'
            if best.exists():
                saved.append(str(best))
                print(f'  ✅ 上身图: {best}')
        except Exception as e:
            print(f'  ⚠️ 失败: {str(e)[:100]}')

    print(f'\n📁 输出目录: {out_dir}')
    return saved


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop outfit', description='服装上身图（平铺→模特展示）')
    ap.add_argument('clothing_image', help='服装图路径（平铺/挂拍）')
    ap.add_argument('--desc', default=None, help='服装描述（可选）')
    ap.add_argument('--model', choices=list(MODEL_PROMPTS.keys()), default='female',
                    help='模特 (female/male)')
    ap.add_argument('--count', type=int, default=1, help='生成张数')
    ap.add_argument('--output', default=None, help='输出目录')
    ap.add_argument('--seed', type=int, default=-1)
    args = ap.parse_args(argv)

    if not os.path.exists(args.clothing_image):
        print(f'❌ 服装图不存在: {args.clothing_image}')
        return 1
    try:
        generate_outfit(args.clothing_image, desc=args.desc, model=args.model,
                        count=args.count, output_dir=args.output, seed=args.seed)
        return 0
    except Exception as e:
        print(f'❌ 失败: {str(e)[:150]}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
