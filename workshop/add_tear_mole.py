"""泪痣后处理 v2——画在内眼角下方（用户修正：不是眼下正中）且小
用法: python add_tear_mole.py <图> [--x 0.44] [--y 0.40] [--size 0.0025] [--out 输出]
默认: 内眼角下方 + 小点（视觉约 2-3px @1000 宽）
"""
from PIL import Image, ImageDraw, ImageFilter
import os, argparse

def add_tear_mole(img_path, x, y, size_ratio, out_path):
    img = Image.open(img_path).convert("RGB")
    W, H = img.size
    cx, cy = int(x * W), int(y * H)
    r = max(2, int(size_ratio * H))
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    # 深棕黑小点（比纯黑自然）
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(55, 40, 50, 255))
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    img.convert("RGB").save(out_path, quality=95)
    print(f"✅ 泪痣(内眼角)已画: ({cx},{cy}) r={r} → {out_path}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("img")
    ap.add_argument("--x", type=float, default=0.44)
    ap.add_argument("--y", type=float, default=0.40)
    ap.add_argument("--size", type=float, default=0.0025)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = a.out or (os.path.splitext(a.img)[0] + "_tearmole.png")
    add_tear_mole(a.img, a.x, a.y, a.size, out)
