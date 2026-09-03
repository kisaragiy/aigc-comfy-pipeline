"""M3 验证：镜头化 prompt vs 平铺描述（同 seed，是否能用 prompt 稳定解决 M3）

诊断集 D2-2 原版（平铺）："a girl standing in the foreground, a train passing in the background"
    —— 把 foreground/background 当文字标签写，模型不买账
镜头化（改写）：景别 + 景深 + 虚实 + 主体清晰
    —— 用摄影镜头语言表达"谁在前/谁在后"

判定维度：①电车大小/位置（应中景、不横贯巨大）②人物在前景清晰 ③前后景层次
验收标准（前置定义）：目标 ≥2/3 镜头化"人前车后"分明，且优于平铺版。

用法:
  python scripts/diag_m3_prompt.py --dry-run
  python scripts/diag_m3_prompt.py            # 2版prompt × 3seed = 6张
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
OUT = ROOT / "workspace" / "m3_prompt"
W, H = 1344, 768
SEEDS = [111111, 222222, 333333]

# 两版 prompt：平铺（诊断原版） vs 镜头化
PLAIN = ("1girl, standing in the foreground, a train passing in the background, "
         "station platform, city")
LENS = ("medium shot, a girl standing in the foreground in sharp focus, looking back, "
        "a train receding into the distance in the soft-focus background, depth of field, "
        "station platform, cinematic composition")
VARIANTS = [("plain", "平铺描述(诊断原版)", PLAIN),
            ("lens", "镜头化改写", LENS)]


def _nid():
    n = [0]

    def nxt() -> str:
        n[0] += 1
        return str(n[0])
    return nxt


def build_wf(prompt: str, seed: int, ckpt: str) -> dict[str, Any]:
    nxt = _nid()
    wf: dict[str, Any] = {}
    ck = nxt()
    wf[ck] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}}
    ep = nxt()
    wf[ep] = {"class_type": "CLIPTextEncode", "inputs": {"text": QUAL + prompt, "clip": [ck, 1]}}
    en = nxt()
    wf[en] = {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": [ck, 1]}}
    lat = nxt()
    wf[lat] = {"class_type": "EmptyLatentImage", "inputs": {"width": W, "height": H, "batch_size": 1}}
    ks = nxt()
    wf[ks] = {"class_type": "KSampler", "inputs": {
        "seed": seed, "steps": 28, "cfg": 6.5, "sampler_name": "dpmpp_2m", "scheduler": "karras",
        "denoise": 1, "model": [ck, 0], "positive": [ep, 0], "negative": [en, 0],
        "latent_image": [lat, 0]}}
    vd = nxt()
    wf[vd] = {"class_type": "VAEDecode", "inputs": {"samples": [ks, 0], "vae": [ck, 2]}}
    sv = nxt()
    wf[sv] = {"class_type": "SaveImage", "inputs": {"filename_prefix": "m3prompt", "images": [vd, 0]}}
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

    print(f"[m3-prompt] {len(VARIANTS)} 版prompt × {len(seeds)} seed = {len(VARIANTS)*len(seeds)} 张")
    if args.dry_run:
        for k, label, p in VARIANTS:
            print(f"  {k:6s} ({label}): {p[:110]}")
        return

    n = 0
    manifest = []
    mpath = OUT / "manifest.json"
    if mpath.exists():
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
    for k, label, p in VARIANTS:
        for seed in seeds:
            n += 1
            t0 = time.time()
            try:
                pid = submit(build_wf(p, seed, args.ckpt), base)
                out = save_first(pid, base, root, OUT / f"{k}_{seed}.png")
            except Exception as e:  # noqa: BLE001
                print(f"[{n}] {k} seed={seed} ❌ {e}")
                continue
            print(f"[{n}] {k} seed={seed} {time.time()-t0:.0f}s -> {out}")
            manifest.append({"variant": k, "label": label, "seed": seed, "file": out, "prompt": p})
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[m3-prompt] 完成")


if __name__ == "__main__":
    main()
