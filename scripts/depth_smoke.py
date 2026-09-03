"""M3 depth 可行性 smoke test（零下载）— 回答两个最关键问题

① 12G VRAM 能否同时载入 wai底模 + controlnet-depth-sdxl-1.0（5G）？会不会 OOM？
   （Flux depth 12G 已证不可用，SDXL depth 未知——这是最大的未知数，先测它）
② 合成"前景亮/背景暗"明暗引导图，ControlNetApply 是否响应布局？

⚠️ 本机无任何 depth 传感器权重（depth_anything*.pth/MiDaS/Zoe 全空），
   故用 PIL 合成一张前后景明暗渐变图作为 ControlNet 输入——这一步只为验证
   "VRAM 够不够 + 明暗引导有没有效"，不是正式 depth 输入。
   若本 smoke 通过，再考虑下载 depth_anything 权重做正式的语义 depth 输入。

用法:
  python scripts/depth_smoke.py --dry-run
  python scripts/depth_smoke.py               # 2种引导(纯渐变/带前景暗块)×同seed=2张
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "agents"))

import requests  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from comfy_utils import comfy_base_url, wait_images, resolve_comfy_root  # noqa: E402

QUAL = "masterpiece, best quality, anime style, detailed illustration, full color, "
NEG = (
    "worst quality, low quality, blurry, jpeg artifacts, lowres, bad anatomy, bad hands, "
    "ugly, deformed, bad proportions, extra limbs, fused fingers, missing fingers, "
    "extra fingers, mutated hands, poorly drawn face, bad eyes, signature, watermark, "
    "text, cropped, monochrome, grayscale, lineart, sketch, uncolored, character sheet"
)
OUT = ROOT / "workspace" / "depth_smoke"
# 前后景布置题：想测"人物在前、电车在后"
PROMPT = ("1girl, standing in the foreground looking back, "
          "a train passing in the background, station platform, city")


def make_guide(kind: str, w: int = 1024, h: int = 576) -> Image.Image:
    """合成明暗引导图（越亮=越近）。depth model 从明暗学近远结构。"""
    img = Image.new("L", (w, h), 200)  # 默认整体偏亮（前景)
    if kind == "gradient":
        # 上暗下亮：远处(顶部)暗、近处(底部)亮
        for y in range(h):
            v = int(30 + 220 * y / h)
            ImageDraw.Draw(img).line([(0, y), (w, y)], fill=v)
    elif kind == "foreground":
        # 背景暗(上部)，前景一个亮块(下部中，模拟人物近)
        for y in range(h):
            v = int(20 + 120 * y / h)  # 背景渐变暗
            ImageDraw.Draw(img).line([(0, y), (w, y)], fill=v)
        # 前景人物：底部长条亮块
        d = ImageDraw.Draw(img)
        d.rectangle([int(w*0.30), int(h*0.40), int(w*0.68), h], fill=250)
        # 圆头
        d.ellipse([int(w*0.40), int(h*0.26), int(w*0.60), int(h*0.52)], fill=250)
    return img


def build_depth_workflow(*, seed: int, guide_path: str, steps: int, cfg: float,
                         ckpt: str, strength: float) -> dict[str, Any]:
    wf: dict[str, Any] = {}
    nid = [0]

    def nxt() -> str:
        nid[0] += 1
        return str(nid[0])

    ck_n = nxt()
    wf[ck_n] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}}
    enc_p = nxt()
    wf[enc_p] = {"class_type": "CLIPTextEncode", "inputs": {"text": QUAL + PROMPT, "clip": [ck_n, 1]}}
    enc_n = nxt()
    wf[enc_n] = {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": [ck_n, 1]}}
    ld = nxt()
    wf[ld] = {"class_type": "LoadImage", "inputs": {"image": guide_path}}
    cn = nxt()
    wf[cn] = {"class_type": "ControlNetLoader",
              "inputs": {"control_net_name": "controlnet-depth-sdxl-1.0.safetensors"}}
    ca = nxt()
    wf[ca] = {"class_type": "ControlNetApply", "inputs": {
        "conditioning": [enc_p, 0], "control_net": [cn, 0],
        "image": [ld, 0], "strength": strength}}
    lat = nxt()
    wf[lat] = {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 576, "batch_size": 1}}
    ks = nxt()
    wf[ks] = {"class_type": "KSampler", "inputs": {
        "seed": seed, "steps": steps, "cfg": cfg, "sampler_name": "dpmpp_2m",
        "scheduler": "karras", "denoise": 1, "model": [ck_n, 0],
        "positive": [ca, 0], "negative": [enc_n, 0], "latent_image": [lat, 0]}}
    vd = nxt()
    wf[vd] = {"class_type": "VAEDecode", "inputs": {"samples": [ks, 0], "vae": [ck_n, 2]}}
    sv = nxt()
    wf[sv] = {"class_type": "SaveImage", "inputs": {
        "filename_prefix": f'depth_smoke_{seed}', "images": [vd, 0]}}
    return wf


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="*", default=None)
    ap.add_argument("--steps", type=int, default=28)
    ap.add_argument("--cfg", type=float, default=6.5)
    ap.add_argument("--ckpt", default="waiIllustriousSDXL_v160.safetensors")
    ap.add_argument("--strength", type=float, default=1.0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    seeds = args.seeds or [111111]
    base = comfy_base_url()
    OUT.mkdir(parents=True, exist_ok=True)
    # 确保 ComfyUI 能读到引导图（放 input/）
    comfy_in = resolve_comfy_root() / "input"
    comfy_in.mkdir(parents=True, exist_ok=True)

    print(f"[depth-smoke] {len(seeds)} seed × 2 引导(gradient/foreground) | "
          f"ckpt={args.ckpt} strength={args.strength}")
    if args.dry_run:
        print(f"  prompt: {PROMPT}")
        print("  引导1: gradient 上暗下亮（远近渐变）")
        print("  引导2: foreground 背景暗+前景亮块（人物近/车远）")
        return

    for seed in seeds:
        for kind in ["gradient", "foreground"]:
            g = make_guide(kind)
            guide_file = f"m3_depthguide_{kind}.png"
            g.save(comfy_in / guide_file)
            wf = build_depth_workflow(seed=seed, guide_path=guide_file, steps=args.steps,
                                      cfg=args.cfg, ckpt=args.ckpt, strength=args.strength)
            t0 = time.time()
            try:
                r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=60)
                if r.status_code != 200:
                    raise RuntimeError(f"{r.status_code}: {r.text[:300]}")
                imgs = wait_images(r.json()["prompt_id"], base, timeout_s=900)
            except Exception as exc:  # noqa: BLE001
                print(f"  ❌ seed={seed} {kind} : {exc}")
                continue
            saved = None
            root = resolve_comfy_root()
            for sub, fn in imgs:
                src = root / "output" / (sub or "") / fn
                if src.exists():
                    dst = OUT / f"depth_{kind}_{seed}.png"
                    dst.write_bytes(src.read_bytes())
                    saved = str(dst)
            print(f"  ✅ seed={seed} {kind}  {time.time()-t0:.0f}s -> {saved}")
    print("[depth-smoke] 完成")


if __name__ == "__main__":
    main()
