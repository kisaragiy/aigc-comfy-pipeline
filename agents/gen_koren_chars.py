#!/usr/bin/env python3
"""
gen_koren_chars.py — 给朋友的小说角色立绘生成（望月 + 冉青青）

标准: 顶级商业立绘(用户定) = waiIllustriousSDXL + Detail-Daemon(0.18) + 光影引导词
边界: 私人使用(只给朋友看, 私聊, 不公开), 非女仆, 不含软色情/性暗示, 小表示(泪痣)尽力还原不强迫

用法:
  python gen_koren_chars.py <name> <seed> [--out-prefix pref] [--detail 0.18]
  name = wangyue | ranqingqing
"""
from __future__ import annotations
import json, os, sys, time, random
import urllib.request

COMFY = 'http://127.0.0.1:8188'
CKPT = 'waiIllustriousSDXL_v160.safetensors'

BASE_POSITIVE = (
    "1girl, solo, masterpiece, best quality, high detail, "
    "cinematic lighting, dramatic rim light, warm golden key light, cool ambient fill, "
    "detailed fabric folds, glossy hair strands, sharp iris highlights, film grain, "
    "detailed eyes, refined face, clean lineart"
)
NEGATIVE = (
    "worst quality, low quality, blurry, bad anatomy, bad hands, missing fingers, "
    "extra fingers, deformed feet, malformed limbs, extra limbs, ugly, "
    "flat lighting, plastic skin, oversaturated, washed out, amateur, "
    "gloves, maid outfit, nude, sexy, nsfw, exposed, "
    "golden key, gold key, clock, gears, pocket watch, key necklace, key pendant, "
    "key, pendant, brass key, ornate key, antique key"
)

# 角色定义（用户设定为准，图片仅参考风格）
CHARS = {
    "wangyue": {
        "cn": "望月(女主)",
        "prompt": (
            "1girl, long black hair, half-up princess hairstyle, "
            "front sections pinned and gathered into a small twist, "
            "back hair long and flowing loose, center parted bangs, "
            "beauty mark under right eye, mole under right eye, "
            "sharp piercing cold eyes, narrow sharp gaze, cold aloof expression, "
            "serious stern face, subtle sharp smirk, elegant cool aura, "
            "black and dark school uniform style clothes, "
            "upper body portrait"
        ),
        "use": "portrait",
    },
    "ranqingqing": {
        "cn": "冉青青(女配)",
        "prompt": (
            "1girl, dark brown short hair to shoulders, "
            "side braid with white ribbon, single side braid, "
            "blunt bangs, big round blue-violet eyes, large expressive blue-violet eyes, "
            "youthful cute round face, energetic cheerful bright expression, "
            "white school shirt with ribbon bow, white blouse with bow tie, plain white shirt, "
            "lively sunny energetic aura, "
            "upper body portrait"
        ),
        "use": "library",
    },
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

def build_workflow(prompt, negative, seed, detail_amount=0.18, cfg=6.5, steps=30):
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

    noise = add({'class_type': 'RandomNoise', 'inputs': {'noise_seed': seed}})
    guider = add({'class_type': 'CFGGuider', 'inputs': {'model': model, 'positive': [pos, 0], 'negative': [neg, 0], 'cfg': cfg}})
    ksampler_sel = add({'class_type': 'KSamplerSelect', 'inputs': {'sampler_name': 'dpmpp_2m'}})
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
    save = add({'class_type': 'SaveImage', 'inputs': {'images': [dec, 0], 'filename_prefix': 'koren_char'}})
    return wf

def main():
    args = sys.argv[1:]
    name = args[0] if args and args[0] in CHARS else 'wangyue'
    seed = int(args[1]) if len(args) > 1 else random.randint(1, 2**31)
    detail = 0.18
    if '--detail' in args:
        detail = float(args[args.index('--detail') + 1])
    ch = CHARS[name]
    prompt = f"{ch['prompt']}, {BASE_POSITIVE}"
    print(f"▶ 生成 {ch['cn']} seed={seed} detail={detail}")
    wf = build_workflow(prompt, NEGATIVE, seed, detail)
    files, pid = submit(wf, timeout=900)
    print(f"  ✅ {files}")

if __name__ == '__main__':
    main()
