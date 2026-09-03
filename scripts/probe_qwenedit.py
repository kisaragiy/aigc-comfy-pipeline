#!/usr/bin/env python3
"""Qwen-Image-Edit 2511 实测（局部编辑能力）

验证：能否一句话改图（发带改红），替代 image2 冷却期的局部编辑。
参考图：望月定稿（双人图右半，红色丝带已有，测"把蓝发夹改红"或"整体微调"）

用法:
  python scripts/probe_qwenedit.py --dry-run
  python scripts/probe_qwenedit.py [--image wangyue_final_ref.png] [--text "..."] [--seed N]
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

DEFAULT_TEXT = ("Keep this character exactly the same, but change the blue hair "
                "accessory to red. Everything else unchanged.")


def build_wf(image: str, text: str, seed: int,
             width: int = 896, height: int = 1152) -> dict:
    return {
        "1": {"class_type": "UnetLoaderGGUF",
              "inputs": {"unet_name": "qwen-image\\qwen-image-edit-2511-Q3_K_M.gguf",
                         "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": "qwen-image\\qwen_2.5_vl_7b_fp8_scaled.safetensors",
                         "type": "qwen_image", "device": "default"}},
        "3": {"class_type": "LoadImage", "inputs": {"image": image}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        "5": {"class_type": "TextEncodeQwenImageEdit",
              "inputs": {"clip": ["2", 0], "prompt": text,
                         "vae": ["4", 0], "image": ["3", 0]}},
        "6": {"class_type": "EmptyLatentImage",
              "inputs": {"width": width, "height": height, "batch_size": 1}},
        "7": {"class_type": "KSampler",
              "inputs": {"model": ["1", 0], "positive": ["5", 0],
                         "negative": ["5", 0],  # Edit 模型常共用正负
                         "latent_image": ["6", 0], "seed": seed, "steps": 28, "cfg": 4.0,
                         "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["4", 0]}},
        "9": {"class_type": "SaveImage",
              "inputs": {"images": ["8", 0], "filename_prefix": "qwen_edit_test"}},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--image", default="wangyue_final_ref.png")
    ap.add_argument("--text", default=DEFAULT_TEXT)
    ap.add_argument("--seed", type=int, default=20260901)
    args = ap.parse_args()

    if args.dry_run:
        wf = build_wf(args.image, args.text, args.seed)
        print(json.dumps({k: v["class_type"] for k, v in wf.items()}, indent=1))
        return

    base = comfy_base_url()
    wf = build_wf(args.image, args.text, args.seed)
    r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=30)
    if r.status_code != 200:
        print(f"❌ 提交失败: {r.text[:600]}")
        return
    pid = r.json()["prompt_id"]
    print(f"提交成功 {pid}，等待出图（Edit 模型约 15-25 分钟）...")
    t0 = time.time()
    imgs = wait_images(pid, base, timeout_s=1800.0)
    print(f"耗时 {time.time()-t0:.0f}s")
    print("imgs:", imgs[:3])


if __name__ == "__main__":
    main()
