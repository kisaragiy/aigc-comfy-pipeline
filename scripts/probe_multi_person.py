#!/usr/bin/env python3
"""①.1 多人互动 — 基线测试（纯 prompt，暴露真实失败模式）

背景：08-30 诊断集实测本管线最弱两项就是**空间关系 15%** 和 **数量控制 30%**，
  而 ① 多人互动同时踩中这两项。08-30 已用 ConditioningSetAreaPercentage 分区
  攻下"两人并排"(加权 87.5%)，但**分区法把画面切成左右两半，天然不适合肢体接触的互动**。

本轮先做基线：纯 prompt 画多人互动，看具体怎么崩，再决定技术路线。
不凭想象选方案。

失败模式关注点：
  ① 人数对不对（多人/少人/融合成一个）
  ② 空间关系对不对（谁在左谁在右、谁在前谁在后）
  ③ 互动动作对不对（拥抱变成并排站、握手变成手融合）
  ④ 属性串味（A 的发色跑到 B 身上）
  ⑤ 肢体接触处是否崩坏（接触点是最难画的）

用法:
  python scripts/probe_multi_person.py --dry-run
  python scripts/probe_multi_person.py
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
STEPS, CFG = 16, 6.5           # ③.2 实测拐点
SAMPLER, SCHEDULER = "dpmpp_2m", "karras"
RUN_ID = time.strftime("%m%d%H%M%S")
OUTDIR = ROOT / "workspace" / "multi_person"

# 用户偏好 V3（融合配方，场景插画用——背景要有内容）
STYLE = ("masterpiece, best quality, highly detailed, official game cg, "
         "promotional illustration, anime cel shading, crisp clean lineart, "
         "flat vivid colors, glossy polished finish")
NEG = ("worst quality, low quality, blurry, jpeg artifacts, lowres, bad anatomy, "
       "bad hands, deformed, bad proportions, extra limbs, extra fingers, "
       "fused fingers, missing fingers, poorly drawn face, mutated, "
       "signature, watermark, text")

# 互动强度递增：并排(无接触) → 对话(有朝向) → 牵手(单点接触) → 拥抱(大面积接触) → 多人
CASES = {
    "M1_sidebyside": (
        "2girls, standing side by side, one with long black hair in a red dress, "
        "one with short blonde hair in a blue dress, looking at viewer, "
        "park background, daytime",
        1024, 1024),
    "M2_facing_talk": (
        "2girls facing each other, talking, one with long black hair in a red dress "
        "on the left, one with short blonde hair in a blue dress on the right, "
        "profile view, cafe interior",
        1024, 1024),
    "M3_holding_hands": (
        "2girls holding hands, one with long black hair in a red dress, "
        "one with short blonde hair in a blue dress, walking together, "
        "street background, full body",
        896, 1152),
    "M4_hug": (
        "2girls hugging each other tightly, one with long black hair in a red dress, "
        "one with short blonde hair in a blue dress, emotional embrace, "
        "sunset background, upper body",
        1024, 1024),
    "M5_three": (
        "3girls sitting around a round table, one with long black hair, "
        "one with short blonde hair, one with silver twintails, "
        "drinking tea and chatting, cafe interior",
        1216, 832),
    "M6_fight": (
        "2girls fighting, one with long black hair swinging a sword, "
        "one with short blonde hair blocking with a shield, "
        "dynamic action pose, ruins background, full body",
        1216, 832),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--seed", type=int, default=20260901)
    args = ap.parse_args()
    OUTDIR.mkdir(parents=True, exist_ok=True)

    (OUTDIR / "manifest.json").write_text(json.dumps(
        {"run_id": RUN_ID, "ckpt": CKPT, "seed": args.seed, "steps": STEPS,
         "cfg": CFG, "style": STYLE, "negative": NEG,
         "cases": {k: v[0] for k, v in CASES.items()},
         "note": "①.1 纯 prompt 基线，用于暴露多人互动的失败模式"},
        ensure_ascii=False, indent=2), encoding="utf-8")

    for k in CASES:
        print(f"  {k}")
    if args.dry_run:
        print(f"[dry-run] {len(CASES)} images -> {OUTDIR}")
        return

    base = comfy_base_url()
    root = resolve_comfy_root()
    t0 = time.time()
    for i, (name, (subj, w, h)) in enumerate(CASES.items(), 1):
        dst = OUTDIR / f"{name}.png"
        if dst.is_file() and dst.stat().st_size > 1024:
            print(f"[{i}/{len(CASES)}] {name} skip"); continue
        wf = build_sdxl_clean_workflow(
            f"{STYLE}, {subj}", negative_prompt=NEG, ckpt=CKPT,
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
        s = root / "output" / (sub or "") / fn
        if s.is_file():
            dst.write_bytes(s.read_bytes())
            print(f"[{i}/{len(CASES)}] {name} ok ({time.time()-t0:.0f}s)")
    print(f"[done] -> {OUTDIR} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
