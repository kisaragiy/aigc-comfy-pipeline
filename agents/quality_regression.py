#!/usr/bin/env python3
"""
quality_regression.py — 质量判据回归库 (正负样本校准)

【用途】持续校准 quality_judge 判据阈值。核心原则（2026-08-24 教训）：
  output/ 目录 AI 生成图均非商业立绘——真商业立绘基准在 kohya_ss/train_data/。
  用正样本(真商业立绘) + 负样本(AI仿立绘)对比判据分布，确认判据不误杀真图。

【用法】
  python quality_regression.py               # 跑默认样本库
  python quality_regression.py --pos DIR --neg DIR   # 自定义样本

【输出】每项判据在正/负样本上的分布 + 误杀率(真图被判fail比例, 越低越好)
"""
from __future__ import annotations

import argparse
import glob
import os
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from quality_judge import judge

# 默认样本库
DEFAULT_POS = [
    r"C:\Users\zwq\kohya_ss\train_data\elisabeth\1_elisabeth\*.png",
    r"C:\Users\zwq\kohya_ss\train_data\elisabeth\1_elisabeth\*.jpg",
]
DEFAULT_NEG = [
    r"C:\Users\zwq\aigc-comfy-pipeline\outputs\2026-08-22_2*-workshop-create\images\pipeline_create_01_002*.png",
]


def collect(globs: list[str]) -> list[str]:
    seen, out = set(), []
    for g in globs:
        for p in sorted(glob.glob(g)):
            if p not in seen:
                seen.add(p)
                out.append(p)
    return out


def run(label: str, paths: list[str]) -> dict:
    metrics = {"sharpness": [], "detail_density": [], "blank_ratio": []}
    fails = []
    pass_cnt = 0
    for p in paths:
        try:
            res = judge(p)
            m = res.get("metrics", {})
            for k in metrics:
                metrics[k].append(m.get(k, 0))
            if res.get("verdict") == "fail":
                fails.append(Path(p).name)
            else:
                pass_cnt += 1
        except Exception:
            continue
    n = len(paths)
    return {
        "label": label, "n": n, "pass": pass_cnt, "fail": n - pass_cnt,
        "fail_rate": (n - pass_cnt) / max(1, n),
        "metrics": metrics, "fails": fails,
    }


def report(res: dict) -> None:
    print(f"\n=== {res['label']} ({res['n']} 张) ===")
    print(f"  pass={res['pass']}  fail={res['fail']}  误杀率={res['fail_rate']*100:.0f}%")
    ms = res["metrics"]
    for k, vals in ms.items():
        if vals:
            print(f"  {k:<16} 中位={statistics.median(vals):.0f} "
                  f"min={min(vals):.0f} max={max(vals):.0f}")
    if res["fails"]:
        print(f"  被判fail: {res['fails'][:6]}{'...' if len(res['fails'])>6 else ''}")


def main() -> None:
    ap = argparse.ArgumentParser(description="质量判据回归库")
    ap.add_argument("--pos", action="append", default=DEFAULT_POS, help="正样本 glob")
    ap.add_argument("--neg", action="append", default=DEFAULT_NEG, help="负样本 glob")
    args = ap.parse_args()

    pos = collect(args.pos)
    neg = collect(args.neg)
    print(f"正样本(真商业立绘): {len(pos)} 张  负样本(AI仿立绘): {len(neg)} 张")

    rp = run("正样本·真商业立绘", pos)
    rn = run("负样本·AI仿立绘", neg)
    report(rp)
    report(rn)

    # 关键结论: 正样本误杀率(应低) vs 负样本检出率(应高)
    print(f"\n=== 校准结论 ===")
    print(f"  正样本误杀率: {rp['fail_rate']*100:.0f}%  (真商业立绘被判fail, 应≈0)")
    print(f"  负样本fail率: {rn['fail_rate']*100:.0f}%  (AI图被判fail, 应高)")
    if rp["fail_rate"] > 0.3:
        print("  ⚠️ 正样本误杀率>30% → 判据过严, 会误杀真商业立绘, 需调阈值!")
    if rn["fail_rate"] < 0.5:
        print("  ⚠️ 负样本fail率<50% → 判据过松, 拦不住AI仿立绘, 需调阈值!")


if __name__ == "__main__":
    main()
