#!/usr/bin/env python3
"""工位 S1 · 基础出图（txt2img）

统一接口：pipeline/stages/s1_txt2img.py --prompt "..." [--negative ...] [--seed N]
          [--steps 16] [--cfg 6.5] [--size WxH] [--ckpt ...] [--style v3|v4] [--outdir ...]

输出：<outdir>/<job_id>.png + <outdir>/manifests/<job_id>.json

依赖：agents/go_knives_lora.py 的 build_sdxl_clean_workflow（实测可用）
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "agents"))
sys.path.insert(0, str(ROOT / "pipeline"))

import requests  # noqa: E402
from comfy_utils import comfy_base_url, wait_images, resolve_comfy_root  # noqa: E402
from go_knives_lora import build_sdxl_clean_workflow  # noqa: E402
from common import new_job, write_manifest  # noqa: E402

DEFAULT_CKPT = "waiIllustriousSDXL_v160.safetensors"

# 偏好档案 V3（场景插画：背景有内容）/ V4（角色立绘：反厚涂负向）
STYLE_V3 = ("masterpiece, best quality, highly detailed, official game cg, "
            "promotional illustration, anime cel shading, crisp clean lineart, "
            "flat vivid colors, glossy polished finish")
STYLE_V4 = ("masterpiece, best quality, highly detailed, official game cg, "
            "promotional illustration, crisp clean lineart, flat vivid colors, "
            "glossy polished finish, ultra detailed rendering")
NEG_BASE = ("worst quality, low quality, blurry, jpeg artifacts, lowres, bad anatomy, "
            "bad hands, deformed, bad proportions, extra limbs, extra fingers, "
            "fused fingers, missing fingers, poorly drawn face, "
            "signature, watermark, text")
NEG_THICK = ("thick oil painting, impasto, painterly brushstrokes, photorealistic, "
             "realistic skin texture, soft blurry shading, muddy colors, sketchy lineart")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--negative", default="")
    ap.add_argument("--seed", type=int, default=20260901)
    ap.add_argument("--steps", type=int, default=16)
    ap.add_argument("--cfg", type=float, default=6.5)
    ap.add_argument("--size", default="1024x1024")
    ap.add_argument("--ckpt", default=DEFAULT_CKPT)
    ap.add_argument("--style", choices=["v3", "v4"], default="v4",
                    help="偏好档案配方：v3=场景插画 v4=角色立绘(默认)")
    ap.add_argument("--outdir", default=str(ROOT / "outputs"))
    args = ap.parse_args()

    style = STYLE_V4 if args.style == "v4" else STYLE_V3
    if args.style == "v4":
        neg = f"{NEG_BASE}, {NEG_THICK}" + (f", {args.negative}" if args.negative else "")
    else:
        neg = NEG_BASE + (f", {args.negative}" if args.negative else "")
    prompt = f"{style}, {args.prompt}"

    w, h = (int(x) for x in args.size.lower().split("x"))
    job = new_job("S1")
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"[S1] {job}  seed={args.seed} steps={args.steps} cfg={args.cfg} {w}x{h}")
    print(f"[S1] prompt: {prompt[:120]}...")

    base = comfy_base_url()
    root = resolve_comfy_root()
    wf = build_sdxl_clean_workflow(
        prompt, negative_prompt=neg, ckpt=args.ckpt,
        width=w, height=h, steps=args.steps, cfg=args.cfg, seed=args.seed,
        sampler="dpmpp_2m", scheduler="karras",
        filename_prefix=f"S1_{job}")
    r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=30)
    if r.status_code != 200:
        print(f"❌ S1 提交失败: {r.text[:300]}")
        return 1
    t0 = time.time()
    imgs = wait_images(r.json()["prompt_id"], base, timeout_s=400.0)
    if not imgs:
        print("❌ S1 无输出图")
        return 1
    sub, fn = imgs[0]
    src = root / "output" / (sub or "") / fn
    if not src.is_file():
        print(f"❌ S1 输出缺失: {src}")
        return 1
    dst = outdir / f"{job}.png"
    dst.write_bytes(src.read_bytes())
    mpath = write_manifest(
        job, "S1", str(dst), prompt,
        {"seed": args.seed, "steps": args.steps, "cfg": args.cfg,
         "size": f"{w}x{h}", "ckpt": args.ckpt, "style": args.style,
         "negative": neg},
        gate=None, history=["S1"], status="ok")
    print(f"✅ S1 完成 {time.time()-t0:.0f}s -> {dst}")
    print(f"   manifest: {mpath}")
    print(f"   JOB_ID={job}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
