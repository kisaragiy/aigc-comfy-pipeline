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
sys.path.insert(0, str(BASE / "agents"))
from comfy_utils import resolve_comfy_root
COMFY_ROOT = resolve_comfy_root()

# 发色 → SDXL 标签（用户定：仅黑/棕——现实发色）
HAIR_TAGS = {
    "black": "natural black hair",
    "brown": "natural dark brown hair",
    "natural": "natural black hair",
}

# 画风质量词（商业画师标准——去脏 + 2026-08-16 用户反馈强化）
# 反馈①: 画风不够商业 → key visual/magazine cover 商业感强化
# 反馈②: 眼睛过大不协调 → proportional eyes 正向 + huge eyes 负向
# 反馈③: 脸部怪异色彩 → natural even skin tone 正向 + color cast 负向
QUALITY_POS = ("MASTERPIECE, best quality, anime style, key visual quality, magazine cover style, "
               "professional illustration, clean lineart, soft cel shading, smooth gradients, crisp edges, "
               "proportional eyes, balanced facial features, natural even skin tone, "
               "detailed hair strands, vibrant saturated colors, layered depth")
QUALITY_NEG = ("worst quality, low quality, blurry, noise, grainy, dirty, messy lineart, "
               "jpeg artifacts, bad anatomy, bad hands, extra fingers, watermark, text, "
               "colorful hair, gradient hair, blue hair, green hair, pink hair, red hair, red gradient, "
               "purple hair, purple gradient, tears, crying, "
               "huge eyes, oversized eyes, disproportionate eyes, mismatched eyes, "
               "color cast, unnatural skin tone, blotchy skin, skin discoloration, uneven skin, "
               "amateur art, sketchy, unfinished, rough shading, flat colors, plain background")


def run(args):
    hair_tag = HAIR_TAGS.get(args.hair, HAIR_TAGS["black"])
    # 2026-08-16: --lora 时若含 style_cine_manga 追加其触发词 mystyle（风格蒸馏 LoRA 的触发词），
    #   让 LoRA 明确作用于画风（商业立绘质感）而不是靠隐性强度偏移（曾导致红渐变发）
    lora_trigger = ", mystyle" if args.lora and "cine_manga" in args.lora else ""
    prompt = f"{QUALITY_POS}, 1girl, {hair_tag}{lora_trigger}, {args.prompt}"

    print(f"═══ 商业画师流程 v1.1 ═══")
    print(f"发色: {args.hair} ({hair_tag}) | 泪痣: {'开' if args.tear_mole else '关'} | 模型: {args.model}")

    # ① 生成（commercial 预设 + face-detailer + 质检）
    cmd = [PY, "-m", "agents", "workshop", "create", prompt,
           "--model", args.model, "--commercial", "--face-detailer",
           "--count", str(args.count), "--min-score", str(args.min_score),
           "--negative", QUALITY_NEG]
    if args.lora:
        cmd += ["--lora", args.lora, "--lora-strength", str(args.lora_strength)]
    if args.steps:
        cmd += ["--steps", str(args.steps)]
    if args.cfg:
        cmd += ["--cfg", str(args.cfg)]
    if args.prompt_ready:
        cmd += ["--prompt-ready"]
    if args.aesthetic_min_score:
        cmd += ["--aesthetic-min-score", str(args.aesthetic_min_score)]
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

    # 解析最优图路径——优先取超分后的图（create 内部已 2.0x 超分——用超分大图做后续处理）
    # 遗漏 4 固化（2026-08-15）: 之前解析到 pipeline_create 原始图（4864×3328）——漏了超分
    #   导致 colorgrade/泪痣都画在低清图上。超分完成后应使用 upscaled_xxx 图。
    best_img = None
    for line in r.stdout.splitlines():
        stripped = line.strip()
        if "超分完成" in stripped:
            up = stripped.split(":")[-1].strip()
            # create 打印的是 ComfyUI 相对路径（output\upscaled_xxx.png）——拼 ComfyUI 输出目录
            # 遗漏 4 固化（2026-08-15）: 之前解析到 pipeline_create 原始图（4864×3328）——
            #   超分完成后应使用 upscaled_xxx 大图（9728×6656）做后续 colorgrade/泪痣
            if Path(up).is_absolute():
                cand = Path(up)
            else:
                cand = COMFY_ROOT / up
            if cand.is_file():
                best_img = str(cand)
                break
    if not best_img:
        for line in r.stdout.splitlines():
            if line.strip().startswith("图片:"):
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
        # 遗漏 5 固化（2026-08-15）: split(":") 会把 Windows 盘符 C: 切掉——
        #   必须 split(":", 1)[-1]（只切第一个冒号）——否则得到 "\DrawingLive\..." 缺盘符
        current = out_lines[0].split(":", 1)[-1].strip()
        print(f"  ✅ {current}")

    # ⑤ 泪痣（可选——内眼角小点，v3 自动定位）
    if args.tear_mole:
        print(f"\n⑤ 泪痣（自动定位内眼角）...")
        out = str(Path(current).with_name(Path(current).stem + "_tearmole.png"))
        r = subprocess.run([PY, str(BASE / "workshop" / "add_tear_mole.py"), current,
                            "--auto",
                            "--size", "0.0016",
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
    ap.add_argument("--lora", default=None, help="LoRA 权重文件名（ComfyUI/models/loras/ 下）——如 style_cine_manga.safetensors 游戏立绘质感")
    ap.add_argument("--lora-strength", type=float, default=0.8, help="LoRA 强度（默认 0.8——风格 LoRA 别拉满防崩）")
    ap.add_argument("--steps", type=int, default=28, help="采样步数（NoobAI 推荐 28）")
    ap.add_argument("--cfg", type=float, default=5.5, help="CFG scale（NoobAI 推荐 5.5——比 Illustrious 的 7.0 低）")
    ap.add_argument("--prompt-ready", action="store_true",
                    help="prompt 已完整构建，跳过 ollama 增强（商业叙事词不被稀释——2026-08-16 修复）")
    ap.add_argument("--aesthetic-min-score", type=float, default=6.0,
                    help="VLM 审美门禁（0-10，低于阈值换 seed 重试——防坏图/纹理图）")
    args = ap.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
