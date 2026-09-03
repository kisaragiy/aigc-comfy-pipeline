#!/usr/bin/env python3
"""④.1/④.2 真人↔二次元互转 — denoise 扫描找拐点

方法（控变量）：固定源图/prompt/seed/底模，**唯一变量 = denoise**。
  denoise 小 → 保结构但转换不足（"半死不活"，还是照片感）
  denoise 大 → 转得彻底但丢身份（"变成另一个人"）
  目标 = 找到两者的平衡点

复用 workshop/img2img.py 的 `_build_img2img_wf`（2026-08-31 已为本任务加 ckpt/steps/cfg 参数）。

用法:
  python scripts/probe_style_transfer.py --dry-run
  python scripts/probe_style_transfer.py --direction r2a     # 真人→二次元
  python scripts/probe_style_transfer.py --direction a2r     # 二次元→真人
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
sys.path.insert(0, str(ROOT / "workshop"))

import requests  # noqa: E402
from comfy_utils import comfy_base_url, wait_images, resolve_comfy_root  # noqa: E402
from img2img import _build_img2img_wf  # noqa: E402

RUN_ID = time.strftime("%m%d%H%M%S")
OUTDIR = ROOT / "workspace" / "style_transfer"
DENOISE_LIST = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
SEED = 20260831

ANIME_CKPT = "waiIllustriousSDXL_v160.safetensors"
REAL_CKPT = "RealVisXL_V5.0_fp16.safetensors"

# 用户偏好配方 V4（preference-profile-zwq-v1.md）
ANIME_STYLE = ("masterpiece, best quality, highly detailed, official game cg, "
               "promotional illustration, crisp clean lineart, flat vivid colors, "
               "glossy polished finish, ultra detailed rendering")
ANIME_NEG = ("worst quality, low quality, blurry, jpeg artifacts, lowres, bad anatomy, "
             "bad hands, deformed, bad proportions, extra limbs, fused fingers, "
             "poorly drawn face, signature, watermark, text, "
             "thick oil painting, impasto, painterly brushstrokes, photorealistic, "
             "realistic skin texture, soft blurry shading, muddy colors, sketchy lineart")

REAL_STYLE = ("RAW photo, photorealistic, ultra detailed skin texture, sharp focus, "
              "85mm portrait lens, natural lighting, film grain")
REAL_NEG = ("anime, illustration, cartoon, painting, drawing, 3d render, cgi, doll, "
            "plastic skin, worst quality, low quality, blurry, bad anatomy, "
            "bad hands, deformed, watermark, text")

DIRECTIONS = {
    # ④.1 真人 → 二次元
    "r2a": {
        "src": ROOT / "workspace" / "transform_src" / "R1_woman_face.png",
        "ckpt": ANIME_CKPT,
        "prompt": f"{ANIME_STYLE}, 1girl, long straight black hair, brown eyes, "
                  f"white shirt, upper body, looking at viewer, indoor soft light",
        "neg": ANIME_NEG, "steps": 16, "cfg": 6.5,
    },
    # ④.2 二次元 → 真人（源图用 steps_curve 的成品二次元图）
    "a2r": {
        "src": ROOT / "workspace" / "steps_curve" / "st028.png",
        "ckpt": REAL_CKPT,
        "prompt": f"{REAL_STYLE}, a young east asian woman, long black hair, "
                  f"white knit sweater, sitting by a cafe window, warm afternoon light",
        "neg": REAL_NEG, "steps": 30, "cfg": 4.5,
    },
    # ②.2 三次元性转：真人男 → 真人女（同一张脸的性别翻转）
    "m2f_real": {
        "src": ROOT / "workspace" / "transform_src" / "R3_man_face.png",
        "ckpt": REAL_CKPT,
        "prompt": f"{REAL_STYLE}, a 26 year old east asian woman, short black hair, "
                  f"brown eyes, feminine face, soft jawline, dark grey shirt, "
                  f"looking at camera, neutral expression, soft window light, upper body",
        "neg": REAL_NEG + ", man, male, masculine, beard, stubble, adam's apple",
        "steps": 30, "cfg": 4.5,
    },
    # ②.1 二次元性转：真人男 → 二次元女（跨风格+跨性别，双重转换难度）
    "m2f_anime": {
        "src": ROOT / "workspace" / "transform_src" / "R3_man_face.png",
        "ckpt": ANIME_CKPT,
        "prompt": f"{ANIME_STYLE}, 1girl, short black hair, brown eyes, "
                  f"dark grey shirt, upper body, looking at viewer, indoor soft light",
        "neg": ANIME_NEG + ", 1boy, male, masculine, beard",
        "steps": 16, "cfg": 6.5,
    },
}


def upload(base: str, path: Path) -> str:
    """上传源图到 ComfyUI input（img2img 的 LoadImage 需要）。"""
    with open(path, "rb") as f:
        r = requests.post(f"{base}/upload/image",
                          files={"image": (path.name, f, "image/png")},
                          data={"overwrite": "true"}, timeout=60)
    r.raise_for_status()
    return r.json()["name"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--direction", default="r2a", choices=list(DIRECTIONS) + ["all"])
    ap.add_argument("--denoise", default=",".join(str(d) for d in DENOISE_LIST))
    args = ap.parse_args()

    dirs = list(DIRECTIONS) if args.direction == "all" else [args.direction]
    dn_list = [float(x) for x in args.denoise.split(",") if x.strip()]
    OUTDIR.mkdir(parents=True, exist_ok=True)

    plan = []
    for dk in dirs:
        cfgd = DIRECTIONS[dk]
        for dn in dn_list:
            plan.append((dk, dn, cfgd))
            print(f"  {dk}  denoise={dn}")
    if args.dry_run:
        for dk in dirs:
            src = DIRECTIONS[dk]["src"]
            print(f"[src] {dk}: {src}  exists={src.is_file()}")
        print(f"[dry-run] {len(plan)} images -> {OUTDIR}")
        return

    base = comfy_base_url()
    root = resolve_comfy_root()
    t0 = time.time()
    uploaded: dict[str, str] = {}

    for i, (dk, dn, cfgd) in enumerate(plan, 1):
        src_path = cfgd["src"]
        if not src_path.is_file():
            print(f"[{i}] {dk} 源图不存在: {src_path}"); continue
        if dk not in uploaded:
            uploaded[dk] = upload(base, src_path)
            print(f"[upload] {dk} <- {src_path.name} => {uploaded[dk]}")

        dst = OUTDIR / f"{dk}_dn{int(dn*100):03d}.png"
        if dst.is_file() and dst.stat().st_size > 1024:
            print(f"[{i}/{len(plan)}] {dst.stem} skip"); continue

        wf = _build_img2img_wf(uploaded[dk], cfgd["prompt"], cfgd["neg"],
                               SEED, denoise=dn, ckpt=cfgd["ckpt"],
                               steps=cfgd["steps"], cfg=cfgd["cfg"])
        wf["7"]["inputs"]["filename_prefix"] = f"{dst.stem}_{RUN_ID}"
        r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=30)
        if r.status_code != 200:
            print(f"[{i}] {dst.stem} SUBMIT FAIL: {r.text[:300]}"); continue
        imgs = wait_images(r.json()["prompt_id"], base, timeout_s=400.0)
        if not imgs:
            print(f"[{i}] {dst.stem} NO IMAGE"); continue
        sub, fn = imgs[0]
        s = root / "output" / (sub or "") / fn
        if s.is_file():
            dst.write_bytes(s.read_bytes())
            print(f"[{i}/{len(plan)}] {dst.stem} ok ({time.time()-t0:.0f}s)")

    (OUTDIR / "manifest.json").write_text(json.dumps(
        {"run_id": RUN_ID, "seed": SEED, "denoise_list": dn_list,
         "directions": {k: {kk: (str(vv) if isinstance(vv, Path) else vv)
                            for kk, vv in v.items()} for k, v in DIRECTIONS.items()}},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] -> {OUTDIR} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
