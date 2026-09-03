"""M6 手道具脱离 — 探路实验（区域"手+剑同区"能否建立握持关系）

M6 根因（网格图已证）：模型把"主体+道具"当独立元素渲染，不建立"手握住道具"的空间关系。
  - 剑悬浮/立身后/当背景，手在身侧摆姿势——手剑是两个元素，不是握持。
  - 与 M1 多人塌缩同源（模型不建立元素间关系），但 M6a(握持)比 M1(并列)更精细——
    区域只锁坐标，锁不住"手握住剑柄"。先探路验证，别一上来就全套。

对比（同 seed）：
  A 纯prompt（基线）: 单条 prompt "girl holding a sword with both hands"
  B 区域"手+剑同区": 手和剑都锁进同一区域 + 握持prompt强化
  C 区域"手区+剑区重叠": 手区与剑区重叠(overlap)，强制空间上贴合

题目：D4-1 双手握剑在身前（商业战斗立绘刚需）
验收标准：B 或 C 比 A 的"剑进手/手碰剑"通过率提升 ≥1/2（2 seed 对照）

用法: python scripts/m6_probe.py --dry-run | 跑
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
NEG = ("worst quality, low quality, blurry, jpeg artifacts, lowres, bad anatomy, bad hands, "
       "ugly, deformed, bad proportions, extra limbs, fused fingers, missing fingers, "
       "extra fingers, mutated hands, poorly drawn face, bad eyes, signature, watermark, "
       "text, cropped, monochrome, grayscale, lineart, sketch, uncolored, character sheet")
OUT = ROOT / "workspace" / "m6_probe"
W, H = 768, 1344  # 全身构图（评手持必须全身/半身，特写看不出握持）
SEEDS = [111111, 222222]

PROMPT_A = "1girl, holding a sword with both hands in front of her, full body, fantasy battle scene"
# B: 手+剑同区域，强化握持
PROMPT_B_HAND = "1girl, both hands gripping a sword handle, fingers wrapped around the hilt"
PROMPT_B_SWORD = "a sword held in her hands, blade pointing down, gripped firmly"


def _nid():
    n = [0]

    def nxt() -> str:
        n[0] += 1
        return str(n[0])
    return nxt


def build_region_wf(kind: str, seed: int, ckpt: str) -> dict[str, Any]:
    """kind='B' 手+剑同区；kind='C' 手区与剑区重叠。"""
    nxt = _nid()
    wf: dict[str, Any] = {}
    ck = nxt()
    wf[ck] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}}

    def enc(t: str) -> str:
        n = nxt()
        wf[n] = {"class_type": "CLIPTextEncode", "inputs": {"text": QUAL + t, "clip": [ck, 1]}}
        return n

    def area(cond: str, x: float, y: float, wd: float, ht: float, strength: float = 1.0) -> str:
        n = nxt()
        wf[n] = {"class_type": "ConditioningSetAreaPercentage", "inputs": {
            "conditioning": [cond, 0], "width": round(wd, 3), "height": round(ht, 3),
            "x": round(x, 3), "y": round(y, 3), "strength": round(strength, 3)}}
        return n

    def comb(a: str, b: str) -> str:
        n = nxt()
        wf[n] = {"class_type": "ConditioningCombine",
                 "inputs": {"conditioning_1": [a, 0], "conditioning_2": [b, 0]}}
        return n

    base = enc("1girl, fantasy battle scene, epic, dynamic, full body")
    if kind == "B":
        # 手+剑 锁进画面中央偏下同一区（手和剑同区，强制贴合）
        hand_area = area(enc(PROMPT_B_HAND), 0.15, 0.35, 0.75, 0.55, 1.4)
        sword_area = area(enc(PROMPT_B_SWORD), 0.15, 0.38, 0.75, 0.50, 1.2)
        pos = comb(comb(base, hand_area), sword_area)
    else:  # C: 手区与剑区重叠（剑区略大，套住手区）
        hand_area = area(enc(PROMPT_B_HAND), 0.20, 0.40, 0.65, 0.45, 1.3)
        sword_area = area(enc(PROMPT_B_SWORD), 0.15, 0.35, 0.75, 0.55, 1.0)
        pos = comb(comb(base, hand_area), sword_area)
    neg = enc(NEG)
    lat = nxt()
    wf[lat] = {"class_type": "EmptyLatentImage", "inputs": {"width": W, "height": H, "batch_size": 1}}
    ks = nxt()
    wf[ks] = {"class_type": "KSampler", "inputs": {
        "seed": seed, "steps": 28, "cfg": 6.5, "sampler_name": "dpmpp_2m", "scheduler": "karras",
        "denoise": 1, "model": [ck, 0], "positive": [pos, 0], "negative": [neg, 0],
        "latent_image": [lat, 0]}}
    vd = nxt()
    wf[vd] = {"class_type": "VAEDecode", "inputs": {"samples": [ks, 0], "vae": [ck, 2]}}
    sv = nxt()
    wf[sv] = {"class_type": "SaveImage", "inputs": {"filename_prefix": f"m6_{kind}_{seed}", "images": [vd, 0]}}
    return wf


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
    seeds = args.seeds or SEEDS
    base = comfy_base_url()
    OUT.mkdir(parents=True, exist_ok=True)
    root = resolve_comfy_root()

    if args.dry_run:
        print("[m6-probe] 题目: D4-1 双手握剑在身前 (全身构图)")
        print("  A 纯prompt  : 单条 'holding a sword with both hands'")
        print("  B 手剑同区  : 手+剑锁中央偏下区, 握持prompt强化")
        print("  C 手剑重叠区: 剑区套住手区(overlap)")
        print(f"  验收: B或C 比 A 的'剑进手'通过率提升>=1/2 ({len(seeds)} seed 对照)")
        return

    n = 0
    manifest = []
    mpath = OUT / "manifest.json"
    if mpath.exists():
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
    done = {(m["variant"], m["seed"]) for m in manifest}
    for variant, builder in [("A", None), ("B", build_region_wf), ("C", build_region_wf)]:
        for seed in seeds:
            if (variant, seed) in done:
                continue
            n += 1
            t0 = time.time()
            try:
                if variant == "A":
                    wf = build_sdxl_clean_workflow(QUAL + PROMPT_A, seed=seed, steps=28, cfg=6.5,
                                                   width=W, height=H, filename_prefix=f"m6_A_{seed}",
                                                   ckpt=args.ckpt, negative_prompt=NEG)
                else:
                    wf = builder(variant, seed, args.ckpt)
                pid = submit(wf, base)
                out = save_first(pid, base, root, OUT / f"{variant}_{seed}.png")
            except Exception as e:  # noqa: BLE001
                print(f"[{n}] {variant} seed={seed} ❌ {e}")
                continue
            print(f"[{n}] {variant} seed={seed} {time.time()-t0:.0f}s -> {out}")
            manifest.append({"variant": variant, "seed": seed, "file": out})
            mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[m6-probe] 完成")


if __name__ == "__main__":
    main()
