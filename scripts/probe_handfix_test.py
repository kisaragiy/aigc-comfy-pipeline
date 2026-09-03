#!/usr/bin/env python3
"""⑧ 手部专修 · 第一步：验证 MeshGraphormer 能否用（需下载 ~650MB 模型）

MeshGraphormer-DepthMapPreprocessor 输出 [IMAGE(手部深度图), MASK(手部区域)]，
配 depth ControlNet + inpaint 即 HandRefiner 标准方案：**只重画手部，其余像素不动**。

本脚本只跑预处理器，验证：① 模型能否下载 ② 手融化的图能否检测到手。
失败则走备选（OpenPose hand_pose_model 已在本机，可从 POSE_KEYPOINT 取手部坐标自建 mask）。
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

SRC = ROOT / "workspace" / "ipa_rootcause" / "E0_baseline_linear.png"
OUT = ROOT / "workspace" / "handfix"


def main() -> None:
    base = comfy_base_url()
    with open(SRC, "rb") as f:
        up = requests.post(f"{base}/upload/image",
                           files={"image": (SRC.name, f, "image/png")},
                           data={"overwrite": "true"}, timeout=60).json()["name"]
    print(f"[upload] {SRC.name}")

    wf = {
        "10": {"class_type": "LoadImage", "inputs": {"image": up}},
        "20": {"class_type": "MeshGraphormer-DepthMapPreprocessor",
               "inputs": {"image": ["10", 0], "resolution": 1024,
                          "mask_bbox_padding": 30, "mask_type": "based_on_depth",
                          "mask_expand": 5, "rand_seed": 88,
                          "detect_thr": 0.6, "presence_thr": 0.6}},
        "21": {"class_type": "SaveImage",
               "inputs": {"images": ["20", 0], "filename_prefix": "HANDTEST_depth"}},
        "22": {"class_type": "MaskToImage", "inputs": {"mask": ["20", 1]}},
        "23": {"class_type": "SaveImage",
               "inputs": {"images": ["22", 0], "filename_prefix": "HANDTEST_mask"}},
    }
    r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=30)
    print("submit:", r.status_code, "" if r.status_code == 200 else r.text[:400])
    if r.status_code != 200:
        return
    t0 = time.time()
    imgs = wait_images(r.json()["prompt_id"], base, timeout_s=1500.0)
    print(f"耗时 {time.time()-t0:.0f}s  产出 {len(imgs) if imgs else 0} 张")
    root = resolve_comfy_root()
    OUT.mkdir(parents=True, exist_ok=True)
    for sub, fn in (imgs or []):
        s = root / "output" / (sub or "") / fn
        if s.is_file():
            (OUT / fn).write_bytes(s.read_bytes())
            print("  ->", fn)


if __name__ == "__main__":
    main()
