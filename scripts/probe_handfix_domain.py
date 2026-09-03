#!/usr/bin/env python3
"""⑧ 手部专修 · 决定性对照：MeshGraphormer 到底能不能用于二次元图

现象：3 张真·手崩二次元图（手清晰可见 + 确实崩坏）→ MeshGraphormer mask 全部全黑。
素材已排除（上一轮误判已纠正，这批手清晰可见），所以问题在工具本身。

假设：MeshGraphormer/HandRefiner 基于**真人手部数据集**(FreiHAND 等)训练，
      动漫手的形态/纹理/线条与真人差异过大 → 检测器失效。

对照实验：
  A 组 真人手部近景（RealVisXL 生成）→ 若能检测到 = 假设成立，工具仅适用真人
  B 组 二次元手部近景 + 阈值降到 0.1  → 排除"只是阈值太高"

用法: python scripts/probe_handfix_domain.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "agents"))

import requests  # noqa: E402
from comfy_utils import comfy_base_url, wait_images, resolve_comfy_root  # noqa: E402
from go_knives_lora import build_sdxl_clean_workflow  # noqa: E402

OUT = ROOT / "workspace" / "handfix"
REAL_CKPT = "RealVisXL_V5.0_fp16.safetensors"

REAL_CASES = {
    "P1_real_spread": "RAW photo, close up of a young woman's hands, "
                      "fingers spread wide, palms facing camera, "
                      "natural skin texture, soft studio light, 85mm lens, sharp focus",
    "P2_real_interlock": "RAW photo, close up of a young woman's hands clasped together, "
                         "fingers interlocked, resting on a table, "
                         "natural skin texture, window light, 85mm lens, sharp focus",
}
REAL_NEG = ("anime, illustration, cartoon, painting, drawing, 3d render, cgi, doll, "
            "worst quality, low quality, blurry, watermark, text")


def gen_real(base, root):
    """生成真人手部近景素材。"""
    made = []
    for name, subj in REAL_CASES.items():
        dst = OUT / f"{name}.png"
        if dst.is_file() and dst.stat().st_size > 1024:
            print(f"[gen] {name} skip"); made.append(dst); continue
        wf = build_sdxl_clean_workflow(
            subj, negative_prompt=REAL_NEG, ckpt=REAL_CKPT,
            width=1024, height=1024, steps=30, cfg=4.5, seed=777,
            sampler="dpmpp_2m", scheduler="karras",
            filename_prefix=f"{name}_{int(time.time())}")
        r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=30)
        if r.status_code != 200:
            print(f"[gen] {name} FAIL {r.text[:200]}"); continue
        imgs = wait_images(r.json()["prompt_id"], base, timeout_s=400.0)
        if not imgs:
            print(f"[gen] {name} NO IMAGE"); continue
        sub, fn = imgs[0]
        s = root / "output" / (sub or "") / fn
        if s.is_file():
            OUT.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(s.read_bytes())
            made.append(dst)
            print(f"[gen] {name} ok")
    return made


def detect(base, root, label, src: Path, thr: float):
    with open(src, "rb") as f:
        up = requests.post(f"{base}/upload/image",
                           files={"image": (src.name, f, "image/png")},
                           data={"overwrite": "true"}, timeout=60).json()["name"]
    wf = {
        "10": {"class_type": "LoadImage", "inputs": {"image": up}},
        "20": {"class_type": "MeshGraphormer-DepthMapPreprocessor",
               "inputs": {"image": ["10", 0], "resolution": 1024,
                          "mask_bbox_padding": 30, "mask_type": "based_on_depth",
                          "mask_expand": 5, "rand_seed": 88,
                          "detect_thr": thr, "presence_thr": thr}},
        "22": {"class_type": "MaskToImage", "inputs": {"mask": ["20", 1]}},
        "23": {"class_type": "SaveImage",
               "inputs": {"images": ["22", 0], "filename_prefix": f"{label}_mask"}},
    }
    r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=30)
    if r.status_code != 200:
        print(f"[{label}] SUBMIT FAIL {r.text[:200]}"); return
    imgs = wait_images(r.json()["prompt_id"], base, timeout_s=600.0)
    for sub, fn in (imgs or []):
        s = root / "output" / (sub or "") / fn
        if s.is_file():
            (OUT / f"{label}_mask.png").write_bytes(s.read_bytes())


def main() -> None:
    base = comfy_base_url()
    root = resolve_comfy_root()
    OUT.mkdir(parents=True, exist_ok=True)

    print("=== A 组：生成真人手部素材 ===")
    reals = gen_real(base, root)

    print("\n=== 检测 ===")
    jobs = [(f"A_{p.stem}", p, 0.6) for p in reals]
    jobs += [("B_anime_thr01", ROOT / "workspace" / "hand_src" / "H3_interlock.png", 0.1)]
    for label, src, thr in jobs:
        if not src.is_file():
            print(f"[{label}] 源图缺失"); continue
        t0 = time.time()
        detect(base, root, label, src, thr)
        print(f"[{label}] {time.time()-t0:.0f}s  thr={thr}  src={src.name}")

    from PIL import Image
    import numpy as np
    print("\n── mask 非零像素占比 ──")
    for label, _, thr in jobs:
        p = OUT / f"{label}_mask.png"
        if not p.is_file():
            print(f"  {label:22s} 无输出"); continue
        a = np.array(Image.open(p).convert("L"))
        ratio = (a > 10).mean()
        print(f"  {label:22s} thr={thr}  {ratio*100:6.2f}%  "
              f"{'✅检测到手' if ratio > 0.001 else '❌全黑'}")


if __name__ == "__main__":
    main()
