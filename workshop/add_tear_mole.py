"""泪痣后处理 v3——自动定位内眼角（2026-08-17 用户反馈修正）
v2 用固定比例 (x*W, y*H) 画——全身/仰拍/中景构图时脸的位置差异大，固定比例画错位置。
v3: 用 YOLO 人脸检测（管线已有 detect_faces）定位脸框 → 内眼角相对位置画泪痣。

内眼角相对位置（脸部 bbox 内）:
  x ≈ bbox_x + 0.40 * bbox_w（左眼内眼角偏左）
  y ≈ bbox_y + 0.38 * bbox_h（眼睛高度）
画在左眼内眼角下方一点（用户定：内眼角下方小点）

用法:
  python add_tear_mole.py <图> [--x 0.44] [--y 0.40] [--size 0.0025] [--out 输出] [--auto]
  --auto: YOLO 检测脸自动定位（推荐——构图多变时位置准确）
"""
from PIL import Image, ImageDraw, ImageFilter
import os, argparse, sys
from pathlib import Path

# 独立脚本运行时 sys.path[0]=workshop/，workshop/inspect 包会遮蔽标准库 inspect
# （module 'inspect' has no attribute 'cleandoc'）——把 workshop 移到 path 末尾，项目根/标准库优先
_PROJ_ROOT = str(Path(__file__).resolve().parent.parent)
_WORKSHOP_DIR = str(Path(__file__).resolve().parent)
if _WORKSHOP_DIR in sys.path:
    sys.path.remove(_WORKSHOP_DIR)
if _PROJ_ROOT not in sys.path:
    sys.path.insert(0, _PROJ_ROOT)


def _detect_face_bbox(img_path: str) -> tuple[float, float] | None:
    """返回 (泪痣x比例, 泪痣y比例) 或 None。
    2026-08-17 用户修正：泪痣画在「外眼角附近」（夫妻宫位置——眼尾外侧斜下方），
    不是内眼角！左右眼无要求（默认角色左眼=图中右侧）。
    """
    try:
        proj_root = str(Path(__file__).resolve().parent.parent)
        agents_dir = str(Path(__file__).resolve().parent.parent / "agents")
        for p in (proj_root, agents_dir):
            if p not in sys.path:
                sys.path.insert(0, p)
        from go_validate import _check_face as detect_faces
        r = detect_faces(img_path)
        if not r or not r.get("detections"):
            print("⚠️ 未检测到人脸")
            return None
        det = r["detections"][0]
        x1, y1, x2, y2 = det["bbox"]
        W_face = x2 - x1
        H_face = y2 - y1
        # 夫妻宫（面相学）：眼尾外侧太阳穴区域——泪痣画在眼尾附近
        # Haar 实测（2026-08-17）：角色左眼（图中右眼）中心 ≈ 脸框(0.70, 0.48)，宽约 5% 脸宽
        # 外眼角 = 中心 x + 半宽 ≈ 0.73；用户 2026-08-17 反馈"更靠近眼尾"→ (0.73, 0.49) 紧贴外眼角
        ex = x1 + 0.73 * W_face
        ey = y1 + 0.49 * H_face
        img = Image.open(img_path)
        iw, ih = img.size
        return (ex / iw, ey / ih)
    except Exception as e:
        print(f"⚠️ 自动定位失败({e})——回退固定比例")
        return None


def add_tear_mole(img_path, x, y, size_ratio, out_path, auto=False):
    img = Image.open(img_path).convert("RGB")
    W, H = img.size
    if auto:
        auto_pos = _detect_face_bbox(img_path)
        if auto_pos:
            x, y = auto_pos
            print(f"  📐 自动定位内眼角: ({x:.3f}, {y:.3f})")
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
    ap.add_argument("--auto", action="store_true", help="YOLO 自动定位内眼角（推荐）")
    a = ap.parse_args()
    out = a.out or (os.path.splitext(a.img)[0] + "_tearmole.png")
    add_tear_mole(a.img, a.x, a.y, a.size, out, auto=a.auto)
