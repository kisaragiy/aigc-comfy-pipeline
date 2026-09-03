#!/usr/bin/env python3
"""工位 S6 · 中度结构重画（lineart + softedge ControlNet）

统一接口：pipeline/stages/s6_lineart.py --input <img> [--prompt ...] [--seed N]
          [--strength 0.85] [--outdir ...]

用途：中度结构崩坏（局部结构模糊、细节丢失）。denoise=1.0 完全重画，
      靠 AnimeLineArt 提取线稿 + softedge ControlNet 保留构图，细节重画。
实测（⑧ 第二轮）：修得了"手融化后重新画出"，保留构图/配色/服装款式。

依赖：scripts/probe_repair2.py 的 build_wf + ROUTES（已实测）
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "agents"))
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "scripts"))

import requests  # noqa: E402
from comfy_utils import comfy_base_url, wait_images, resolve_comfy_root  # noqa: E402
from probe_repair2 import build_wf, upload, ROUTES  # noqa: E402
from common import new_job, write_manifest  # noqa: E402

CKPT = "waiIllustriousSDXL_v160.safetensors"
PROMPT_DEFAULT = ("masterpiece, best quality, highly detailed, official game cg, "
                  "promotional illustration, crisp clean lineart, flat vivid colors, "
                  "glossy polished finish, 1girl, long black hair, detailed face, "
                  "detailed hands")
NEG_DEFAULT = ("worst quality, low quality, blurry, jpeg artifacts, lowres, bad anatomy, "
               "bad hands, deformed, bad proportions, extra limbs, extra fingers, "
               "fused fingers, missing fingers, poorly drawn face, "
               "chromatic aberration, color fringing, glitch, torn, artifacts, noise, "
               "signature, watermark, text")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--prompt", default=PROMPT_DEFAULT)
    ap.add_argument("--negative", default=NEG_DEFAULT)
    ap.add_argument("--seed", type=int, default=20260901)
    ap.add_argument("--strength", type=float, default=0.85)
    ap.add_argument("--outdir", default=str(ROOT / "outputs"))
    args = ap.parse_args()

    from PIL import Image
    img = Path(args.input)
    if not img.is_file():
        print(f"❌ S6 输入不存在: {img}")
        return 1
    job = new_job("S6")
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    base = comfy_base_url()
    root = resolve_comfy_root()
    up = upload(base, img)
    w, h = Image.open(img).size
    # ROUTES["E_lineart"] = ("AnimeLineArtPreprocessor", {}, CN_SOFTEDGE, 0.85)
    pre_node, pre_args, cn, _ = ROUTES["E_lineart"]
    wf = build_wf(up, pre_node, pre_args, cn, args.strength, w, h, f"S6_{job}")
    r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=30)
    if r.status_code != 200:
        print(f"❌ S6 提交失败: {r.text[:300]}")
        return 1
    t0 = time.time()
    imgs = wait_images(r.json()["prompt_id"], base, timeout_s=400.0)
    if not imgs:
        print("❌ S6 无输出图")
        return 1
    # probe_repair2 的 build_wf 同时输出 _PRE 图和成品；取成品（不含 _PRE）
    for sub, fn in imgs:
        if "_PRE_" in fn:
            continue
        src = root / "output" / (sub or "") / fn
        if src.is_file():
            dst = outdir / f"{job}.png"
            dst.write_bytes(src.read_bytes())
            write_manifest(
                job, "S6", str(dst), args.prompt,
                {"route": "lineart", "strength": args.strength,
                 "seed": args.seed, "ckpt": CKPT,
                 "input": str(img), "negative": args.negative},
                gate=None, history=["S6"], status="ok")
            print(f"✅ S6 完成 {time.time()-t0:.0f}s -> {dst}")
            print(f"   JOB_ID={job}")
            return 0
    print("❌ S6 输出缺失")
    return 1


if __name__ == "__main__":
    sys.exit(main())
