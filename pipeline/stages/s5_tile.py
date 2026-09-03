#!/usr/bin/env python3
"""工位 S5 · 表层缺陷修复（tile ControlNet）

统一接口：pipeline/stages/s5_tile.py --input <img> [--denoise 0.6] [--tile-strength 0.5]
          [--prompt ...] [--seed N] [--outdir ...]

输出：<outdir>/<job_id>.png + manifest（history 追加 S5）

依赖：scripts/probe_repair.py 的 build_wf（实测：tile 修噪点/色差/红边）
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
from probe_repair import build_wf, upload, PROMPT, NEG  # noqa: E402
from common import new_job, write_manifest  # noqa: E402

CKPT = "waiIllustriousSDXL_v160.safetensors"
TILE_CN = "controlnet-tile-sdxl-1.0.safetensors"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--denoise", type=float, default=0.6)
    ap.add_argument("--tile-strength", type=float, default=0.5)
    ap.add_argument("--prompt", default=PROMPT)
    ap.add_argument("--negative", default=NEG)
    ap.add_argument("--seed", type=int, default=20260901)
    ap.add_argument("--outdir", default=str(ROOT / "outputs"))
    args = ap.parse_args()

    from PIL import Image
    img = Path(args.input)
    if not img.is_file():
        print(f"❌ S5 输入不存在: {img}")
        return 1
    job = new_job("S5")
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    base = comfy_base_url()
    root = resolve_comfy_root()
    up = upload(base, img)
    w, h = Image.open(img).size
    wf = build_wf(up, args.denoise, args.tile_strength, w, h, f"S5_{job}")
    r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=30)
    if r.status_code != 200:
        print(f"❌ S5 提交失败: {r.text[:300]}")
        return 1
    t0 = time.time()
    imgs = wait_images(r.json()["prompt_id"], base, timeout_s=400.0)
    if not imgs:
        print("❌ S5 无输出图")
        return 1
    sub, fn = imgs[0]
    src = root / "output" / (sub or "") / fn
    if not src.is_file():
        print(f"❌ S5 输出缺失: {src}")
        return 1
    dst = outdir / f"{job}.png"
    dst.write_bytes(src.read_bytes())
    write_manifest(
        job, "S5", str(dst), args.prompt,
        {"denoise": args.denoise, "tile_strength": args.tile_strength,
         "seed": args.seed, "ckpt": CKPT, "controlnet": TILE_CN,
         "input": str(img), "negative": args.negative},
        gate=None, history=["S5"], status="ok")
    print(f"✅ S5 完成 {time.time()-t0:.0f}s -> {dst}")
    print(f"   JOB_ID={job}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
