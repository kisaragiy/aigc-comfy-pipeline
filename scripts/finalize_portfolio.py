# -*- coding: utf-8 -*-
"""Restore samples + compress 示例/ workflow screenshots into docs/assets/."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
EXAMPLE_DIR = ROOT / "示例"
ASSETS = ROOT / "docs" / "assets"

sys.path.insert(0, str(SCRIPTS))
import bootstrap_portfolio as bp  # noqa: E402


def compress_examples():
    try:
        from PIL import Image
    except ImportError:
        print("skip example compress: no PIL")
        return

    if not EXAMPLE_DIR.is_dir():
        return

    ASSETS.mkdir(parents=True, exist_ok=True)
    mapping = []
    for i, src in enumerate(sorted(EXAMPLE_DIR.glob("*.png")), start=1):
        if src.stat().st_size < 5000:
            continue
        dst = ASSETS / f"workflow_demo_{i:02d}.jpg"
        im = Image.open(src).convert("RGB")
        im.thumbnail((1280, 960), Image.Resampling.LANCZOS)
        im.save(dst, format="JPEG", quality=85, optimize=True)
        mapping.append(f"{dst.name}\t{src.name}")
        print(f"docs/assets/{dst.name} <- {src.name}")

    if mapping:
        (ASSETS / "sources.txt").write_text("\n".join(mapping) + "\n", encoding="utf-8")


if __name__ == "__main__":
    bp.main()
    compress_examples()
    print("finalize done.")
