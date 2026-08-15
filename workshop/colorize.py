#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/colorize.py — 线稿上色（B-colorize）v1.0
==================================================
B站 22K 热度：黑白线稿 → 自动上色。
流程：
  1. 线稿 → Canny 结构线（保留线条）
  2. ControlNet Canny 引导 + 上色 prompt → 彩色成图
  3. 线条保真（Canny 权重高）+ 颜色自由

用法:
  python -m agents workshop colorize <线稿图> [--desc "粉色头发少女"] [--color "粉色调"]
"""

import argparse, json, os, sys, time, urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent


def _http():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _submit(wf, timeout=300):
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


def _build_colorize_wf(upload_name, prompt, negative, seed, strength=0.9):
    """Canny ControlNet 线稿上色工作流"""
    wf = {}
    # 加载线稿
    wf['10'] = {'class_type': 'LoadImage', 'inputs': {'image': upload_name}}
    # Canny 提取
    wf['20'] = {'class_type': 'Canny',
                'inputs': {'image': ['10', 0], 'low_threshold': 0.2, 'high_threshold': 0.8}}
    # ControlNet 加载
    wf['30'] = {'class_type': 'ControlNetLoader',
                'inputs': {'control_net_name': 'control_v11p_sd15_canny.pth'}}
    wf['40'] = {'class_type': 'ControlNetApply',
                'inputs': {'conditioning': ['50', 0], 'control_net': ['30', 0],
                           'image': ['20', 0], 'strength': strength}}
    # 模型
    wf['1'] = {'class_type': 'CheckpointLoaderSimple',
               'inputs': {'ckpt_name': 'waiIllustriousSDXL_v160.safetensors'}}
    wf['2'] = {'class_type': 'CLIPTextEncode',
               'inputs': {'text': prompt, 'clip': ['1', 1]}}
    wf['3'] = {'class_type': 'CLIPTextEncode',
               'inputs': {'text': negative or 'worst quality, blurry, low quality', 'clip': ['1', 1]}}
    # 尺寸与原图一致（文件不在则默认 1024——健壮性，测试/异常场景）
    try:
        from PIL import Image
        orig = Image.open(os.path.join(r'C:\DrawingLive\ComfyUI\input', upload_name))
        w, h = orig.size
    except Exception:
        w, h = 1024, 1024
    wf['4'] = {'class_type': 'EmptyLatentImage',
               'inputs': {'width': (w // 8) * 8, 'height': (h // 8) * 8, 'batch_size': 1}}
    wf['50'] = {'class_type': 'CLIPTextEncode',
                'inputs': {'text': prompt, 'clip': ['1', 1]}}
    wf['5'] = {'class_type': 'KSampler',
               'inputs': {'model': ['1', 0], 'positive': ['40', 0], 'negative': ['3', 0],
                          'latent_image': ['4', 0], 'seed': seed, 'steps': 30, 'cfg': 6.0,
                          'sampler_name': 'dpmpp_2m', 'scheduler': 'karras', 'denoise': 1.0}}
    wf['6'] = {'class_type': 'VAEDecode', 'inputs': {'samples': ['5', 0], 'vae': ['1', 2]}}
    wf['7'] = {'class_type': 'SaveImage',
               'inputs': {'images': ['6', 0], 'filename_prefix': 'colorize'}}
    return wf


def colorize_lineart(lineart_path, desc=None, color_hint=None, seed=-1,
                     output=None, negative=None):
    """黑白线稿 → 彩色。

    Args:
        lineart_path: 线稿图路径
        desc: 内容描述（可选，帮助上色理解）
        color_hint: 色调提示（如 "粉色头发，蓝色眼睛"）

    Returns:
        输出路径
    """
    from PIL import Image
    COMFY_OUTPUT = r'C:\DrawingLive\ComfyUI\output'

    # 描述翻译
    desc_en = desc or "anime character"
    try:
        from workshop.layer import _translate_desc
        desc_en = _translate_desc(desc) if desc else "anime character"
    except Exception:
        pass
    hint_en = color_hint or ""
    try:
        from workshop.layer import _translate_desc
        hint_en = _translate_desc(color_hint) if color_hint else ""
    except Exception:
        pass

    prompt = f"{desc_en}, {hint_en}, colored illustration, vibrant colors, cel shading, detailed, clean lineart preserved".strip(', ')

    # 上传线稿
    print(f'  📤 上传线稿...')
    up_name = _load_image_file(lineart_path)

    seed_actual = seed if seed >= 0 else int(time.time()) % 2**31
    print(f'  🎨 上色中 (ControlNet Canny, seed={seed_actual})...')
    wf = _build_colorize_wf(up_name, prompt, negative, seed_actual)
    files = _submit(wf, timeout=600)
    if not files:
        raise RuntimeError('上色无输出')

    src = os.path.join(COMFY_OUTPUT, files[0])
    out_path = output or str(PROJECT / 'outputs' / f"colorize_{time.strftime('%Y%m%d_%H%M%S')}.png")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(src, 'rb') as f_in, open(out_path, 'wb') as f_out:
        f_out.write(f_in.read())
    print(f'  🎨 上色完成: {out_path}')
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop colorize', description='线稿上色（Canny ControlNet）')
    ap.add_argument('lineart', help='线稿图路径（黑白）')
    ap.add_argument('--desc', default=None, help='内容描述（辅助上色理解）')
    ap.add_argument('--color', default=None, help='色调提示（如 "粉色头发蓝色眼睛"）')
    ap.add_argument('--output', default=None, help='输出路径')
    ap.add_argument('--seed', type=int, default=-1)
    args = ap.parse_args(argv)

    if not os.path.exists(args.lineart):
        print(f'❌ 线稿不存在: {args.lineart}')
        return 1
    try:
        colorize_lineart(args.lineart, desc=args.desc, color_hint=args.color,
                         seed=args.seed, output=args.output)
        return 0
    except Exception as e:
        print(f'❌ 上色失败: {str(e)[:150]}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
