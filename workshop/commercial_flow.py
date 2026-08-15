#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/commercial_flow.py — 商业画师标准出图流程 v1.0
========================================================
业界商业画师 AI 流程（本次实战验证固化）:
  ① 生成: SDXL/Flux + 商业预设(anime_commercial 风格词) + face-detailer 修脸
  ② 质检: VLM 六维评分 + 阈值筛选（低于阈值自动重跑）
  ③ 色彩统一: colorgrade（自动白平衡去"脏"感）
  ④ 超分: 2.0x（可选）
  ⑤ 泪痣/特征后处理: 内眼角小点（可选——精确可控）
  ⑥ 终检: finalcheck（flip 倒置镜像 + focus 焦点引导——可选）

用法:
  python -m agents workshop commercial_flow "<prompt>" \
      [--hair black|brown|natural] [--tear-mole] [--mole-x 0.445] [--mole-y 0.40] \
      [--count 3] [--min-score 6.5] [--model sdxl|flux] [--ref 参考图] [--no-upscale]

发色规范（中国高中女生现实发色——用户 2026-08-15 定）:
  black   纯黑（默认）
  brown   深棕（自然染/天生棕）
  禁用: 金/粉/蓝/渐变（"像中专小太妹"——用户原话）

泪痣规范（用户 2026-08-15 定）:
  位置: 左眼内眼角下方（x≈0.445, y≈0.40——可调）
  大小: 小点（r≈0.0022 比例——视觉 2-3px @1000 宽——不过大）
"""
import argparse, os, subprocess, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PY = sys.executable

# 发色 → SDXL 标签（用户定：仅黑/棕——现实发色）
HAIR_TAGS = {
    "black": "natural black hair",
    "brown": "natural dark brown hair",
    "natural": "natural black hair",
}

# 画风质量词（商业画师标准——去脏）
QUALITY_POS = "MASTERPIECE, best quality, anime style, clean lineart, soft cel shading, smooth gradients, crisp edges"
QUALITY_NEG = ("worst quality, low quality, blurry, noise, grainy, dirty, messy lineart, "
               "jpeg artifacts, bad anatomy, bad hands, extra fingers, watermark, text, "
               "colorful hair, gradient hair, blue hair, green hair, pink hair, tears, crying")


def run(args):
    hair_tag = HAIR_TAGS.get(args.hair, HAIR_TAGS["black"])
    prompt = f"{QUALITY_POS}, 1girl, {hair_tag}, {args.prompt}"

    print(f"═══ 商业画师流程 v1.1 ═══")
    print(f"发色: {args.hair} ({hair_tag}) | 泪痣: {'开' if args.tear_mole else '关'} | 模型: {args.model}")

    # ① 生成（commercial 预设 + face-detailer + 质检）
    cmd = [PY, "-m", "agents", "workshop", "create", prompt,
           "--model", args.model, "--commercial", "--face-detailer",
           "--count", str(args.count), "--min-score", str(args.min_score),
           "--negative", QUALITY_NEG]
    if args.ref:
        cmd += ["--ref", args.ref]
    print(f"\n① 生成（--commercial + face-detailer + 质检阈值 {args.min_score}）...")
    r = subprocess.run(cmd, cwd=BASE, capture_output=True, text=True, timeout=900)
    print(r.stdout[-2000:] if r.stdout else r.stderr[-1000:])
    if r.returncode != 0:
        print("❌ 生成失败"); return 1

    # 质检降级链（遗漏 1/2——2026-08-15 实战固化）:
    #   YOLO 对动漫脸误报"脸崩/3 张人脸"→ 不能直接弃图——VLM 二次确认或目视
    #   VLM 全挂（ollama 不稳定）→ 跳过评分——生成图照常交付（标注"未质检"）
    if "脸: 崩了" in r.stdout or "脸崩" in r.stdout:
        print("⚠️ 质检报脸崩——YOLO 对动漫脸已知误报（GAP-ANALYSIS）——保留候选，目视二次确认")
    if "综合分" not in r.stdout and "质检报告" not in r.stdout:
        print("⚠️ VLM 质检未输出（ollama 可能不稳定）——降级：图照常交付，标注未质检")

    # 解析最优图路径（从输出提取 "图片: <路径>"）
    best_img = None
    for line in r.stdout.splitlines():
        if line.strip().startswith("图片:") or line.strip().startswith(" 图片:"):
            best_img = line.split("图片:")[-1].strip()
            break
    if not best_img or not Path(best_img).is_file():
        print("❌ 未找到最优图"); return 1
    print(f"\n✅ 最优图: {best_img}")

    current = best_img

    # ③ 色彩统一（colorgrade——去脏）
    # 顺序注意（遗漏 3 固化）: 先 colorgrade → 再泪痣（泪痣尺寸按最终比例自适应——add_tear_mole 用比例非像素）
    # 超分在 create 内已完成（--commercial 默认 2.0x）——泪痣画在超分后的最终分辨率上（比例自适应）
    print(f"\n③ colorgrade 色彩统一...")
    r = subprocess.run([PY, "-m", "agents", "workshop", "colorgrade", current],
                       cwd=BASE, capture_output=True, text=True, timeout=300)
    out_lines = [l for l in r.stdout.splitlines() if "色彩统一完成" in l]
    if out_lines:
        current = out_lines[0].split(":")[-1].strip()
        print(f"  ✅ {current}")

    # ⑤ 泪痣（可选——内眼角小点）
    if args.tear_mole:
        print(f"\n⑤ 泪痣（内眼角 x={args.mole_x}, y={args.mole_y}）...")
        out = str(Path(current).with_name(Path(current).stem + "_tearmole.png"))
        r = subprocess.run([PY, str(BASE / "workshop" / "add_tear_mole.py"), current,
                            "--x", str(args.mole_x), "--y", str(args.mole_y),
                            "--out", out], capture_output=True, text=True, timeout=120)
        print(f"  {r.stdout.strip()}")
        current = out if Path(out).is_file() else current

    print(f"\n═══ 完成 ═══")
    print(f"终稿: {current}")
    print(f"（后续可手动跑 finalcheck: python -m agents workshop finalcheck \"{current}\" --flip --focus）")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="workshop commercial_flow", description="商业画师标准出图流程")
    ap.add_argument("prompt")
    ap.add_argument("--hair", default="black", choices=["black", "brown", "natural"])
    ap.add_argument("--tear-mole", action="store_true", help="画泪痣（内眼角小点）")
    ap.add_argument("--mole-x", type=float, default=0.445)
    ap.add_argument("--mole-y", type=float, default=0.40)
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--min-score", type=float, default=6.5)
    ap.add_argument("--model", default="sdxl", choices=["sdxl", "flux"])
    ap.add_argument("--ref", default=None)
    args = ap.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
