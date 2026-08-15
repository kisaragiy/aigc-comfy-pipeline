#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/thumbnail.py — AI 版 thumbnail 构图筛选（画师模式 v1.0）
=================================================================
业界画师最核心习惯移植: 先画多张构图草稿（thumbnail）选方向 → 再精修。
AI 对应: 多构图方向 × 低步数快速生成 → contact sheet 画板 → 选中 → 精修。

用法:
  python -m agents workshop thumbnail "校服少女, 黑发短发, 侧辫, 泪痣, 青春感" [--commercial-flow]
      --commercial-flow  选中后自动走商业画师全流程（generate→colorgrade→泪痣）
      --hair black|brown 发色（默认 black——用户规范：仅黑/棕）
      --fast-steps 18    thumbnail 阶段步数（低=快）
      --select N         直接精修第 N 个方向（跳过看板——批量场景）

构图方向（业界画师 thumbnail 分类——每方向 = 构图词 + 分辨率）:
  1 远景环境   wide shot, full body, environmental    1344x768
  2 中景半身   medium shot, half body                  896x1152
  3 特写表情   close-up, upper body, face focus        896x896
  4 三分法     rule of thirds, subject at left third   896x1152
  5 中心构图   centered composition                    896x896
  6 俯视       high angle shot, looking down           896x896
  7 仰视       low angle shot, looking up              896x896
  8 回眸       looking back over shoulder              896x1152
