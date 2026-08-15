#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/bg_replace.py — 背景替换（B-bg-replace）v1.0
=======================================================
核心生图操作：背景替换——保留主体（SAM 抠图），替换背景。
流程：
  1. SAM 抠主体（GroundingDino 文本定位 "person"/"subject"）
  2. 主体 mask 保留
  3. img2img 重绘背景区域（mask 外）→ 新背景
  4. 输出对比图

用法:
  python -m agents workshop bg-replace <原图> "新背景描述" [--subject person] [--compare]
"""

import argparse, json, os, sys, time, urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent


def _http():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _submit(wf, timeout=600):
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


def _load_image_file(image_path):
    COMFY = 'http://127.0.0.1:8188'
    import mimetypes
    boundary = '----hermesboundary' + str(time.time()).replace('.', '')
    fname = os.path.basename(image_path)
    mtype = mimetypes.guess_type(fname)[0] or 'image/png'
    with open(image_path, 'rb') as f:
        data = f.read()
    body = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="image"; filename="{fname}"\r\n'
        f'Content-Type: {mtype}\r\n\r\n'
    ).encode() + data + f'\r\n--{boundary}--\r\n'.encode()
    req = urllib.request.Request(COMFY + '/upload/image', data=body,
                                 headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
    r = json.loads(_http().open(req, timeout=60).read())
    return r['name']


def bg_replace(source_image, new_bg_desc, subject='person', seed=-1,
               output=None, compare=True, negative=None):
    """背景替换（SAM 抠主体 + 背景区域重绘）。

    Args:
        source_image: 原图路径
        new_bg_desc: 新背景描述（中文，如 "海边沙滩 夕阳"）
        subject: 主体文本定位（默认 person）
        compare: 输出前后对比图

    Returns:
        输出路径
    """
    if not os.path.exists(source_image):
        raise FileNotFoundError(f'原图不存在: {source_image}')

    # 新背景 prompt 翻译
    try:
        from workshop.layer import _translate_desc
        bg_en = _translate_desc(new_bg_desc)
    except Exception:
        bg_en = new_bg_desc

    COMFY_OUTPUT = r'C:\DrawingLive\ComfyUI\output'
    COMFY_INPUT = r'C:\DrawingLive\ComfyUI\input'

    # 1. 上传 + SAM 抠主体
    print(f'  🔍 1/3 SAM 定位主体: "{subject}"...')
    up_name = _load_image_file(source_image)
    seg_wf = {}
    seg_wf['10'] = {'class_type': 'LoadImage', 'inputs': {'image': up_name}}
    seg_wf['20'] = {'class_type': 'SAMModelLoader', 'inputs': {'model_name': 'sam_vit_b_01ec64.pth'}}
    seg_wf['30'] = {'class_type': 'GroundingDinoSAMSegment',
                    'inputs': {'sam_model': ['20', 0], 'image': ['10', 0],
                               'prompt': subject, 'threshold': 0.3, 'box_threshold': 0.3}}
    seg_files = _submit(seg_wf, timeout=300)
    if not seg_files:
        raise RuntimeError('SAM 抠图无输出')
    mask_file = os.path.join(COMFY_OUTPUT, seg_files[0])
    if not os.path.exists(mask_file):
        raise RuntimeError(f'mask 不存在: {mask_file}')
    print(f'  ✅ 主体 mask: {seg_files[0]}')

    # 2. 反向 mask（背景=重绘区）+ 重绘
    print(f'  🎨 2/3 替换背景: {new_bg_desc}...')
    # 上传 mask 到 input
    mask_dst = os.path.join(COMFY_INPUT, seg_files[0])
    with open(mask_file, 'rb') as f_in, open(mask_dst, 'wb') as f_out:
        f_out.write(f_in.read())

    wf = {}
    wf['10'] = {'class_type': 'LoadImage', 'inputs': {'image': up_name}}
    wf['11'] = {'class_type': 'VAEEncode', 'inputs': {'pixels': ['10', 0], 'vae': ['1', 2]}}
    wf['12'] = {'class_type': 'LoadImage', 'inputs': {'image': seg_files[0]}}
    wf['13'] = {'class_type': 'ImageToMask', 'inputs': {'image': ['12', 0], 'channel': 'red'}}
    wf['15'] = {'class_type': 'InvertMask', 'inputs': {'mask': ['13', 0]}}
    wf['14'] = {'class_type': 'SetLatentNoiseMask',
                'inputs': {'samples': ['11', 0], 'mask': ['15', 0]}}
    wf['1'] = {'class_type': 'CheckpointLoaderSimple',
               'inputs': {'ckpt_name': 'waiIllustriousSDXL_v160.safetensors'}}
    wf['2'] = {'class_type': 'CLIPTextEncode',
               'inputs': {'text': f"{bg_en}, matching lighting and perspective, high quality", 'clip': ['1', 1]}}
    wf['3'] = {'class_type': 'CLIPTextEncode',
               'inputs': {'text': negative or 'worst quality, blurry, deformed subject', 'clip': ['1', 1]}}
    wf['5'] = {'class_type': 'KSampler',
               'inputs': {'model': ['1', 0], 'positive': ['2', 0], 'negative': ['3', 0],
                          'latent_image': ['14', 0], 'seed': seed if seed >= 0 else int(time.time()) % 2**31,
                          'steps': 32, 'cfg': 6.5, 'sampler_name': 'dpmpp_2m',
                          'scheduler': 'karras', 'denoise': 1.0}}
    wf['6'] = {'class_type': 'VAEDecode', 'inputs': {'samples': ['5', 0], 'vae': ['1', 2]}}
    wf['7'] = {'class_type': 'SaveImage', 'inputs': {'images': ['6', 0], 'filename_prefix': 'bg_replace'}}
    files = _submit(wf, timeout=600)
    if not files:
        raise RuntimeError('背景替换无输出')

    src = os.path.join(COMFY_OUTPUT, files[0])
    out_path = output or str(PROJECT / 'outputs' / f"bg_replace_{time.strftime('%Y%m%d_%H%M%S')}.png")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(src, 'rb') as f_in, open(out_path, 'wb') as f_out:
        f_out.write(f_in.read())
    print(f'  ✅ 3/3 背景替换完成: {out_path}')

    if compare:
        try:
            from workshop.compare import make_compare
            cmp_path = out_path.replace('.png', '_对比.png')
            make_compare(source_image, out_path, output=cmp_path)
            print(f'  📊 对比图: {cmp_path}')
        except Exception as e:
            print(f'  ⚠️ 对比失败: {str(e)[:80]}')

    return out_path


def batch_bg_replace(image_dir, new_bg_desc, subject='person', seed=-1,
                     glob_pattern='*.png', output_dir=None, compare=False):
    """批量背景替换（目录内所有图统一换背景——批量换场景）。

    Args:
        image_dir: 图片目录
        new_bg_desc: 新背景描述
        subject: 主体定位
        glob_pattern: 匹配模式
        output_dir: 输出目录
        compare: 每张对比图

    Returns:
        [输出路径...]
    """
    import glob
    imgs = sorted(glob.glob(os.path.join(image_dir, glob_pattern)))
    if not imgs:
        print(f'⚠️ {image_dir} 下无 {glob_pattern} 文件')
        return []
    out_root = Path(output_dir or (PROJECT / 'outputs' / f"batch_bg_{time.strftime('%Y%m%d_%H%M%S')}"))
    saved = []
    print(f'📚 批量背景替换 {len(imgs)} 张 → {new_bg_desc}')
    for i, img in enumerate(imgs):
        print(f'\n  [{i+1}/{len(imgs)}] {os.path.basename(img)}')
        try:
            out = bg_replace(img, new_bg_desc, subject=subject,
                             seed=seed + i * 19,
                             output=str(out_root / f"r_{i+1:02d}.png"),
                             compare=compare)
            if out:
                saved.append(out)
        except Exception as e:
            print(f'  ⚠️ 失败: {str(e)[:80]}')
    print(f'\n📁 批量输出: {out_root}（{len(saved)} 张）')
    return saved


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop bg-replace', description='背景替换（SAM 抠主体+重绘背景）')
    ap.add_argument('image', help='原图路径')
    ap.add_argument('desc', nargs='*', help='新背景描述（中文）')
    ap.add_argument('--subject', default='person', help='主体文本定位（person/subject/cat 等）')
    ap.add_argument('--dir', default=None, help='批量替换目录（所有 png/jpg）')
    ap.add_argument('--output', default=None, help='输出路径/目录')
    ap.add_argument('--seed', type=int, default=-1)
    ap.add_argument('--no-compare', action='store_true', help='不出对比图')
    args = ap.parse_args(argv)

    desc = ' '.join(args.desc)
    if not desc:
        print('用法: bg-replace <原图|--dir 目录> "新背景描述" [--subject person]')
        return 1

    # 批量模式
    if args.dir:
        try:
            batch_bg_replace(args.dir, desc, subject=args.subject, seed=args.seed,
                             output_dir=args.output, compare=not args.no_compare)
            return 0
        except Exception as e:
            print(f'❌ 批量背景替换失败: {str(e)[:150]}')
            return 1

    try:
        bg_replace(args.image, desc, subject=args.subject, seed=args.seed,
                   output=args.output, compare=not args.no_compare)
        return 0
    except Exception as e:
        print(f'❌ 背景替换失败: {str(e)[:150]}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
