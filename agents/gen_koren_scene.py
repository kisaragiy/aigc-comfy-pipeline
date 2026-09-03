#!/usr/bin/env python3
"""
gen_koren_scene.py — 小说《北山实验中学》角色全身立绘（校园日常风）

画风: 青春猪头少年式校园日常(思春期症候群奇幻, 无魔法, 架空CN高中) — 明亮自然光, 不套哥特幻想
修正: 去掉celeste污染(银发/琥珀眼/黑哥特裙/星空/钟表/金钥匙), 用校园少年形象
设定: 全员cn人, 高一~高三, 白衬衫校服, 全身图, 操场/教室/走廊校园场景

用法: python gen_koren_scene.py <name> <seed> [--detail 0.15]
      name = ranqingqing | wangyue
"""
from __future__ import annotations
import json, os, sys, time, random
import urllib.request

COMFY = 'http://127.0.0.1:8188'
CKPT = 'waiIllustriousSDXL_v160.safetensors'

# 校园日常画风基底 —— 暖色自然光, 青春日常, 不用暗黑电影感
SCHOOL_BASE = (
    "1girl, solo, school uniform, "
    "warm natural light, soft golden sunlight, gentle ambient light, "
    "clean crisp anime style, detailed school uniform fabric, "
    "masterpiece, best quality, high detail, fresh youthful color palette"
)
NEGATIVE = (
    "worst quality, low quality, blurry, bad anatomy, bad hands, missing fingers, "
    "extra fingers, deformed feet, malformed limbs, extra limbs, ugly, "
    "flat lighting, plastic skin, oversaturated, washed out, amateur, "
    "dark gothic, gothic dress, black lace, maid outfit, silver hair, amber eyes, "
    "golden key, gold key, clock, gears, pocket watch, key pendant, "
    "nude, sexy, nsfw, exposed, fantasy castle, magic, wings, "
    "long hair, very long hair, floor length hair, waist length hair, "
    "japanese sailor uniform, sailor collar, sailor school uniform, korean school uniform, "
    "necktie, long tie, loose tie, striped tie"
)

CHARS = {
    "ranqingqing": {
        "cn": "冉青青(班长)",
        "prompt": (
            "1girl, short dark brown hair to shoulders, wispy soft ends, "
            "shoulder-length bob haircut, chin-length hair, "
            "side braid by her left ear, braid tucked with white ribbon bow, "
            "blunt bangs, big round blue-violet eyes, "
            "youthful soft round face, gentle shy smile, wistful warm expression, "
            "slightly blushing cheeks, tender kind aura, "
            "Chinese school uniform, white dress shirt, "
            "red striped necktie tied into a bow at collar, "
            "red plaid pleated skirt, three-quarter body visible, "
            "embroidered school crest emblem on chest, "
            "three-quarter body portrait, standing, full outfit visible, "
            "evening campus, warm sunset light through a window, school hallway, "
            "soft golden backlight, cozy melancholic mood"
        ),
        "use": "library",
    },
    "wangyue": {
        "cn": "望月(女主/学生会长)",
        "prompt": (
            "1girl, long black hair, half-up princess hairstyle, "
            "front sections gathered into a twist, back hair long and flowing, "
            "beauty mark under right eye, mole under right eye, "
            "dark brown eyes, deep brown eyes, black pupils, "
            "calm composed cold expression, serious solemn face, "
            "emotionless aloof gaze, dignified aloof aura, "
            "student council president, imposing presence, "
            "Chinese school uniform, white dress shirt, "
            "large red ribbon bow tied at collar, big red bow knot, "
            "red plaid pleated skirt, embroidered school crest emblem on chest, "
            "half body portrait, seated at a desk, "
            "student council office, morning sunlight through window, dusty light rays, "
            "looking up toward the doorway, authoritative composed posture, "
            "orderly papers on desk, dignified, refined"
        ),
        "use": "portrait",
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

def build_workflow(prompt, negative, seed, detail_amount=0.15, cfg=6.0, steps=30):
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
    # 全身立绘: 高长竖版
    empty = add({'class_type': 'EmptyLatentImage', 'inputs': {'width': 832, 'height': 1216, 'batch_size': 1}})
    sample = add({'class_type': 'SamplerCustomAdvanced', 'inputs': {
        'noise': [noise, 0], 'guider': [guider, 0], 'sampler': [dd, 0],
        'sigmas': [scheduler, 0], 'latent_image': [empty, 0]}})
    dec = add({'class_type': 'VAEDecode', 'inputs': {'samples': [sample, 0], 'vae': vae}})
    save = add({'class_type': 'SaveImage', 'inputs': {'images': [dec, 0], 'filename_prefix': 'koren_scene'}})
    return wf

def main():
    args = sys.argv[1:]
    name = args[0] if args and args[0] in CHARS else 'ranqingqing'
    seed = int(args[1]) if len(args) > 1 else random.randint(1, 2**31)
    detail = 0.15
    if '--detail' in args:
        detail = float(args[args.index('--detail') + 1])
    ch = CHARS[name]
    prompt = f"{ch['prompt']}, {SCHOOL_BASE}"
    print(f"▶ 校园全身 [{ch['cn']}] seed={seed} detail={detail}")
    wf = build_workflow(prompt, NEGATIVE, seed, detail)
    files, pid = submit(wf, timeout=900)
    print(f"  ✅ {files}")

if __name__ == '__main__':
    main()
