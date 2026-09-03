#!/usr/bin/env python3
"""Koren 小说 · 角色设定图 v2（按朋友反馈修正）

三张角色卡：
  R1 冉青青 —— 朋友认可图1(图 ref1)，头发到肩膀、蝴蝶结礼服+百褶裙
  R2 望月   —— 朋友认可图2(图 ref2)，发带改红色、蝴蝶结礼服+百褶裙
  R3 男主晨烨 —— 170cm/微肌肉/凶恶死鱼眼/疲惫眼神（高须龙儿+比企谷八幡），
                带领礼服+西裤（茶山光正实验学校男式）

方法：IPAdapter composition（保人物结构）锚定参考形象 + prompt 控服装。
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

# 茶山光正实验学校校服（按小说：没写默认光正校服，不是礼服西裤/水手服）
SCHOOL_GIRL = ("school uniform: white shirt blouse, pleated skirt, plain neat uniform")
SCHOOL_BOY = ("school uniform: white dress shirt, dark trousers, plain neat uniform")

ROLES = {
    "R1_ranqingqing": {
        "ref": "ranqingqing_ref2.png",
        "prompt": ("1girl, short dark brown hair to neck, one side braid with small "
                   "light purple bow, brown eyes, gentle shy expression, "
                   "cheerful kind girl, "
                   f"{SCHOOL_GIRL}, "
                   "warm corridor lighting, half body, clean cel shading"),
        "weight": 0.45,
    },
    "R2_wangyue": {
        "ref": "wangyue_ref2.png",
        "prompt": ("1girl, long dark brown hair, messy bangs, half-up braided hair, "
                   "teardrop mole under left eye, brown eyes, "
                   "white shirt blouse with a RED bow tie (red ribbon bow), "
                   "bright RED hair ribbon on side of head, all hair accessories "
                   "are RED, red bow, pleated skirt, "
                   "cold calm dignified expression, aloof beautiful student council "
                   "president, "
                   "classroom afternoon light, upper body, clean cel shading"),
        "weight": 0.15,
    },
    "R3_chenye": {
        "ref": "chenye_ref.png",
        "prompt": ("1boy, high school student, slim slender build, 170cm, "
                   "black short hair to ears, messy bangs over brows, "
                   "dark brown eyes, droopy half-lidded dead fish eyes, "
                   "tired calm expression, intimidating but not evil, "
                   f"{SCHOOL_BOY}, "
                   "campus background, upper body, clean cel shading"),
        "weight": 0.45,
    },
}


def build_wf(role: dict, seed: int, outdir: Path) -> None:
    add = {}
    wf = {}

    def a(node_id: str, cls: str, inputs: dict) -> None:
        add[node_id] = {"class_type": cls, "inputs": inputs}
        wf[node_id] = add[node_id]

    a("1", "CheckpointLoaderSimple", {"ckpt_name": CKPT})
    model, clip, vae = ["1", 0], ["1", 1], ["1", 2]

    if role["ref"]:
        a("2", "LoadImage", {"image": role["ref"]})
        a("3", "IPAdapterUnifiedLoader", {"model": model, "preset": "PLUS FACE (portraits)"})
        a("4", "IPAdapterAdvanced", {
            "model": ["3", 0], "ipadapter": ["3", 1], "image": ["2", 0],
            "weight": role["weight"], "weight_type": "linear",
            "combine_embeds": "concat", "start_at": 0.0, "end_at": 1.0,
            "embeds_scaling": "V only"})
        model = ["4", 0]

    a("5", "CLIPTextEncode", {"text": role["prompt"], "clip": clip})
    a("6", "CLIPTextEncode", {"text": NEGATIVE, "clip": clip})
    a("7", "EmptyLatentImage", {"width": 896, "height": 1152, "batch_size": 1})
    a("8", "KSampler", {
        "model": model, "positive": ["5", 0], "negative": ["6", 0],
        "latent_image": ["7", 0], "seed": seed, "steps": 20, "cfg": 6.5,
        "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0})
    a("9", "VAEDecode", {"samples": ["8", 0], "vae": vae})
    a("10", "SaveImage", {"images": ["9", 0], "filename_prefix": f"char_{seed}"})

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
        dst = outdir / fn
        dst.write_bytes(src.read_bytes())
        print(f"  ✅ {time.time()-t0:.0f}s -> {dst}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="逗号分隔 R1,R2,R3")
    ap.add_argument("--seed", type=int, default=20260901)
    args = ap.parse_args()
    OUTDIR = ROOT / "outputs" / "koren" / "chars"
    OUTDIR.mkdir(parents=True, exist_ok=True)

    names = list(ROLES)
    if args.only:
        keep = [x.strip() for x in args.only.split(",")]
        names = [k for k in names if any(k.startswith(p) for p in keep)]

    for i, name in enumerate(names):
        print(f"═══ {name} ═══")
        build_wf(ROLES[name], args.seed + i * 100, OUTDIR)


if __name__ == "__main__":
    main()
