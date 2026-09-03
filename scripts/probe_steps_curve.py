#!/usr/bin/env python3
"""③.2 质量拐点轴 + ⑩ DETAIL_MIN 定标（一个实验两用）

用途一（③.2）：扫 steps 找「够用点」——多少步之后再加步数收益就很小了，省时间省显存。
用途二（⑩ bug1）：低 steps 图 = 真·半成品/平涂敷衍样本，
    正好用来给失效的 `DETAIL_MIN`（现为 2.5，实际值域 273~5277）重新定标。

配方用用户偏好档案 V4（official game cg 融合 + 反厚涂负向），
固定 seed/prompt/cfg/采样器，**唯一变量 = steps**。

用法:
  python scripts/probe_steps_curve.py --dry-run
  python scripts/probe_steps_curve.py
  python scripts/probe_steps_curve.py --steps 2,4,8,16,28
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
SEED = 20260831
CFG = 6.5
SAMPLER, SCHEDULER = "dpmpp_2m", "karras"
RUN_ID = time.strftime("%m%d%H%M%S")
OUTDIR = ROOT / "workspace" / "steps_curve"

# 用户偏好 V4 配方（preference-profile-zwq-v1.md）
STYLE = ("official game cg, promotional illustration, crisp clean lineart, "
         "flat vivid colors, glossy polished finish, ultra detailed rendering")
SUBJECT = ("one young woman, long black hair, amber eyes, sitting by a cafe window, "
           "chin resting on hand, warm afternoon light, white knit sweater")
PROMPT = f"masterpiece, best quality, highly detailed, {STYLE}, {SUBJECT}"
NEG = ("worst quality, low quality, blurry, jpeg artifacts, lowres, bad anatomy, "
       "bad hands, deformed, bad proportions, extra limbs, fused fingers, "
       "missing fingers, poorly drawn face, signature, watermark, text, error, cropped, "
       "thick oil painting, impasto, painterly brushstrokes, photorealistic, "
       "realistic skin texture, soft blurry shading, muddy colors, sketchy lineart")
W, H = 896, 1152

DEFAULT_STEPS = [2, 4, 6, 8, 12, 16, 20, 24, 28, 36]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--steps", default=",".join(map(str, DEFAULT_STEPS)))
    args = ap.parse_args()
    steps_list = [int(s) for s in args.steps.split(",") if s.strip()]
    OUTDIR.mkdir(parents=True, exist_ok=True)

    (OUTDIR / "manifest.json").write_text(json.dumps(
        {"run_id": RUN_ID, "seed": SEED, "cfg": CFG, "ckpt": CKPT,
         "prompt": PROMPT, "negative": NEG, "size": [W, H],
         "steps_list": steps_list}, ensure_ascii=False, indent=2), encoding="utf-8")

    for s in steps_list:
        print(f"  steps={s:>3d} -> st{s:03d}.png")
    if args.dry_run:
        print(f"[dry-run] {len(steps_list)} images -> {OUTDIR}")
        return

    base = comfy_base_url()
    root = resolve_comfy_root()
    t0 = time.time()
    timing = {}
    for i, s in enumerate(steps_list, 1):
        dst = OUTDIR / f"st{s:03d}.png"
        if dst.is_file() and dst.stat().st_size > 1024:
            print(f"[{i}/{len(steps_list)}] steps={s} skip"); continue
        t1 = time.time()
        wf = build_sdxl_clean_workflow(
            PROMPT, negative_prompt=NEG, ckpt=CKPT, width=W, height=H,
            steps=s, cfg=CFG, seed=SEED, sampler=SAMPLER, scheduler=SCHEDULER,
            filename_prefix=f"st{s:03d}_{RUN_ID}")
        r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=30)
        if r.status_code != 200:
            print(f"[{i}] steps={s} SUBMIT FAIL: {r.text[:200]}"); continue
        imgs = wait_images(r.json()["prompt_id"], base, timeout_s=300.0)
        if not imgs:
            print(f"[{i}] steps={s} NO IMAGE"); continue
        sub, fn = imgs[0]
        src = root / "output" / (sub or "") / fn
        if src.is_file():
            dst.write_bytes(src.read_bytes())
            dt = time.time() - t1
            timing[s] = round(dt, 1)
            print(f"[{i}/{len(steps_list)}] steps={s:>3d} ok  {dt:.1f}s")

    (OUTDIR / "timing.json").write_text(
        json.dumps(timing, indent=2), encoding="utf-8")
    print(f"[done] -> {OUTDIR} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
