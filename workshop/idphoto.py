#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/idphoto.py — AI 证件照（B-idphoto）v1.0
==================================================
B站 648K 热度（今日最高）：在家拍证件照。
流程：
  1. 原照片 → SAM 抠人像（GroundingDinoSAMSegment "person"）
  2. 换底色（白/蓝/红——证件照标准）
  3. 裁切证件照规格（一寸 295x413 / 二寸 413x579 / 小二寸 413x531）
  4. 人像居中 + 头顶留白（证件照规范：头占比 2/3）

用法:
  python -m agents workshop idphoto <照片路径> [--bg blue] [--size 1inch|2inch]
"""

import argparse, json, os, sys, time, urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent

# 证件照底色（RGB）
BG_COLORS = {
    "white": (255, 255, 255),
    "blue": (67, 142, 219),    # 标准证件蓝
    "red": (255, 0, 0),
}

# 证件照规格（像素）
SIZES = {
    "1inch": (295, 413),   # 一寸
    "2inch": (413, 579),   # 二寸
    "small2": (413, 531),  # 小二寸
}


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
    """上传图片到 ComfyUI → (upload_name)"""
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


def _build_segment_wf(upload_name):
    """SAM 抠人像工作流 → 输出 mask 保存"""
    wf = {}
    # 加载原图
    wf['10'] = {'class_type': 'LoadImage', 'inputs': {'image': upload_name}}
    # SAM 模型（轻量 vit_b）
    wf['20'] = {'class_type': 'SAMModelLoader', 'inputs': {'model_name': 'sam_vit_b_01ec64.pth'}}
    # GroundingDino + SAM 分割（文本提示 "person"）
    wf['30'] = {'class_type': 'GroundingDinoSAMSegment',
                'inputs': {'sam_model': ['20', 0], 'image': ['10', 0],
                           'prompt': 'person', 'threshold': 0.3, 'box_threshold': 0.3}}
    return wf


def _person_bbox(mask_image_path):
    """从 mask 图算人像 bbox（非零区域）"""
    from PIL import Image
    img = Image.open(mask_image_path).convert('L')
    px = img.load()
    w, h = img.size
    min_x, min_y, max_x, max_y = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            if px[x, y] > 128:
                if x < min_x: min_x = x
                if x > max_x: max_x = x
                if y < min_y: min_y = y
                if y > max_y: max_y = y
    if max_x < 0:
        return None
    return (min_x, min_y, max_x, max_y)


def idphoto(image_path, bg='blue', size='1inch', output=None, beauty=False,
            all_colors=False, outfit=None):
    """证件照生成。

    Args:
        image_path: 照片路径
        bg: 底色 white/blue/red
        size: 规格 1inch/2inch/small2
        beauty: 美颜（磨皮+提亮）
        all_colors: 三色一键全出（白/蓝/红各一张）
        outfit: 换装（西装/衬衫/白衬衫/深色西装——生成正式服装照）

    Returns:
        输出路径 或 [路径...]
    """
    if bg not in BG_COLORS:
        raise ValueError(f'底色可选: {list(BG_COLORS.keys())}')
    if size not in SIZES:
        raise ValueError(f'规格可选: {list(SIZES.keys())}')

    COMFY_OUTPUT = r'C:\DrawingLive\ComfyUI\output'
    out_w, out_h = SIZES[size]
    bg_color = BG_COLORS[bg]

    # 0. 换装（--outfit：ref 原图 + 换装 prompt → 生成正式服装照 → 走证件照流程）
    if outfit:
        print(f'  👔 换装: {outfit}（IPAdapter 参考原图）...')
        try:
            from workshop.create import create_from_nl
            import tempfile
            outfit_dir = Path(tempfile.mkdtemp(prefix='idphoto_outfit_'))
            outfit_prompts = {
                "西装": "wearing a formal dark suit, white shirt, tie, formal ID photo style",
                "衬衫": "wearing a formal white shirt, no tie, formal ID photo style",
                "白衬衫": "wearing a clean white formal shirt, formal ID photo style",
                "深色西装": "wearing a dark navy suit, white shirt, formal ID photo style",
            }
            outfit_en = outfit_prompts.get(outfit, f"wearing {outfit}, formal ID photo style")
            create_from_nl(
                f"same person, {outfit_en}, ID photo, front facing, neutral expression, head and shoulders",
                count=1, model_type='sdxl', seed=-1,
                ref_path=image_path, ip_weight=0.75,
                prompt_ready=True, inspect=False, dry_run=False,
                output_dir=str(outfit_dir),
            )
            best = outfit_dir / 'best.png'
            if best.exists():
                image_path = str(best)
                print(f'  ✅ 换装完成: {image_path}')
        except Exception as e:
            print(f'  ⚠️ 换装失败（用原图继续）: {str(e)[:100]}')

    # 1. 上传 + SAM 抠图（三色共用一次抠图）
    print(f'  📤 上传照片 + SAM 抠人像...')
    up_name = _load_image_file(image_path)
    seg_files = _submit(_build_segment_wf(up_name), timeout=300)
    if not seg_files:
        raise RuntimeError('抠图无输出')
    # 找 mask 文件（SAM 输出 image + mask）
    mask_path = os.path.join(COMFY_OUTPUT, seg_files[0])
    if not os.path.exists(mask_path):
        raise RuntimeError(f'mask 不存在: {mask_path}')

    # 2. 人像 bbox
    bbox = _person_bbox(mask_path)
    if not bbox:
        raise RuntimeError('未检测到人像')
    print(f'  📐 人像区域: {bbox}')

    from PIL import Image, ImageEnhance, ImageFilter

    # 3. 裁切人像（10% 边距）
    orig = Image.open(image_path).convert('RGB')
    min_x, min_y, max_x, max_y = bbox
    pad_x = int((max_x - min_x) * 0.08)
    pad_y = int((max_y - min_y) * 0.10)
    crop = orig.crop((max(0, min_x - pad_x), max(0, min_y - pad_y),
                      min(orig.width, max_x + pad_x), min(orig.height, max_y + pad_y)))

    # 美颜（磨皮+提亮，只对皮肤区域——简易版：整体轻磨皮+亮度）
    if beauty:
        # 磨皮：轻微高斯模糊（3px）+ 边缘保留（原图混合 40%）
        smooth = crop.filter(ImageFilter.GaussianBlur(1.2))
        crop = Image.blend(crop, smooth, 0.45)
        # 提亮 + 饱和度微调
        crop = ImageEnhance.Brightness(crop).enhance(1.06)
        crop = ImageEnhance.Color(crop).enhance(1.08)
        print(f'  ✨ 美颜开启（磨皮+提亮）')

    # 4. mask 裁切 + 平滑边缘
    mask_img = Image.open(mask_path).convert('L').resize(orig.size)
    mask_crop = mask_img.crop((max(0, min_x - pad_x), max(0, min_y - pad_y),
                               min(orig.width, max_x + pad_x), min(orig.height, max_y + pad_y)))
    mask_crop = mask_crop.point(lambda v: min(255, v + 30))

    # 5. 输出（单色 or 三色）
    colors = list(BG_COLORS.keys()) if all_colors else [bg]
    out_paths = []
    for c in colors:
        bg_c = BG_COLORS[c]
        canvas = Image.new('RGB', crop.size, bg_c)
        canvas.paste(crop, (0, 0), mask_crop)
        # 缩放到规格（头占比 2/3）
        ratio = min(out_w / canvas.width, out_h / canvas.height)
        new_w, new_h = int(canvas.width * ratio), int(canvas.height * ratio)
        canvas = canvas.resize((new_w, new_h), Image.LANCZOS)
        final = Image.new('RGB', (out_w, out_h), bg_c)
        x = (out_w - new_w) // 2
        y = int((out_h - new_h) * 0.35)
        final.paste(canvas, (x, y))
        # 输出
        if all_colors:
            p = output or str(PROJECT / 'outputs' / f"idphoto_{c}_{time.strftime('%Y%m%d_%H%M%S')}.png")
        else:
            p = output or str(PROJECT / 'outputs' / f"idphoto_{bg}_{time.strftime('%Y%m%d_%H%M%S')}.png")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        from workshop.image_utils import save_image_with_meta
        save_image_with_meta(final, p, source_path=image_path,
                             extra_meta={'idphoto': 'true', 'idphoto_bg': bg, 'idphoto_size': size})
        print(f'  🪪 证件照: {p} ({out_w}x{out_h} {c}底)')
        out_paths.append(p)

    return out_paths if all_colors else out_paths[0]


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop idphoto', description='AI证件照（SAM抠图+换底色+规格）')
    ap.add_argument('image', help='照片路径')
    ap.add_argument('--bg', choices=list(BG_COLORS.keys()), default='blue', help='底色 (white/blue/red)')
    ap.add_argument('--size', choices=list(SIZES.keys()), default='1inch', help='规格 (1inch/2inch/small2)')
    ap.add_argument('--beauty', action='store_true', help='美颜（磨皮+提亮）')
    ap.add_argument('--all-colors', action='store_true', help='三色一键全出（白/蓝/红）')
    ap.add_argument('--outfit', default=None, choices=['西装', '衬衫', '白衬衫', '深色西装'],
                    help='换装（IPAdapter 参考原图生成正式服装）')
    ap.add_argument('--output', default=None, help='输出路径')
    args = ap.parse_args(argv)

    try:
        idphoto(args.image, bg=args.bg, size=args.size, output=args.output,
                beauty=args.beauty, all_colors=args.all_colors, outfit=args.outfit)
        return 0
    except Exception as e:
        print(f'❌ 证件照失败: {str(e)[:150]}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
