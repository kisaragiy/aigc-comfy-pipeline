#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/colorgrade.py — 色彩氛围统一（画师流程 M4）v1.0
=========================================================
画师收尾: 整体色彩平衡（全局色调统一，消除"花"感）。
自动化: PIL 自动白平衡 + 可选色温/饱和度微调 → 统一氛围。

用法:
  python -m agents workshop colorgrade <图片> [--warm 0.1] [--saturation 1.05] [--output 路径]
      --warm 0.1        色温偏移（正=暖，负=冷，0=自动白平衡）
      --saturation 1.05 饱和度倍率
      --strength 0.5    调整强度（0-1，默认 0.5 保守）
"""

import argparse, os, re, sys
from pathlib import Path


def colorgrade(image_path, warm=None, saturation=1.05, strength=0.5, output=None):
    """全局色彩平衡 → 返回输出路径列表。

    warm=None 时自动白平衡（灰色世界假设）；warm 数值 = 色温偏移（正暖负冷）。
    strength 控制调整强度（0=原图，1=全量）。
    """
    from PIL import Image, ImageEnhance, ImageStat

    img = Image.open(image_path).convert('RGB')

    # 1. 自动白平衡（灰色世界假设：RGB 均值拉平）
    stat = ImageStat.Stat(img)
    means = stat.mean  # [R, G, B]
    avg = sum(means) / 3
    gains = [avg / max(m, 1e-6) for m in means]

    # 2. 色温偏移（warm>0 暖，<0 冷）
    if warm is not None:
        gains[0] *= (1 + warm * 0.3)      # R 通道
        gains[2] *= (1 - warm * 0.3)      # B 通道

    # 3. 应用增益（按 strength 插值）
    r, g, b = img.split()
    import PIL.Image as I
    r = r.point(lambda v, g_=gains[0], s_=strength: _blend(v, v * g_, s_))
    g = g.point(lambda v, g_=gains[1], s_=strength: _blend(v, v * g_, s_))
    b = b.point(lambda v, g_=gains[2], s_=strength: _blend(v, v * g_, s_))
    img = I.merge('RGB', (r, g, b))

    # 4. 饱和度微调
    if saturation != 1.0:
        img = ImageEnhance.Color(img).enhance(1 + (saturation - 1) * strength)

    # 5. 保存
    out = output or (Path(image_path).parent / f'color_grade_{Path(image_path).stem}.png')
    out = str(out)
    img.save(out)
    print(f'  🎨 色彩统一完成: {out}')
    print(f'  （白平衡增益 R:{gains[0]:.2f} G:{gains[1]:.2f} B:{gains[2]:.2f}'
          + (f' | 色温 {"暖" if warm > 0 else "冷"}{abs(warm):.2f}' if warm is not None else ' | 自动白平衡')
          + f' | 饱和度 x{saturation}）')
    return [out]


def _blend(orig, adjusted, strength):
    """插值：strength=0 原图，1 全量调整"""
    return int(orig + (adjusted - orig) * strength)


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop colorgrade', description='色彩氛围统一（画师 M4）')
    ap.add_argument('image', help='待调整图片')
    ap.add_argument('--warm', type=float, default=None,
                    help='色温偏移（正=暖，负=冷；缺省=自动白平衡）')
    ap.add_argument('--saturation', type=float, default=1.05, help='饱和度倍率（默认 1.05）')
    ap.add_argument('--strength', type=float, default=0.5, help='调整强度 0-1（默认 0.5 保守）')
    ap.add_argument('--output', default=None, help='输出路径（默认同目录 color_grade_前缀）')
    args = ap.parse_args(argv)

    img = os.path.expanduser(args.image)
    m = re.match(r'^/([a-zA-Z])/(.*)$', img)
    if m:
        img = m.group(1) + ':/' + m.group(2)
    if not os.path.exists(img):
        print(f'图片不存在: {img}')
        return 1
    try:
        colorgrade(img, warm=args.warm, saturation=args.saturation,
                   strength=args.strength, output=args.output)
        return 0
    except Exception as e:
        print(f'❌ 色彩统一失败: {str(e)[:150]}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
