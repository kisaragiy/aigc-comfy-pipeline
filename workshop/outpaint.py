#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/outpaint.py — 扩图（B-outpaint）v1.0
==============================================
核心生图操作：扩图（outpaint）——把画面向四周延伸（生成新的延伸内容）。
方案：扩画布（白/透明）→ 扩展区 mask → 局部重绘（inpaint）→ 拼回。

用法:
  python -m agents workshop outpaint <原图> [--right 300] [--bottom 300] "延伸描述"
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


def _expand_canvas(image_path, right=0, bottom=0, left=0, top=0, out_path=None):
    """PIL 扩画布（白色扩展区）→ 返回 (扩展图路径, mask路径)"""
    from PIL import Image, ImageDraw
    img = Image.open(image_path).convert('RGB')
    w, h = img.size
    nw, nh = w + left + right, h + top + bottom
    canvas = Image.new('RGB', (nw, nh), (255, 255, 255))
    canvas.paste(img, (left, top))
    # mask：扩展区为白色（重绘区），原图为黑色（保留区）
    mask = Image.new('L', (nw, nh), 0)
    d = ImageDraw.Draw(mask)
    if right > 0:
        d.rectangle([w + left, top, nw, top + h], fill=255)
    if bottom > 0:
        d.rectangle([left, h + top, left + w, nh], fill=255)
    if left > 0:
        d.rectangle([0, top, left, top + h], fill=255)
    if top > 0:
        d.rectangle([left, 0, left + w, top], fill=255)
    # 角落区域也重绘
    if right > 0 and bottom > 0:
        d.rectangle([w + left, h + top, nw, nh], fill=255)
    if left > 0 and bottom > 0:
        d.rectangle([0, h + top, left, nh], fill=255)
    if right > 0 and top > 0:
        d.rectangle([w + left, 0, nw, top], fill=255)
    if left > 0 and top > 0:
        d.rectangle([0, 0, left, top], fill=255)

    COMFY_INPUT = r'C:\DrawingLive\ComfyUI\input'
    ts = int(time.time())
    exp_path = os.path.join(COMFY_INPUT, f'outpaint_exp_{ts}.png')
    mask_path = os.path.join(COMFY_INPUT, f'outpaint_mask_{ts}.png')
    canvas.save(exp_path)
    mask.save(mask_path)
    return exp_path, mask_path, (left, top, nw, nh)


def _build_outpaint_wf(exp_name, mask_name, prompt, negative, seed, denoise=1.0):
    """扩图重绘工作流（整图 latent + mask 限制重绘区）"""
    wf = {}
    wf['10'] = {'class_type': 'LoadImage', 'inputs': {'image': exp_name}}
    wf['11'] = {'class_type': 'VAEEncode', 'inputs': {'pixels': ['10', 0], 'vae': ['1', 2]}}
    wf['12'] = {'class_type': 'LoadImage', 'inputs': {'image': mask_name}}
    wf['13'] = {'class_type': 'ImageToMask', 'inputs': {'image': ['12', 0], 'channel': 'red'}}
    wf['14'] = {'class_type': 'SetLatentNoiseMask',
                'inputs': {'samples': ['11', 0], 'mask': ['13', 0]}}
    wf['1'] = {'class_type': 'CheckpointLoaderSimple',
               'inputs': {'ckpt_name': 'waiIllustriousSDXL_v160.safetensors'}}
    wf['2'] = {'class_type': 'CLIPTextEncode',
               'inputs': {'text': prompt, 'clip': ['1', 1]}}
    wf['3'] = {'class_type': 'CLIPTextEncode',
               'inputs': {'text': negative or 'worst quality, blurry, deformed, white edges', 'clip': ['1', 1]}}
    wf['5'] = {'class_type': 'KSampler',
               'inputs': {'model': ['1', 0], 'positive': ['2', 0], 'negative': ['3', 0],
                          'latent_image': ['14', 0], 'seed': seed, 'steps': 32, 'cfg': 6.5,
                          'sampler_name': 'dpmpp_2m', 'scheduler': 'karras', 'denoise': denoise}}
    wf['6'] = {'class_type': 'VAEDecode', 'inputs': {'samples': ['5', 0], 'vae': ['1', 2]}}
    wf['7'] = {'class_type': 'SaveImage',
               'inputs': {'images': ['6', 0], 'filename_prefix': 'outpaint'}}
    return wf


