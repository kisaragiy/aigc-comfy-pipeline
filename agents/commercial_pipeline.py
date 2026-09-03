#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""商业级管线：基础生成 → hires fix → FaceDetailer → UltimateSDUpscale → 调色
对齐业界最佳实践商业画师流程。"""
import json, os, sys, time, random
import urllib.request

COMFY = 'http://127.0.0.1:8188'
CKPT = 'NoobAI-XL-v1.1.safetensors'
LORA = 'elisabeth_sdxl.safetensors'
REF_IMG = 'elisabeth_official.png'
OUT_PREFIX = 'commercial'

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

def build_workflow(prompt, negative, seed):
    """基础生成 → hires fix → FaceDetailer → UltimateSDUpscale 全链工作流"""
    wf = {}
    n = 1
    def add(node):
        nonlocal n
        wf[str(n)] = node
        n += 1
        return str(n - 1)

    # 1. Checkpoint + LoRA
    ckpt = add({'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': CKPT}})
    lora = add({'class_type': 'LoraLoader', 'inputs': {
        'model': [ckpt, 0], 'clip': [ckpt, 1],
        'lora_name': LORA, 'strength_model': 0.6, 'strength_clip': 0.6}})
    model, clip, vae = [lora, 0], [lora, 1], [ckpt, 2]

    # 2. 提示词
    pos = add({'class_type': 'CLIPTextEncode', 'inputs': {'text': prompt, 'clip': clip}})
    neg = add({'class_type': 'CLIPTextEncode', 'inputs': {'text': negative, 'clip': clip}})

    # 3. 基础生成 896x1152
    empty = add({'class_type': 'EmptyLatentImage', 'inputs': {'width': 896, 'height': 1152, 'batch_size': 1}})
    base = add({'class_type': 'KSampler', 'inputs': {
        'model': model, 'positive': [pos, 0], 'negative': [neg, 0],
        'latent_image': [empty, 0], 'seed': seed, 'steps': 28, 'cfg': 6.5,
        'sampler_name': 'dpmpp_2m', 'scheduler': 'karras', 'denoise': 1.0}})

    # 3b. 解码基础图（供像素超分）
    dec0 = add({'class_type': 'VAEDecode', 'inputs': {'samples': [base, 0], 'vae': vae}})

    # 4. 像素超分 2x（4x-UltraSharp → 缩到 1792x2304；不经 latent，零 tiled 伪影）
    us_model = add({'class_type': 'UpscaleModelLoader', 'inputs': {
        'model_name': '4x-UltraSharp.pth'}})
    upscaled = add({'class_type': 'ImageUpscaleWithModel', 'inputs': {
        'upscale_model': [us_model, 0], 'image': [dec0, 0]}})
    final_img0 = add({'class_type': 'ImageScale', 'inputs': {
        'image': [upscaled, 0], 'upscale_method': 'lanczos',
        'width': 1792, 'height': 2304, 'crop': 'disabled'}})

    # 5. USDU tile 重绘补细节（tile 小=512，denoise 0.2 轻重构，避免接缝伪影）
    usdu = add({'class_type': 'UltimateSDUpscale', 'inputs': {
        'image': [final_img0, 0], 'model': model, 'positive': [pos, 0], 'negative': [neg, 0],
        'vae': vae, 'upscale_by': 1.0,
        'upscale_model': [us_model, 0],
        'redraw_width': 1024, 'redraw_height': 1024,
        'seed': seed + 1, 'steps': 16, 'cfg': 5.5,
        'sampler_name': 'dpmpp_2m', 'scheduler': 'karras',
        'denoise': 0.15,
        'mode_type': 'Linear', 'tile_width': 512, 'tile_height': 512,
        'mask_blur': 8, 'tile_padding': 32,
        'seam_fix_mode': 'Band Pass', 'seam_fix_denoise': 1.0,
        'seam_fix_width': 64, 'seam_fix_mask_blur': 8, 'seam_fix_padding': 16,
        'force_uniform_tiles': True, 'tiled_decode': False, 'batch_size': 1}})

    # 6. FaceDetailer 修脸（脸部小区域重绘，不触发大图 tiled）
    fd_bbox = add({'class_type': 'UltralyticsDetectorProvider', 'inputs': {
        'model_name': 'bbox/face_yolov8m.pt'}})
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

    # 6b. HandDetailer 修手（hand_yolov8s 检测手部 SEGS → DetailerForEach 局部重绘）
    hd_bbox = add({'class_type': 'UltralyticsDetectorProvider', 'inputs': {
        'model_name': 'bbox/hand_yolov8s.pt'}})
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

    # 7. 保存
    final_img = hd

    # 8. 保存
    save = add({'class_type': 'SaveImage', 'inputs': {
        'images': [final_img, 0], 'filename_prefix': OUT_PREFIX}})
    return wf

def main():
    prompt = sys.argv[1] if len(sys.argv) > 1 else ''
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else random.randint(1, 2**31)
    if not prompt:
        prompt = ('elisabeth, 1girl, silver-white hair, twin tails, blue ribbon, blue eyes, '
                  'white sailor-style dress, blue-white striped collar, navy bow, white gloves, '
                  'front view, full body, detailed fabric folds, glossy hair strands, '
                  'refined eyes with highlights, masterpiece, best quality')
    negative = ('worst quality, low quality, blurry, bad anatomy, bad hands, missing fingers, '
                'extra fingers, deformed feet, malformed limbs, distorted proportions, '
                'extra limbs, ugly, bad proportions, long neck, cross-eyed, plastic, flat')
    print(f'提交商业管线 (seed={seed})...')
    wf = build_workflow(prompt, negative, seed)
    files, pid = submit(wf, timeout=900)
    print(f'✅ 完成: {files}')
    print(f'  prompt_id: {pid}')

if __name__ == '__main__':
    main()
