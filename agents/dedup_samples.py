#!/usr/bin/env python3
"""清理商业立绘样本库：内容哈希去重 + 移除低质小图。

用法: python dedup_samples.py [--dir <样本目录>] [--min-size 512]
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path

from PIL import Image


def main() -> None:
    ap = argparse.ArgumentParser(description="样本库去重清理")
    ap.add_argument("--dir", default=r"C:\Users\zwq\kohya_ss\train_data\commercial_samples")
    ap.add_argument("--min-size", type=int, default=512, help="最短边下限(px)")
    args = ap.parse_args()

    d = Path(args.dir)
    files = sorted(d.glob("*"))
    print(f"清理前: {len(files)} 张")

    seen: dict[str, Path] = {}
    removed = 0
    for f in files:
        # 1. 内容哈希去重
        h = hashlib.md5(f.read_bytes()).hexdigest()
        if h in seen:
            print(f"  去重删除: {f.name} (同 {seen[h].name})")
            f.unlink()
            removed += 1
            continue
        seen[h] = f
        # 2. 尺寸过滤
        try:
            with Image.open(f) as im:
                if min(im.size) < args.min_size:
                    print(f"  小图删除: {f.name} ({im.size})")
                    f.unlink()
                    removed += 1
        except Exception as e:
            print(f"  损坏删除: {f.name} ({str(e)[:40]})")
            f.unlink()
            removed += 1

    remain = sorted(d.glob("*"))
    print(f"清理后: {len(remain)} 张 (删除 {removed})")


if __name__ == "__main__":
    main()
