#!/usr/bin/env python3
"""⑧ 第二轮：结构级 ControlNet 修崩坏 — 验证「抽象层级 vs 修复能力」

第一轮结论：tile(像素级) 修得了表层缺陷(噪点/色差), 修不了结构缺陷(手融化/撕裂),
  因为它忠实复制原图结构 = 照着崩坏重画一遍。

本轮假设：**抽象层级越高, 越能丢弃崩坏, 但也越丢失原图信息**。
  tile(像素) < lineart/softedge(边缘) < depth(空间) < openpose(骨架)

四条路线全部 denoise=1.0（完全重画, 只靠 ControlNet 提供结构）:
  E_lineart  AnimeLineArtPreprocessor  + softedge CN   边缘级(用户原需求"转线图重画")
  F_softedge PiDiNetPreprocessor       + softedge CN   边缘级(严格匹配)
  G_depth    DepthAnythingV2Preproc    + depth CN      空间级
  H_pose     OpenposePreprocessor      + OpenPoseXL2   骨架级

每条路线**同时保存预处理结果图**——看清"提取出的结构"长什么样, 才知道崩坏是在哪一层被带进去的。

用法:
  python scripts/probe_repair2.py --dry-run
  python scripts/probe_repair2.py --src all
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

CKPT = "waiIllustriousSDXL_v160.safetensors"
SEED = 20260831
RUN_ID = time.strftime("%m%d%H%M%S")
OUTDIR = ROOT / "workspace" / "repair2"

CN_SOFTEDGE = "controlnet-sd-xl-1.0-softedge-dexined.safetensors"
CN_DEPTH = "controlnet-depth-sdxl-1.0.safetensors"
CN_POSE = "OpenPoseXL2.safetensors"

SOURCES = {
    "E4": ROOT / "workspace" / "ipa_rootcause" / "E4_scaling_Vonly.png",
    "E0": ROOT / "workspace" / "ipa_rootcause" / "E0_baseline_linear.png",
}

PROMPT = ("masterpiece, best quality, highly detailed, official game cg, "
          "promotional illustration, crisp clean lineart, flat vivid colors, "
          "glossy polished finish, 1girl, long white hair, twintails, "
          "gothic lolita dress, detailed face, detailed hands, "
          "standing in a library, bookshelves background")
NEG = ("worst quality, low quality, blurry, jpeg artifacts, lowres, bad anatomy, "
       "bad hands, deformed, bad proportions, extra limbs, extra fingers, "
       "fused fingers, missing fingers, poorly drawn face, mutated, "
       "chromatic aberration, color fringing, glitch, torn, artifacts, noise, "
       "signature, watermark, text")

# label -> (预处理节点, 预处理额外参数, ControlNet 文件, strength)
ROUTES = {
    "E_lineart":  ("AnimeLineArtPreprocessor", {}, CN_SOFTEDGE, 0.85),
    "F_softedge": ("PiDiNetPreprocessor", {"safe": "enable"}, CN_SOFTEDGE, 0.85),
    "G_depth":    ("DepthAnythingV2Preprocessor",
                   {"ckpt_name": "depth_anything_v2_vitl.pth"}, CN_DEPTH, 0.85),
    "H_pose":     ("OpenposePreprocessor",
                   {"detect_hand": "enable", "detect_body": "enable",
                    "detect_face": "enable"}, CN_POSE, 0.85),
}


def upload(base: str, path: Path) -> str:
    with open(path, "rb") as f:
        r = requests.post(f"{base}/upload/image",
                          files={"image": (path.name, f, "image/png")},
                          data={"overwrite": "true"}, timeout=60)
    r.raise_for_status()
    return r.json()["name"]


def build_wf(upload_name: str, pre_node: str, pre_args: dict, cn_file: str,
             strength: float, w: int, h: int, prefix: str) -> dict:
    wf: dict = {}
    wf["1"] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}}
    wf["10"] = {"class_type": "LoadImage", "inputs": {"image": upload_name}}
    # 预处理: 抽取结构。resolution 取原图长边, 保证结构图与生成尺寸对齐
    wf["20"] = {"class_type": pre_node,
                "inputs": {"image": ["10", 0], "resolution": max(w, h), **pre_args}}
    # 单独保存预处理结果 —— 看清"提取出的结构"本身
    wf["21"] = {"class_type": "SaveImage",
                "inputs": {"images": ["20", 0], "filename_prefix": f"{prefix}_PRE"}}
    wf["2"] = {"class_type": "CLIPTextEncode", "inputs": {"text": PROMPT, "clip": ["1", 1]}}
    wf["3"] = {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["1", 1]}}
    wf["30"] = {"class_type": "ControlNetLoader", "inputs": {"control_net_name": cn_file}}
    wf["40"] = {"class_type": "ControlNetApplyAdvanced",
                "inputs": {"positive": ["2", 0], "negative": ["3", 0],
                           "control_net": ["30", 0], "image": ["20", 0],
                           "strength": strength, "start_percent": 0.0,
                           "end_percent": 1.0}}
    # denoise=1.0 完全重画: 空 latent, 结构只来自 ControlNet
    wf["4"] = {"class_type": "EmptyLatentImage",
               "inputs": {"width": (w // 8) * 8, "height": (h // 8) * 8, "batch_size": 1}}
    wf["5"] = {"class_type": "KSampler",
               "inputs": {"model": ["1", 0], "positive": ["40", 0], "negative": ["40", 1],
                          "latent_image": ["4", 0], "seed": SEED, "steps": 24, "cfg": 6.5,
                          "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0}}
    wf["6"] = {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}}
    wf["7"] = {"class_type": "SaveImage",
               "inputs": {"images": ["6", 0], "filename_prefix": prefix}}
    return wf


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--src", default="E4", choices=list(SOURCES) + ["all"])
    ap.add_argument("--routes", default=",".join(ROUTES))
    args = ap.parse_args()
    srcs = list(SOURCES) if args.src == "all" else [args.src]
    routes = [r for r in args.routes.split(",") if r.strip() in ROUTES]
    OUTDIR.mkdir(parents=True, exist_ok=True)

    for sk in srcs:
        for r in routes:
            print(f"  {sk}_{r}  {ROUTES[r][0]} + {ROUTES[r][2][:28]}")
    if args.dry_run:
        print(f"[dry-run] {len(srcs)*len(routes)} images -> {OUTDIR}")
        return

    from PIL import Image
    base = comfy_base_url()
    root = resolve_comfy_root()
    t0 = time.time()
    n = 0
    for sk in srcs:
        sp = SOURCES[sk]
        if not sp.is_file():
            print(f"[skip] 源图不存在 {sp}"); continue
        up = upload(base, sp)
        w, h = Image.open(sp).size
        (OUTDIR / f"{sk}_0_SOURCE.png").write_bytes(sp.read_bytes())
        print(f"[upload] {sk} ({w}x{h})")

        for rk in routes:
            n += 1
            pre_node, pre_args, cn, st = ROUTES[rk]
            dst = OUTDIR / f"{sk}_{rk}.png"
            if dst.is_file() and dst.stat().st_size > 1024:
                print(f"[{n}] {dst.stem} skip"); continue
            wf = build_wf(up, pre_node, pre_args, cn, st, w, h, f"{sk}_{rk}_{RUN_ID}")
            r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=30)
            if r.status_code != 200:
                print(f"[{n}] {dst.stem} SUBMIT FAIL: {r.text[:400]}"); continue
            imgs = wait_images(r.json()["prompt_id"], base, timeout_s=500.0)
            if not imgs:
                print(f"[{n}] {dst.stem} NO IMAGE"); continue
            # 两个输出: 预处理图(_PRE) 与 成品, 按文件名区分
            for sub, fn in imgs:
                s = root / "output" / (sub or "") / fn
                if not s.is_file():
                    continue
                tgt = OUTDIR / (f"{sk}_{rk}_PRE.png" if "_PRE_" in fn else f"{sk}_{rk}.png")
                tgt.write_bytes(s.read_bytes())
            print(f"[{n}] {dst.stem} ok ({time.time()-t0:.0f}s)")

    (OUTDIR / "manifest.json").write_text(json.dumps(
        {"run_id": RUN_ID, "seed": SEED, "denoise": 1.0, "steps": 24, "cfg": 6.5,
         "routes": {k: {"pre": v[0], "cn": v[2], "strength": v[3]}
                    for k, v in ROUTES.items()}},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] -> {OUTDIR} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
