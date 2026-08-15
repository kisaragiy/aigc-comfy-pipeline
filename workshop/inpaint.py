#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/inpaint.py — 局部重绘（B-inpaint）v1.0
================================================
B站超火场景：局部修改（"AI局部重绘/改不满意的地方"）。
两种 mask 方式：
  - --area "物体/部位名"：SAM GroundingDino 文本定位区域自动 mask
  - --box x,y,w,h：手动矩形区域

用法:
  python -m agents workshop inpaint <原图> "修改描述" --area "眼睛" [--denoise 0.8]
  python -m agents workshop inpaint <原图> "把头发变粉色" --box 100,50,300,300
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


def _sam_mask_wf(upload_name, prompt_area):
    """SAM 文本定位 mask 工作流 → 返回 mask 图文件名"""
    wf = {}
    wf['10'] = {'class_type': 'LoadImage', 'inputs': {'image': upload_name}}
    wf['20'] = {'class_type': 'SAMModelLoader', 'inputs': {'model_name': 'sam_vit_b_01ec64.pth'}}
    wf['30'] = {'class_type': 'GroundingDinoSAMSegment',
                'inputs': {'sam_model': ['20', 0], 'image': ['10', 0],
                           'prompt': prompt_area, 'threshold': 0.3, 'box_threshold': 0.3}}
    return wf


def _build_inpaint_wf(upload_name, mask_name, prompt, negative, seed, denoise=0.8,
                      invert=False):
    """局部重绘工作流（SetLatentNoiseMask + denoise），invert=True 反向 mask"""
    wf = {}
    wf['10'] = {'class_type': 'LoadImage', 'inputs': {'image': upload_name}}
    wf['11'] = {'class_type': 'VAEEncode', 'inputs': {'pixels': ['10', 0], 'vae': ['1', 2]}}
    wf['12'] = {'class_type': 'LoadImage', 'inputs': {'image': mask_name}}
    # mask 转 latent mask
    wf['13'] = {'class_type': 'ImageToMask',
                'inputs': {'image': ['12', 0], 'channel': 'red'}}
    # 反向 mask（保留区域重绘——invert）
    if invert:
        wf['15'] = {'class_type': 'InvertMask',
                    'inputs': {'mask': ['13', 0]}}
        mask_src = ['15', 0]
    else:
        mask_src = ['13', 0]
    # SetLatentNoiseMask：只重绘 mask 区域
    wf['14'] = {'class_type': 'SetLatentNoiseMask',
                'inputs': {'samples': ['11', 0], 'mask': mask_src}}
    # 模型
    wf['1'] = {'class_type': 'CheckpointLoaderSimple',
               'inputs': {'ckpt_name': 'waiIllustriousSDXL_v160.safetensors'}}
    wf['2'] = {'class_type': 'CLIPTextEncode',
               'inputs': {'text': prompt, 'clip': ['1', 1]}}
    wf['3'] = {'class_type': 'CLIPTextEncode',
               'inputs': {'text': negative or 'worst quality, blurry, deformed', 'clip': ['1', 1]}}
    wf['5'] = {'class_type': 'KSampler',
               'inputs': {'model': ['1', 0], 'positive': ['2', 0], 'negative': ['3', 0],
                          'latent_image': ['14', 0], 'seed': seed, 'steps': 30, 'cfg': 6.5,
                          'sampler_name': 'dpmpp_2m', 'scheduler': 'karras', 'denoise': denoise}}
    wf['6'] = {'class_type': 'VAEDecode', 'inputs': {'samples': ['5', 0], 'vae': ['1', 2]}}
    wf['7'] = {'class_type': 'SaveImage',
               'inputs': {'images': ['6', 0], 'filename_prefix': 'inpaint'}}
    return wf


def _make_box_mask(image_path, box, out_path, feather=0):
    """矩形 mask（PIL），feather>0 时边缘高斯羽化（过渡自然）"""
    from PIL import Image, ImageDraw, ImageFilter
    img = Image.open(image_path).convert('L')
    d = ImageDraw.Draw(img)
    d.rectangle(box, fill=255)
    if feather > 0:
        img = img.filter(ImageFilter.GaussianBlur(feather))
    img.save(out_path)
    return os.path.basename(out_path)


