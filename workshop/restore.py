#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/restore.py — 老照片修复（B-restore）v1.0
==================================================
B站 6.8K 热度场景：老照片修复（去模糊/高清化/上色）。
两条路径：
  1. 本地管线已有超分（postprocess 2x/4x）→ 先超分再增强
  2. 简易版：PIL 去噪 + 锐化 + 对比度 + 可选上色（黑白照→暖色调）

用法:
  python -m agents workshop restore <图片路径> [--color] [--output 路径]
"""

import argparse, os, sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent


def _restore_basic(image_path, output_path, color=False, sharpness=1.6,
                   contrast=1.1, denoise=True):
    """简易修复：去噪+锐化+对比度，可选上色（暖色调）。"""
    from PIL import Image, ImageEnhance, ImageFilter

    img = Image.open(image_path).convert('RGB')

    # 1. 去噪（轻微模糊去掉噪点）
    if denoise:
        img = img.filter(ImageFilter.MedianFilter(size=3))

    # 2. 锐化（清晰度）
    img = ImageEnhance.Sharpness(img).enhance(sharpness)

    # 3. 对比度/色彩增强
    img = ImageEnhance.Contrast(img).enhance(contrast)
    img = ImageEnhance.Color(img).enhance(1.15)

    # 4. 上色（黑白/褪色照 → 暖色调修复感）
    if color:
        r, g, b = img.split()
        r = r.point(lambda x: min(255, int(x * 1.08)))
        g = g.point(lambda x: min(255, int(x * 1.02)))
        b = b.point(lambda x: int(x * 0.96))
        img = Image.merge('RGB', (r, g, b))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, quality=95)
    return output_path


def _restore_upscale(image_path, output_path, factor=2):
    """尝试调用管线超分（若可用）——先超分再修复。"""
    try:
        from agents.postprocess import upscale_image
        upscaled = upscale_image(image_path, factor=factor)
        if upscaled:
            return _restore_basic(upscaled, output_path, color=False)
    except Exception:
        pass
    # 超分不可用 → 直接 PIl 放大（LANCZOS 平滑）
    from PIL import Image
    img = Image.open(image_path).convert('RGB')
    w, h = img.size
    img = img.resize((w * factor, h * factor), Image.LANCZOS)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, quality=95)
    return output_path


def _restore_scratch(image_path, output_path, strength=2):
    """划痕修复：检测高亮/暗色线条划痕并修复。

    方法：亮度极值检测（划痕通常是异常亮/暗的细线）→ 中值滤波定向替换。
    """
    from PIL import Image, ImageFilter
    import numpy as np

    img = Image.open(image_path).convert('L')
    arr = np.array(img, dtype=np.float32)

    # 划痕 = 与周围差异极大的像素（高亮白线或暗线）
    med = np.array(img.filter(ImageFilter.MedianFilter(size=5)), dtype=np.float32)
    diff = np.abs(arr - med)

    # 阈值：差异 > 3σ 视为划痕
    sigma = diff.std() + 1e-6
    mask = diff > (sigma * 3.0)

    # 修复：划痕像素用中值替换（多次迭代提高覆盖）
    repaired = np.array(img.filter(ImageFilter.MedianFilter(size=7)), dtype=np.float32)
    out_arr = arr.copy()
    n_fixed = int(mask.sum())  # 初始划痕像素数（统计用）
    for _ in range(strength):
        out_arr[mask] = repaired[mask]
        # 重新检测（修复后再查一遍）
        med2 = np.array(Image.fromarray(out_arr.astype(np.uint8)).filter(ImageFilter.MedianFilter(size=5)), dtype=np.float32)
        diff2 = np.abs(out_arr - med2)
        mask = diff2 > (diff2.std() + 1e-6) * 3.0

    out_img = Image.fromarray(out_arr.astype(np.uint8)).convert('RGB')
    out_img.save(output_path)
    print(f'  🩹 划痕修复: {n_fixed} 像素')
    return output_path


def restore_photo(image_path, output=None, color=False, upscale=0, scratch=False):
    """老照片修复入口。

    Args:
        image_path: 照片路径
        output: 输出路径（默认 outputs/restored_<ts>.png）
        color: 上色模式（黑白照→暖色调）
        upscale: 超分倍率（0=不超分，2=2x，4=4x）
        scratch: 划痕修复（老照片白线/暗线）

    Returns:
        输出路径
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f'照片不存在: {image_path}')
    import time
    out_path = output or str(PROJECT / 'outputs' / f"restored_{time.strftime('%Y%m%d_%H%M%S')}.png")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    from workshop.image_utils import open_image_safe
    open_image_safe(image_path)  # 校验图片可读（损坏→友好 ValueError）
    # 流水线式组合（任意组合可同时用）：
    # scratch → basic(去噪/锐化/上色) → upscale
    current = image_path
    tmp_path = out_path + '.tmp.png'

    if scratch:
        print(f'  🩹 划痕修复...')
        _restore_scratch(current, tmp_path)
        current = tmp_path

    # 基础修复（去噪+锐化+可选上色）——除非只做划痕/超分
    if not (scratch and upscale <= 1 and not color):
        print(f'  ✨ 基础修复（去噪+锐化{"+上色" if color else ""}）...')
        _restore_basic(current, tmp_path, color=color)
        current = tmp_path

    if upscale > 1:
        print(f'  🔍 超分 {upscale}x...')
        _restore_upscale(current, out_path, factor=upscale)
        current = out_path
    else:
        with open(current, 'rb') as f_in, open(out_path, 'wb') as f_out:
            f_out.write(f_in.read())

    # 清理临时文件
    if os.path.exists(tmp_path) and tmp_path != out_path:
        os.remove(tmp_path)
    if os.path.exists(current) and current != out_path and current != image_path:
        try:
            os.remove(current)
        except Exception:
            pass

    print(f'  🎨 修复完成: {out_path}')
    if color:
        print(f'  🌈 已上色（暖色调）')
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop restore', description='老照片修复（去噪/锐化/上色）')
    ap.add_argument('image', help='照片路径')
    ap.add_argument('--color', action='store_true', help='上色模式（黑白→暖色）')
    ap.add_argument('--upscale', type=int, default=0, help='超分倍率 (2/4)')
    ap.add_argument('--scratch', action='store_true', help='划痕修复（白线/暗线）')
    ap.add_argument('--output', default=None, help='输出路径')
    args = ap.parse_args(argv)

    try:
        restore_photo(args.image, output=args.output, color=args.color,
                      upscale=args.upscale, scratch=args.scratch)
        return 0
    except Exception as e:
        print(f'❌ 修复失败: {str(e)[:150]}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
