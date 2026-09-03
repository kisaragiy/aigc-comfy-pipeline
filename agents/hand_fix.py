#!/usr/bin/env python3
"""
hand_fix.py — 手部局部修复（D2 路径A: 局部重绘，不重生成整张）

原理: BboxDetectorSEGS(hand_yolov8s 检测手) → DetailerForEach(对检出的手局部重绘)
手段: 只重绘手机区域, 保留原图其他部分(构图/脸/氛围不动)。
      用高 step 重绘手部细节, 修"手指熔块/缺指/结构错"。

用法: python hand_fix.py <img> <seed> [--denoise 0.5] [--out out.png]
"""
from __future__ import annotations
import json, os, sys, time
import urllib.request
import random

COMFY = 'http://127.0.0.1:8188'
CKPT = 'NoobAI-XL-v1.1.safetensors'
OUT_PREFIX = 'hand_fix'

def http():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))

def submit(wf, timeout=600):
    body = json.dumps({'prompt': wf}).encode()
    req = urllib.request.Request(COMFY + '/prompt', data=body, headers={'Content-Type': 'application/json'})
    r = json.loads(http().open(req, timeout=30).read())
    if 'error' in r:
        raise RuntimeError(str(r['error'])[:300])
    pid = r['prompt_id']
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            d = json.loads(http().open(COMFY + f'/history/{pid}', timeout=5).read())
            if pid in d:
                files = []
                for node in d[pid].get('outputs', {}).values():
                    for img in node.get('images', []):
                        files.append(img['filename'])
                if files:
                    return files, pid
        except Exception:
            pass
        time.sleep(2)
    raise TimeoutError('生成超时')

def build_workflow(img_name, prompt, negative, seed, denoise=0.5):
    wf = {}
    n = 1
    def add(node):
        nonlocal n
        wf[str(n)] = node
        n += 1
        return str(n - 1)

    ckpt = add({'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': CKPT}})
    model, clip, vae = [ckpt, 0], [ckpt, 1], [ckpt, 2]

    pos = add({'class_type': 'CLIPTextEncode', 'inputs': {'text': prompt, 'clip': clip}})
    neg = add({'class_type': 'CLIPTextEncode', 'inputs': {'text': negative, 'clip': clip}})

    # 载入原图
    load = add({'class_type': 'LoadImage', 'inputs': {'image': img_name}})
    img = [load, 0]

    # 手部检测 + 局部重绘 (DetailerForEach)
    hd_bbox = add({'class_type': 'UltralyticsDetectorProvider', 'inputs': {'model_name': 'bbox/hand_yolov8s.pt'}})
    hd_segs = add({'class_type': 'BboxDetectorSEGS', 'inputs': {
        'bbox_detector': [hd_bbox, 0], 'image': img, 'labels': '',
        'threshold': 0.4, 'dilation': 10, 'crop_factor': 2.5, 'drop_size': 10}})
    hd = add({'class_type': 'DetailerForEach', 'inputs': {
        'image': img, 'segs': [hd_segs, 0], 'model': model, 'clip': clip, 'vae': vae,
        'guide_size': 512, 'guide_size_for': True, 'max_size': 1024,
        'seed': seed, 'steps': 22, 'cfg': 6.0,
        'sampler_name': 'dpmpp_2m', 'scheduler': 'karras',
        'positive': [pos, 0], 'negative': [neg, 0],
        'denoise': denoise, 'feather': 20, 'noise_mask': True,
        'force_inpaint': True, 'cycle': 2,
        'sam_detection_hint': 'center-1', 'sam_dilation': 0, 'sam_threshold': 0.93,
        'sam_bbox_expansion': 0, 'sam_mask_hint_threshold': 0.7,
        'sam_mask_hint_use_negative': 'False', 'drop_size': 10,
        'wildcard': ''}})

    save = add({'class_type': 'SaveImage', 'inputs': {'images': [hd, 0], 'filename_prefix': OUT_PREFIX}})
    return wf

# 手部修复专用 prompt: 强调"手部结构清晰/手指分节/自然姿态"
HAND_EXTRA = (
    ", detailed hands, well-defined fingers, distinct finger joints, "
    "natural hand pose, proper finger anatomy, clean knuckles"
)
NEGATIVE = (
    "worst quality, low quality, blurry, bad anatomy, bad hands, missing fingers, "
    "extra fingers, deformed feet, malformed limbs, extra limbs, distorted proportions, "
    "fused fingers, melted fingers, no finger joints, plastic"
)

def main():
    if len(sys.argv) < 2:
        print('用法: hand_fix.py <img名(ComfyUI/input下)> <seed> [--denoise 0.5]')
        sys.exit(1)
    img_name = sys.argv[1]
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else random.randint(1, 2**31)
    denoise = 0.5
    if '--denoise' in sys.argv:
        denoise = float(sys.argv[sys.argv.index('--denoise') + 1])
    prompt = HAND_EXTRA  # 局部重绘用强手部正向词
    print(f'▶ 手部局部修复 (img={img_name}, seed={seed}, denoise={denoise})')
    wf = build_workflow(img_name, prompt, NEGATIVE, seed, denoise)
    files, pid = submit(wf, timeout=600)
    print(f'  ✅ {files}')

if __name__ == '__main__':
    main()