def inpaint(source_image, desc, area=None, box=None, denoise=0.8, seed=-1,
            output=None, negative=None, areas=None, compare=False, feather=0,
            invert=False):
    """局部重绘。

    Args:
        source_image: 原图路径
        desc: 修改描述（中文）
        area: SAM 文本定位区域（如 "眼睛"/"头发"）
        box: (x1,y1,x2,y2) 矩形区域（area 和 box 二选一）
        areas: 多区域列表 [("眼睛","红色"), ("头发","粉色")]——逐区重绘叠加
        denoise: 重绘强度
        compare: 输出前后对比图
        feather: mask 边缘羽化像素（过渡自然）
        invert: 反向重绘（mask 外区域重绘——保留定位区域）

    Returns:
        输出路径
    """
    if not os.path.exists(source_image):
        raise FileNotFoundError(f'原图不存在: {source_image}')
    if not area and not box and not areas:
        raise ValueError('需要 --area（文本定位）、--box（矩形区域）或 --areas（多区域）')

    # 中文翻译
    prompt_en = desc
    try:
        from workshop.layer import _translate_desc
        prompt_en = _translate_desc(desc) if desc else ""
    except Exception:
        pass

    COMFY_OUTPUT = r'C:\DrawingLive\ComfyUI\output'
    COMFY_INPUT = r'C:\DrawingLive\ComfyUI\input'

    # 1. 上传原图
    up_name = _load_image_file(source_image)

    # 1.5 多区域模式：逐区重绘叠加（前一轮结果作为下一轮输入）
    if areas:
        current = source_image
        for ai, (a_area, a_desc) in enumerate(areas):
            print(f'  🔄 区域 {ai+1}/{len(areas)}: "{a_area}" → {a_desc}')
            a_en = a_desc
            try:
                from workshop.layer import _translate_desc
                a_en = _translate_desc(a_desc) if a_desc else ""
            except Exception:
                pass
            mask_files = _submit(_sam_mask_wf(up_name, a_area), timeout=300)
            if not mask_files:
                print(f'  ⚠️ 区域 {a_area} mask 失败，跳过')
                continue
            mask_name = mask_files[0]
            s = (seed if seed >= 0 else int(time.time())) + ai * 31
            wf = _build_inpaint_wf(up_name, mask_name, a_en, negative, s, denoise,
                                   invert=invert)
            files = _submit(wf, timeout=600)
            if not files:
                print(f'  ⚠️ 区域 {a_area} 重绘失败，跳过')
                continue
            # 本轮结果作为下轮输入
            from PIL import Image
            res_img = Image.open(os.path.join(COMFY_OUTPUT, files[0])).convert('RGB')
            tmp_path = os.path.join(COMFY_INPUT, f'inpaint_stage_{int(time.time())}_{ai}.png')
            res_img.save(tmp_path)
            up_name = _load_image_file(tmp_path)
            current = tmp_path
        # 最终结果复制
        out_path = output or str(PROJECT / 'outputs' / f"inpaint_{time.strftime('%Y%m%d_%H%M%S')}.png")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(current, 'rb') as f_in, open(out_path, 'wb') as f_out:
            f_out.write(f_in.read())
        print(f'  ✅ 多区域重绘完成: {out_path}')
        if compare:
            try:
                from workshop.compare import make_compare
                cmp_path = out_path.replace('.png', '_对比.png')
                make_compare(source_image, out_path, output=cmp_path)
            except Exception as e:
                print(f'  ⚠️ 对比图失败: {str(e)[:80]}')
        return out_path

    # 2. mask 获取
    if box:
        mask_name = _make_box_mask(source_image, box,
                                   os.path.join(COMFY_INPUT, f'box_mask_{int(time.time())}.png'),
                                   feather=feather)
        print(f'  📦 矩形区域: {box} (羽化{feather}px)')
    else:
        print(f'  🔍 SAM 定位: "{area}"...')
        mask_files = _submit(_sam_mask_wf(up_name, area), timeout=300)
        if not mask_files:
            raise RuntimeError('SAM mask 无输出')
        mask_name = mask_files[0]
        print(f'  ✅ mask: {mask_name}')

    # 3. 局部重绘
    seed_actual = seed if seed >= 0 else int(time.time()) % 2**31
    wf = _build_inpaint_wf(up_name, mask_name, prompt_en, negative, seed_actual, denoise,
                           invert=invert)
    print(f'  🎨 局部重绘中 (denoise={denoise}, seed={seed_actual})...')
    files = _submit(wf, timeout=600)
    if not files:
        raise RuntimeError('重绘无输出')

    src = os.path.join(COMFY_OUTPUT, files[0])
    out_path = output or str(PROJECT / 'outputs' / f"inpaint_{time.strftime('%Y%m%d_%H%M%S')}.png")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(src, 'rb') as f_in, open(out_path, 'wb') as f_out:
        f_out.write(f_in.read())
    print(f'  ✅ 局部重绘完成: {out_path}')
    if compare:
        try:
            from workshop.compare import make_compare
            cmp_path = out_path.replace('.png', '_对比.png')
            make_compare(source_image, out_path, output=cmp_path)
        except Exception as e:
            print(f'  ⚠️ 对比图失败: {str(e)[:80]}')
    return out_path


