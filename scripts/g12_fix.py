"""G1/G2 修复探路 — 拥抱克制版 + 群像计数强化

G1 拥抱（探路发现）：肢体紧密交叠"拥抱"会融合/穿模+意外裸露——封面/情绪图核心但模型弱项。
  修法：**克制拥抱**（侧抱/背抱/3/4拥抱，避免全身交叠），看能否画对。
G2 群像人数（探路发现）：3人站一排"多出背景人"——M4计数+M1塌缩复合。
  修法：**prompt计数强化**（exactly three, no one else）+ 负向 extra person。

验收标准（前置定义）：
  G1: ≥1/2 克制拥抱无严重肢体融合穿模
  G2: ≥1/2 恰好3人、无背景多余人

用法: python scripts/g12_fix.py --dry-run | 跑
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
from go_knives_lora import build_sdxl_clean_workflow  # noqa: E402

QUAL = "masterpiece, best quality, anime style, detailed illustration, full color, "
NEG_BASE = ("worst quality, low quality, blurry, jpeg artifacts, lowres, bad anatomy, bad hands, "
            "ugly, deformed, bad proportions, extra limbs, fused fingers, missing fingers, "
            "extra fingers, mutated hands, poorly drawn face, bad eyes, signature, watermark, "
            "text, cropped, monochrome, grayscale, lineart, sketch, uncolored, character sheet")
NEG_COUNT = NEG_BASE + ", extra person, third person, background people, crowd"
OUT = ROOT / "workspace" / "g12_fix"
SEED = 333333

# G1 拥抱克制版（避免全身交叠）
G1 = [
    ("sidehug", "two girls in a gentle side hug, one girl wrapping arm around the other's shoulder,"
                "calm emotional moment, clothed, full body",
     (896, 1152), "侧抱：手臂绕肩不穿模/衣着完整"),
    ("backhug", "two girls, one girl hugging the other from behind, arms around her waist,"
                "clothed, gentle, full body",
     (768, 1344), "背抱：从后环腰/手臂位置合理/不裸露"),
    ("quietembrace", "two girls in a gentle quiet embrace, heads resting together,"
                     "soft clothing, warm light",
     (896, 1152), "静谧拥抱：上半身交叠/无明显融合"),
]
# G2 群像计数强化
G2 = [
    ("tri_exact", "three girls standing in a row, exactly three girls, no one else, no extra person,"
                  "group photo, full body",
     (1344, 768), "3人站排+计数强化：恰好3人/无背景多余人"),
    ("tri_sofa", "three girls sitting together on a sofa, exactly three girls, no one else,"
                 "full body, indoor",
     (1344, 768), "3人坐沙发+计数强化：恰好3人/无多余人"),
]


def _nid():
    n = [0]

    def nxt() -> str:
        n[0] += 1
        return str(n[0])
    return nxt


def build_wf(prompt: str, neg: str, seed: int, ckpt: str, w: int, h: int) -> dict[str, Any]:
    return build_sdxl_clean_workflow(QUAL + prompt, seed=seed, steps=28, cfg=6.5,
                                     width=w, height=h, filename_prefix="g12fix",
                                     ckpt=ckpt, negative_prompt=neg)


def submit(wf: dict, base: str) -> str:
    r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code}: {r.text[:300]}")
    return r.json()["prompt_id"]


def save_first(pid: str, base: str, root: Path, out: Path) -> str | None:
    try:
        imgs = wait_images(pid, base, timeout_s=600)
    except Exception as e:  # noqa: BLE001
        print(f"   wait 失败: {e}")
        return None
    for sub, fn in imgs:
        src = root / "output" / (sub or "") / fn
        if src.exists():
            out.write_bytes(src.read_bytes())
            return str(out)
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="*", default=None)
    ap.add_argument("--ckpt", default="waiIllustriousSDXL_v160.safetensors")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    seeds = args.seeds or [SEED]
    base = comfy_base_url()
    OUT.mkdir(parents=True, exist_ok=True)
    root = resolve_comfy_root()

    import random
    cases = [(f"G1_{k}", p, NEG_BASE, res, note) for k, p, res, note in G1] + \
            [(f"G2_{k}", p, NEG_COUNT, res, note) for k, p, res, note in G2]

    if args.dry_run:
        print(f"[g12-fix] {len(cases)} 题 × {len(seeds)} seed | 拥抱克制版+群像计数强化")
        for cid, p, neg, res, note in cases:
            print(f"  {cid:16s} {res} | {note}")
        return

    n = 0
    manifest = []
    mpath = OUT / "manifest.json"
    if mpath.exists():
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
    done = {(m["id"], m["seed"]) for m in manifest}
    for cid, prompt, neg, (w, h), note in cases:
        for seed in seeds:
            if (cid, seed) in done:
                continue
            n += 1
            t0 = time.time()
            try:
                pid = submit(build_wf(prompt, neg, seed, args.ckpt, w, h), base)
                out = save_first(pid, base, root, OUT / f"{cid}_{seed}.png")
            except Exception as e:  # noqa: BLE001
                print(f"[{n}] {cid} seed={seed} ❌ {e}")
                continue
            print(f"[{n}] {cid} seed={seed} {time.time()-t0:.0f}s -> {out}")
            manifest.append({"id": cid, "seed": seed, "file": out, "prompt": prompt,
                             "note": note, "neg_key": "count" if "extra person" in neg else "base"})
            mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[g12-fix] 完成")


if __name__ == "__main__":
    main()
