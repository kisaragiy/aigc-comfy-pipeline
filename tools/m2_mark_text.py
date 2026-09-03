"""M2 后处理贴字工具 — AI 无字图 → 场景化英文嵌入

M2 死穴：AI 画面内嵌英文 5 字母以上全崩（MAGIC/RAMEN 0/4）。
正解（与泪痣/add_tear_mole 同理）：AI 出无字图 → PIL 后期贴真实字体文字。
biztext 为中文封面标题、固定位置；本脚本补 M2 的"画面内英文嵌字"：
  - 按场景选字体：店招/霓虹=加粗无衬线(Sans)，书封/书名=衬线(Serif)
  - 支持旋转/透视(perspective)、描边(双色)、发光(霓虹用)
  - 锚点按场景默认（招牌=中上，书封=中，霓虹=中线偏上）

用法:
  python tools/m2_mark_text.py <图> "CAFE" --scene sign   # 店招
  python tools/m2_mark_text.py <图> "MAGIC" --scene book   # 书封
  python tools/m2_mark_text.py <图> "RAMEN" --scene neon   # 霓虹
  --x 0.5 --y 0.32 --font-size 120 --rotation -4 --out out.png
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PROJ = Path(__file__).resolve().parent.parent

FONTS = {
    # 无衬线（店招/霓虹/现代）
    "sans_bold": "C:/Windows/Fonts/arialbd.ttf",
    "sans": "C:/Windows/Fonts/arial.ttf",
    "impact": "C:/Windows/Fonts/impact.ttf",
    # 衬线（书封/书名/复古）
    "serif": "C:/Windows/Fonts/georgia.ttf",
    "serif_bold": "C:/Windows/Fonts/georgiab.ttf",
}
# 按 scene 默认：font/位置/颜色/是否发光/是否透视
SCENES = {
    "sign": dict(font="sans_bold", color=(255, 255, 255), glow=0.0, rot=0,
                 x=0.5, y=0.30, size=0.16, stroke=(0, 0, 0), perspective=False,
                 desc="店招（无衬线粗体+黑描边）"),
    "neon": dict(font="impact", color=(255, 90, 120), glow=1.6, rot=0,
                 x=0.5, y=0.32, size=0.20, stroke=(40, 0, 20), perspective=False,
                 desc="霓虹（大字+发光+粉红）"),
    "book": dict(font="serif_bold", color=(40, 30, 20), glow=0.0, rot=0,
                 x=0.5, y=0.50, size=0.14, stroke=(230, 220, 190), perspective=True,
                 desc="书封（衬线+浅描边+微透视）"),
    "shelf": dict(font="serif", color=(200, 190, 170), glow=0.0, rot=-2,
                  x=0.5, y=0.55, size=0.12, stroke=(30, 25, 20), perspective=False,
                  desc="门牌/标牌（衬线+轻微上斜）"),
}


def _load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = FONTS.get(name, FONTS["sans_bold"])
    return ImageFont.truetype(path, size)


def _text_measure(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def draw_text_perspective(img: Image.Image, text: str, font, center, width, height,
                          fill, stroke=None, stroke_width=0, glow=0.0, perspective=False,
                          rot=0.0):
    """在透明层画文字，支持旋转/透视/发光（霓虹）。"""
    # 独立透明层
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = center
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = int(cx - tw / 2)
    ty = int(cy - th / 2)

    if glow > 0:
        # 发光：多次放大模糊 + 稀释
        glow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow_layer)
        gd.text((tx, ty), text, font=font, fill=(*fill, 200), stroke_width=int(font.size * 0.12),
                stroke_fill=(*fill, 200))
        glow_layer = glow_layer.filter(__import__("PIL.ImageFilter", fromlist=["ImageFilter"]).GaussianBlur(6))
        # 多次叠加增强辉光
        for _ in range(int(glow * 2)):
            layer = Image.alpha_composite(layer, glow_layer)
        d = ImageDraw.Draw(layer)

    if stroke:
        d.text((tx, ty), text, font=font, fill=(*fill, 255),
               stroke_width=stroke_width or max(2, font.size // 20), stroke_fill=(*stroke, 255))
    else:
        d.text((tx, ty), text, font=font, fill=(*fill, 255))

    # 旋转
    if rot:
        layer = layer.rotate(rot, expand=False, resample=Image.BICUBIC)
    # 透视（简单的水平梯形压缩——书封侧视感）
    if perspective:
        # 用 transform 做顶部收紧（书脊透视）
        w, h = img.size
        layer = layer.transform((w, h), Image.PERSPECTIVE,
                                (1, 0, 0, 0.08, 1, 0, 0, 0.0002),
                                resample=Image.BICUBIC)
    return layer


def mark_text(image_path: str, text: str, scene: str, *, x=None, y=None,
              font_size=None, rotation=None, out=None, opacity=1.0) -> str:
    img = Image.open(image_path).convert("RGB")
    sc = SCENES[scene]
    w, h = img.size
    cx = (x if x is not None else sc["x"]) * w
    cy = (y if y is not None else sc["y"]) * h
    size = font_size or int(max(w, h) * sc["size"])
    font = _load_font(sc["font"], size)
    draw = ImageDraw.Draw(img)
    rot = rotation if rotation is not None else sc["rot"]

    layer = draw_text_perspective(img, text, font, (cx, cy), w, h, sc["color"],
                                  stroke=sc["stroke"], glow=sc["glow"],
                                  perspective=sc["perspective"], rot=rot)
    if opacity < 1.0:
        a = layer.split()[3].point(lambda p: int(p * opacity))
        layer.putalpha(a)
    img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")

    out = out or str(Path(image_path).with_name(f"{Path(image_path).stem}_text_{scene}.png"))
    img.save(out)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("text", help="要贴的字（英文）")
    ap.add_argument("--scene", default="sign", choices=list(SCENES.keys()),
                    help=f"场景：{', '.join(sc for sc in SCENES)}")
    ap.add_argument("--x", type=float, default=None, help="文字中心x比例 0-1")
    ap.add_argument("--y", type=float, default=None, help="文字中心y比例 0-1")
    ap.add_argument("--font-size", type=int, default=None)
    ap.add_argument("--rotation", type=float, default=None, help="旋转角度（度，负=上斜）")
    ap.add_argument("--opacity", type=float, default=1.0)
    ap.add_argument("--font", default=None, help="覆盖字体名（sans_bold等）")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    if args.font:
        SCENES[args.scene]["font"] = args.font
    print(f"[m2-mark] scene={args.scene} ({SCENES[args.scene]['desc']}) 贴 '{args.text}'")
    out = mark_text(args.image, args.text, args.scene, x=args.x, y=args.y,
                    font_size=args.font_size, rotation=args.rotation,
                    out=args.out, opacity=args.opacity)
    print(f"  -> {out}")


if __name__ == "__main__":
    main()