def batch_inpaint(image_dir, desc, area=None, box=None, denoise=0.8, seed=-1,
                  glob_pattern='*.png', output_dir=None, compare=False, feather=0):
    """批量局部重绘（目录内所有图统一区域重绘——批量改眼睛/批量去水印等）。

    Args:
        image_dir: 图片目录
        desc: 修改描述
        area: SAM 文本定位区域（所有图同一个区域）
        box: 矩形区域（所有图同一个区域）
        glob_pattern: 匹配模式
        output_dir: 输出目录
        compare: 每张输出前后对比图
        feather: mask 羽化

    Returns:
        [输出路径...]
    """
    import glob
    if not area and not box:
        raise ValueError('批量模式需要 --area 或 --box（所有图同一区域）')
    imgs = sorted(glob.glob(os.path.join(image_dir, glob_pattern)))
    if not imgs:
        print(f'⚠️ {image_dir} 下无 {glob_pattern} 文件')
        return []
    out_root = Path(output_dir or (PROJECT / 'outputs' / f"batch_inpaint_{time.strftime('%Y%m%d_%H%M%S')}"))
    saved = []
    print(f'📚 批量 inpaint {len(imgs)} 张 (区域: {area or box}, denoise={denoise})...')
    for i, img in enumerate(imgs):
        print(f'\n  [{i+1}/{len(imgs)}] {os.path.basename(img)}')
        try:
            out = inpaint(img, desc, area=area, box=box, denoise=denoise,
                          seed=seed + i * 13, output=str(out_root / f"r_{i+1:02d}.png"),
                          feather=feather)
            if out:
                saved.append(out)
                if compare:
                    from workshop.compare import make_compare
                    make_compare(img, out, output=str(out_root / f"r_{i+1:02d}_对比.png"))
        except Exception as e:
            print(f'  ⚠️ 失败: {str(e)[:80]}')
    print(f'\n📁 批量输出: {out_root}（{len(saved)} 张）')
    return saved


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop inpaint', description='局部重绘（SAM/矩形 mask）')
    ap.add_argument('image', help='原图路径')
    ap.add_argument('desc', nargs='*', help='修改描述（中文）')
    ap.add_argument('--area', default=None, help='SAM 文本定位区域（如 "眼睛"/"头发"）')
    ap.add_argument('--box', default=None, help='矩形区域 x1,y1,x2,y2')
    ap.add_argument('--areas', default=None,
                    help='多区域 区域:描述 逗号分隔（如 "眼睛:红色眼睛,头发:粉色头发"）')
    ap.add_argument('--denoise', type=float, default=0.8, help='重绘强度')
    ap.add_argument('--compare', action='store_true', help='输出前后对比图')
    ap.add_argument('--feather', type=int, default=0, help='mask 边缘羽化像素（过渡自然）')
    ap.add_argument('--invert', action='store_true', help='反向重绘（mask 外区域——保留定位区域）')
    ap.add_argument('--watermark', action='store_true',
                    help='去水印模式（自动检测角落水印区域 + 重绘）')
    ap.add_argument('--dir', default=None, help='批量处理目录（所有图统一区域重绘）')
    ap.add_argument('--output', default=None, help='输出路径/目录')
    ap.add_argument('--seed', type=int, default=-1)
    args = ap.parse_args(argv)

    desc = ' '.join(args.desc)
    if not desc:
        print('用法: inpaint <原图> "修改" --area "眼睛" | --box x1,y1,x2,y2 | --areas "眼睛:红,头发:粉"')
        return 1
    box = None
    if args.box:
        try:
            parts = [int(p.strip()) for p in args.box.split(',')]
            box = tuple(parts[:4])
        except Exception:
            print('❌ --box 格式: x1,y1,x2,y2')
            return 1
    areas = None
    if args.areas:
        areas = []
        for seg in args.areas.split(','):
            if ':' in seg:
                a, d = seg.split(':', 1)
                areas.append((a.strip(), d.strip()))
            else:
                areas.append((seg.strip(), desc))

    # 批量模式
    if args.dir:
        try:
            batch_inpaint(args.dir, desc, area=args.area, box=box,
                          denoise=args.denoise, seed=args.seed,
                          output_dir=args.output, compare=args.compare,
                          feather=args.feather)
            return 0
        except Exception as e:
            print(f'❌ 批量 inpaint 失败: {str(e)[:150]}')
            return 1

    # 去水印模式：自动定位右下角水印区（常见位置）+ 默认描述
    if args.watermark:
        try:
            from PIL import Image as PImage
            w, h = PImage.open(args.image).size
            box = (int(w * 0.55), int(h * 0.75), w - int(w * 0.03), h - int(h * 0.05))
            if not desc:
                desc = 'clean background without watermark, remove logo and text'
            args.denoise = max(args.denoise, 0.75)
            print(f'  💧 去水印模式: 区域 {box}')
        except Exception as e:
            print(f'  ⚠️ 水印定位失败: {str(e)[:80]}')

    try:
        inpaint(args.image, desc, area=args.area, box=box, denoise=args.denoise,
                seed=args.seed, output=args.output, areas=areas, compare=args.compare,
                feather=args.feather, invert=args.invert)
        return 0
    except Exception as e:
        print(f'❌ 局部重绘失败: {str(e)[:150]}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
