#!/usr/bin/env python3
"""实际验证 gate_commercial：SDXL 生成 + 出图后自动判据拦截。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from comfy_utils import generate_with_quality

PROMPT = ("masterpiece, best quality, commercial illustration, 1girl, "
          "silver-violet long straight hair, blue eyes, "
          "white vintage dress, blue bow tie, standing, white background, "
          "soft lighting, detailed hair, cel shading, clean lineart")

NEG = ("worst quality, low quality, blurry, jpeg artifacts, bad anatomy, "
       "bad hands, extra fingers, deformed, ugly, watermark, text")

from go_knives_lora import build_sdxl_clean_workflow
import random

def build_fn(prompt, seed=-1, **kwargs):
    """wrapper: generate_with_quality 期望 (wf, seed) 元组。"""
    wf = build_sdxl_clean_workflow(prompt, seed=seed, **kwargs)
    actual_seed = seed if seed != -1 else random.randint(1, 2**48 - 1)
    return wf, actual_seed

def main():
    print("=== 实际验证 gate_commercial (SDXL 生成 + 判据拦截) ===")
    result = generate_with_quality(
        build_fn,
        PROMPT,
        negative_prompt=NEG,
        seed=20260824,
        filename_prefix="pipeline_gate_test",
        steps=22, cfg=6.5,
        width=896, height=1152,
        min_score=0.0,
        max_retries=2,
        gate_commercial=True,
        no_validate=False,
        ckpt="waiIllustriousSDXL_v160.safetensors",
    )
    print("\n=== 生成结果 ===")
    print(f"  seed: {result.get('seed')}")
    print(f"  images: {result.get('images')}")
    print(f"  retries: {result.get('retries')}")
    if result.get("images"):
        img = result["images"][0]
        from quality_judge import judge
        print(f"\n=== 判据复核 {os.path.basename(img)} ===")
        res = judge(img)
        print(f"  verdict: {res['verdict']}")
        print(f"  metrics: {res.get('metrics')}")

if __name__ == "__main__":
    main()
