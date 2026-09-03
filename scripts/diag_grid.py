"""诊断集判定辅助 — 按类别拼网格图（P0-2）

分层判定策略（依据 B 阶段结论：本地VLM判质不可靠，人眼/主模型vision是最终裁判）：
  第一层 网格总览：数量/空间/颜色串位/要素缺失 → 缩略图足够判定
  第二层 单张放大：手指结构/画面内文字拼写 → 必须原图细看

用法:
  python scripts/diag_grid.py            # 全类别出网格
  python scripts/diag_grid.py --cat D4   # 单类
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
DIAG = ROOT / "workspace" / "diag"
CELL_W = 620          # 每格宽度（保证数人/辨色够看）
LABEL_H = 34
COLS = 4


def build_grid(items: list[dict], out: Path, title: str) -> Path | None:
    cells = [it for it in items if it.get("file") and Path(it["file"]).exists()]
    if not cells:
        return None
    thumbs = []
    for it in cells:
        im = Image.open(it["file"]).convert("RGB")
        h = int(im.height * CELL_W / im.width)
        thumbs.append((it, im.resize((CELL_W, h), Image.LANCZOS)))

    rows = (len(thumbs) + COLS - 1) // COLS
    row_h = [max(t[1].height for t in thumbs[r * COLS:(r + 1) * COLS]) + LABEL_H for r in range(rows)]
    W = CELL_W * min(COLS, len(thumbs))
    H = sum(row_h)
    canvas = Image.new("RGB", (W, H), (24, 24, 28))
    d = ImageDraw.Draw(canvas)
    y = 0
    for r in range(rows):
        x = 0
        for it, im in thumbs[r * COLS:(r + 1) * COLS]:
            d.rectangle([x, y, x + CELL_W, y + LABEL_H], fill=(40, 44, 52))
            d.text((x + 8, y + 10), f'{it["id"]}  seed={it["seed"]}  {it["res"][0]}x{it["res"][1]}',
                   fill=(230, 230, 235))
            canvas.paste(im, (x, y + LABEL_H))
            x += CELL_W
        y += row_h[r]
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, quality=92)
    print(f"{title}: {out}  ({len(thumbs)} 格, {canvas.width}x{canvas.height})")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cat", default=None)
    args = ap.parse_args()
    manifest = json.loads((DIAG / "manifest.json").read_text(encoding="utf-8"))
    cats: dict[str, list[dict]] = {}
    for m in manifest:
        cats.setdefault(m["cat"], []).append(m)
    for cat, items in sorted(cats.items()):
        if args.cat and not cat.startswith(args.cat):
            continue
        items.sort(key=lambda x: (x["id"], x["seed"]))
        build_grid(items, DIAG / "grids" / f"grid_{cat}.jpg", cat)
        # 判定单：把期望打成 markdown 表，人/主模型逐条打勾
        lines = [f"## {cat}\n", "| ID | seed | 期望（二值判定） | PASS/FAIL | 失败模式 |", "|---|---|---|---|---|"]
        seen = set()
        for it in items:
            key = it["id"]
            exp = it["expect"] if key not in seen else "（同上）"
            seen.add(key)
            lines.append(f'| {it["id"]} | {it["seed"]} | {exp} |  |  |')
        (DIAG / "grids" / f"sheet_{cat}.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
