#!/usr/bin/env python3
"""Koren 小说 · 其他角色形象初稿

陈霸南 / 晨煊 / 田地 —— 从小说原文提取外貌，纯 prompt 生成（无参考图）。
CN 化：黑/棕发、深瞳。

用法: python scripts/koren_sidechars.py [--seed N]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "agents"))

import requests  # noqa: E402
from comfy_utils import comfy_base_url, wait_images, resolve_comfy_root  # noqa: E402

CKPT = "waiIllustriousSDXL_v160.safetensors"
NEGATIVE = ("worst quality, low quality, blurry, jpeg artifacts, lowres, bad anatomy, "
            "bad hands, deformed, bad proportions, extra limbs, extra fingers, "
            "fused fingers, poorly drawn face, text, watermark, signature, "
            "chromatic aberration")

# 光正校服男式（衬衫+长裤）
SCHOOL_BOY = "white dress shirt, dark trousers, plain school uniform"

ROLES = {
    "CB_chenbanan": {
        "title": "陈霸南（男主好友）",
        "prompt": ("1boy, tall slim high school student, 185cm, lean athletic build "
                   "not bodybuilder, average teenager physique, "
                   "short black hair, roguish smirk, unbuttoned shirt collar, "
                   "loose tie, dark brown eyes, wild carefree attitude, "
                   f"{SCHOOL_BOY}, "
                   "school corridor background, upper body, clean cel shading"),
    },
    "CX_chenxuan": {
        "title": "晨煊（姐姐）",
        "prompt": ("1girl, petite tiny figure, 150cm, college freshman, "
                   "short dark brown hair with a blue hair clip, "
                   "bright cheerful smile, playful mischievous expression, "
                   "dark brown eyes, casual college outfit: simple t-shirt and "
                   "jeans or casual dress, "
                   "bright campus background, upper body, clean cel shading"),
    },
    "TD_tiandi": {
        "title": "田地（班主任/物理老师）",
        "prompt": ("1man, middle-aged teacher, 45 years old, bald head, "
                   "wearing glasses, slight stubble, tired experienced expression, "
                   "white shirt, dark tie, hands resting naturally, "
                   "classroom background with blackboard, upper body, clean cel shading"),
    },
}


def run(prompt: str, seed: int, prefix: str) -> None:
    wf = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": NEGATIVE, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 896, "height": 1152, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0],
            "latent_image": ["4", 0], "seed": seed, "steps": 22, "cfg": 6.5,
            "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": prefix}},
    }
    base = comfy_base_url()
    root = resolve_comfy_root()
    r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=30)
    if r.status_code != 200:
        print(f"  ❌ 提交失败: {r.text[:200]}")
        return
    t0 = time.time()
    imgs = wait_images(r.json()["prompt_id"], base, timeout_s=400.0)
    if not imgs:
        print("  ❌ 无输出")
        return
    sub, fn = imgs[0]
    src = root / "output" / (sub or "") / fn
    if src.is_file():
        dst = ROOT / "outputs" / "koren" / "chars" / f"{prefix}.png"
        dst.write_bytes(src.read_bytes())
        print(f"  ✅ {time.time()-t0:.0f}s -> {dst}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="CB,CX,TD")
    ap.add_argument("--seed", type=int, default=20260901)
    args = ap.parse_args()
    names = [x.strip() for x in args.only.split(",")]
    matched = []
    for key in ROLES:
        if any(key.startswith(p) for p in names):
            matched.append(key)
    for i, key in enumerate(matched):
        role = ROLES[key]
        print(f"═══ {role['title']} ═══")
        run(role["prompt"], args.seed + i * 17, key)


if __name__ == "__main__":
    main()
