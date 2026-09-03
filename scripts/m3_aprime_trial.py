"""M3 方案A' 实测 — 语义深度模板直接喂 ControlNet（vs 纯 prompt）

方案 C（草图→DepthAnything→ControlNet）已证伪：草图布局错→深度错→ControlNet固化错误。
方案 A'：把"人前景亮/车后景暗"直接编码成语义深度图，跳过草图与 DepthAnything，
      让 ControlNet 直接读"我想要的布局"。这才是"自然语言空间语义→图"的正路。

题型：人前景/车后景（诊断集 D2-2）。用改进版 fgbg 模板（v2，有真实轮廓感）。

判定维度：
  ① 电车大小/位置（应中景、不横贯全图、不巨大）
  ② 人物是否在前景清晰
  ③ 前后景层次
  ④ depth模板 是否比 纯prompt 更可控
同 seed 对比，3 个 seed 看稳定性。

用法:
  python scripts/m3_aprime_trial.py --dry-run
  python scripts/m3_aprime_trial.py                 # 3seed × (depth模板 + 纯prompt) = 6张
  python scripts/m3_aprime_trial.py --no-plain      # 只跑 depth 模板
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
OUT = ROOT / "workspace" / "m3_aprime"
W, H = 1344, 768
PROMPT_FGBG = ("1girl, standing in the foreground looking back, "
               "a train passing in the background, station platform, city")
TEMPLATE_FGBG = ROOT / "workspace" / "depth_templates_v2" / "depth_fgbg.png"
SEEDS = [111111, 222222, 333333]
STRENGTH = 1.0


def _nid():
    n = [0]

    def nxt() -> str:
        n[0] += 1
        return str(n[0])
    return nxt


def build_depth_template_wf(tpl: Path, seed: int, ckpt: str, strength: float) -> dict[str, Any]:
    nxt = _nid()
    wf: dict[str, Any] = {}
    ck = nxt()
    wf[ck] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}}
    ep = nxt()
    wf[ep] = {"class_type": "CLIPTextEncode", "inputs": {"text": QUAL + PROMPT_FGBG, "clip": [ck, 1]}}
    en = nxt()
    wf[en] = {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": [ck, 1]}}
    ld = nxt()
    wf[ld] = {"class_type": "LoadImage", "inputs": {"image": tpl.name}}
    cn = nxt()
    wf[cn] = {"class_type": "ControlNetLoader",
              "inputs": {"control_net_name": "controlnet-depth-sdxl-1.0.safetensors"}}
    ca = nxt()
    wf[ca] = {"class_type": "ControlNetApply", "inputs": {
        "conditioning": [ep, 0], "control_net": [cn, 0], "image": [ld, 0], "strength": strength}}
    lat = nxt()
    wf[lat] = {"class_type": "EmptyLatentImage", "inputs": {"width": W, "height": H, "batch_size": 1}}
    ks = nxt()
    wf[ks] = {"class_type": "KSampler", "inputs": {
        "seed": seed, "steps": 28, "cfg": 6.5, "sampler_name": "dpmpp_2m", "scheduler": "karras",
        "denoise": 1, "model": [ck, 0], "positive": [ca, 0], "negative": [en, 0],
        "latent_image": [lat, 0]}}
    vd = nxt()
    wf[vd] = {"class_type": "VAEDecode", "inputs": {"samples": [ks, 0], "vae": [ck, 2]}}
    sv = nxt()
    wf[sv] = {"class_type": "SaveImage", "inputs": {"filename_prefix": "aprime_tpl", "images": [vd, 0]}}
    return wf


def build_plain_wf(seed: int, ckpt: str) -> dict[str, Any]:
    nxt = _nid()
    wf: dict[str, Any] = {}
    ck = nxt()
    wf[ck] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}}
    ep = nxt()
    wf[ep] = {"class_type": "CLIPTextEncode", "inputs": {"text": QUAL + PROMPT_FGBG, "clip": [ck, 1]}}
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
    wf[sv] = {"class_type": "SaveImage", "inputs": {"filename_prefix": "aprime_plain", "images": [vd, 0]}}
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
    ap.add_argument("--strength", type=float, default=STRENGTH)
    ap.add_argument("--no-plain", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    seeds = args.seeds or SEEDS
    base = comfy_base_url()
    OUT.mkdir(parents=True, exist_ok=True)
    root = resolve_comfy_root()
    comfy_in = root / "input"
    comfy_in.mkdir(parents=True, exist_ok=True)

    # 把模板复制到 ComfyUI/input/ 供 LoadImage 用
    tpl_file = TEMPLATE_FGBG.name
    (comfy_in / tpl_file).write_bytes(TEMPLATE_FGBG.read_bytes())

    print(f"[aprime] {len(seeds)} seed × {2 if not args.no_plain else 1} 方案 = "
          f"{len(seeds)*(2 if not args.no_plain else 1)} 张 | strength={args.strength}")
    if args.dry_run:
        print(f"  模板: {TEMPLATE_FGBG}")
        print(f"  prompt: {PROMPT_FGBG}")
        print("  方案: [depth模板] vs [纯prompt]  same seed")
        return

    n = 0
    manifest = []
    mpath = OUT / "manifest.json"
    if mpath.exists():
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
    for seed in seeds:
        for tag, wf_fn in ([("depth", build_depth_template_wf), ("plain", build_plain_wf)]
                           if not args.no_plain else [("depth", build_depth_template_wf)]):
            n += 1
            if tag == "depth":
                wf = wf_fn(TEMPLATE_FGBG, seed, args.ckpt, args.strength)
            else:
                wf = wf_fn(seed, args.ckpt)
            t0 = time.time()
            try:
                pid = submit(wf, base)
                out = save_first(pid, base, root, OUT / f"{tag}_{seed}.png")
            except Exception as e:  # noqa: BLE001
                print(f"[{n}] {tag} seed={seed} ❌ {e}")
                continue
            print(f"[{n}] {tag} seed={seed} {time.time()-t0:.0f}s -> {out}")
            manifest.append({"tag": tag, "seed": seed, "file": out,
                             "strength": args.strength, "prompt": PROMPT_FGBG})
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[aprime] 完成")


if __name__ == "__main__":
    main()
