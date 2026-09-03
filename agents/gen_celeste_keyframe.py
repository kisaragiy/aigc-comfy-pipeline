#!/usr/bin/env python3
"""
gen_celeste_keyframe.py — celeste 定稿图生成（C阶段 P0-1a）
用商业级管线（NoobAI + hires fix + FaceDetailer + HandDetailer）出 celeste 官方立绘水准图。
不含 elisabeth LoRA——celeste 先用纯角色卡 prompt + 固定seed（C阶段计划: 先锚定后LoRA）。
"""
from __future__ import annotations
import json, os, sys, time, random
import urllib.request

COMFY = 'http://127.0.0.1:8188'
CKPT = 'NoobAI-XL-v1.1.safetensors'
OUT_PREFIX = 'celeste_keyframe'

# celeste 角色卡 → 英文 prompt（oc_to_prompt 中文未翻译, 这里手动英文）
CELESTE_PROMPT = (
    "celeoc, 1girl, silver-white hair, long twin tails, amber-gold eyes, "
    "black gothic dress with lace details, delicate lace collar, "
    "cinematic lighting, anime lineart, game illustration structure, "
    "detailed fabric folds, glossy hair strands, refined eyes with highlights, "
    "masterpiece, best quality, front view, upper body portrait"
)
NEGATIVE = (
    "worst quality, low quality, blurry, bad anatomy, bad hands, missing fingers, "
    "extra fingers, deformed feet, malformed limbs, distorted proportions, "
    "extra limbs, ugly, bad proportions, long neck, cross-eyed, plastic, flat"
)

def http():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))

def submit(wf, timeout=900):
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

def build_workflow(prompt, negative, seed):
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
    empty = add({'class_type': 'EmptyLatentImage', 'inputs': {'width': 896, 'height': 1152, 'batch_size': 1}})
    base = add({'class_type': 'KSampler', 'inputs': {
        'model': model, 'positive': [pos, 0], 'negative': [neg, 0],
        'latent_image': [empty, 0], 'seed': seed, 'steps': 28, 'cfg': 6.5,
        'sampler_name': 'dpmpp_2m', 'scheduler': 'karras', 'denoise': 1.0}})
    dec0 = add({'class_type': 'VAEDecode', 'inputs': {'samples': [base, 0], 'vae': vae}})
    us_model = add({'class_type': 'UpscaleModelLoader', 'inputs': {'model_name': '4x-UltraSharp.pth'}})
    upscaled = add({'class_type': 'ImageUpscaleWithModel', 'inputs': {'upscale_model': [us_model, 0], 'image': [dec0, 0]}})
    final_img0 = add({'class_type': 'ImageScale', 'inputs': {
        'image': [upscaled, 0], 'upscale_method': 'lanczos', 'width': 1792, 'height': 2304, 'crop': 'disabled'}})
    usdu = add({'class_type': 'UltimateSDUpscale', 'inputs': {
        'image': [final_img0, 0], 'model': model, 'positive': [pos, 0], 'negative': [neg, 0],
        'vae': vae, 'upscale_by': 1.0, 'upscale_model': [us_model, 0],
        'redraw_width': 1024, 'redraw_height': 1024, 'seed': seed + 1, 'steps': 16, 'cfg': 5.5,
        'sampler_name': 'dpmpp_2m', 'scheduler': 'karras', 'denoise': 0.15,
        'mode_type': 'Linear', 'tile_width': 512, 'tile_height': 512,
        'mask_blur': 8, 'tile_padding': 32, 'seam_fix_mode': 'Band Pass', 'seam_fix_denoise': 1.0,
        'seam_fix_width': 64, 'seam_fix_mask_blur': 8, 'seam_fix_padding': 16,
        'force_uniform_tiles': True, 'tiled_decode': False, 'batch_size': 1}})
    fd_bbox = add({'class_type': 'UltralyticsDetectorProvider', 'inputs': {'model_name': 'bbox/face_yolov8m.pt'}})
    fd = add({'class_type': 'FaceDetailer', 'inputs': {
        'image': [usdu, 0], 'model': model, 'clip': clip, 'vae': vae,
        'guide_size': 512, 'guide_size_for': True, 'max_size': 1024,
        'seed': seed + 2, 'steps': 16, 'cfg': 5.5,
        'sampler_name': 'dpmpp_2m', 'scheduler': 'karras',
        'positive': [pos, 0], 'negative': [neg, 0],
        'denoise': 0.3, 'feather': 20, 'noise_mask': True,
        'force_inpaint': True, 'cycle': 1,
        'bbox_threshold': 0.5, 'bbox_dilation': 10, 'bbox_crop_factor': 3.0,
        'sam_detection_hint': 'center-1', 'sam_dilation': 0, 'sam_threshold': 0.93,
        'sam_bbox_expansion': 0, 'sam_mask_hint_threshold': 0.7,
        'sam_mask_hint_use_negative': 'False', 'drop_size': 10,
        'bbox_detector': [fd_bbox, 0], 'wildcard': ''}})
    hd_bbox = add({'class_type': 'UltralyticsDetectorProvider', 'inputs': {'model_name': 'bbox/hand_yolov8s.pt'}})
    hd_segs = add({'class_type': 'BboxDetectorSEGS', 'inputs': {
        'bbox_detector': [hd_bbox, 0], 'image': [fd, 0], 'labels': '',
        'threshold': 0.4, 'dilation': 12, 'crop_factor': 2.5, 'drop_size': 10}})
    hd = add({'class_type': 'DetailerForEach', 'inputs': {
        'image': [fd, 0], 'segs': [hd_segs, 0], 'model': model, 'clip': clip, 'vae': vae,
        'guide_size': 384, 'guide_size_for': True, 'max_size': 768,
        'seed': seed + 3, 'steps': 18, 'cfg': 5.5,
        'sampler_name': 'dpmpp_2m', 'scheduler': 'karras',
        'positive': [pos, 0], 'negative': [neg, 0],
        'denoise': 0.35, 'feather': 20, 'noise_mask': True,
        'force_inpaint': True, 'cycle': 1,
        'sam_detection_hint': 'center-1', 'sam_dilation': 0, 'sam_threshold': 0.93,
        'sam_bbox_expansion': 0, 'sam_mask_hint_threshold': 0.7,
        'sam_mask_hint_use_negative': 'False', 'drop_size': 10,
        'wildcard': ''}})
    save = add({'class_type': 'SaveImage', 'inputs': {'images': [hd, 0], 'filename_prefix': OUT_PREFIX}})
    return wf

def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else random.randint(1, 2**31)
    prompt = CELESTE_PROMPT
    print(f'提交 celeste 定稿 (seed={seed})...')
    wf = build_workflow(prompt, NEGATIVE, seed)
    files, pid = submit(wf, timeout=900)
    print(f'✅ 完成: {files}')
    print(f'  prompt_id: {pid}')

if __name__ == '__main__':
    main()