def outpaint(source_image, desc=None, right=0, bottom=0, left=0, top=0,
             seed=-1, output=None, negative=None, denoise=1.0, tile=False,
             iterations=1, target_w=0, target_h=0):
    """扩图（向指定方向延伸画面）。

    Args:
        source_image: 原图路径
        desc: 延伸内容描述（如 "远处的天空和山峦"）
        right/bottom/left/top: 各方向扩展像素
        tile: 无缝平铺模式（上下左右各扩 25%，生成可平铺壁纸）
        iterations: 循环扩图次数（每次在上次结果上继续扩——放大倍数）
        target_w/target_h: 目标尺寸（自动计算右/下扩展量，扩到指定尺寸）

    Returns:
        输出路径
    """
    if not os.path.exists(source_image):
        raise FileNotFoundError(f'原图不存在: {source_image}')
    if right + bottom + left + top == 0 and not tile and not (target_w or target_h):
        raise ValueError('至少一个方向扩展 > 0、使用 --tile 或指定 --target-w/--target-h')
    if right < 0 or bottom < 0 or left < 0 or top < 0:
        raise ValueError('扩展方向不能为负数（right/bottom/left/top 均需 >= 0）')
    if target_w < 0 or target_h < 0:
        raise ValueError('目标尺寸不能为负数（--target-w/--target-h 需 >= 0）')

    # 目标尺寸模式：自动计算右/下扩展量
    if target_w or target_h:
        from PIL import Image as PImage
        _w, _h = PImage.open(source_image).size
        if target_w > _w:
            right = target_w - _w
        if target_h > _h:
            bottom = target_h - _h
        print(f'  🎯 目标尺寸: {target_w or _w}x{target_h or _h}（原 {_w}x{_h}，+右{right} +下{bottom}）')

    # 无缝平铺模式：四方向各扩 25%（seamless 壁纸）
    if tile:
        from PIL import Image as PImage
        _w, _h = PImage.open(source_image).size
        right = bottom = left = top = max(_w, _h) // 4
        desc = desc or "seamless repeating pattern, matching edges perfectly, tileable background, continue the pattern naturally"

    # 中文翻译
    prompt_en = desc or "continue the scene naturally, seamless extension, matching style and lighting"
    try:
        from workshop.layer import _translate_desc
        if desc:
            prompt_en = _translate_desc(desc)
    except Exception:
        pass

    COMFY_OUTPUT = r'C:\DrawingLive\ComfyUI\output'

    # 循环扩图：每次在上次结果上继续扩（iterations 次）
    current_input = source_image
    current_output = None
    for it in range(max(1, iterations)):
        # 1. 扩画布 + mask
        exp_path, mask_path, bounds = _expand_canvas(current_input, right, bottom, left, top)
        exp_name = os.path.basename(exp_path)
        mask_name = os.path.basename(mask_path)
        print(f'  📐 扩图[{it+1}/{iterations}]: +右{right} +下{bottom} +左{left} +上{top} → {bounds[2]}x{bounds[3]}')

        # 2. 上传扩展图（mask 已在 input 目录）
        _load_image_file(exp_path)

        # 3. 重绘扩展区
        seed_actual = (seed if seed >= 0 else int(time.time()) % 2**31) + it * 41
        wf = _build_outpaint_wf(exp_name, mask_name, prompt_en, negative, seed_actual, denoise)
        print(f'  🎨 扩图重绘中 (seed={seed_actual})...')
        files = _submit(wf, timeout=600)
        if not files:
            raise RuntimeError('扩图无输出')

        src = os.path.join(COMFY_OUTPUT, files[0])
        if it == iterations - 1:
            current_output = output or str(PROJECT / 'outputs' / f"outpaint_{time.strftime('%Y%m%d_%H%M%S')}.png")
            os.makedirs(os.path.dirname(current_output), exist_ok=True)
            with open(src, 'rb') as f_in, open(current_output, 'wb') as f_out:
                f_out.write(f_in.read())
            print(f'  ✅ 扩图完成: {current_output}')
        else:
            # 中间结果作为下一轮输入
            from PIL import Image
            res_img = Image.open(src).convert('RGB')
            COMFY_INPUT = r'C:\DrawingLive\ComfyUI\input'
            mid_path = os.path.join(COMFY_INPUT, f'outpaint_stage_{int(time.time())}_{it}.png')
            res_img.save(mid_path)
            current_input = mid_path
            print(f'  🔄 第 {it+1} 轮完成，继续下一轮...')

    return current_output


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop outpaint', description='扩图（向四周延伸画面）')
    ap.add_argument('image', help='原图路径')
    ap.add_argument('desc', nargs='*', help='延伸内容描述（中文）')
    ap.add_argument('--right', type=int, default=0, help='向右扩展像素')
    ap.add_argument('--bottom', type=int, default=0, help='向下扩展像素')
    ap.add_argument('--left', type=int, default=0, help='向左扩展像素')
    ap.add_argument('--top', type=int, default=0, help='向上扩展像素')
    ap.add_argument('--tile', action='store_true', help='无缝平铺模式（四方向扩 25%，可平铺壁纸）')
    ap.add_argument('--iterations', type=int, default=1, help='循环扩图次数（放大倍数）')
    ap.add_argument('--target-w', type=int, default=0, help='目标宽度（自动算右扩展）')
    ap.add_argument('--target-h', type=int, default=0, help='目标高度（自动算下扩展）')
    ap.add_argument('--output', default=None, help='输出路径')
    ap.add_argument('--seed', type=int, default=-1)
    args = ap.parse_args(argv)

    desc = ' '.join(args.desc)
    try:
        outpaint(args.image, desc or None, right=args.right, bottom=args.bottom,
                 left=args.left, top=args.top, seed=args.seed, output=args.output,
                 tile=args.tile, iterations=args.iterations,
                 target_w=args.target_w, target_h=args.target_h)
        return 0
    except Exception as e:
        print(f'❌ 扩图失败: {str(e)[:150]}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
