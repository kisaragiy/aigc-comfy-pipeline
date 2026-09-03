#!/usr/bin/env python3
"""Koren 小说 · 场景图重出（角色定稿后）

S1 初遇望月：IPAdapter 锚定望月定稿 → 学生会办公室场景
S4 天台师生：分区生图（左=晨烨锚定，右=秃顶老教师田地）

用法:
  python scripts/koren_scenes_v2.py --only S1,S4 [--seed N]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "agents"))

import requests  # noqa: E402
from comfy_utils import comfy_base_url, wait_images, resolve_comfy_root  # noqa: E402

CKPT = "waiIllustriousSDXL_v160.safetensors"
NEGATIVE = ("worst quality, low quality, blurry, jpeg artifacts, lowres, bad anatomy, "
            "bad hands, deformed, bad proportions, extra limbs, extra fingers, "
            "fused fingers, poorly drawn face, text, watermark, signature, "
            "chromatic aberration")

# 望月定稿特征（下半身已定：裸腿+白短袜+黑帆布鞋）
WANGYUE = ("1girl, long straight black hair, thick bangs, half-up hair with bright "
           "RED ribbon, teardrop mole under left eye, dark brown eyes, "
           "white shirt blouse with RED bow tie, gray plaid pleated skirt, "
           "bare legs, white short socks, black canvas shoes, "
           "cold calm dignified expression, aloof beautiful student council president")
CHENYE = ("1boy, high school student, slim slender build, 170cm, black short hair, "
          "messy bangs, droopy half-lidded dead fish eyes, tired calm expression, "
          "intimidating but not evil, white dress shirt, dark trousers")


def build_ipa_scene(ref: str, prompt: str, seed: int, prefix: str,
                    outdir: Path | None = None,
                    w: int = 896, h: int = 1152) -> None:
    """S1 类：IPAdapter 锚定角色 + 场景 prompt。"""
    wf = {}
    add = {}
    def a(nid, cls, inputs):
        add[nid] = {"class_type": cls, "inputs": inputs}
        wf[nid] = add[nid]
    a("1", "CheckpointLoaderSimple", {"ckpt_name": CKPT})
    model, clip, vae = ["1", 0], ["1", 1], ["1", 2]
    a("2", "LoadImage", {"image": ref})
    a("3", "IPAdapterUnifiedLoader", {"model": model, "preset": "PLUS FACE (portraits)"})
    a("4", "IPAdapterAdvanced", {
        "model": ["3", 0], "ipadapter": ["3", 1], "image": ["2", 0],
        "weight": 0.60, "weight_type": "linear",
        "combine_embeds": "concat", "start_at": 0.0, "end_at": 1.0,
        "embeds_scaling": "V only"})
    model = ["4", 0]
    a("5", "CLIPTextEncode", {"text": prompt, "clip": clip})
    a("6", "CLIPTextEncode", {"text": NEGATIVE, "clip": clip})
    a("7", "EmptyLatentImage", {"width": w, "height": h, "batch_size": 1})
    a("8", "KSampler", {"model": model, "positive": ["5", 0], "negative": ["6", 0],
                        "latent_image": ["7", 0], "seed": seed, "steps": 22, "cfg": 6.5,
                        "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0})
    a("9", "VAEDecode", {"samples": ["8", 0], "vae": vae})
    a("10", "SaveImage", {"images": ["9", 0], "filename_prefix": prefix})
    _submit(wf, prefix, outdir)


def _submit(wf: dict, prefix: str, outdir: Path | None = None) -> None:
    base = comfy_base_url()
    root = resolve_comfy_root()
    r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=30)
    if r.status_code != 200:
        print(f"  ❌ 提交失败: {r.text[:200]}")
        return
    t0 = time.time()
    imgs = wait_images(r.json()["prompt_id"], base, timeout_s=400.0)
    if not imgs:
        print("  ❌ 无输出")
        return
    sub, fn = imgs[0]
    src = root / "output" / (sub or "") / fn
    if src.is_file():
        dst = outdir / fn if outdir else src
        if outdir:
            dst.write_bytes(src.read_bytes())
        print(f"  ✅ {time.time()-t0:.0f}s -> {dst}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="S1,S4")
    ap.add_argument("--seed", type=int, default=20260901)
    args = ap.parse_args()
    OUTDIR = ROOT / "outputs" / "koren"
    OUTDIR.mkdir(parents=True, exist_ok=True)
    names = [x.strip() for x in args.only.split(",")]

    if "S1" in names:
        print("═══ S1 学生会初遇望月 ═══")
        build_ipa_scene(
            "wangyue_final_ref.png",
            f"{WANGYUE}, sitting at a desk in a dusty old student council office, "
            "reviewing documents with a red pen, dust particles floating in sunlight, "
            "sunbeam through window, morning light, dignified, upper body",
            args.seed + 1, f"S1_meet_{args.seed}", OUTDIR)

    if "S4" in names:
        print("═══ S4 天台师生 ═══")
        build_ipa_scene(
            "chenye_ref.png",
            f"{CHENYE}, standing on school rooftop at sunset with an old bald "
            "middle-aged teacher, golden evening sun, warm orange sky, "
            "teacher is bald with glasses smoking a cigarette, wind blowing",
            args.seed + 2, f"S4_roof_{args.seed}", OUTDIR)


if __name__ == "__main__":
    main()
