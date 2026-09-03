#!/usr/bin/env python3
"""④ 真人↔二次元互转 — 第一步：生成「真人」素材

为什么自己生成而不用真实照片：
  ① 隐私安全（不碰用户/他人照片）
  ② 可控可复现（固定 prompt/seed，实验可重跑）
  ③ 双向都能用（同一角色的真人版可作 ④.2 二次元→真人的对照真值）

底模 RealVisXL_V5.0_fp16（本机唯一写实向 SDXL 模型）。

用法:
  python scripts/make_real_source.py --dry-run
  python scripts/make_real_source.py
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
from go_knives_lora import build_sdxl_clean_workflow  # noqa: E402

CKPT = "RealVisXL_V5.0_fp16.safetensors"
RUN_ID = time.strftime("%m%d%H%M%S")
OUTDIR = ROOT / "workspace" / "transform_src"

# 写实模型的典型参数（与二次元模型不同：cfg 更低）
STEPS, CFG = 30, 4.5
SAMPLER, SCHEDULER = "dpmpp_2m", "karras"

QUALITY = ("RAW photo, photorealistic, ultra detailed skin texture, "
           "sharp focus, 85mm portrait lens, natural lighting, film grain")

NEG = ("anime, illustration, cartoon, painting, drawing, 3d render, cgi, doll, "
       "plastic skin, airbrushed, worst quality, low quality, blurry, lowres, "
       "bad anatomy, bad hands, deformed, extra limbs, fused fingers, "
       "watermark, text, signature")

# 素材设计：覆盖 ④ 与 ② 两个方向的需求
SOURCES = {
    # ④.1 主素材：正面近景，五官清晰 → 便于判定"转完还是不是同一个人"
    "R1_woman_face": (
        "a 25 year old east asian woman, long straight black hair, "
        "brown eyes, natural makeup, white shirt, looking at camera, "
        "neutral expression, soft window light, indoor, upper body",
        896, 1152),
    # ④.1 复杂场景：验证背景/衣物在转换中的表现
    "R2_woman_street": (
        "a 25 year old east asian woman, long black hair, beige trench coat, "
        "standing on a city street in the evening, bokeh city lights behind, "
        "full body, candid photography",
        768, 1344),
    # ② 性转素材：男性，用于三次元性转对照
    "R3_man_face": (
        "a 26 year old east asian man, short black hair, brown eyes, "
        "clean shaven, dark grey shirt, looking at camera, neutral expression, "
        "soft window light, indoor, upper body",
        896, 1152),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--seed", type=int, default=88888)
    args = ap.parse_args()
    OUTDIR.mkdir(parents=True, exist_ok=True)

    (OUTDIR / "manifest.json").write_text(json.dumps(
        {"run_id": RUN_ID, "ckpt": CKPT, "seed": args.seed,
         "steps": STEPS, "cfg": CFG, "quality": QUALITY, "negative": NEG,
         "sources": {k: v[0] for k, v in SOURCES.items()}},
        ensure_ascii=False, indent=2), encoding="utf-8")

    for k in SOURCES:
        print(f"  {k}")
    if args.dry_run:
        print(f"[dry-run] {len(SOURCES)} images -> {OUTDIR}")
        return

    base = comfy_base_url()
    root = resolve_comfy_root()
    t0 = time.time()
    for i, (name, (subj, w, h)) in enumerate(SOURCES.items(), 1):
        dst = OUTDIR / f"{name}.png"
        if dst.is_file() and dst.stat().st_size > 1024:
            print(f"[{i}/{len(SOURCES)}] {name} skip"); continue
        wf = build_sdxl_clean_workflow(
            f"{QUALITY}, {subj}", negative_prompt=NEG, ckpt=CKPT,
            width=w, height=h, steps=STEPS, cfg=CFG, seed=args.seed,
            sampler=SAMPLER, scheduler=SCHEDULER,
            filename_prefix=f"{name}_{RUN_ID}")
        r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=30)
        if r.status_code != 200:
            print(f"[{i}] {name} SUBMIT FAIL: {r.text[:200]}"); continue
        imgs = wait_images(r.json()["prompt_id"], base, timeout_s=400.0)
        if not imgs:
            print(f"[{i}] {name} NO IMAGE"); continue
        sub, fn = imgs[0]
        src = root / "output" / (sub or "") / fn
        if src.is_file():
            dst.write_bytes(src.read_bytes())
            print(f"[{i}/{len(SOURCES)}] {name} ok ({time.time()-t0:.0f}s)")
    print(f"[done] -> {OUTDIR} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
