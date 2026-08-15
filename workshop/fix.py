#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/fix.py — 局部修复（inpaint）v1.0
=========================================
画师改一只手 = 改一只手。这是我们的"局部橡皮擦"：
指定区域 → mask（羽化）→ SetLatentNoiseMask 局部重绘 → 合成输出。

用法:
  python -m agents workshop fix <图片> --prompt "新的局部描述"
      [--box x,y,w,h]                   手动指定区域（像素坐标）
      [--auto face|hand]                YOLO 自动检测脸部/手部区域
      [--denoise 0.6]                   重绘强度（0.3=微调 0.8=大改）
      [--model sdxl]                    模型（sdxl/flux）
      [--negative "坏词"]               负面词
      [--out 输出路径]                  默认 outputs/fix_<时间>/
"""

import argparse, base64, json, os, re, subprocess, sys, time, urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
COMFY = 'http://127.0.0.1:8188'
COMFY_VENV_PY = r'C:\DrawingLive\ComfyUI\venv\Scripts\python.exe'
CKPT_SDXL = 'waiIllustriousSDXL_v160.safetensors'
OUT_BASE = PROJECT / 'outputs'
TMP = PROJECT / 'workspace' / 'fix_tmp'
TMP.mkdir(parents=True, exist_ok=True)

def _norm(p):
    p = os.path.expanduser(p)
    m = re.match(r'^/([a-zA-Z])/(.*)$', p)
    if m:
        p = m.group(1) + ':/' + m.group(2)
    return p

def _http():
    """禁用代理的 urllib opener（环境 http_proxy 会劫持 localhost/内网）"""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))

def _comfy_alive():
    try:
        r = _http().open(COMFY + '/queue', timeout=3)
        return r.status == 200
    except Exception:
        return False

def _wait_images(prompt_id, timeout=180):
    """轮询 /history 等图生成完，返回输出文件列表"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = _http().open(COMFY + f'/history/{prompt_id}', timeout=5)
            d = json.loads(r.read())
            if prompt_id in d:
                outs = d[prompt_id].get('outputs', {})
                files = []
                for node in outs.values():
                    for img in node.get('images', []):
                        files.append(img['filename'])
                if files:
                    return files
        except Exception:
            pass
        time.sleep(2)
    return []

# ── 区域定位 ──

def _detect_yolo(img_path, kind='face'):
    """subprocess 调 ComfyUI venv python + YOLO 检测 bbox。
    返回 [x1,y1,x2,y2] 或 None"""
    model = 'face_yolov8m.pt' if kind == 'face' else 'hand_yolov8s.pt'
    script = f'''
import sys
from ultralytics import YOLO
img = r"{img_path}"
m = YOLO(r"C:\\DrawingLive\\ComfyUI\\models\\ultralytics\\bbox\\{model}")
r = m(img, verbose=False)
boxes = r[0].boxes
if boxes is None or len(boxes) == 0:
    print("NONE"); sys.exit(0)
b = boxes.xyxy[0].tolist()
print(",".join(str(int(x)) for x in b))
'''
    try:
        env = os.environ.copy()
        env['PYTHONPATH'] = r'C:\DrawingLive\ComfyUI\venv\Lib\site-packages'
        env.pop('http_proxy', None)
        env.pop('https_proxy', None)
        r = subprocess.run([COMFY_VENV_PY, '-c', script], capture_output=True,
                           text=True, timeout=60, env=env)
        out = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ''
        if out and out != 'NONE' and ',' in out:
            x1, y1, x2, y2 = map(int, out.split(','))
            return [x1, y1, x2, y2]
    except Exception as e:
        print(f'  ⚠️ YOLO 检测失败: {str(e)[:80]}')
    return None

def _make_mask(img_path, box, feather=30, expand=0.15):
    """PIL 生成黑底白块 mask（羽化）。box=[x1,y1,x2,y2] 可选 expand 扩展比例"""
    from PIL import Image, ImageDraw, ImageFilter
    img = Image.open(img_path)
    w, h = img.size
    x1, y1, x2, y2 = box
    # 扩展
    bw, bh = x2 - x1, y2 - y1
    ex, ey = int(bw * expand), int(bh * expand)
    x1, y1 = max(0, x1 - ex), max(0, y1 - ey)
    x2, y2 = min(w, x2 + ex), min(h, y2 + ey)
    mask = Image.new('L', (w, h), 0)
    ImageDraw.Draw(mask).rectangle([x1, y1, x2, y2], fill=255)
    if feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(feather))
    path = TMP / f'mask_{int(time.time())}.png'
    mask.save(path)
    return str(path), (x1, y1, x2, y2)

# ── inpaint 工作流（SDXL） ──

