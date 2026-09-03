#!/usr/bin/env python3
"""Qwen-Image 2512 实测 v2（ComfyUI 内置标准工作流）

UnetLoaderGGUF → CLIPLoader(qwen_image) → CLIPTextEncode → KSampler → VAEDecode

用法:
  python scripts/probe_qwenimage.py --dry-run
  python scripts/probe_qwenimage.py [--model ...] [--text "..."] [--seed N]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "agents"))

import requests  # noqa: E402
from comfy_utils import comfy_base_url, wait_images  # noqa: E402

PROMPT = ("A beautiful Chinese high school girl student council president, "
          "long straight black hair with bangs, a bright RED hair ribbon, "
          "white shirt blouse with a RED bow tie, gray plaid pleated skirt, "
          "white short socks and black canvas shoes, cold calm dignified expression, "
          "standing in a sunny classroom, anime style, high quality")
NEGATIVE = "low quality, blurry, deformed, bad anatomy"


def build_wf(model: str, prompt: str, negative: str, seed: int,
             width: int = 896, height: int = 1152) -> dict:
    return {
        "1": {"class_type": "UnetLoaderGGUF",
              "inputs": {"unet_name": model, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": "qwen-image\\qwen_2.5_vl_7b_fp8_scaled.safetensors",
                         "type": "qwen_image", "device": "default"}},
        "3": {"class_type": "CLIPTextEncode",
              "inputs": {"text": prompt, "clip": ["2", 0]}},
        "4": {"class_type": "CLIPTextEncode",
              "inputs": {"text": negative, "clip": ["2", 0]}},
        "5": {"class_type": "EmptyLatentImage",
              "inputs": {"width": width, "height": height, "batch_size": 1}},
        "6": {"class_type": "KSampler",
              "inputs": {"model": ["1", 0], "positive": ["3", 0], "negative": ["4", 0],
                         "latent_image": ["5", 0], "seed": seed, "steps": 28, "cfg": 4.0,
                         "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["8", 0]}},
        "8": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        "9": {"class_type": "SaveImage",
              "inputs": {"images": ["7", 0], "filename_prefix": "qwen_test"}},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--text", default=PROMPT)
    ap.add_argument("--model", default="qwen-image\\qwen-image-2512-Q3_K_M.gguf")
    ap.add_argument("--seed", type=int, default=20260901)
    args = ap.parse_args()

    if args.dry_run:
        wf = build_wf(args.model, args.text, NEGATIVE, args.seed)
        print(json.dumps({k: v["class_type"] for k, v in wf.items()}, indent=1))
        return

    base = comfy_base_url()
    wf = build_wf(args.model, args.text, NEGATIVE, args.seed)
    r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=30)
    if r.status_code != 200:
        print(f"❌ 提交失败: {r.text[:600]}")
        return
    pid = r.json()["prompt_id"]
    print(f"提交成功 {pid}，等待出图（Qwen 首次加载慢）...")
    t0 = time.time()
    imgs = wait_images(pid, base, timeout_s=900.0)
    print(f"耗时 {time.time()-t0:.0f}s")
    print("imgs:", imgs[:3])


if __name__ == "__main__":
    main()
