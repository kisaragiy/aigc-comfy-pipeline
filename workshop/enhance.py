#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/enhance.py — 高清修复管线（B-enhance）v1.0
====================================================
一键高清修复：去噪 → 超分 → 修脸 → 对比图（全链路串联）。
组合 restore（去噪/锐化/上色/超分）+ GFPGAN 修脸 + compare 对比。

用法:
  python -m agents workshop enhance <图片> [--upscale 2] [--color] [--face] [--compare]
"""

import argparse, os, sys, time
from pathlib import Path
import urllib.request

PROJECT = Path(__file__).resolve().parent.parent


def enhance(image_path, upscale=2, color=False, face=True, compare=True,
            output=None):
    """高清修复管线。

    Args:
        image_path: 原图路径
        upscale: 超分倍数（0=不超分）
        color: 上色（黑白老照片）
        face: 修脸（GFPGAN——检测到人脸时）
        compare: 输出前后对比图

    Returns:
        输出路径
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f'图片不存在: {image_path}')
    # 校验图片可读（损坏/非图片 → 立即友好报错，不静默走完全流程）
    from workshop.image_utils import open_image_safe
    open_image_safe(image_path)

    out_dir = Path(output or (PROJECT / 'outputs' / f"enhance_{time.strftime('%Y%m%d_%H%M%S')}"))
    out_dir.mkdir(parents=True, exist_ok=True)

    current = image_path
    steps = []

    # 1. 去噪 + 锐化 + 上色（restore）
    print(f'  🔧 1/4 去噪+锐化{"+上色" if color else ""}...')
    try:
        from workshop.restore import restore_photo
        r1 = str(out_dir / 'step1_restore.png')
        restore_photo(current, output=r1, color=color, upscale=0)
        current = r1
        steps.append('restore')
    except Exception as e:
        print(f'  ⚠️ 去噪失败: {str(e)[:80]}')

    # 2. 超分（restore upscale）
    if upscale > 1:
        print(f'  🔍 2/4 超分 ×{upscale}...')
        try:
            from workshop.restore import _restore_upscale
            r2 = str(out_dir / f'step2_upscale{upscale}x.png')
            _restore_upscale(current, r2, factor=upscale)
            current = r2
            steps.append(f'upscale{upscale}x')
        except Exception as e:
            print(f'  ⚠️ 超分失败: {str(e)[:80]}')
    else:
        print(f'  ⏭️ 2/4 跳过超分（--upscale 0）')

    # 3. 修脸（YOLO 检测 + 局部重绘修复——复用 fix 模块）
    if face:
        print(f'  🪪 3/4 修脸（YOLO 检测 + 局部重绘）...')
        try:
            import sys as _sys
            sys.path.insert(0, str(PROJECT))
            from workshop.fix import _detect_yolo, _make_mask, _build_inpaint_wf, _comfy_alive, _wait_images
            import shutil, json as _json
            from PIL import Image as _PILImage

            if not _comfy_alive():
                print(f'  ⏭️ ComfyUI 未运行，跳过修脸')
            else:
                box = _detect_yolo(current, 'face')
                if box:
                    mask_path, real_box = _make_mask(current, box)
                    comfy_input = r'C:\DrawingLive\ComfyUI\input'
                    img_dst = os.path.join(comfy_input, os.path.basename(current))
                    mask_dst = os.path.join(comfy_input, os.path.basename(mask_path))
                    shutil.copy(current, img_dst)
                    shutil.copy(mask_path, mask_dst)
                    s = int(time.time()) % 2**31
                    wf = _build_inpaint_wf(current, mask_path,
                                           'detailed face, clear facial features, natural skin, high quality',
                                           'blurry face, deformed face, bad anatomy', 0.4, s)
                    # 提交工作流 → 拿 prompt_id → 轮询（修复：原来把请求 JSON 当 prompt_id 传导致死等）
                    from workshop.fix import _http, COMFY
                    body = _json.dumps({'prompt': wf}).encode()
                    req = urllib.request.Request(COMFY + '/prompt', data=body,
                                                 headers={'Content-Type': 'application/json'})
                    r = _json.loads(_http().open(req, timeout=30).read())
                    if 'error' in r:
                        print(f'  ⚠️ 提交失败: {str(r["error"])[:80]}')
                        pid = None
                    else:
                        pid = r['prompt_id']
                        print(f'  已提交 prompt_id={pid}，等待生成...')
                    files = _wait_images(pid, timeout=300) if pid else []
                    if files:
                        r3 = str(out_dir / 'step3_face.png')
                        with open(os.path.join(r'C:\DrawingLive\ComfyUI\output', files[0]), 'rb') as f_in, open(r3, 'wb') as f_out:
                            f_out.write(f_in.read())
                        current = r3
                        steps.append('face')
                        print(f'  ✅ 修脸: {r3}')
                    else:
                        print(f'  ⚠️ 修脸无输出，跳过')
                else:
                    print(f'  ⏭️ 未检测到人脸，跳过修脸')
        except Exception as e:
            print(f'  ⚠️ 修脸失败: {str(e)[:80]}')
    else:
        print(f'  ⏭️ 3/4 跳过修脸（--no-face）')

    # 4. 对比图
    print(f'  🖼️ 4/4 对比图...')
    out_path = str(out_dir / 'enhanced.png')
    with open(current, 'rb') as f_in, open(out_path, 'wb') as f_out:
        f_out.write(f_in.read())
    print(f'  ✅ 高清修复完成: {out_path}（步骤: {" → ".join(steps)}）')

    if compare:
        try:
            from workshop.compare import make_compare
            cmp_path = str(out_dir / '对比.png')
            make_compare(image_path, out_path, output=cmp_path)
            print(f'  📊 对比图: {cmp_path}')
        except Exception as e:
            print(f'  ⚠️ 对比失败: {str(e)[:80]}')

    return out_path


