#!/usr/bin/env python3
"""⑧ 崩坏图 → 重画修复 · 路线对照实验

源素材：⑨ 实验跑出来的真崩坏图（IPAdapter 过冲）——不用另找素材，
  E4 = 整图黄绿撕裂/面部崩坏/多手（最严重）
  E0 = 红边噪点/结构撕裂/手融化

为什么不用 workshop/colorize.py：
  它 ControlNetLoader 写死 `control_v11p_sd15_canny.pth`（SD1.5）却配 SDXL 底模，
  且该文件本机不存在 → 必然报错。本机也没有任何 SDXL canny ControlNet。
  可用的 SDXL ControlNet 只有 softedge-dexined / tile / depth / inpaint / openpose。
  → 修崩坏的正解是 **tile**（保整体结构、重绘细节，且无需预处理器节点）。

四条路线（同源图/同 seed/同 prompt，只变修复策略）:
  A img2img denoise 0.60 + tile 0.5   —— 温和修复，最大保留原构图
  B img2img denoise 0.75 + tile 0.5   —— 强修复
  C img2img denoise 0.75  无 ControlNet —— 对照组（证明 tile 到底有没有用）
  D 全重画 denoise 1.00 + tile 0.8    —— 只借结构，画面全新画

用法:
  python scripts/probe_repair.py --dry-run
  python scripts/probe_repair.py
  python scripts/probe_repair.py --src E0
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
from comfy_utils import comfy_base_url, wait_images, resolve_comfy_root  # noqa: E402

CKPT = "waiIllustriousSDXL_v160.safetensors"
TILE_CN = "controlnet-tile-sdxl-1.0.safetensors"
SEED = 20260831
RUN_ID = time.strftime("%m%d%H%M%S")
OUTDIR = ROOT / "workspace" / "repair"

SOURCES = {
    "E4": ROOT / "workspace" / "ipa_rootcause" / "E4_scaling_Vonly.png",
    "E0": ROOT / "workspace" / "ipa_rootcause" / "E0_baseline_linear.png",
}

# 修复目标描述（用用户偏好 V4 配方）
PROMPT = ("masterpiece, best quality, highly detailed, official game cg, "
          "promotional illustration, crisp clean lineart, flat vivid colors, "
          "glossy polished finish, 1girl, long black hair, detailed face, "
          "detailed hands, standing in a library, bookshelves background")
NEG = ("worst quality, low quality, blurry, jpeg artifacts, lowres, bad anatomy, "
       "bad hands, deformed, bad proportions, extra limbs, extra fingers, "
       "fused fingers, missing fingers, poorly drawn face, mutated, "
       "chromatic aberration, color fringing, glitch, torn, artifacts, noise, "
       "signature, watermark, text")

# (label, denoise, tile_strength or None)
ROUTES = [
    ("A_dn060_tile050", 0.60, 0.5),
    ("B_dn075_tile050", 0.75, 0.5),
    ("C_dn075_notile", 0.75, None),
    ("D_full_tile080", 1.00, 0.8),
]


def upload(base: str, path: Path) -> str:
    with open(path, "rb") as f:
        r = requests.post(f"{base}/upload/image",
                          files={"image": (path.name, f, "image/png")},
                          data={"overwrite": "true"}, timeout=60)
    r.raise_for_status()
    return r.json()["name"]


def build_wf(upload_name: str, denoise: float, tile_strength: float | None,
             w: int, h: int, prefix: str) -> dict:
    """img2img(+可选 tile ControlNet) 修复工作流。

    denoise=1.0 时改用 EmptyLatentImage（完全重画，仅靠 ControlNet 借结构）。
    """
    wf: dict = {}
    wf["1"] = {"class_type": "CheckpointLoaderSimple",
               "inputs": {"ckpt_name": CKPT}}
    wf["10"] = {"class_type": "LoadImage", "inputs": {"image": upload_name}}
    wf["2"] = {"class_type": "CLIPTextEncode",
               "inputs": {"text": PROMPT, "clip": ["1", 1]}}
    wf["3"] = {"class_type": "CLIPTextEncode",
               "inputs": {"text": NEG, "clip": ["1", 1]}}

    # latent 来源：全重画用空 latent, 否则用源图编码
    if denoise >= 0.999:
        wf["4"] = {"class_type": "EmptyLatentImage",
                   "inputs": {"width": (w // 8) * 8, "height": (h // 8) * 8,
                              "batch_size": 1}}
        latent = ["4", 0]
    else:
        wf["11"] = {"class_type": "VAEEncode",
                    "inputs": {"pixels": ["10", 0], "vae": ["1", 2]}}
        latent = ["11", 0]

    pos, neg = ["2", 0], ["3", 0]
    if tile_strength is not None:
        wf["30"] = {"class_type": "ControlNetLoader",
                    "inputs": {"control_net_name": TILE_CN}}
        # ControlNetApplyAdvanced: 同时作用于 positive/negative（SDXL 标准用法）
        wf["40"] = {"class_type": "ControlNetApplyAdvanced",
                    "inputs": {"positive": pos, "negative": neg,
                               "control_net": ["30", 0], "image": ["10", 0],
                               "strength": tile_strength,
                               "start_percent": 0.0, "end_percent": 1.0}}
        pos, neg = ["40", 0], ["40", 1]

    wf["5"] = {"class_type": "KSampler",
               "inputs": {"model": ["1", 0], "positive": pos, "negative": neg,
                          "latent_image": latent, "seed": SEED, "steps": 24,
                          "cfg": 6.5, "sampler_name": "dpmpp_2m",
                          "scheduler": "karras", "denoise": denoise}}
    wf["6"] = {"class_type": "VAEDecode",
               "inputs": {"samples": ["5", 0], "vae": ["1", 2]}}
    wf["7"] = {"class_type": "SaveImage",
               "inputs": {"images": ["6", 0], "filename_prefix": prefix}}
    return wf


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--src", default="E4", choices=list(SOURCES) + ["all"])
    args = ap.parse_args()
    srcs = list(SOURCES) if args.src == "all" else [args.src]
    OUTDIR.mkdir(parents=True, exist_ok=True)

    for sk in srcs:
        for label, dn, ts in ROUTES:
            print(f"  {sk}_{label}  denoise={dn} tile={ts}")
    if args.dry_run:
        for sk in srcs:
            print(f"[src] {sk}: {SOURCES[sk]} exists={SOURCES[sk].is_file()}")
        print(f"[dry-run] {len(srcs)*len(ROUTES)} images -> {OUTDIR}")
        return

    from PIL import Image
    base = comfy_base_url()
    root = resolve_comfy_root()
    t0 = time.time()
    n = 0
    for sk in srcs:
        src_path = SOURCES[sk]
        if not src_path.is_file():
            print(f"[skip] 源图不存在: {src_path}"); continue
        up = upload(base, src_path)
        w, h = Image.open(src_path).size
        # 源图也拷一份进结果目录，方便拼网格时做前后对比
        (OUTDIR / f"{sk}_0_SOURCE.png").write_bytes(src_path.read_bytes())
        print(f"[upload] {sk} <- {src_path.name} ({w}x{h})")

        for label, dn, ts in ROUTES:
            n += 1
            dst = OUTDIR / f"{sk}_{label}.png"
            if dst.is_file() and dst.stat().st_size > 1024:
                print(f"[{n}] {dst.stem} skip"); continue
            wf = build_wf(up, dn, ts, w, h, f"{sk}_{label}_{RUN_ID}")
            r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=30)
            if r.status_code != 200:
                print(f"[{n}] {dst.stem} SUBMIT FAIL: {r.text[:300]}"); continue
            imgs = wait_images(r.json()["prompt_id"], base, timeout_s=400.0)
            if not imgs:
                print(f"[{n}] {dst.stem} NO IMAGE"); continue
            sub, fn = imgs[0]
            s = root / "output" / (sub or "") / fn
            if s.is_file():
                dst.write_bytes(s.read_bytes())
                print(f"[{n}] {dst.stem} ok ({time.time()-t0:.0f}s)")

    (OUTDIR / "manifest.json").write_text(json.dumps(
        {"run_id": RUN_ID, "seed": SEED, "ckpt": CKPT, "tile_controlnet": TILE_CN,
         "prompt": PROMPT, "negative": NEG,
         "routes": [{"label": l, "denoise": d, "tile": t} for l, d, t in ROUTES]},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] -> {OUTDIR} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
