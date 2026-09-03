"""M3 空间介词 — 先用区域 Conditioning 做上下/containment（零成本替先验证）

设计依据：
  M1 已证区域 Conditioning 能表达"左右并列"（A1-A4 8/8）。
  M3 空间介词拆两类：
    ① 上下/containment（猫在桌下包在桌上）→ 应是区域强项，横向分区改为纵向分区即可
    ② 前后景/遮挡（人在电车前/高个在矮个后）→ z 轴，区域表达不了，才需 depth
  本脚本先测 ①：能否用上下区域 + base 把 containment 空间关系锁死。

垂直区域（ConditioningSetAreaPercentage 的 y 即纵向）：
  上区 y=0, h=0.55（放"上"的物体）  下区 y=0.45, h=0.55（放"下"的物体，轻微重叠）
  base 覆盖全图（场景/桌面/框架，不设 area）

用法:
  python scripts/diag_m3.py --dry-run
  python scripts/diag_m3.py                    # 3题×2seed=6张，tag=updown
  python scripts/diag_m3.py --only D23
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "agents"))

import requests  # noqa: E402

from comfy_utils import comfy_base_url, wait_images, resolve_comfy_root  # noqa: E402

QUAL = "masterpiece, best quality, anime style, detailed illustration, full color, "
NEG = (
    "worst quality, low quality, blurry, jpeg artifacts, lowres, bad anatomy, bad hands, "
    "ugly, deformed, bad proportions, extra limbs, fused fingers, missing fingers, "
    "extra fingers, mutated hands, poorly drawn face, bad eyes, signature, watermark, "
    "text, cropped, monochrome, grayscale, lineart, sketch, uncolored, character sheet"
)
SEEDS = [111111, 222222]

# M3 空间题：全部按"上下"语义拆解区域
CASES = [
    dict(id="D23", ref="D2-3 猫桌下/包桌上", res=(1344, 768),
         base="cafe interior, wooden table, warm light",
         top="a handbag resting on top of the wooden table",
         bottom="a cat sitting under the table",
         expect="上=包在桌面上，下=猫在桌下（上下 containment 正确，猫被桌沿部分遮挡）"),
    dict(id="D22", ref="D2-2 人前景/电车后景", res=(1344, 768),
         base="train station platform, city street",
         top="a train passing in the distance, sky, buildings",
         bottom="a girl standing in the foreground, looking at camera",
         expect="下=人在前景清晰，上=电车在远处后景（前后层次分明）"),
    dict(id="D25", ref="D2-5 高个后/矮个前", res=(1216, 832),
         base="2girls, park, trees",
         top="a taller girl standing behind",
         bottom="a shorter girl standing in front",
         expect="下=矮个在前，上/后=高个在后（遮挡关系正确，矮个挡住高个下半身）"),
]
OUT = ROOT / "workspace" / "diag_m3"


def build_updown_workflow(case: dict, *, seed: int, steps: int, cfg: float,
                          ckpt: str, split_ratio: float, region_strength: float) -> dict[str, Any]:
    w, h = case["res"]
    wf: dict[str, Any] = {}
    nid = [0]

    def nxt() -> str:
        nid[0] += 1
        return str(nid[0])

    ck = nxt()
    wf[ck] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}}

    def enc(text: str) -> str:
        n = nxt()
        wf[n] = {"class_type": "CLIPTextEncode", "inputs": {"text": text, "clip": [ck, 1]}}
        return n

    def area(cond: str, y: float, hgt: float, strength: float) -> str:
        n = nxt()
        wf[n] = {"class_type": "ConditioningSetAreaPercentage", "inputs": {
            "conditioning": [cond, 0], "width": 1.0, "height": round(hgt, 3),
            "x": 0.0, "y": round(y, 3), "strength": round(strength, 3)}}
        return n

    def combine(a: str, b: str) -> str:
        n = nxt()
        wf[n] = {"class_type": "ConditioningCombine",
                 "inputs": {"conditioning_1": [a, 0], "conditioning_2": [b, 0]}}
        return n

    c_base = enc(QUAL + case["base"])
    # 上区 / 下区（轻微重叠，避免硬切）——y 从 0(顶) 到 0.45(下区起点)
    c_top = area(enc(QUAL + case["top"]), 0.0, split_ratio + 0.05, region_strength)
    c_bot = area(enc(QUAL + case["bottom"]), 1.0 - split_ratio - 0.05, split_ratio + 0.05, region_strength)
    positive = combine(combine(c_base, c_top), c_bot)
    negative = enc(NEG)

    lat = nxt()
    wf[lat] = {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}}
    ks = nxt()
    wf[ks] = {"class_type": "KSampler", "inputs": {
        "seed": seed, "steps": steps, "cfg": cfg, "sampler_name": "dpmpp_2m",
        "scheduler": "karras", "denoise": 1, "model": [ck, 0],
        "positive": [positive, 0], "negative": [negative, 0], "latent_image": [lat, 0]}}
    vd = nxt()
    wf[vd] = {"class_type": "VAEDecode", "inputs": {"samples": [ks, 0], "vae": [ck, 2]}}
    sv = nxt()
    wf[sv] = {"class_type": "SaveImage", "inputs": {
        "filename_prefix": f'm3_{case["id"]}_{seed}', "images": [vd, 0]}}
    return wf


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    ap.add_argument("--seeds", type=int, nargs="*", default=None)
    ap.add_argument("--steps", type=int, default=28)
    ap.add_argument("--cfg", type=float, default=6.5)
    ap.add_argument("--ckpt", default="waiIllustriousSDXL_v160.safetensors")
    ap.add_argument("--split-ratio", type=float, default=0.42,
                    help="各区域纵向高度比例（上下各占约 0.42，重叠 0.13）")
    ap.add_argument("--region-strength", type=float, default=1.0)
    ap.add_argument("--tag", default="updown")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    seeds = args.seeds or SEEDS
    cases = [c for c in CASES if not args.only or c["id"].lower() == args.only.lower()]
    base = comfy_base_url()
    OUT.mkdir(parents=True, exist_ok=True)
    mpath = OUT / f"manifest_{args.tag}.json"
    manifest: list[dict] = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else []

    print(f"[m3] {len(cases)} 题 × {len(seeds)} seed = {len(cases)*len(seeds)} 张 | split={args.split_ratio}")
    if args.dry_run:
        for c in cases:
            print(f'  {c["id"]} ({c["ref"]})  期望: {c["expect"]}')
        return

    root = resolve_comfy_root()
    n = 0
    for c in cases:
        for seed in seeds:
            n += 1
            wf = build_updown_workflow(c, seed=seed, steps=args.steps, cfg=args.cfg, ckpt=args.ckpt,
                                       split_ratio=args.split_ratio, region_strength=args.region_strength)
            t0 = time.time()
            try:
                r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=60)
                if r.status_code != 200:
                    raise RuntimeError(f"{r.status_code}: {r.text[:300]}")
                imgs = wait_images(r.json()["prompt_id"], base, timeout_s=600)
            except Exception as exc:  # noqa: BLE001
                print(f'[{n}] {c["id"]} seed={seed} ❌ {exc}')
                continue
            saved = None
            for sub, fn in imgs:
                src = root / "output" / (sub or "") / fn
                if src.exists():
                    dst = OUT / f'{c["id"]}_{seed}_{args.tag}.png'
                    dst.write_bytes(src.read_bytes())
                    saved = str(dst)
            print(f'[{n}] {c["id"]} seed={seed} {time.time()-t0:.0f}s -> {saved}')
            manifest.append({"id": c["id"], "ref": c["ref"], "seed": seed, "tag": args.tag,
                             "expect": c["expect"], "file": saved,
                             "params": {"split_ratio": args.split_ratio}})
            mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[m3] 完成，manifest={mpath}")


if __name__ == "__main__":
    main()
