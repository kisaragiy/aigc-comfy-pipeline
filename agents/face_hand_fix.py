#!/usr/bin/env python3
"""
face_hand_fix.py — D阶段第2轮: 面部+手部 双重局部修复

在已有图上做 FaceDetailer(修脸眼神/睫毛) + HandDetailer(修手,高denoise让手指分明)。
局部重绘, 保留构图/氛围。用于对 七维质检定位的"手部糊化/面部眼神弱" 定向修复。

用法: python face_hand_fix.py <img名(ComfyUI/input下)> <seed> [--hand-denoise 0.55] [--face-denoise 0.35]
"""
from __future__ import annotations
import json, os, sys, time, random
import urllib.request

COMFY = 'http://127.0.0.1:8188'
CKPT = 'NoobAI-XL-v1.1.safetensors'
OUT_PREFIX = 'face_hand_fix'

# 局部重绘正向词: 强"手指分明/眼神聚焦/睫毛分层"
FACE_HAND_POS = (
    "detailed expressive eyes, distinct eyelashes, focused gaze, "
    "well-defined eyelids, sharp iris highlights, "
    "detailed hands, defined fingers, distinct finger joints, "
    "natural hand pose, clean finger anatomy"
)
NEGATIVE = (
    "worst quality, low quality, blurry, bad anatomy, bad hands, missing fingers, "
    "extra fingers, deformed feet, malformed limbs, extra limbs, distorted proportions, "
    "fused fingers, melted fingers, no finger joints, opaque eyes, empty gaze, "
    "flat eyes, smudged lashes, plastic"
)

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

def build_workflow(img_name, seed, hand_denoise=0.55, face_denoise=0.35):
    wf = {}
    n = 1
    def add(node):
        nonlocal n
        wf[str(n)] = node
        n += 1
        return str(n - 1)

    ckpt = add({'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': CKPT}})
    model, clip, vae = [ckpt, 0], [ckpt, 1], [ckpt, 2]
    pos = add({'class_type': 'CLIPTextEncode', 'inputs': {'text': FACE_HAND_POS, 'clip': clip}})
    neg = add({'class_type': 'CLIPTextEncode', 'inputs': {'text': NEGATIVE, 'clip': clip}})
    load = add({'class_type': 'LoadImage', 'inputs': {'image': img_name}})
    img = [load, 0]

    # ① FaceDetailer (修脸)
    fd_bbox = add({'class_type': 'UltralyticsDetectorProvider', 'inputs': {'model_name': 'bbox/face_yolov8m.pt'}})
    face = add({'class_type': 'FaceDetailer', 'inputs': {
        'image': img, 'model': model, 'clip': clip, 'vae': vae,
        'guide_size': 512, 'guide_size_for': True, 'max_size': 1024,
        'seed': seed + 10, 'steps': 24, 'cfg': 6.0,
        'sampler_name': 'dpmpp_2m', 'scheduler': 'karras',
        'positive': [pos, 0], 'negative': [neg, 0],
        'denoise': face_denoise, 'feather': 20, 'noise_mask': True,
        'force_inpaint': True, 'cycle': 2,
        'bbox_threshold': 0.5, 'bbox_dilation': 10, 'bbox_crop_factor': 3.0,
        'sam_detection_hint': 'center-1', 'sam_dilation': 0, 'sam_threshold': 0.93,
        'sam_bbox_expansion': 0, 'sam_mask_hint_threshold': 0.7,
        'sam_mask_hint_use_negative': 'False', 'drop_size': 10,
        'bbox_detector': [fd_bbox, 0], 'wildcard': ''}})

    # ② HandDetailer (修手, 高denoise)
    hd_bbox = add({'class_type': 'UltralyticsDetectorProvider', 'inputs': {'model_name': 'bbox/hand_yolov8s.pt'}})
    hd_segs = add({'class_type': 'BboxDetectorSEGS', 'inputs': {
        'bbox_detector': [hd_bbox, 0], 'image': [face, 0], 'labels': '',
        'threshold': 0.4, 'dilation': 12, 'crop_factor': 2.5, 'drop_size': 10}})
    hand = add({'class_type': 'DetailerForEach', 'inputs': {
        'image': [face, 0], 'segs': [hd_segs, 0], 'model': model, 'clip': clip, 'vae': vae,
        'guide_size': 512, 'guide_size_for': True, 'max_size': 1024,
        'seed': seed + 11, 'steps': 30, 'cfg': 6.5,
        'sampler_name': 'dpmpp_2m', 'scheduler': 'karras',
        'positive': [pos, 0], 'negative': [neg, 0],
        'denoise': hand_denoise, 'feather': 24, 'noise_mask': True,
        'force_inpaint': True, 'cycle': 2,
        'sam_detection_hint': 'center-1', 'sam_dilation': 0, 'sam_threshold': 0.93,
        'sam_bbox_expansion': 0, 'sam_mask_hint_threshold': 0.7,
        'sam_mask_hint_use_negative': 'False', 'drop_size': 10,
        'wildcard': ''}})

    save = add({'class_type': 'SaveImage', 'inputs': {'images': [hand, 0], 'filename_prefix': OUT_PREFIX}})
    return wf

def main():
    if len(sys.argv) < 2:
        print('用法: face_hand_fix.py <img名> <seed> [--hand-denoise 0.55] [--face-denoise 0.35]')
        sys.exit(1)
    img_name = sys.argv[1]
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else random.randint(1, 2**31)
    hand_d, face_d = 0.55, 0.35
    if '--hand-denoise' in sys.argv:
        hand_d = float(sys.argv[sys.argv.index('--hand-denoise') + 1])
    if '--face-denoise' in sys.argv:
        face_d = float(sys.argv[sys.argv.index('--face-denoise') + 1])
    print(f'▶ 面+手 双重修复 (img={img_name}, seed={seed}, hand_d={hand_d}, face_d={face_d})')
    wf = build_workflow(img_name, seed, hand_d, face_d)
    files, pid = submit(wf, timeout=700)
    print(f'  ✅ {files}')

if __name__ == '__main__':
    main()
