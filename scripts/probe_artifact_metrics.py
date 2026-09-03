#!/usr/bin/env python3
"""探针：找能区分「高频噪点/撕裂型故障」的量化指标。

背景（2026-08-31 实测）：现有 quality_judge 的锐度(拉普拉斯方差)/细节密度对
IPAdapter 过冲产生的撕裂图**完全失明且指标反向**——
  E0 撕裂图 锐度 7288(最高) / E8 干净图 锐度 1315(最低) → 按锐度选图会选中废图。

本脚本计算多个候选指标，用已知 ground truth 验证哪个指标能把故障图和干净图分开。

Ground truth（人眼判定，见 knowledge/aigc/ipadapter-rootcause-20260831.md）：
  BAD  : E0(红边噪点/结构撕裂/手融化), E4(整图黄绿撕裂/面部崩坏/多手)
  WARN : E5(绿色偏), E6(手指诡异但结构正常)
  GOOD : E1, E2, E3, E7, E8

候选指标（均为无参考指标，对标 IQA 常规做法）：
  chroma_edge_mismatch : RGB 通道边缘图的不一致度 —— 色差撕裂的直接特征
  hf_energy_ratio      : FFT 高频能量占比 —— 噪点越多越高
  edge_density         : Canny 边缘像素占比 —— 碎边缘越多越高
  local_var_dispersion : 局部方差的变异系数 —— 撕裂导致空间不均匀
  sat_p99              : 饱和度 99 分位 —— 抓过饱和色带
  colorfulness         : Hasler-Süsstrunk 色彩丰富度

用法：
  python scripts/probe_artifact_metrics.py workspace/ipa_rootcause
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

try:
    import cv2
except ImportError:
    cv2 = None

GROUND_TRUTH = {
    "E0_baseline_linear": "BAD",
    "E4_scaling_Vonly": "BAD",
    "E5_preset_standard": "WARN",
    "E6_ckpt_wai": "WARN",
    "E1_style_transfer": "GOOD",
    "E2_composition": "GOOD",
    "E3_weight_025": "GOOD",
    "E7_end_at_04": "GOOD",
    "E8_no_ipadapter": "GOOD",
}


def metrics(path: Path) -> dict:
    im = Image.open(path).convert("RGB")
    # 统一缩放，消除分辨率影响
    im = im.resize((512, int(512 * im.height / im.width)), Image.LANCZOS)
    a = np.asarray(im).astype(np.float32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    gray = (0.299 * r + 0.587 * g + 0.114 * b)

    out: dict[str, float] = {}

    # ① 通道边缘不一致度：色差撕裂时 R/G/B 的边缘位置对不上
    def sobel(ch):
        gx = np.abs(np.diff(ch, axis=1, prepend=ch[:, :1]))
        gy = np.abs(np.diff(ch, axis=0, prepend=ch[:1, :]))
        return np.hypot(gx, gy)

    er, eg, eb = sobel(r), sobel(g), sobel(b)
    emax = np.maximum.reduce([er, eg, eb]) + 1e-6
    mism = (np.abs(er - eg) + np.abs(eg - eb) + np.abs(er - eb)) / (3 * emax)
    strong = emax > np.percentile(emax, 85)           # 只在强边缘处统计
    out["chroma_edge_mismatch"] = float(mism[strong].mean())

    # ② FFT 高频能量占比
    f = np.fft.fftshift(np.abs(np.fft.fft2(gray)))
    h, w = f.shape
    cy, cx = h // 2, w // 2
    yy, xx = np.ogrid[:h, :w]
    rad = np.hypot(yy - cy, xx - cx)
    rmax = rad.max()
    out["hf_energy_ratio"] = float(f[rad > 0.35 * rmax].sum() / (f.sum() + 1e-9))

    # ③ Canny 边缘密度
    if cv2 is not None:
        edges = cv2.Canny(gray.astype(np.uint8), 80, 180)
        out["edge_density"] = float((edges > 0).mean())
    else:
        out["edge_density"] = float("nan")

    # ④ 局部方差的变异系数（撕裂 → 空间分布极不均匀）
    k = 16
    hh, ww = gray.shape[0] // k * k, gray.shape[1] // k * k
    blocks = gray[:hh, :ww].reshape(hh // k, k, ww // k, k).transpose(0, 2, 1, 3)
    bv = blocks.reshape(-1, k * k).var(axis=1)
    out["local_var_dispersion"] = float(bv.std() / (bv.mean() + 1e-9))

    # ⑤ 饱和度 99 分位
    mx, mn = a.max(axis=2), a.min(axis=2)
    sat = (mx - mn) / (mx + 1e-6)
    out["sat_p99"] = float(np.percentile(sat, 99))

    # ⑥ Hasler-Süsstrunk colorfulness
    rg = r - g
    yb = 0.5 * (r + g) - b
    out["colorfulness"] = float(
        np.hypot(rg.std(), yb.std()) + 0.3 * np.hypot(rg.mean(), yb.mean()))

    # ⑦ 参照：现有判据（拉普拉斯方差）
    lap = (gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2]
           + gray[1:-1, 2:] - 4 * gray[1:-1, 1:-1])
    out["laplacian_var(现有)"] = float(lap.var())
    return out


def main() -> None:
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "workspace/ipa_rootcause")
    rows = []
    for f in sorted(src.glob("E*.png")):
        gt = GROUND_TRUTH.get(f.stem, "?")
        rows.append((f.stem, gt, metrics(f)))
    if not rows:
        print("no images"); return

    keys = list(rows[0][2])
    hdr = f"{'image':22s} {'GT':5s}" + "".join(f"{k[:19]:>21s}" for k in keys)
    print(hdr); print("-" * len(hdr))
    for name, gt, m in sorted(rows, key=lambda x: (x[1] != "BAD", x[0])):
        print(f"{name:22s} {gt:5s}" + "".join(f"{m[k]:21.4f}" for k in keys))

    # 判别力：BAD 组 vs GOOD 组的分离度（越大越好，>1 表示可分）
    print("\n判别力（|均值差| / 合并标准差，>1.0 = 有区分度，>2.0 = 强区分）:")
    for k in keys:
        bad = [m[k] for _, gt, m in rows if gt == "BAD"]
        good = [m[k] for _, gt, m in rows if gt == "GOOD"]
        if len(bad) < 2 or len(good) < 2:
            continue
        pooled = np.sqrt((np.var(bad) + np.var(good)) / 2) + 1e-9
        d = abs(np.mean(bad) - np.mean(good)) / pooled
        flag = "★★ 强" if d > 2 else ("★ 可用" if d > 1 else "  弱")
        direction = "BAD更高" if np.mean(bad) > np.mean(good) else "BAD更低"
        print(f"  {k:24s} d={d:6.2f}  {flag:8s} ({direction}: "
              f"BAD均值={np.mean(bad):.4f} GOOD均值={np.mean(good):.4f})")


if __name__ == "__main__":
    main()