"""
import argparse, os, subprocess, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PY = sys.executable
OUT_DIR = BASE / "workspace" / "thumbnail"

COMPOSITIONS = {
    "basic": [
        {"name": "远景环境", "tags": "wide shot, full body, environmental, small figure in large scene", "w": 1344, "h": 768},
        {"name": "中景半身", "tags": "medium shot, half body, waist up", "w": 896, "h": 1152},
        {"name": "特写表情", "tags": "close-up, upper body, face focus, detailed eyes", "w": 896, "h": 896},
        {"name": "三分法", "tags": "rule of thirds, subject positioned at left third, negative space on right", "w": 896, "h": 1152},
        {"name": "中心构图", "tags": "centered composition, symmetrical, subject in middle", "w": 896, "h": 896},
        {"name": "俯视", "tags": "high angle shot, viewed from above", "w": 896, "h": 896},
        {"name": "仰视", "tags": "low angle shot, viewed from below, heroic", "w": 896, "h": 896},
        {"name": "回眸", "tags": "looking back over shoulder, three-quarter view", "w": 896, "h": 1152},
    ],
    "advanced": [
        {"name": "大远景", "tags": "extreme wide shot, very small figure in vast environment, sense of scale", "w": 1344, "h": 768},
        {"name": "近景胸像", "tags": "bust shot, chest up, intimate framing", "w": 896, "h": 896},
        {"name": "大特写", "tags": "extreme close-up, eyes only, macro detail, emotion in eyes", "w": 896, "h": 896},
        {"name": "鸟瞰", "tags": "bird's eye view, directly from above, top-down", "w": 896, "h": 896},
        {"name": "荷兰角", "tags": "dutch angle, tilted composition, dynamic unease", "w": 896, "h": 1152},
        {"name": "黄金分割", "tags": "golden ratio composition, subject at golden point intersection", "w": 896, "h": 1152},
        {"name": "对角线", "tags": "diagonal composition, dynamic flow along diagonal line", "w": 896, "h": 1152},
        {"name": "框架构图", "tags": "framed composition, subject seen through foreground frame like door or window", "w": 896, "h": 1152},
    ],
    "mood": [
        {"name": "留白孤独", "tags": "minimal composition, small lonely figure in large empty space, lots of negative space", "w": 1344, "h": 768},
        {"name": "背影悬念", "tags": "viewed from behind, back view, mysterious atmosphere", "w": 896, "h": 1152},
        {"name": "剪影逆光", "tags": "silhouette, backlit, strong rim light, dark figure against bright background", "w": 896, "h": 1152},
        {"name": "镜像对称", "tags": "mirror reflection, symmetrical composition with reflection", "w": 896, "h": 896},
        {"name": "视线引导", "tags": "subject looking at object inside frame, eye direction leads viewer", "w": 896, "h": 1152},
        {"name": "温馨紧凑", "tags": "cozy close composition, warm tones, intimate atmosphere, subject fills frame", "w": 896, "h": 896},
        {"name": "压迫感", "tags": "low angle from below, towering background, oppressive scale, small subject against huge structures", "w": 896, "h": 1152},
        {"name": "双人互动", "tags": "two girls, interaction between them, dynamic duo composition", "w": 1216, "h": 832},
    ],
}
GROUP_NAMES = {"basic": "基础组", "advanced": "进阶组", "mood": "情绪组"}

HAIR = {
    "black": "natural black hair",
    "brown": "natural dark brown hair",
}

QUALITY_POS = "MASTERPIECE, best quality, anime style, clean lineart, soft cel shading"
QUALITY_NEG = ("worst quality, low quality, blurry, noise, grainy, dirty, "
               "colorful hair, gradient hair, tears, watermark, text, extra fingers")


def gen_one(prompt, idx, comp, hair, steps, model="sdxl"):
    """单个方向生成（低步数——快）"""
    w, h = comp["w"], comp["h"]
    p = f"{QUALITY_POS}, 1girl, {HAIR[hair]}, {prompt}, {comp['tags']}"
    out = OUT_DIR / f"thumb_{idx:02d}_{comp['name']}.png"
    cmd = [PY, "-m", "agents", "workshop", "create", p,
           "--model", model, "--commercial", "--steps", str(steps),
           "--count", "1", "--min-score", "4.5",  # thumbnail 阶段阈值低（快）
           "--negative", QUALITY_NEG, "--output", str(out)]
    r = subprocess.run(cmd, cwd=BASE, capture_output=True, text=True, timeout=300)
    # 找生成图（create --output 可能不生效——从输出解析）
    for line in r.stdout.splitlines():
        if line.strip().startswith("图片:") or line.strip().startswith(" 图片:"):
            return line.split("图片:")[-1].strip()
    # 兜底：OUT_DIR 下最新文件
    if out.is_file():
        return str(out)
    return None


def make_contact_sheet(images):
    """PIL 拼 contact sheet（画师 thumbnail 板——2 列网格 + 标签）"""
    from PIL import Image, ImageDraw
    os.makedirs(OUT_DIR, exist_ok=True)
    thumbs = []
    for p in images:
        if p and Path(p).is_file():
            img = Image.open(p)
            img.thumbnail((400, 400))
            thumbs.append((Path(p).stem, img))
    if not thumbs:
        print("❌ 无生成图"); return None
    cols, cell = 2, 420
    rows = (len(thumbs) + 1) // 2
    sheet = Image.new("RGB", (cols * cell, rows * (cell + 30)), (245, 245, 245))
    d = ImageDraw.Draw(sheet)
    for i, (name, img) in enumerate(thumbs):
        x = (i % cols) * cell + 10
        y = (i // cols) * (cell + 30) + 10
        sheet.paste(img, (x, y))
        d.text((x, y + 400), name, fill=(0, 0, 0))
    sheet_path = OUT_DIR / "contact_sheet.png"
    sheet.save(sheet_path, quality=90)
    print(f"📋 Contact sheet: {sheet_path}")
    return str(sheet_path)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="workshop thumbnail", description="AI 版 thumbnail 构图筛选（画师模式）")
    ap.add_argument("prompt", help="角色/场景描述（不含构图词——自动套 8 方向）")
    ap.add_argument("--hair", default="black", choices=["black", "brown"])
    ap.add_argument("--fast-steps", type=int, default=18)
    ap.add_argument("--select", type=int, default=None, help="直接精修第 N 个方向（组内序号 1-8）")
    ap.add_argument("--group", default="basic", choices=["basic", "advanced", "mood", "all"],
                    help="构图组: basic(基础8) / advanced(进阶8) / mood(情绪8) / all(24)")
    ap.add_argument("--commercial-flow", action="store_true", help="选中后自动走商业画师全流程")
    args = ap.parse_args(argv)

    os.makedirs(OUT_DIR, exist_ok=True)
    comps_all = {}
    if args.group == "all":
        for g, comps in COMPOSITIONS.items():
            comps_all.update({f"{g}-{i}": c for i, c in enumerate(comps, 1)})
    else:
        comps_all = {f"{i}": c for i, c in enumerate(COMPOSITIONS[args.group], 1)}
    group_label = "全部(24)" if args.group == "all" else GROUP_NAMES[args.group]
    print(f"═══ AI thumbnail 构图筛选（画师模式）═══")
    print(f"角色: {args.prompt} | 发色: {args.hair} | 构图组: {group_label} | thumbnail 步数: {args.fast_steps}")

    # --select: 跳过看板直接精修指定方向
    if args.select:
        comp = COMPOSITIONS[args.group][args.select - 1]
        print(f"→ 精修方向 {args.select}: {comp['name']} ({comp['tags']})")
        flow_cmd = [PY, "-m", "agents", "workshop", "commercial_flow",
                    f"{args.prompt}, {comp['tags']}", "--hair", args.hair]
        if args.commercial_flow:
            flow_cmd += ["--tear-mole"]
        return subprocess.run(flow_cmd, cwd=BASE).returncode

    # ① 各方向低步数快速生成
    images = []
    for i, (key, comp) in enumerate(comps_all.items(), 1):
        print(f"\n[{i}/{len(comps_all)}] {comp['name']} ...")
        img = gen_one(args.prompt, i, comp, args.hair, args.fast_steps)
        images.append(img)
        print(f"  → {img}")

    # ② contact sheet 画板
    sheet = make_contact_sheet(images)
    if not sheet:
        return 1

    # ③ 提示精修用法
    print(f"\n═══ 画板完成 ═══")
    print(f"看板: {sheet}")
    print(f"选择方向精修: python -m agents workshop thumbnail \"{args.prompt}\" --select <1-8> --commercial-flow")
    return 0


if __name__ == "__main__":
    sys.exit(main())
