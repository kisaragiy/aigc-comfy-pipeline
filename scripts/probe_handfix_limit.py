#!/usr/bin/env python3
"""⑧ 手部专修 · 检测能力边界测试

第一次测试发现：E0(手彻底融化成黑团) → MeshGraphormer 输出全黑，检测不到手。
推断：HandRefiner 修的是「能认出是手但画错」，修不了「完全没有手」。

本脚本验证该推断，三组对照：
  T1 E0 + 阈值降到 0.3        —— 融化的手，降阈值能否救回
  T2 E4_F_softedge + 默认0.6  —— 畸形但形状可辨的手（HandRefiner 的目标场景）
  T3 st028 + 默认0.6          —— 正常清晰的手（阳性对照，验证工具本身正常）

T3 若也检测不到 = 工具/参数有问题；T3 能检测到而 T1 不能 = 推断成立。
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

OUT = ROOT / "workspace" / "handfix"

# (标签, 源图, detect_thr, presence_thr)
# 2026-08-31 重做：原用 E0/E4 是误判素材（图里根本没有可见的手），全部替换为
# make_hand_source.py 造出的真·手崩样本（手清晰可见 + 确实崩坏）
CASES = [
    ("R1_interlock", ROOT / "workspace" / "hand_src" / "H3_interlock.png", 0.6, 0.6),
    ("R2_reach", ROOT / "workspace" / "hand_src" / "H5_reach.png", 0.6, 0.6),
    ("R3_spread", ROOT / "workspace" / "hand_src" / "H1_spread.png", 0.6, 0.6),
]


def main() -> None:
    base = comfy_base_url()
    root = resolve_comfy_root()
    OUT.mkdir(parents=True, exist_ok=True)
    for label, src, dthr, pthr in CASES:
        if not src.is_file():
            print(f"[skip] {label} 源图不存在 {src}"); continue
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
                              "detect_thr": dthr, "presence_thr": pthr}},
            "21": {"class_type": "SaveImage",
                   "inputs": {"images": ["20", 0], "filename_prefix": f"{label}_depth"}},
            "22": {"class_type": "MaskToImage", "inputs": {"mask": ["20", 1]}},
            "23": {"class_type": "SaveImage",
                   "inputs": {"images": ["22", 0], "filename_prefix": f"{label}_mask"}},
        }
        r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=30)
        if r.status_code != 200:
            print(f"[{label}] SUBMIT FAIL {r.text[:300]}"); continue
        t0 = time.time()
        imgs = wait_images(r.json()["prompt_id"], base, timeout_s=600.0)
        got = 0
        for sub, fn in (imgs or []):
            s = root / "output" / (sub or "") / fn
            if s.is_file():
                tag = "depth" if "_depth_" in fn else "mask"
                (OUT / f"{label}_{tag}.png").write_bytes(s.read_bytes())
                got += 1
        print(f"[{label}] {time.time()-t0:.0f}s  产出{got}张  src={src.name}")

    # 用像素统计判断是否真的检测到手（全黑=没检测到）
    from PIL import Image
    import numpy as np
    print("\n── mask 非零像素占比（0% = 没检测到手）──")
    for label, _, _, _ in CASES:
        p = OUT / f"{label}_mask.png"
        if not p.is_file():
            print(f"  {label:20s} 无输出"); continue
        a = np.array(Image.open(p).convert("L"))
        ratio = (a > 10).mean()
        print(f"  {label:20s} {ratio*100:6.2f}%  {'✅检测到' if ratio > 0.001 else '❌全黑'}")


if __name__ == "__main__":
    main()