def batch_enhance(image_dir, upscale=2, color=False, face=True, compare=True,
                  glob_pattern='*.png', output_dir=None):
    """批量高清修复（目录内所有图——老照片批量修复场景）。

    Args:
        image_dir: 图片目录
        upscale/color/face/compare: 同 enhance
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
    out_root = Path(output_dir or (PROJECT / 'outputs' / f"batch_enhance_{time.strftime('%Y%m%d_%H%M%S')}"))
    saved = []
    print(f'📚 批量高清修复 {len(imgs)} 张 (upscale={upscale})...')
    for i, img in enumerate(imgs):
        print(f'\n  [{i+1}/{len(imgs)}] {os.path.basename(img)}')
        try:
            out = enhance(img, upscale=upscale, color=color, face=face,
                          compare=compare, output=str(out_root / f"img_{i+1:02d}"))
            if out:
                saved.append(out)
        except Exception as e:
            print(f'  ⚠️ 失败: {str(e)[:80]}')
    print(f'\n📁 批量输出: {out_root}（{len(saved)} 张）')
    return saved


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop enhance', description='高清修复管线（去噪→超分→修脸→对比）')
    ap.add_argument('image', help='图片路径')
    ap.add_argument('--upscale', type=int, default=2, help='超分倍数（0=不超分）')
    ap.add_argument('--color', action='store_true', help='上色（黑白老照片）')
    ap.add_argument('--no-face', action='store_true', help='不修脸')
    ap.add_argument('--no-compare', action='store_true', help='不出对比图')
    ap.add_argument('--dir', default=None, help='批量修复目录（所有 png/jpg）')
    ap.add_argument('--output', default=None, help='输出目录')
    args = ap.parse_args(argv)

    # 批量模式
    if args.dir:
        try:
            batch_enhance(args.dir, upscale=args.upscale, color=args.color,
                          face=not args.no_face, compare=not args.no_compare,
                          output_dir=args.output)
            return 0
        except Exception as e:
            print(f'❌ 批量修复失败: {str(e)[:150]}')
            return 1

    try:
        enhance(args.image, upscale=args.upscale, color=args.color,
                face=not args.no_face, compare=not args.no_compare,
                output=args.output)
        return 0
    except Exception as e:
        print(f'❌ 高清修复失败: {str(e)[:150]}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
