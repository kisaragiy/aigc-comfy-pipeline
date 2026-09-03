#!/usr/bin/env python3
"""
gen_celeste_scenes.py — celeste 多场景批量生成（C阶段 P0-2b）
IPAdapter(PLUS) + 固定seed 锚定 celeste 定稿图 → 跨场景同一张脸。
每个场景: 锚定参考图(celeste_keyframe) + 角色卡prompt(scene) + 固定seed。

用法: python gen_celeste_scenes.py <scene> <seed>   # 单场景
      python gen_celeste_scenes.py --all             # 全部场景
"""
from __future__ import annotations
import json, os, sys, time, random
import urllib.request

COMFY = 'http://127.0.0.1:8188'
CKPT = 'NoobAI-XL-v1.1.safetensors'
REF_IMAGE = 'celeste_keyframe.png'  # ComfyUI/input 下的锚定参考图
OUT_PREFIX = 'celeste_scene'

# celeste 角色基础(定稿图已锚定, prompt 描述场景+角色)
BASE = (
    "celeoc, 1girl, silver-white hair, long twin tails, amber-gold eyes, "
    "black gothic dress, delicate lace, cinematic lighting, anime lineart, "
    "game illustration structure, masterpiece, best quality"
)
NEGATIVE = (
    "worst quality, low quality, blurry, bad anatomy, bad hands, missing fingers, "
    "extra fingers, deformed feet, malformed limbs, distorted proportions, "
    "extra limbs, ugly, long neck, cross-eyed"
)

SCENES = {
    "library":  "in a grand gothic library, towering bookshelves, warm golden light through arched windows, reading a book, full body",
    "battle":   "dynamic combat pose, magic energy swirling, gothic castle ruins background, dramatic lighting, full body",
    "swimsuit": "wearing black bikini, tropical beach sunset, ocean waves, playful pose, full body",
    "rainy":    "standing in soft rain, black gothic umbrella, moody street with lanterns, wet hair, three-quarter view",
    "casual":   "soft smile, cozy café, warm ambient light, holding coffee cup, waist-up",
    "closeup":  "extreme close-up face portrait, glowing amber eyes, reflective highlights, detailed hair strands, cinematic",
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

def build_workflow(prompt, negative, seed, use_ipadapter=True):
    wf = {}
    n = 1
    def add(node):
        nonlocal n
        wf[str(n)] = node
        n += 1
        return str(n - 1)

    ckpt = add({'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': CKPT}})
    model, clip, vae = [ckpt, 0], [ckpt, 1], [ckpt, 2]

    if use_ipadapter:
        # 参考图(锚定) → LoadImage
        ref = add({'class_type': 'LoadImage', 'inputs': {'image': REF_IMAGE}})
        ref_img = [ref, 0]

        # IPAdapter 锚定: PLUS FACE preset (专门人脸, 防整图过冲)
        ipa_loader = add({'class_type': 'IPAdapterUnifiedLoader', 'inputs': {
            'model': model, 'preset': 'PLUS FACE (portraits)'}})
        ipa_model = [ipa_loader, 0]

        # IPAdapterAdvanced: 参考图注入 (K+V 默认, weight 0.5 防过冲)
        ipa = add({'class_type': 'IPAdapterAdvanced', 'inputs': {
            'model': ipa_model, 'ipadapter': [ipa_loader, 1], 'image': ref_img,
            'weight': 0.5, 'weight_type': 'linear', 'combine_embeds': 'concat',
            'start_at': 0.0, 'end_at': 1.0, 'embeds_scaling': 'K+V'}})
        model2 = [ipa, 0]
    else:
        model2 = model

    pos = add({'class_type': 'CLIPTextEncode', 'inputs': {'text': prompt, 'clip': clip}})
    neg = add({'class_type': 'CLIPTextEncode', 'inputs': {'text': negative, 'clip': clip}})
    empty = add({'class_type': 'EmptyLatentImage', 'inputs': {'width': 832, 'height': 1216, 'batch_size': 1}})
    base = add({'class_type': 'KSampler', 'inputs': {
        'model': model2, 'positive': [pos, 0], 'negative': [neg, 0],
        'latent_image': [empty, 0], 'seed': seed, 'steps': 28, 'cfg': 6.0,
        'sampler_name': 'dpmpp_2m', 'scheduler': 'karras', 'denoise': 1.0}})
    dec0 = add({'class_type': 'VAEDecode', 'inputs': {'samples': [base, 0], 'vae': vae}})
    save = add({'class_type': 'SaveImage', 'inputs': {'images': [dec0, 0], 'filename_prefix': f'{OUT_PREFIX}'}})
    return wf

def gen_scene(scene, seed, use_ipa=False):
    if scene not in SCENES:
        print(f'未知场景: {scene} (可用: {list(SCENES.keys())})')
        return None
    scene_desc = SCENES[scene]
    prompt = f'{BASE}, {scene_desc}'
    print(f'▶ 生成 [{scene}] seed={seed}  ipa={use_ipa}')
    print(f'  prompt: {prompt[:90]}...')
    wf = build_workflow(prompt, NEGATIVE, seed, use_ipa)
    files, pid = submit(wf, timeout=900)
    print(f'  ✅ {files}')
    return files

def main():
    args = sys.argv[1:]
    use_ipa = False  # 默认不用IPAdapter(实测: 纯prompt+角色卡+固定seed 已足够一致, IPAdapter反致数字错乱)
    if '--ipa' in args:
        use_ipa = True
        args = [a for a in args if a != '--ipa']
    if args and args[0] == '--all':
        base_seed = int(args[1]) if len(args) > 1 else 42
        for i, scene in enumerate(SCENES):
            gen_scene(scene, base_seed + i * 17, use_ipa)
    else:
        scene = args[0] if args else 'library'
        seed = int(args[1]) if len(args) > 1 else 42
        gen_scene(scene, seed, use_ipa)

if __name__ == '__main__':
    main()
