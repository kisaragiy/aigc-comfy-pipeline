"""颜色守恒量化探针 — 头部区域取样统计（R4 判定辅助）

颜色是代码可客观判定的（不同于结构崩坏只能人眼）——本探针给组间可比数字，
最终归属仍由人眼复核（头发/发带/背景在同一取样框内，粗糙但同构图同seed组间可比）。

指标（头部近似框 x∈[0.25,0.75] y∈[0.05,0.40]）：
  dark_ratio  : 暗低饱和像素占比 → 黑发守恒指标（越高越黑）
  warm_ratio  : 暖橙红高饱和占比 → 被夕阳染色指标（越低越好）
  red_ratio   : 纯红高饱和占比   → 红发带存在指标（需要一定占比但不宜过高）
"""
from __future__ import annotations
import colorsys, json, sys
from pathlib import Path
from PIL import Image

BOX = (0.25, 0.05, 0.75, 0.40)

def probe(path: str) -> dict:
    im = Image.open(path).convert("RGB")
    W, H = im.size
    x0, y0, x1, y1 = int(BOX[0]*W), int(BOX[1]*H), int(BOX[2]*W), int(BOX[3]*H)
    crop = im.crop((x0, y0, x1, y1)).resize((160, 160), Image.BILINEAR)
    px = list(crop.getdata())
    n = len(px)
    dark = warm = red = 0
    for r, g, b in px:
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        hd = h*360
        if v < 0.38 and s < 0.45:
            dark += 1
        if s > 0.45 and v > 0.30 and (hd < 45 or hd > 330):
            warm += 1
            if s > 0.55 and (hd < 15 or hd > 345):
                red += 1
    return {"dark_ratio": round(dark/n, 3), "warm_ratio": round(warm/n, 3), "red_ratio": round(red/n, 3)}

if __name__ == "__main__":
    mf = Path(sys.argv[1] if len(sys.argv) > 1 else
              "C:/Users/zwq/aigc-comfy-pipeline/workspace/diag_color/manifest.json")
    m = json.loads(mf.read_text(encoding="utf-8"))
    rows = {}
    for it in m:
        if not it.get("file"):
            continue
        st = probe(it["file"])
        it.update(st)
        rows.setdefault(it["tag"], []).append(st)
    mf.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f'{"组":14s} {"dark(黑发↑)":>12s} {"warm(染色↓)":>12s} {"red(发带)":>10s}')
    for tag in sorted(rows):
        v = rows[tag]
        avg = lambda k: sum(x[k] for x in v)/len(v)  # noqa: E731
        print(f'{tag:14s} {avg("dark_ratio"):12.3f} {avg("warm_ratio"):12.3f} {avg("red_ratio"):10.3f}')
