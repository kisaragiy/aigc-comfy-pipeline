#!/usr/bin/env python3
"""把一组图拼成带标签的网格图（盲测/对照实验通用）。

用法:
  python scripts/make_grid.py <目录> <输出.jpg> [--cols N] [--width W] [--pattern glob]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def load_font(size: int):
    for p in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
              r"C:\Windows\Fonts\arial.ttf"]:
        try:
            return ImageFont.truetype(p, size)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("srcdir")
    ap.add_argument("out")
    ap.add_argument("--cols", type=int, default=6)
    ap.add_argument("--width", type=int, default=420, help="每格宽度")
    ap.add_argument("--pattern", default="*.png")
    args = ap.parse_args()

    files = sorted(Path(args.srcdir).glob(args.pattern))
    if not files:
        print("no images"); sys.exit(1)

    label_h = 34
    cell_w = args.width
    thumbs = []
    for f in files:
        im = Image.open(f).convert("RGB")
        ratio = cell_w / im.width
        im = im.resize((cell_w, int(im.height * ratio)), Image.LANCZOS)
        thumbs.append((f.stem, im))

    cell_h = max(im.height for _, im in thumbs) + label_h
    cols = min(args.cols, len(thumbs))
    rows = (len(thumbs) + cols - 1) // cols

    canvas = Image.new("RGB", (cols * cell_w, rows * cell_h), (24, 24, 28))
    draw = ImageDraw.Draw(canvas)
    font = load_font(22)

    for i, (name, im) in enumerate(thumbs):
        r, c = divmod(i, cols)
        x, y = c * cell_w, r * cell_h
        draw.text((x + 8, y + 6), name, fill=(255, 220, 120), font=font)
        canvas.paste(im, (x, y + label_h))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, quality=92)
    print(f"[grid] {len(thumbs)} imgs, {cols}x{rows} -> {out}  ({canvas.size[0]}x{canvas.size[1]})")


if __name__ == "__main__":
    main()
