#!/usr/bin/env python3
"""
gen_celeste_dd.py — 带 Detail-Daemon 的 celeste 生成（抗AI味/提质感）

工作流结构:
  CheckpointLoader → CLIPText(正负) → RandomNoise + CFGGuider + KSamplerSelect
  → DetailDaemonSamplerNode(包装) + BasicScheduler → SamplerCustomAdvanced → VAE → Save

用法: python gen_celeste_dd.py <scene> <seed> [--detail 0.18] [--cfg 6.5]
"""
from __future__ import annotations
import json, os, sys, time, random
import urllib.request

COMFY = 'http://127.0.0.1:8188'
CKPT = 'NoobAI-XL-v1.1.safetensors'
OUT_PREFIX = 'celeste_dd'

BASE = (
    "celeoc, 1girl, silver-white hair, long twin tails, amber-gold eyes, "
    "black gothic dress, delicate lace, cinematic lighting, "
    "dramatic rim light, warm golden key light, cool ambient fill, "
    "detailed fabric folds, glossy hair strands, sharp iris highlights, "
    "masterpiece, best quality, high detail, film grain"
)
NEGATIVE = (
    "worst quality, low quality, blurry, bad anatomy, bad hands, missing fingers, "
    "extra fingers, deformed feet, malformed limbs, extra limbs, ugly, "
    "flat lighting, plastic skin, oversaturated, washed out, amateur"
)

SCENES = {
    "library":  "in a grand gothic library, towering bookshelves, warm golden light through arched windows, full body",
    "battle":   "dynamic combat pose, magic energy swirling, gothic castle ruins, dramatic lighting, full body",
    "swimsuit": "wearing black bikini, tropical beach sunset, ocean waves, warm sunset rim light, full body",
    "rainy":    "standing in soft rain, black umbrella, moody lantern-lit street, wet hair, three-quarter",
    "casual":   "soft smile, cozy cafe, warm ambient light, holding coffee cup, waist-up",
    "closeup":  "extreme close-up face, glowing amber eyes, detailed iris, cinematic",
    "portrait": "upper body portrait, elegant pose, refined eyes, dramatic lighting",
    "maid":     "wearing a black and white gothic maid outfit, white frilly apron, lace headdress, holding a silver tea tray, elegant classic maid cafe interior, warm lighting",
}

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

def build_workflow(prompt, negative, seed, detail_amount=0.18, cfg=6.5, steps=30, ckpt=CKPT):
    wf = {}
    n = 1
    def add(node):
        nonlocal n
        wf[str(n)] = node
        n += 1
        return str(n - 1)

    ckpt = add({'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': ckpt}})
    model, clip, vae = [ckpt, 0], [ckpt, 1], [ckpt, 2]
    pos = add({'class_type': 'CLIPTextEncode', 'inputs': {'text': prompt, 'clip': clip}})
    neg = add({'class_type': 'CLIPTextEncode', 'inputs': {'text': negative, 'clip': clip}})

    # SamplerCustomAdvanced 组件
    noise = add({'class_type': 'RandomNoise', 'inputs': {'noise_seed': seed}})
    guider = add({'class_type': 'CFGGuider', 'inputs': {'model': model, 'positive': [pos, 0], 'negative': [neg, 0], 'cfg': cfg}})
    ksampler_sel = add({'class_type': 'KSamplerSelect', 'inputs': {'sampler_name': 'dpmpp_2m'}})
    # Detail-Daemon 包装 sampler
    dd = add({'class_type': 'DetailDaemonSamplerNode', 'inputs': {
        'sampler': [ksampler_sel, 0], 'detail_amount': detail_amount,
        'start': 0.2, 'end': 0.8, 'bias': 0.5, 'exponent': 1.0,
        'start_offset': 0.0, 'end_offset': 0.0, 'fade': 0.0,
        'smooth': True, 'cfg_scale_override': 0.0}})
    scheduler = add({'class_type': 'BasicScheduler', 'inputs': {'model': model, 'scheduler': 'karras', 'steps': steps, 'denoise': 1.0}})
    empty = add({'class_type': 'EmptyLatentImage', 'inputs': {'width': 832, 'height': 1216, 'batch_size': 1}})
    sample = add({'class_type': 'SamplerCustomAdvanced', 'inputs': {
        'noise': [noise, 0], 'guider': [guider, 0], 'sampler': [dd, 0],
        'sigmas': [scheduler, 0], 'latent_image': [empty, 0]}})
    dec = add({'class_type': 'VAEDecode', 'inputs': {'samples': [sample, 0], 'vae': vae}})
    save = add({'class_type': 'SaveImage', 'inputs': {'images': [dec, 0], 'filename_prefix': OUT_PREFIX}})
    return wf

def main():
    args = sys.argv[1:]
    scene = args[0] if args else 'swimsuit'
    seed = int(args[1]) if len(args) > 1 else 777
    detail = 0.18
    if '--detail' in args:
        detail = float(args[args.index('--detail') + 1])
    ckpt = CKPT
    if '--ckpt' in args:
        ckpt = args[args.index('--ckpt') + 1]
    desc = SCENES.get(scene, scene)
    prompt = f'{BASE}, {desc}'
    print(f'▶ DD生成 [{scene}] seed={seed} detail={detail} ckpt={ckpt}')
    wf = build_workflow(prompt, NEGATIVE, seed, detail, ckpt=ckpt)
    files, pid = submit(wf, timeout=900)
    print(f'  ✅ {files}')

if __name__ == '__main__':
    main()
