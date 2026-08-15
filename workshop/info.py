#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/info.py — 图片信息查看（B-info）v1.0
==============================================
核心工具：查看图片信息——尺寸/格式/EXIF/AI 生成参数（ComfyUI metadata）。
用途：
  - 确认 AI 生成图的参数（seed/prompt/模型）
  - 批量检查图片规格

用法:
  python -m agents workshop info <图片> [--full]
"""

import argparse, json, os, sys
from pathlib import Path


def _get_info(image_path):
    """提取图片信息。"""
    from PIL import Image
    from workshop.image_utils import open_image_safe
    img = open_image_safe(image_path)
    info = {
        '文件': os.path.basename(image_path),
        '路径': os.path.abspath(image_path),
        '格式': img.format,
        '模式': img.mode,
        '尺寸': f'{img.width}x{img.height}',
        '大小': f'{os.path.getsize(image_path) / 1024:.1f} KB',
    }
    # EXIF 基础信息
    try:
        exif = img.getexif()
        if exif:
            import datetime
            for tag in (36867, 306):  # DateTimeOriginal, DateTime
                if tag in exif:
                    info['拍摄时间'] = str(exif[tag])
                    break
            if 271 in exif:
                info['设备'] = str(exif[271])
            if 272 in exif:
                info['设备型号'] = str(exif[272])
    except Exception:
        pass
    return info


def _get_ai_meta(image_path):
    """提取 AI 生成参数（ComfyUI PNG metadata）。"""
    from PIL import Image
    img = Image.open(image_path)
    meta = {}
    try:
        # PNG tEXt chunks（ComfyUI 存 prompt/workflow）
        for k, v in img.info.items():
            if k in ('prompt', 'workflow', 'parameters', 'Description'):
                meta[k] = v[:2000] if v else ''
    except Exception:
        pass
    return meta


def batch_info(image_dir, glob_pattern='*.png'):
    """批量图片信息（目录规格检查——尺寸/格式/AI参数汇总表）。

    Args:
        image_dir: 图片目录
        glob_pattern: 匹配模式

    Returns:
        [(文件名, 尺寸, 格式, 大小, AI参数?)]
    """
    import glob
    imgs = sorted(glob.glob(os.path.join(image_dir, glob_pattern)))
    if not imgs:
        print(f'⚠️ {image_dir} 下无 {glob_pattern} 文件')
        return []
    rows = []
    print(f'\n📚 目录图片信息（{len(imgs)} 张）:')
    print(f'  {"文件":<32} {"尺寸":<12} {"格式":<6} {"大小":<10} AI参数')
    print(f'  ' + '-' * 70)
    for img in imgs:
        try:
            info = _get_info(img)
            ai = _get_ai_meta(img)
            rows.append((os.path.basename(img), info['尺寸'], info['格式'], info['大小'], bool(ai)))
            print(f'  {os.path.basename(img):<32} {info["尺寸"]:<12} {info["格式"]:<6} {info["大小"]:<10} {"✅" if ai else "—"}')
        except Exception as e:
            print(f'  {os.path.basename(img):<32} ⚠️ {str(e)[:40]}')
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop info', description='图片信息查看')
    ap.add_argument('image', help='图片路径（或 --dir 目录）')
    ap.add_argument('--full', action='store_true', help='显示完整 AI 生成参数（可能很长）')
    ap.add_argument('--dir', default=None, help='批量查看目录（所有 png/jpg 汇总表）')
    args = ap.parse_args(argv)

    # 批量模式
    if args.dir:
        batch_info(args.dir)
        return 0

    if not os.path.exists(args.image):
        print(f'❌ 图片不存在: {args.image}')
        return 1

    info = _get_info(args.image)
    print(f'\n📋 图片信息:')
    for k, v in info.items():
        print(f'  {k}: {v}')

    ai_meta = _get_ai_meta(args.image)
    if ai_meta:
        print(f'\n🤖 AI 生成参数:')
        for k, v in ai_meta.items():
            if args.full or k != 'workflow':
                print(f'  [{k}] {v[:500]}{"..." if len(v) > 500 else ""}')
            else:
                print(f'  [{k}] (工作流完整 JSON，用 --full 查看)')
    else:
        print(f'\nℹ️ 未检测到 AI 生成参数（普通图片）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
