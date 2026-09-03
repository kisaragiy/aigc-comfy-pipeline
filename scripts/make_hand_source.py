#!/usr/bin/env python3
"""⑧ 手部专修 · 素材制造：造出真正的手部崩坏图

【为什么重造】2026-08-31 判断失误纠正：
  原用 E0/E4 作"手崩"素材是**误判**——那张图角色双手垂在身侧被长发完全遮挡，
  画面里根本没有可见的手；胸前黑团是哥特萝莉裙的蕾丝领口装饰。
  MeshGraphormer 输出全黑不是工具坏了，是我给了它一张没有手的图。
  基于该误判得出的所有"手部修复"结论全部作废。

【正确做法】手部近景 + 复杂手势 = AI 画手崩坏率最高的场景，
  用它造出真·手崩样本（多指/融指/畸形），再验证 HandRefiner。
  关键：手必须**清晰可见且占画面比例大**，否则检测器无从下手。

用法:
  python scripts/make_hand_source.py --dry-run
  python scripts/make_hand_source.py
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

CKPT = "waiIllustriousSDXL_v160.safetensors"
STEPS, CFG = 16, 6.5          # ③.2 实测拐点
SAMPLER, SCHEDULER = "dpmpp_2m", "karras"
RUN_ID = time.strftime("%m%d%H%M%S")
OUTDIR = ROOT / "workspace" / "hand_src"

STYLE = ("masterpiece, best quality, highly detailed, official game cg, "
         "promotional illustration, crisp clean lineart, flat vivid colors")

# ⚠️ 故意不写 "perfect hands / detailed fingers" 这类修正词，
#    也不在负向里放 bad hands —— 目的就是让它自然崩，拿到真样本。
NEG = ("worst quality, low quality, blurry, jpeg artifacts, lowres, "
       "signature, watermark, text, cropped")

# 手部占画面比例大 + 复杂手势 = 崩坏率最高
CASES = {
    "H1_spread": "1girl, close up on her hands, both hands raised near face, "
                 "fingers spread wide open, palms facing viewer, "
                 "long black hair, white shirt, indoor soft light",
    "H2_hold_cup": "1girl, close up, holding a coffee cup with both hands, "
                   "fingers wrapped around the cup, upper body, cafe, warm light",
    "H3_interlock": "1girl, close up, both hands clasped together in front of chest, "
                    "fingers interlocked, praying gesture, long black hair, indoor",
    "H4_peace": "1girl, upper body, one hand raised making a peace sign near her cheek, "
                "other hand on hip, smiling, long black hair, outdoor",
    "H5_reach": "1girl, reaching one hand toward the viewer, palm open, "
                "fingers clearly visible, foreshortening, upper body, indoor",
    "H6_weapon": "1girl, gripping a sword hilt with both hands, close up on the grip, "
                 "fingers around the handle, armor, dramatic light",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--seed", type=int, default=4321)
    args = ap.parse_args()
    OUTDIR.mkdir(parents=True, exist_ok=True)

    (OUTDIR / "manifest.json").write_text(json.dumps(
        {"run_id": RUN_ID, "ckpt": CKPT, "seed": args.seed, "steps": STEPS,
         "cfg": CFG, "style": STYLE, "negative": NEG, "cases": CASES,
         "note": "故意不加手部修正词，目的是拿到真·手崩样本"},
        ensure_ascii=False, indent=2), encoding="utf-8")

    for k in CASES:
        print(f"  {k}")
    if args.dry_run:
        print(f"[dry-run] {len(CASES)} images -> {OUTDIR}")
        return

    base = comfy_base_url()
    root = resolve_comfy_root()
    t0 = time.time()
    for i, (name, subj) in enumerate(CASES.items(), 1):
        dst = OUTDIR / f"{name}.png"
        if dst.is_file() and dst.stat().st_size > 1024:
            print(f"[{i}/{len(CASES)}] {name} skip"); continue
        wf = build_sdxl_clean_workflow(
            f"{STYLE}, {subj}", negative_prompt=NEG, ckpt=CKPT,
            width=1024, height=1024, steps=STEPS, cfg=CFG, seed=args.seed,
            sampler=SAMPLER, scheduler=SCHEDULER,
            filename_prefix=f"{name}_{RUN_ID}")
        r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=30)
        if r.status_code != 200:
            print(f"[{i}] {name} SUBMIT FAIL: {r.text[:200]}"); continue
        imgs = wait_images(r.json()["prompt_id"], base, timeout_s=400.0)
        if not imgs:
            print(f"[{i}] {name} NO IMAGE"); continue
        sub, fn = imgs[0]
        s = root / "output" / (sub or "") / fn
        if s.is_file():
            dst.write_bytes(s.read_bytes())
            print(f"[{i}/{len(CASES)}] {name} ok ({time.time()-t0:.0f}s)")
    print(f"[done] -> {OUTDIR} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
