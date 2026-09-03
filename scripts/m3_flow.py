"""M3 端到端链路验证 — 语义深度引导 vs 纯 prompt（双步方案）

验证目标：M3 前后景/containment 能否靠「语义深度图 + ControlNet」正确引导。

双步方案（工业依据：语义深度图比合成几何块可靠——DepthAnything 有真实物体轮廓）：
  Step A  区域 conditioning 生成布局草图（人前景/车后景，布局大致对即可）
  Step B  DepthAnything 提取草图的语义深度图 → ControlNet depth → 精修出最终图
  对照    same seed 纯 prompt（无 depth）——看 depth 到底有没有带来增量的前后景增益

⚠️ 本脚本只做"单张链路验证"，不做批量——先证明链路成立再谈成本复用。
   首次 DepthAnything 加载 large 模型 ~6min（lowvram 换页慢），是已知成本。

用法:
  python scripts/m3_flow.py --dry-run
  python scripts/m3_flow.py                        # 1布局草图 + 1语义深度生图 + 1纯prompt对照
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
from PIL import Image  # noqa: E402

from comfy_utils import comfy_base_url, wait_images, resolve_comfy_root  # noqa: E402

QUAL = "masterpiece, best quality, anime style, detailed illustration, full color, "
NEG = (
    "worst quality, low quality, blurry, jpeg artifacts, lowres, bad anatomy, bad hands, "
    "ugly, deformed, bad proportions, extra limbs, fused fingers, missing fingers, "
    "extra fingers, mutated hands, poorly drawn face, bad eyes, signature, watermark, "
    "text, cropped, monochrome, grayscale, lineart, sketch, uncolored, character sheet"
)
OUT = ROOT / "workspace" / "m3_flow"

# M3 核心题：人前景 / 电车后景（诊断集 D2-2，空间介词 of)
PROMPT = ("1girl, standing in the foreground looking back, "
          "a train passing in the background, station platform, city")
W, H = 1344, 768


def _nid():
    n = [0]

    def nxt() -> str:
        n[0] += 1
        return str(n[0])
    return nxt


def build_area_sketch(seed: int, ckpt: str) -> dict[str, Any]:
    """Step A: 区域 conditioning 生成布局草图（前景人下区 / 后景车上区）。"""
    nxt = _nid()
    wf: dict[str, Any] = {}
    ck = nxt()
    wf[ck] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}}

    def enc(t: str) -> str:
        n = nxt()
        wf[n] = {"class_type": "CLIPTextEncode", "inputs": {"text": QUAL + t, "clip": [ck, 1]}}
        return n

    def area(cond: str, y: float, hgt: float) -> str:
        n = nxt()
        wf[n] = {"class_type": "ConditioningSetAreaPercentage", "inputs": {
            "conditioning": [cond, 0], "width": 1.0, "height": round(hgt, 3),
            "x": 0.0, "y": round(y, 3), "strength": 1.0}}
        return n

    def comb(a: str, b: str) -> str:
        n = nxt()
        wf[n] = {"class_type": "ConditioningCombine",
                 "inputs": {"conditioning_1": [a, 0], "conditioning_2": [b, 0]}}
        return n

    base = enc("train station platform, city, sky")
    top = area(enc("a train passing in the background, platform, buildings"), 0.0, 0.5)
    bot = area(enc("a girl standing in the foreground looking back at camera"), 0.5, 0.5)
    pos = comb(comb(base, top), bot)
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
    wf[sv] = {"class_type": "SaveImage", "inputs": {"filename_prefix": "m3_sketch", "images": [vd, 0]}}
    return wf


def build_depth_guided(ref_image: str, seed: int, ckpt: str,
                       strength: float, ckpt_name: str) -> dict[str, Any]:
    """Step B: DepthAnything(参考图) → 语义深度图 → ControlNet depth → SDXL 生图。"""
    nxt = _nid()
    wf: dict[str, Any] = {}
    ck = nxt()
    wf[ck] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}}
    ep = nxt()
    wf[ep] = {"class_type": "CLIPTextEncode", "inputs": {"text": QUAL + PROMPT, "clip": [ck, 1]}}
    en = nxt()
    wf[en] = {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": [ck, 1]}}
    ld = nxt()
    wf[ld] = {"class_type": "LoadImage", "inputs": {"image": ref_image}}
    da = nxt()
    wf[da] = {"class_type": "DepthAnythingPreprocessor", "inputs": {
        "image": [ld, 0], "ckpt_name": ckpt_name, "resolution": 512}}
    cn = nxt()
    wf[cn] = {"class_type": "ControlNetLoader",
              "inputs": {"control_net_name": "controlnet-depth-sdxl-1.0.safetensors"}}
    ca = nxt()
    wf[ca] = {"class_type": "ControlNetApply", "inputs": {
        "conditioning": [ep, 0], "control_net": [cn, 0], "image": [da, 0], "strength": strength}}
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
    wf[sv] = {"class_type": "SaveImage", "inputs": {"filename_prefix": "m3_depth", "images": [vd, 0]}}
    return wf


def build_plain(seed: int, ckpt: str) -> dict[str, Any]:
    """对照: 纯 prompt（无 any depth），测 baseline。"""
    nxt = _nid()
    wf: dict[str, Any] = {}
    ck = nxt()
    wf[ck] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}}
    ep = nxt()
    wf[ep] = {"class_type": "CLIPTextEncode", "inputs": {"text": QUAL + PROMPT, "clip": [ck, 1]}}
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
    wf[sv] = {"class_type": "SaveImage", "inputs": {"filename_prefix": "m3_plain", "images": [vd, 0]}}
    return wf


def submit(wf: dict, base: str) -> str:
    r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code}: {r.text[:300]}")
    return r.json()["prompt_id"]


def save_first(pid: str, base: str, root: Path, out: Path) -> str | None:
    try:
        imgs = wait_images(pid, base, timeout_s=900)
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
    ap.add_argument("--seed", type=int, default=111111)
    ap.add_argument("--ckpt", default="waiIllustriousSDXL_v160.safetensors")
    ap.add_argument("--strength", type=float, default=1.0)
    ap.add_argument("--depth-ckpt", default="depth_anything_vitl14.pth")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    base = comfy_base_url()
    OUT.mkdir(parents=True, exist_ok=True)
    root = resolve_comfy_root()
    comfy_in = root / "input"
    comfy_in.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        print(f"[m3-flow] prompt: {PROMPT}")
        print(f"  Step A: 区域条件生成布局草图 ({W}x{H})")
        print(f"  Step B: DepthAnything({args.depth_ckpt}) 提语义深度 → ControlNet(strength={args.strength}) 精修")
        print(f"  对照:    same seed 纯 prompt")
        print("  ⚠️ 首次 DepthAnything 加载 large ~6min（lowvram 换页慢）")
        return

    # Step A: 布局草图（区域辅助）
    print("[m3-flow] Step A: 生成布局草图…")
    try:
        pid = submit(build_area_sketch(args.seed, args.ckpt), base)
        sketch = save_first(pid, base, root, OUT / "sketch_A.png")
        print(f"  草图 -> {sketch}")
    except Exception as e:  # noqa: BLE001
        print(f"  Step A 失败: {e}")
        return
    if not sketch:
        print("  Step A 无产出，中止")
        return

    # Step B: DepthAnything 从草图提语义深度 → ControlNet
    print("[m3-flow] Step B: 语义深度引导生图（DepthAnything 首次加载 ~6min）…")
    ref_name = "m3_ref_sketch.png"
    root_path = Path(sketch)
    # 复制草图到 ComfyUI/input/ 供 LoadImage 用
    (comfy_in / ref_name).write_bytes(root_path.read_bytes())
    t0 = time.time()
    try:
        pid = submit(build_depth_guided(ref_name, args.seed, args.ckpt, args.strength, args.depth_ckpt), base)
        depth_out = save_first(pid, base, root, OUT / "depth_B.png")
        print(f"  depth 引导图 -> {depth_out}  ({time.time()-t0:.0f}s)")
    except Exception as e:  # noqa: BLE001
        print(f"  Step B 失败: {e}")

    # 对照: 纯 prompt
    print("[m3-flow] 对照: 纯 prompt 生图…")
    try:
        pid = submit(build_plain(args.seed, args.ckpt), base)
        plain = save_first(pid, base, root, OUT / "plain_C.png")
        print(f"  纯 prompt -> {plain}")
    except Exception as e:  # noqa: BLE001
        print(f"  对照失败: {e}")
    print("[m3-flow] 完成")


if __name__ == "__main__":
    main()
