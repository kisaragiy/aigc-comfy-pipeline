#!/usr/bin/env python3
"""工位 S9 · 超分（RealESRGAN x4）

统一接口：pipeline/stages/s9_upscale.py --input <img> [--model 4x-UltraSharp.pth|RealESRGAN_x4plus.pth]
          [--target-width 0] [--outdir ...]

用途：交付前自动超分（商业图最短边需≥1500，原始生成 896/1024 常不够）。
流程：UpscaleModelLoader → ImageUpscaleWithModel(4x) → ImageScale(降回目标尺寸) → Save

依赖：ComfyUI 内置节点（UpscaleModelLoader/ImageUpscaleWithModel，已确认存在）
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

import requests  # noqa: E402
from comfy_utils import comfy_base_url, wait_images, resolve_comfy_root  # noqa: E402
from common import new_job, write_manifest  # noqa: E402

UPSCALE_DIR = Path(r"C:\DrawingLive\ComfyUI\models\upscale_models")
DEFAULT_MODEL = "4x-UltraSharp.pth"   # 63.9MB，人像/立绘常用
ALT_MODEL = "RealESRGAN_x4plus.pth"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--target-width", type=int, default=0,
                    help="目标长边像素（0=保持 4x 原始输出）")
    ap.add_argument("--outdir", default=str(ROOT / "outputs"))
    args = ap.parse_args()

    from PIL import Image
    img = Path(args.input)
    if not img.is_file():
        print(f"❌ S9 输入不存在: {img}")
        return 1
    job = new_job("S9")
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    base = comfy_base_url()
    root = resolve_comfy_root()
    w, h = Image.open(img).size

    # 上传原图
    with open(img, "rb") as f:
        up = requests.post(f"{base}/upload/image",
                           files={"image": (img.name, f, "image/png")},
                           data={"overwrite": "true"}, timeout=60).json()["name"]

    wf = {
        "1": {"class_type": "LoadImage", "inputs": {"image": up}},
        "2": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": args.model}},
        "3": {"class_type": "ImageUpscaleWithModel",
              "inputs": {"upscale_model": ["2", 0], "image": ["1", 0]}},
    }
    if args.target_width > 0:
        wf["4"] = {"class_type": "ImageScale",
                   "inputs": {"image": ["3", 0],
                              "upscale_method": "lanczos",
                              "width": args.target_width,
                              "height": int(h * args.target_width / w),
                              "crop": "disabled"}}
        save_in = ["4", 0]
    else:
        save_in = ["3", 0]
    wf["5"] = {"class_type": "SaveImage",
               "inputs": {"images": save_in, "filename_prefix": f"S9_{job}"}}

    r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=30)
    if r.status_code != 200:
        print(f"❌ S9 提交失败: {r.text[:300]}")
        return 1
    t0 = time.time()
    imgs = wait_images(r.json()["prompt_id"], base, timeout_s=600.0)
    if not imgs:
        print("❌ S9 无输出图")
        return 1
    sub, fn = imgs[0]
    src = root / "output" / (sub or "") / fn
    if not src.is_file():
        print(f"❌ S9 输出缺失: {src}")
        return 1
    dst = outdir / f"{job}.png"
    dst.write_bytes(src.read_bytes())
    from PIL import Image as I2
    ow, oh = I2.open(dst).size
    write_manifest(
        job, "S9", str(dst), None,
        {"model": args.model, "input_size": f"{w}x{h}", "output_size": f"{ow}x{oh}",
         "input": str(img)},
        gate=None, history=["S9"], status="ok")
    print(f"✅ S9 完成 {time.time()-t0:.0f}s  {w}x{h} -> {ow}x{oh} -> {dst}")
    print(f"   JOB_ID={job}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
