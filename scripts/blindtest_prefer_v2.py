#!/usr/bin/env python3
"""③.2 偏好向量验证 — 用新题材验证从盲测提炼的偏好是否泛化

盲测 v1 结论（2026-08-31 用户实打分）：
  ✅ 接受：S5=official game cg(最爱) / S2=anime cel shading / S1=watercolor(仅人像)
  ❌ 拒绝：S3=cinematic semi-real / S4=korean semi-real / S6=thick oil painting
  → 偏好向量：**平涂系(明确线稿+干净色块) 优于 厚涂系(弱线稿+光影渐变堆写实)**

本轮验证（换新题材，避免自证）：
  变量 = 画风词组合（4 组）
  固定 = 题材/seed/采样参数/底模
  目的 = ①S5 vs S2 谁更稳 ②融合是否更好 ③负向排除厚涂是否有效

用法：
  python scripts/blindtest_prefer_v2.py --dry-run
  python scripts/blindtest_prefer_v2.py
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
RUN_ID = time.strftime("%m%d%H%M%S")
STEPS, CFG = 28, 6.5
SAMPLER, SCHEDULER = "dpmpp_2m", "karras"
QUALITY = "masterpiece, best quality, highly detailed"
OUTDIR = ROOT / "workspace" / "blindtest" / "prefer_v2"

# 基础负向（与盲测 v1 一致）
NEG_BASE = ("worst quality, low quality, blurry, jpeg artifacts, lowres, bad anatomy, "
            "bad hands, deformed, bad proportions, extra limbs, fused fingers, "
            "missing fingers, poorly drawn face, signature, watermark, text, error, cropped")

# 针对「拒绝厚涂系」追加的负向（本轮验证重点）
NEG_ANTI_THICK = (", thick oil painting, impasto, painterly brushstrokes, "
                  "photorealistic, realistic skin texture, soft blurry shading, "
                  "muddy colors, sketchy lineart")

# 变量：4 组画风词
VARIANTS = {
    "V1_S5_officialcg": dict(
        style="official game cg, ultra detailed rendering, glossy polished finish, "
              "promotional illustration",
        neg=NEG_BASE),
    "V2_S2_celshade": dict(
        style="anime cel shading, flat vivid colors, crisp clean lineart, tv anime style",
        neg=NEG_BASE),
    "V3_fusion": dict(
        style="official game cg, promotional illustration, crisp clean lineart, "
              "flat vivid colors, glossy polished finish, ultra detailed rendering",
        neg=NEG_BASE),
    "V4_fusion_antithick": dict(
        style="official game cg, promotional illustration, crisp clean lineart, "
              "flat vivid colors, glossy polished finish, ultra detailed rendering",
        neg=NEG_BASE + NEG_ANTI_THICK),
}

# 新题材（盲测 v1 没用过，验证泛化）
SUBJECTS = {
    "T1battle": ("full body, one young woman, long black hair, amber eyes, "
                 "dynamic battle pose, holding a slender sword, dark fantasy armor, "
                 "sparks and embers, ruined castle courtyard at night", 768, 1344),
    "T2sitting": ("one young woman, long black hair, amber eyes, sitting by a cafe window, "
                  "chin resting on hand, warm afternoon light, white knit sweater, "
                  "coffee cup on table", 896, 1152),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--seeds", default=str(SEED),
                    help="逗号分隔多 seed（铁律：单变量对比样本需≥4，同 seed 配对）")
    ap.add_argument("--only-variants", default=None, help="逗号分隔变体前缀，如 V3,V4")
    ap.add_argument("--only-subjects", default=None, help="逗号分隔题材前缀，如 T2")
    args = ap.parse_args()
    OUTDIR.mkdir(parents=True, exist_ok=True)

    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    vkeys = list(VARIANTS)
    if args.only_variants:
        pre = [x.strip() for x in args.only_variants.split(",")]
        vkeys = [k for k in vkeys if any(k.startswith(p) for p in pre)]
    tkeys = list(SUBJECTS)
    if args.only_subjects:
        pre = [x.strip() for x in args.only_subjects.split(",")]
        tkeys = [k for k in tkeys if any(k.startswith(p) for p in pre)]

    jobs = []
    for vk in vkeys:
        v = VARIANTS[vk]
        for tk in tkeys:
            subj, w, h = SUBJECTS[tk]
            for sd in seeds:
                # 单 seed 时保持旧命名（兼容已生成的文件，可断点续传）
                nm = f"{vk}__{tk}" if len(seeds) == 1 and sd == SEED else f"{vk}__{tk}__s{sd}"
                jobs.append({"name": nm, "seed": sd,
                             "prompt": f"{QUALITY}, {v['style']}, {subj}",
                             "neg": v["neg"], "w": w, "h": h})

    (OUTDIR / "manifest.json").write_text(json.dumps(
        {"run_id": RUN_ID, "seeds": seeds, "ckpt": CKPT, "variants": VARIANTS,
         "subjects": {k: v[0] for k, v in SUBJECTS.items()}, "jobs": jobs},
        ensure_ascii=False, indent=2), encoding="utf-8")

    for j in jobs:
        print(f"  {j['name']}")
    if args.dry_run:
        print(f"[dry-run] {len(jobs)} images -> {OUTDIR}")
        return

    base = comfy_base_url()
    root = resolve_comfy_root()
    t0 = time.time()
    for i, j in enumerate(jobs, 1):
        dst = OUTDIR / f"{j['name']}.png"
        if dst.is_file() and dst.stat().st_size > 1024:
            print(f"[{i}/{len(jobs)}] {j['name']} skip"); continue
        wf = build_sdxl_clean_workflow(
            j["prompt"], negative_prompt=j["neg"], ckpt=CKPT,
            width=j["w"], height=j["h"], steps=STEPS, cfg=CFG, seed=j["seed"],
            sampler=SAMPLER, scheduler=SCHEDULER,
            filename_prefix=f"{j['name']}_{RUN_ID}")
        r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=30)
        if r.status_code != 200:
            print(f"[{i}/{len(jobs)}] {j['name']} SUBMIT FAIL: {r.text[:200]}"); continue
        imgs = wait_images(r.json()["prompt_id"], base, timeout_s=300.0)
        if not imgs:
            print(f"[{i}/{len(jobs)}] {j['name']} NO IMAGE"); continue
        sub, fn = imgs[0]
        src = root / "output" / (sub or "") / fn
        if src.is_file():
            dst.write_bytes(src.read_bytes())
            print(f"[{i}/{len(jobs)}] {j['name']} ok ({time.time()-t0:.0f}s)")
    print(f"[done] -> {OUTDIR} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
