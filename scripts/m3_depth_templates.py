"""M3 方案A' v2 — 语义深度模板改进（真实物体轮廓感）

v1 模板太"示意图"（生硬矩形），ControlNet 的 depth 是从明暗结构学近远关系的，
得让明暗块有"这是人/这是车"的可辨识形状，才传得了语义。

改进要点（人前景/车后景 fgbg）：
  - 前景人物：头(圆)+肩(弧)+躯干(梯形)，白亮=近，带轻微光晕
  - 后景电车：横向长条带轮子/车窗纵格，暗灰=远，位置偏上占中景
  - 背景天空/建筑：更暗，带一点纵向渐变，制造纵深
  用高斯模糊让边缘柔和，避免生硬。

产物仍只是"理想深度图"——直接喂 ControlNet depth（不走草图、不走 DepthAnything）。
"""
from __future__ import annotations

import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "workspace" / "depth_templates_v2"
W, H = 1344, 768


def gradient(floor: int, ceil: int, img=None) -> Image.Image:
    img = img or Image.new("L", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        v = int(floor + (ceil - floor) * y / H)
        d.line([(0, y), (W, y)], fill=v)
    return img


def fgbg_person_foreground() -> Image.Image:
    """语义：人前景(近·亮) / 车后景(远·暗)。"""
    img = gradient(20, 110)  # 背景整体偏暗
    d = ImageDraw.Draw(img)
    # --- 远景：天空(更暗) + 建筑剪影 ---
    d.rectangle([0, 0, W, int(H*0.30)], fill=18)
    for x in range(0, W, 150):
        d.rectangle([x, int(H*0.12), x+70, int(H*0.30)], fill=36)
    # --- 中景：电车（横向长条，带车窗纵格）---
    d.rounded_rectangle([int(W*0.05), int(H*0.34), int(W*0.92), int(H*0.58)],
                        radius=40, fill=70)
    for x in range(int(W*0.10), int(W*0.86), 60):
        d.rounded_rectangle([x, int(H*0.37), x+42, int(H*0.55)], radius=12, fill=52)
    # 电车下沿轮子暗块
    for x in range(int(W*0.12), int(W*0.80), 170):
        d.ellipse([x, int(H*0.56), x+70, int(H*0.62)], fill=30)
    # --- 前景：人物（右下，白亮=近）---
    px, py = int(W*0.66), int(H*0.44)
    d.ellipse([px, py, px+int(W*0.13), py+int(H*0.22)], fill=248)          # 头
    d.pieslice([px-int(W*0.14), py+int(H*0.20), px+int(W*0.30), py+int(H*0.34)],
               180, 360, fill=240)                                          # 肩
    d.rounded_rectangle([px+int(W*0.02), py+int(H*0.26), px+int(W*0.16), py+int(H*0.90)],
                        radius=40, fill=245)                                # 躯干
    # 人物周圈微光晕，强化"近"
    glow = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(glow)
    gd.ellipse([px-int(W*0.10), py-int(H*0.08), px+int(W*0.24), py+int(H*0.98)], fill=90)
    img = Image.composite(img, Image.blend(img, glow, 0.0), Image.new("L", (W, H), 0))
    return Image.blend(img, glow, 0.18)


def updown_contain() -> Image.Image:
    """语义：包在桌上(上·远·暗) / 猫在桌下(下·近·亮)。"""
    img = gradient(28, 120)
    d = ImageDraw.Draw(img)
    # 桌面横板(顶部，远)：深
    d.rectangle([0, 0, W, int(H*0.46)], fill=60)
    # 桌上"包"：亮块(桌面上的高光物体)
    d.rounded_rectangle([int(W*0.14), int(H*0.14), int(W*0.36), int(H*0.34)], radius=18, fill=208)
    d.rounded_rectangle([int(W*0.16), int(H*0.16), int(W*0.34), int(H*0.32)], radius=16, fill=238)
    # 桌沿(中带，暗)
    d.rectangle([0, int(H*0.44), W, int(H*0.52)], fill=40)
    # 桌下"猫"：近亮剪影
    cx, cy = int(W*0.58), int(H*0.70)
    d.ellipse([cx, cy, cx+int(W*0.17), cy+int(H*0.24)], fill=235)          # 头
    d.rounded_rectangle([cx-int(W*0.02), cy+int(H*0.20), cx+int(W*0.19), cy+int(H*0.34)],
                        radius=26, fill=240)                                # 身
    return img


def two_person_foreback() -> Image.Image:
    """语义：矮个在前(近·亮·低) / 高个在后(远·稍暗·高)。"""
    img = gradient(45, 125)
    d = ImageDraw.Draw(img)
    # 后(高)人：稍暗，高
    hx, hy = int(W*0.32), int(H*0.14)
    d.ellipse([hx, hy, hx+int(W*0.13), hy+int(H*0.22)], fill=150)
    d.rounded_rectangle([hx-int(W*0.02), hy+int(H*0.20), hx+int(W*0.15), hy+int(H*0.92)],
                        radius=40, fill=120)
    # 前(矮)人：亮，低左
    fx, fy = int(W*0.12), int(H*0.34)
    d.ellipse([fx, fy, fx+int(W*0.14), fy+int(H*0.24)], fill=245)
    d.rounded_rectangle([fx-int(W*0.03), fy+int(H*0.22), fx+int(W*0.17), fy+int(H*0.98)],
                        radius=42, fill=248)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in [("fgbg", fgbg_person_foreground),
                     ("updown", updown_contain),
                     ("twodepth", two_person_foreback)]:
        img = fn().filter(ImageFilter.GaussianBlur(2.2))  # 更柔的过渡
        p = OUT / f"depth_{name}.png"
        img.save(p)
        print(f"  {name} -> {p}")
    print(f"[templates-v2] 完成，目录={OUT}")


if __name__ == "__main__":
    main()