def _build_inpaint_wf(img_path, mask_path, prompt, negative, denoise, seed):
    cid = 1
    def nxt(i):
        return str(i)
    wf = {}
    n = cid; cid += 1
    wf[nxt(n)] = {'class_type': 'CheckpointLoaderSimple',
                  'inputs': {'ckpt_name': CKPT_SDXL}}
    ckpt = nxt(n)
    n = cid; cid += 1
    wf[nxt(n)] = {'class_type': 'CLIPTextEncode',
                  'inputs': {'text': prompt, 'clip': [ckpt, 1]}}
    pos = nxt(n)
    n = cid; cid += 1
    wf[nxt(n)] = {'class_type': 'CLIPTextEncode',
                  'inputs': {'text': negative, 'clip': [ckpt, 1]}}
    neg = nxt(n)
    n = cid; cid += 1
    wf[nxt(n)] = {'class_type': 'LoadImage', 'inputs': {'image': os.path.basename(img_path)}}
    img_node = nxt(n)
    n = cid; cid += 1
    wf[nxt(n)] = {'class_type': 'LoadImage', 'inputs': {'image': os.path.basename(mask_path)}}
    mask_node = nxt(n)
    n = cid; cid += 1
    wf[nxt(n)] = {'class_type': 'VAEEncode',
                  'inputs': {'pixels': [img_node, 0], 'vae': [ckpt, 2]}}
    lat = nxt(n)
    n = cid; cid += 1
    wf[nxt(n)] = {'class_type': 'SetLatentNoiseMask',
                  'inputs': {'samples': [lat, 0], 'mask': [mask_node, 1]}}
    masked = nxt(n)
    n = cid; cid += 1
    wf[nxt(n)] = {'class_type': 'KSampler',
                  'inputs': {'model': [ckpt, 0], 'positive': [pos, 0],
                             'negative': [neg, 0], 'latent_image': [masked, 0],
                             'seed': seed, 'steps': 28, 'cfg': 6.5,
                             'sampler_name': 'dpmpp_2m', 'scheduler': 'karras',
                             'denoise': denoise}}
    samp = nxt(n)
    n = cid; cid += 1
    wf[nxt(n)] = {'class_type': 'VAEDecode',
                  'inputs': {'samples': [samp, 0], 'vae': [ckpt, 2]}}
    dec = nxt(n)
    n = cid; cid += 1
    wf[nxt(n)] = {'class_type': 'SaveImage',
                  'inputs': {'images': [dec, 0], 'filename_prefix': 'pipeline_fix'}}
    return wf

# ── main ──

def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop fix', description='局部修复（inpaint）')
    ap.add_argument('image', help='原图路径')
    ap.add_argument('--prompt', required=True, help='局部重绘描述（英文或中文）')
    ap.add_argument('--box', default=None, help='区域 x1,y1,x2,y2（像素）')
    ap.add_argument('--auto', choices=['face', 'hand'], default=None,
                    help='YOLO 自动检测脸/手区域')
    ap.add_argument('--denoise', type=float, default=0.6)
    ap.add_argument('--negative', default='bad anatomy, bad hands, extra fingers, blurry, lowres')
    ap.add_argument('--out', default=None, help='输出目录（默认 outputs/fix_<时间>/）')
    ap.add_argument('--seed', type=int, default=-1)
    args = ap.parse_args(argv)

    img = _norm(args.image)
    if not os.path.exists(img):
        print(f'图片不存在: {img}')
        return
    if not _comfy_alive():
        print('ComfyUI 未运行（127.0.0.1:8188）。先启动再试。')
        return

    # 1. 区域定位
    box = None
    if args.box:
        try:
            box = [int(x) for x in args.box.split(',')]
        except Exception:
            print('--box 格式: x1,y1,x2,y2')
            return
    elif args.auto:
        box = _detect_yolo(img, args.auto)
        if box:
            print(f'  YOLO 检测到 {args.auto} 区域: {box}')
        else:
            print(f'  ⚠️ YOLO 未检测到 {args.auto}，用整图下半部代替')
            from PIL import Image
            w, h = Image.open(img).size
            box = [0, int(h * 0.5), w, h]
    else:
        from PIL import Image
        w, h = Image.open(img).size
        print(f'  图片尺寸 {w}x{h}。未指定区域，默认整图重绘（denoise={args.denoise} 控制强度）')
        box = [0, 0, w, h]

    # 2. mask
    mask_path, real_box = _make_mask(img, box)
    print(f'  修复区域: {real_box} | mask: {mask_path}')

    # 3. 复制图片到 ComfyUI input（LoadImage 需要 input 目录）
    import shutil
    comfy_input = r'C:\DrawingLive\ComfyUI\input'
    img_dst = os.path.join(comfy_input, os.path.basename(img))
    mask_dst = os.path.join(comfy_input, os.path.basename(mask_path))
    shutil.copy(img, img_dst)
    shutil.copy(mask_path, mask_dst)

    # 4. 提交
    seed = args.seed if args.seed >= 0 else int(time.time()) % 2**31
    wf = _build_inpaint_wf(img, mask_path, args.prompt, args.negative, args.denoise, seed)
    body = json.dumps({'prompt': wf}).encode()
    req = urllib.request.Request(COMFY + '/prompt', data=body,
                                 headers={'Content-Type': 'application/json'})
    r = json.loads(_http().open(req, timeout=30).read())
    if 'error' in r:
        print(f'提交失败: {r["error"]}')
        return
    pid = r['prompt_id']
    print(f'  已提交 prompt_id={pid}，等待生成...')

    files = _wait_images(pid)
    if not files:
        print('  生成超时/无输出')
        return
    out_dir = Path(_norm(args.out)) if args.out else OUT_BASE / f'fix_{time.strftime("%Y%m%d_%H%M%S")}'
    out_dir.mkdir(parents=True, exist_ok=True)
    comfy_out = r'C:\DrawingLive\ComfyUI\output'
    saved = []
    for f in files:
        src = os.path.join(comfy_out, f)
        if os.path.exists(src):
            dst = out_dir / f
            shutil.copy(src, dst)
            saved.append(str(dst))
    print(f'\n✅ 修复完成: {saved}')
    print(f'  对比: 原图 {img}')

if __name__ == '__main__':
    main()
