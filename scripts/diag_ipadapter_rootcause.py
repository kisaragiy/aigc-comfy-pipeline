#!/usr/bin/env python3
"""⑨.2 IPAdapter「整图错乱」根因定位实验 — OFAT 控变量

方法论（SOUL：一次只改一个变量）：
  E0 = 完全复现 C 阶段故障配置（basline）
  E1..E7 = 从 E0 出发，每次只改一个变量
  E8 = 无 IPAdapter 纯 prompt（参照基准）

判定：出图后人眼看「有没有紫金色错乱/撕裂」。
  故障复现 → E0 应错乱
  哪个变量让 E0 恢复正常 → 那就是根因

依据（一手源码，见 knowledge/aigc/ipadapter-field-reference-20260831.md）：
  weight_type='linear'         → 全部 block 等强注入（侵入最强）
  weight_type='style transfer' → SDXL 只注入 block 6（风格通道）
  weight_type='composition'    → SDXL 只注入 block 3（构图通道）

用法：
  python scripts/diag_ipadapter_rootcause.py --dry-run
  python scripts/diag_ipadapter_rootcause.py            # 9 张
  python scripts/diag_ipadapter_rootcause.py --only E0,E1
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

import requests  # noqa: E402
from comfy_utils import comfy_base_url, wait_images, resolve_comfy_root  # noqa: E402

RUN_ID = time.strftime("%m%d%H%M%S")
OUTDIR = ROOT / "workspace" / "ipa_rootcause"

# ── C 阶段故障现场原配置（✅ 实证自 agents/gen_celeste_scenes.py）────────
BASE = dict(
    ckpt="NoobAI-XL-v1.1.safetensors",
    ref="celeste_keyframe.png",
    preset="PLUS FACE (portraits)",
    weight=0.5,
    weight_type="linear",
    combine_embeds="concat",
    start_at=0.0,
    end_at=1.0,
    embeds_scaling="K+V",
    width=832, height=1216, steps=28, cfg=6.0, seed=42,
    use_ipa=True,
)

PROMPT = ("celeoc, 1girl, silver-white hair, long twin tails, amber-gold eyes, "
          "black gothic dress, delicate lace, cinematic lighting, anime lineart, "
          "masterpiece, best quality, standing in a gothic library, bookshelves")
NEGATIVE = ("worst quality, low quality, blurry, bad anatomy, bad hands, "
            "deformed, extra limbs, fused fingers, watermark, text")

# ── OFAT 实验组：每组只改一个变量 ──────────────────────────────────────
EXPERIMENTS = {
    "E0_baseline_linear":      {},                                   # 复现故障
    "E1_style_transfer":       {"weight_type": "style transfer"},    # 仅 block6
    "E2_composition":          {"weight_type": "composition"},       # 仅 block3
    "E3_weight_025":           {"weight": 0.25},                     # 降权重
    "E4_scaling_Vonly":        {"embeds_scaling": "V only"},         # 换缩放
    "E5_preset_standard":      {"preset": "STANDARD (medium strength)"},  # 换模型
    "E6_ckpt_wai":             {"ckpt": "waiIllustriousSDXL_v160.safetensors"},  # 换底模
    "E7_end_at_04":            {"end_at": 0.4},                      # 只前期注入
    "E8_no_ipadapter":         {"use_ipa": False},                   # 纯 prompt 参照
}


def build(cfg: dict, tag: str) -> dict:
    wf: dict = {}
    n = [0]

    def add(node):
        n[0] += 1
        wf[str(n[0])] = node
        return str(n[0])

    ckpt = add({"class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": cfg["ckpt"]}})
    model, clip, vae = [ckpt, 0], [ckpt, 1], [ckpt, 2]

    if cfg["use_ipa"]:
        ref = add({"class_type": "LoadImage", "inputs": {"image": cfg["ref"]}})
        loader = add({"class_type": "IPAdapterUnifiedLoader",
                      "inputs": {"model": model, "preset": cfg["preset"]}})
        ipa = add({"class_type": "IPAdapterAdvanced", "inputs": {
            "model": [loader, 0], "ipadapter": [loader, 1], "image": [ref, 0],
            "weight": cfg["weight"], "weight_type": cfg["weight_type"],
            "combine_embeds": cfg["combine_embeds"],
            "start_at": cfg["start_at"], "end_at": cfg["end_at"],
            "embeds_scaling": cfg["embeds_scaling"]}})
        model = [ipa, 0]

    pos = add({"class_type": "CLIPTextEncode", "inputs": {"text": PROMPT, "clip": clip}})
    neg = add({"class_type": "CLIPTextEncode", "inputs": {"text": NEGATIVE, "clip": clip}})
    lat = add({"class_type": "EmptyLatentImage",
               "inputs": {"width": cfg["width"], "height": cfg["height"], "batch_size": 1}})
    ks = add({"class_type": "KSampler", "inputs": {
        "model": model, "positive": [pos, 0], "negative": [neg, 0],
        "latent_image": [lat, 0], "seed": cfg["seed"], "steps": cfg["steps"],
        "cfg": cfg["cfg"], "sampler_name": "dpmpp_2m", "scheduler": "karras",
        "denoise": 1.0}})
    dec = add({"class_type": "VAEDecode", "inputs": {"samples": [ks, 0], "vae": vae}})
    add({"class_type": "SaveImage",
         "inputs": {"images": [dec, 0], "filename_prefix": f"ipa_{tag}_{RUN_ID}"}})
    return wf


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", default=None, help="逗号分隔实验 ID 前缀，如 E0,E1")
    args = ap.parse_args()

    OUTDIR.mkdir(parents=True, exist_ok=True)
    names = list(EXPERIMENTS)
    if args.only:
        keep = [x.strip() for x in args.only.split(",")]
        names = [k for k in names if any(k.startswith(p) for p in keep)]

    manifest = []
    for name in names:
        cfg = dict(BASE); cfg.update(EXPERIMENTS[name])
        changed = EXPERIMENTS[name] or {"(none)": "baseline"}
        manifest.append({"id": name, "changed": changed, "config": cfg,
                         "verdict": "", "note": ""})
        print(f"{name:24s} changed={changed}")

    (OUTDIR / "manifest.json").write_text(
        json.dumps({"run_id": RUN_ID, "prompt": PROMPT, "base": BASE,
                    "experiments": manifest}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    if args.dry_run:
        print(f"[dry-run] {len(names)} experiments planned -> {OUTDIR}")
        return

    base_url = comfy_base_url()
    comfy_root = resolve_comfy_root()
    t0 = time.time()

    for i, name in enumerate(names, 1):
        dst = OUTDIR / f"{name}.png"
        if dst.is_file() and dst.stat().st_size > 1024:
            print(f"[{i}/{len(names)}] {name} skip (exists)")
            continue
        cfg = dict(BASE); cfg.update(EXPERIMENTS[name])
        wf = build(cfg, name)
        try:
            r = requests.post(f"{base_url}/prompt", json={"prompt": wf}, timeout=30)
            if r.status_code != 200:
                print(f"[{i}/{len(names)}] {name} SUBMIT FAIL {r.status_code}: {r.text[:300]}")
                continue
            imgs = wait_images(r.json()["prompt_id"], base_url, timeout_s=600.0)
            if not imgs:
                print(f"[{i}/{len(names)}] {name} NO IMAGE")
                continue
            sub, fn = imgs[0]
            src = comfy_root / "output" / (sub or "") / fn
            if src.is_file():
                dst.write_bytes(src.read_bytes())
                print(f"[{i}/{len(names)}] {name} ok ({time.time()-t0:.0f}s)")
        except Exception as e:  # noqa: BLE001
            print(f"[{i}/{len(names)}] {name} ERROR: {type(e).__name__}: {e}")

    print(f"[done] -> {OUTDIR}  ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
