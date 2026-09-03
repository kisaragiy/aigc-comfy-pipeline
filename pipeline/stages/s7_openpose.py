#!/usr/bin/env python3
"""工位 S7 · 重度重画（openpose 骨架级）

统一接口：pipeline/stages/s7_openpose.py --input <img> [--prompt ...] [--seed N]
          [--strength 0.85] [--outdir ...]

用途：重度崩坏（肢体崩坏/全局撕裂）且不保留原图细节。denoise=1.0 完全重画，
      靠 OpenPose 骨架（含手部关键点推断）重建结构。
⚠️ 局限（⑧ 实测）：≈ 重画，只剩姿态，原图信息丢最多。仅用于"重度且不保原图"。

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
                  "glossy polished finish, 1girl, detailed face, detailed hands")
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
        print(f"❌ S7 输入不存在: {img}")
        return 1
    job = new_job("S7")
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    base = comfy_base_url()
    root = resolve_comfy_root()
    up = upload(base, img)
    w, h = Image.open(img).size
    # ROUTES["H_pose"] = ("OpenposePreprocessor", {detect_hand...}, CN_POSE, 0.85)
    pre_node, pre_args, cn, _ = ROUTES["H_pose"]
    wf = build_wf(up, pre_node, pre_args, cn, args.strength, w, h, f"S7_{job}")
    r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=30)
    if r.status_code != 200:
        print(f"❌ S7 提交失败: {r.text[:300]}")
        return 1
    t0 = time.time()
    imgs = wait_images(r.json()["prompt_id"], base, timeout_s=400.0)
    if not imgs:
        print("❌ S7 无输出图")
        return 1
    for sub, fn in imgs:
        if "_PRE_" in fn:
            continue
        src = root / "output" / (sub or "") / fn
        if src.is_file():
            dst = outdir / f"{job}.png"
            dst.write_bytes(src.read_bytes())
            write_manifest(
                job, "S7", str(dst), args.prompt,
                {"route": "openpose", "strength": args.strength,
                 "seed": args.seed, "ckpt": CKPT,
                 "input": str(img), "negative": args.negative},
                gate=None, history=["S7"], status="ok")
            print(f"✅ S7 完成 {time.time()-t0:.0f}s -> {dst}")
            print(f"   JOB_ID={job}")
            return 0
    print("❌ S7 输出缺失")
    return 1


if __name__ == "__main__":
    sys.exit(main())
