#!/usr/bin/env python3
"""①.2 Stage B — RegionalPrompt + RegionalSampler 最小demo（L1: 左/右半区mask）

【目的】验证接线通不通，不追求效果。通了 → 换拥抱图/精细mask；不通 → 查节点用法。

【核心思路】按"人"分区域而非按"位置"分：
  每个角色一个 RegionalPrompt(mask + 专属conditioning) + RegionalSampler 串Base。
  这样互动场景里"黑长发红裙"和"金短发蓝裙"各管各的区域，串色就断了。

【节点结构】
  CheckpointLoaderSimple → model/clip
  ├─ base: CLIPTextEncode(场景prompt) → KSAMPLER_ADVANCED → base_sampler
  ├─ 角色A: CLIPTextEncode(左prompt) → KSAMPLER_ADVANCED → RegionalPrompt(mask=左)
  ├─ 角色B: CLIPTextEncode(右prompt) → KSAMPLER_ADVANCED → RegionalPrompt(mask=右)
  EmptyLatentImage → samples
  RegionalSampler(samples, base_sampler, regional_prompts) → latent
  VAEDecode → SaveImage

【mask】L1 = 用PIL生成左/右半区黑白图（按画面的位置分）。后续可换OpenPose/分割。

用法:
  python scripts/probe_regional.py --dry-run
  python scripts/probe_regional.py --mode sidebyside|hug
  python scripts/probe_regional.py --mode hug --mask-mode bbox
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "agents"))

import requests  # noqa: E402
from comfy_utils import comfy_base_url, wait_images, resolve_comfy_root  # noqa: E402

CKPT = "waiIllustriousSDXL_v160.safetensors"
RUN_ID = time.strftime("%m%d%H%M%S")
OUT = ROOT / "workspace" / "regional"
STEPS, CFG = 16, 6.5
SEED = 20260901

STYLE = ("masterpiece, best quality, highly detailed, official game cg, "
         "anime cel shading, crisp clean lineart, flat vivid colors")
NEG = ("worst quality, low quality, blurry, jpeg artifacts, lowres, bad anatomy, "
       "bad hands, deformed, bad proportions, extra limbs, extra fingers, "
       "fused fingers, missing fingers, poorly drawn face, signature, watermark, text")

CHAR_L = "1girl, long black hair, red dress"      # 左区 prompt
CHAR_R = "1girl, short blonde hair, blue dress"   # 右区 prompt


def upload_image(base: str, path: Path) -> str:
    with open(path, "rb") as f:
        r = requests.post(f"{base}/upload/image",
                          files={"image": (path.name, f, "image/png")},
                          data={"overwrite": "true"}, timeout=60)
    r.raise_for_status()
    return r.json()["name"]


def make_split_mask(w: int, h: int, mode: str, vert_ratio: float = 0.5) -> tuple:
    """L1: 生成左/右半区 mask（黑白图），返回 (左图路径, 右图路径)。

    mode=sidebyside: 垂直中线切，左半=左角色，右半=右角色
    mode=hug: 用更粗糙的斜切（后续换OpenPose/分割）
    """
    OUT.mkdir(parents=True, exist_ok=True)
    left = np.zeros((h, w), dtype=np.uint8)
    right = np.zeros((h, w), dtype=np.uint8)
    if mode == "sidebyside":
        left[:, : int(w * vert_ratio)] = 255
        right[:, int(w * vert_ratio):] = 255
    elif mode == "hug":
        # 拥抱：垂直中线 + 斜切让交界平滑，允许中部重叠
        left[:, : int(w * 0.55)] = 255
        right[:, int(w * 0.45):] = 255
    lp = OUT / "mask_left.png"
    rp = OUT / "mask_right.png"
    Image.fromarray(left).save(lp)
    Image.fromarray(right).save(rp)
    return lp, rp


def build_regional_wf(base_sampler: dict, regional_prompts: list, seed: int,
                      w: int, h: int) -> dict:
    """构造 RegionalSampler 工作流。"""
    wf = {}
    nid = iter(range(1, 100))
    # 基础
    wf[str(next(nid))] = base_sampler  # base sampler 由调用方提供
    # ... 简化：直接构造完整图
    return wf


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--mode", default="sidebyside", choices=["sidebyside", "hug"])
    args = ap.parse_args()

    w, h = 1024, 1024
    OUT.mkdir(parents=True, exist_ok=True)
    left_m, right_m = make_split_mask(w, h, args.mode)
    if args.dry_run:
        print(f"[dry-run] mode={args.mode} {w}x{h} -> masks {left_m.name}/{right_m.name}")
        print("  结构: base场景prompt + 2×RegionalPrompt(左右mask) + RegionalSampler")
        return

    base = comfy_base_url()
    root = resolve_comfy_root()

    # 上传两个 mask
    up_left = upload_image(base, left_m)
    up_right = upload_image(base, right_m)
    print(f"[upload] left={up_left}  right={up_right}")

    # 引入 RegionalSampler 节点（直接构造工作流）
    scene = f"{STYLE}, 2girls hugging each other tightly, sunset background, upper body" \
        if args.mode == "hug" else f"{STYLE}, 2girls standing side by side, park background"
    
    # 构造节点图（ImpactPack Regional：每区域 = ToBasicPipe + Provider + RegionalPrompt(mask)）
    wf = {}
    wf["1"] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}}

    # ── BASE 区域（全局场景/负向，兜底采样器）──
    wf["2"] = {"class_type": "CLIPTextEncode", "inputs": {"text": scene, "clip": ["1", 1]}}
    wf["3"] = {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["1", 1]}}
    wf["4"] = {"class_type": "ToBasicPipe", "inputs": {"model": ["1", 0], "clip": ["1", 1],
                                                      "vae": ["1", 2], "positive": ["2", 0],
                                                      "negative": ["3", 0]}}
    wf["5"] = {"class_type": "KSamplerAdvancedProvider",
               "inputs": {"cfg": CFG, "sampler_name": "dpmpp_2m", "scheduler": "karras",
                          "sigma_factor": 1.0, "basic_pipe": ["4", 0]}}

    # ── 区域 A（左：黑长发红裙）──
    wf["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": f"{STYLE}, {CHAR_L}", "clip": ["1", 1]}}
    wf["7"] = {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["1", 1]}}
    wf["8"] = {"class_type": "ToBasicPipe", "inputs": {"model": ["1", 0], "clip": ["1", 1],
                                                      "vae": ["1", 2], "positive": ["6", 0],
                                                      "negative": ["7", 0]}}
    wf["9"] = {"class_type": "KSamplerAdvancedProvider",
               "inputs": {"cfg": CFG, "sampler_name": "dpmpp_2m", "scheduler": "karras",
                          "sigma_factor": 1.0, "basic_pipe": ["8", 0]}}

    # ── 区域 B（右：金短发蓝裙）──
    wf["10"] = {"class_type": "CLIPTextEncode", "inputs": {"text": f"{STYLE}, {CHAR_R}", "clip": ["1", 1]}}
    wf["11"] = {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["1", 1]}}
    wf["12"] = {"class_type": "ToBasicPipe", "inputs": {"model": ["1", 0], "clip": ["1", 1],
                                                       "vae": ["1", 2], "positive": ["10", 0],
                                                       "negative": ["11", 0]}}
    wf["13"] = {"class_type": "KSamplerAdvancedProvider",
                "inputs": {"cfg": CFG, "sampler_name": "dpmpp_2m", "scheduler": "karras",
                           "sigma_factor": 1.0, "basic_pipe": ["12", 0]}}

    # ── mask ──
    wf["14"] = {"class_type": "LoadImageMask", "inputs": {"image": up_left, "channel": "red"}}
    wf["15"] = {"class_type": "LoadImageMask", "inputs": {"image": up_right, "channel": "red"}}

    # ── RegionalPrompt(mask, sampler) ──
    wf["16"] = {"class_type": "RegionalPrompt", "inputs": {"mask": ["14", 0], "advanced_sampler": ["9", 0]}}
    wf["17"] = {"class_type": "RegionalPrompt", "inputs": {"mask": ["15", 0], "advanced_sampler": ["13", 0]}}

    # ── Combine ──
    wf["18"] = {"class_type": "CombineRegionalPrompts",
                "inputs": {"regional_prompts1": ["16", 0], "regional_prompts2": ["17", 0]}}

    # ── RegionalSampler ──
    wf["19"] = {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}}
    wf["20"] = {"class_type": "RegionalSampler",
                "inputs": {"seed": SEED, "seed_2nd": SEED, "seed_2nd_mode": "ignore",
                           "steps": STEPS, "base_only_steps": 2, "denoise": 1.0,
                           "samples": ["19", 0], "base_sampler": ["5", 0],
                           "regional_prompts": ["18", 0], "overlap_factor": 10,
                           "restore_latent": True, "additional_mode": "DISABLE",
                           "additional_sampler": "AUTO", "additional_sigma_ratio": 0.3}}

    wf["21"] = {"class_type": "VAEDecode", "inputs": {"samples": ["20", 0], "vae": ["1", 2]}}
    wf["22"] = {"class_type": "SaveImage",
                "inputs": {"images": ["21", 0], "filename_prefix": f"regional_{args.mode}_{RUN_ID}"}}

    r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=60)
    if r.status_code != 200:
        print(f"❌ SUBMIT FAIL: {r.text[:600]}")
        return
    t0 = time.time()
    imgs = wait_images(r.json()["prompt_id"], base, timeout_s=600.0)
    if not imgs:
        print("❌ NO IMAGE")
        return
    for sub, fn in imgs:
        s = root / "output" / (sub or "") / fn
        if s.is_file():
            dst = OUT / f"{args.mode}_out_{SEED}.png"
            dst.write_bytes(s.read_bytes())
            print(f"✅ mode={args.mode} {time.time()-t0:.0f}s -> {dst.name}")


if __name__ == "__main__":
    main()
