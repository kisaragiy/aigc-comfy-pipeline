#!/usr/bin/env python3
"""③.2 画风偏好盲测 v1 — 控变量出图矩阵

设计（对标 SOUL「物对物」评价场景：严格控变量）：
  固定量: 底模 waiIllustriousSDXL_v160 / seed / steps 28 / cfg 6.5 / dpmpp_2m+karras / 主体描述 / 负向词
  变量  : 只变「画风词」一项
  题材  : 2 个（近景人像 + 全身场景）——同一画风在不同题材表现不同，单题材会误判

盲测纪律:
  1. 输出文件名只带编号（S1..S6），不带画风名 → 用户看图时不知道哪个是什么
  2. 映射表单独落盘 mapping.json，用户打完分才揭晓
  3. 固定 seed，同一 seed 跨风格可比

用法:
  python scripts/blindtest_style.py --dry-run
  python scripts/blindtest_style.py                # 6风格 × 2题材 = 12 张
"""
from __future__ import annotations

import argparse
import json
import random
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
SEED = 777777
RUN_ID = time.strftime("%m%d%H%M%S")
STEPS = 28
CFG = 6.5
SAMPLER = "dpmpp_2m"
SCHEDULER = "karras"

# 中性质量前缀（不含会主导画风的词，如 clean lineart —— 08-30 已实证会污染）
QUALITY = "masterpiece, best quality, highly detailed"

NEGATIVE = (
    "worst quality, low quality, blurry, jpeg artifacts, lowres, bad anatomy, "
    "bad hands, deformed, bad proportions, extra limbs, fused fingers, "
    "missing fingers, poorly drawn face, signature, watermark, text, error, cropped"
)

# 变量：画风词（唯一变量）
STYLES = {
    "A_celshade": "anime cel shading, flat vivid colors, crisp clean lineart, tv anime style",
    "B_thickpaint": "thick oil painting style, painterly brushstrokes, rich impasto texture, digital painting",
    "C_semireal_kr": "semi-realistic, soft gradient shading, korean webtoon style, delicate rendering",
    "D_watercolor": "watercolor illustration, soft pastel palette, delicate washes, light airy tone",
    "E_cinematic": "cinematic semi-realistic anime, dramatic film lighting, subtle film grain, movie still",
    "F_officialcg": "official game cg, ultra detailed rendering, glossy polished finish, promotional illustration",
}

# 题材（固定，不是变量）
SUBJECTS = {
    "P1portrait": (
        "upper body portrait, one young woman, long black hair, "
        "amber eyes, looking at viewer, soft window light, indoor",
        896, 1152,
    ),
    "P2fullbody": (
        "full body, one young woman, long black hair, amber eyes, "
        "standing on a city street at dusk, neon signs behind, wind blowing coat",
        768, 1344,
    ),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--outdir", default=str(ROOT / "workspace" / "blindtest" / "style_v1"))
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # 盲测编号：随机打乱风格→编号映射，避免顺序暗示
    keys = list(STYLES)
    random.Random(20260831).shuffle(keys)
    code_map = {f"S{i+1}": k for i, k in enumerate(keys)}

    jobs = []
    for code, style_key in code_map.items():
        for subj_code, (subj, w, h) in SUBJECTS.items():
            prompt = f"{QUALITY}, {STYLES[style_key]}, {subj}"
            jobs.append({
                "code": code, "style_key": style_key, "subject": subj_code,
                "prompt": prompt, "w": w, "h": h,
                "filename": f"blind_{code}_{subj_code}",
            })

    mapping = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "fixed": {"ckpt": CKPT, "seed": SEED, "steps": STEPS, "cfg": CFG,
                  "sampler": SAMPLER, "scheduler": SCHEDULER, "quality_prefix": QUALITY},
        "variable": "style words only",
        "code_map": code_map,
        "style_words": STYLES,
        "subjects": {k: v[0] for k, v in SUBJECTS.items()},
        "jobs": jobs,
    }
    (outdir / "mapping.json").write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[plan] {len(jobs)} images -> {outdir}")
    for j in jobs:
        print(f"  {j['filename']}  ({j['style_key']})")
    if args.dry_run:
        return

    base = comfy_base_url()
    comfy_root = resolve_comfy_root()
    done = []
    t0 = time.time()

    for i, j in enumerate(jobs, 1):
        dst = outdir / f"{j['filename']}.png"
        # 断点续传：已生成的直接跳过（被中断/重跑时不浪费 GPU）
        if dst.is_file() and dst.stat().st_size > 1024:
            print(f"[{i}/{len(jobs)}] {j['filename']} skip (already exists)")
            done.append(str(dst))
            continue
        # ⚠️ 破缓存：ComfyUI 对完全相同的工作流会缓存命中，
        #   此时 /history 的 outputs 为空 → wait_images 无限空等（2026-08-31 实测踩坑）。
        #   给 filename_prefix 加 run_id 使工作流 hash 变化，强制真实执行。
        #   seed/prompt/采样参数全部不变 → 控变量依旧成立。
        run_tag = f"{j['filename']}_{RUN_ID}"
        wf = build_sdxl_clean_workflow(
            j["prompt"],
            negative_prompt=NEGATIVE,
            ckpt=CKPT,
            width=j["w"], height=j["h"],
            steps=STEPS, cfg=CFG, seed=SEED,
            sampler=SAMPLER, scheduler=SCHEDULER,
            filename_prefix=run_tag,
        )
        r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=30)
        r.raise_for_status()
        pid = r.json()["prompt_id"]
        imgs = wait_images(pid, base, timeout_s=300.0)
        if not imgs:
            print(f"[{i}/{len(jobs)}] {j['filename']} FAILED (no image returned)")
            continue
        for sub, fn in imgs:
            src = comfy_root / "output" / (sub or "") / fn
            if src.is_file():
                dst.write_bytes(src.read_bytes())
                done.append(str(dst))
        print(f"[{i}/{len(jobs)}] {j['filename']} ok  ({time.time()-t0:.0f}s)")

    (outdir / "done.json").write_text(
        json.dumps(done, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] {len(done)} images in {time.time()-t0:.0f}s -> {outdir}")


if __name__ == "__main__":
    main()
