"""R4 精确颜色守恒 — 四方案同 seed 对比

R4 现象（gen_two demo 实测）：prompt 写 "long black hair, red hair ribbon"，
夕阳场景下黑发被染成红棕、红发带出成黄绿 → 精确颜色特征被场景光照/相邻属性侵蚀。

对标一手源（本机 ComfyUI 源码 comfy/sd1_clip.py:348 token_weights）：
  (word)      → weight *= 1.1（裸括号累乘）
  (word:1.4)  → weight = 1.4（绝对覆盖）
  encode_token_weights(): 权重通过与 empty-token embedding 插值实现
  ⚠️ 与 A1111 的 mean 归一化不同 → 高权重是"相对空嵌入外推"，可能反而加剧溢出，必须实测。

四组（单人构图，先排除多人变量）：
  V0 baseline  原样
  V1 weight    关键颜色加权重括号
  V2 negative  负向排斥错误颜色
  V3 both      V1 + V2
判定：同 seed 配对，人眼(vision)主判 + color_probe 代码统计辅助。

用法:
  python scripts/diag_color.py --dry-run
  python scripts/diag_color.py                 # 4组×3seed=12张
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

QUAL = "masterpiece, best quality, anime style, detailed illustration, full color, "
# R4 复现场景：强暖色光照（夕阳）+ 需守恒的冷/暗色特征（黑发）+ 小面积精确色（红发带）
SUBJ_PLAIN = ("1girl, long black hair, red hair ribbon, white sailor uniform, upper body, "
              "school rooftop at sunset, warm golden light, cinematic lighting")
SUBJ_WEIGHT = ("1girl, (long black hair:1.4), (red hair ribbon:1.3), (white sailor uniform:1.2), "
               "upper body, school rooftop at sunset, warm golden light, cinematic lighting")

NEG_BASE = (
    "worst quality, low quality, blurry, jpeg artifacts, lowres, bad anatomy, bad hands, "
    "ugly, deformed, extra limbs, fused fingers, poorly drawn face, signature, watermark, "
    "text, cropped, monochrome, grayscale, lineart, sketch, uncolored"
)
# 负向排斥：把"错误发色"和"错误发带色"明确排掉
NEG_COLOR = NEG_BASE + (
    ", red hair, brown hair, orange hair, blonde hair, ginger hair, colored hair, "
    "gradient hair, green ribbon, yellow ribbon, blue ribbon, white ribbon"
)

GROUPS = [
    dict(tag="V0_baseline", prompt=SUBJ_PLAIN, neg=NEG_BASE,
         desc="基线：原样 prompt"),
    dict(tag="V1_weight", prompt=SUBJ_WEIGHT, neg=NEG_BASE,
         desc="权重括号 (black hair:1.4)(red ribbon:1.3)"),
    dict(tag="V2_negative", prompt=SUBJ_PLAIN, neg=NEG_COLOR,
         desc="负向排斥错误颜色"),
    dict(tag="V3_both", prompt=SUBJ_WEIGHT, neg=NEG_COLOR,
         desc="权重 + 负向"),
]
SEEDS = [111111, 222222, 333333]
OUT = ROOT / "workspace" / "diag_color"
RES = (896, 1152)  # 半身竖构图（管线映射表：中景 896x1152）


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="*", default=None)
    ap.add_argument("--only", default=None, help="仅跑某组 tag 前缀，如 V1")
    ap.add_argument("--steps", type=int, default=28)
    ap.add_argument("--cfg", type=float, default=6.5)
    ap.add_argument("--ckpt", default="waiIllustriousSDXL_v160.safetensors")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    seeds = args.seeds or SEEDS
    groups = [g for g in GROUPS if not args.only or g["tag"].startswith(args.only)]
    base = comfy_base_url()
    OUT.mkdir(parents=True, exist_ok=True)
    mpath = OUT / "manifest.json"
    manifest: list[dict] = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else []

    print(f"[color] {len(groups)} 组 × {len(seeds)} seed = {len(groups)*len(seeds)} 张 | {RES[0]}x{RES[1]}")
    if args.dry_run:
        for g in groups:
            print(f'  {g["tag"]:14s} {g["desc"]}')
            print(f'     +: {g["prompt"][:110]}')
            print(f'     -: ...{g["neg"][-100:]}')
        return

    root = resolve_comfy_root()
    n = 0
    for g in groups:
        for seed in seeds:
            n += 1
            wf = build_sdxl_clean_workflow(
                QUAL + g["prompt"], seed=seed, steps=args.steps, cfg=args.cfg,
                width=RES[0], height=RES[1], filename_prefix=f'color_{g["tag"]}_{seed}',
                ckpt=args.ckpt, negative_prompt=g["neg"])
            t0 = time.time()
            try:
                r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=60)
                if r.status_code != 200:
                    raise RuntimeError(f"{r.status_code}: {r.text[:300]}")
                imgs = wait_images(r.json()["prompt_id"], base, timeout_s=600)
            except Exception as exc:  # noqa: BLE001
                print(f'[{n}] {g["tag"]} seed={seed} ❌ {exc}')
                continue
            saved = None
            for sub, fn in imgs:
                src = root / "output" / (sub or "") / fn
                if src.exists():
                    dst = OUT / f'{g["tag"]}_{seed}.png'
                    dst.write_bytes(src.read_bytes())
                    saved = str(dst)
            print(f'[{n}] {g["tag"]} seed={seed} {time.time()-t0:.0f}s -> {saved}')
            manifest.append({"tag": g["tag"], "desc": g["desc"], "seed": seed,
                             "file": saved, "prompt": g["prompt"], "neg_tail": g["neg"][-80:]})
            mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[color] 完成，manifest={mpath}")


if __name__ == "__main__":
    main()
