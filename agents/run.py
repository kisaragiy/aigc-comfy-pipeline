"""一句话提交 ComfyUI 文生图（--video 可切换视频生成）。

用法示例:
  python -m agents run "赛博朋克少女"
  python -m agents run --raw "cinematic girl, portrait"
  python -m agents run --preset anime "日系少女"
  python -m agents run --lora knives_flux.safetensors "白色连衣裙"
  python -m agents run --model 4b --steps 15 "prompt"
  python -m agents run "城市夜景" --video
  python -m agents run "行走的人物" --video --ref start.png --frames 49
"""
from __future__ import annotations

import argparse
import sys

from comfy_utils import (
    QUALITY_PRESETS,
    VIDEO_PRESETS,
    bootstrap_agents_path,
    generate_with_quality,
    optimize_prompt,
)

bootstrap_agents_path()

COMFY_URL = "http://127.0.0.1:8188/prompt"


def _build_image_kwargs(args: argparse.Namespace) -> dict:
    """从 args 提取图片生成参数（传给 build_flux_workflow）。"""
    kw = {}
    for key in ("steps", "cfg", "width", "height",
                "sampler", "scheduler",
                "lora_strength"):
        val = getattr(args, key, None)
        if val is not None:
            kw[key] = val
    kw["negative_prompt"] = args.negative or ""
    if args.lora:
        kw["lora_name"] = args.lora
    if args.prefix:
        kw["filename_prefix"] = args.prefix
    if args.model:
        kw["model_variant"] = args.model
    return kw


def _build_video_kwargs(args: argparse.Namespace) -> dict:
    """从 args 提取视频生成参数（传给 build_video_workflow）。"""
    kw = {
        "no_validate": True,
        "preset": args.preset,
    }
    for key in ("steps", "cfg", "width", "height", "seed",
                "sampler", "scheduler", "frames", "fps", "denoise"):
        val = getattr(args, key, None)
        if val is not None:
            kw[key] = val
    if args.negative:
        kw["negative"] = args.negative
    if args.ref:
        kw["ref_image"] = args.ref
        kw.setdefault("denoise", 0.85)
    kw.pop("timeout", None)
    kw["wait_timeout"] = getattr(args, "timeout", None) or 1800
    return kw


def _run_image_mode(prompt: str, args: argparse.Namespace) -> None:
    """Flux 文生图模式。"""
    from go_flux import build_flux_workflow
    from comfy_utils import comfy_base_url

    positive = prompt if args.raw else optimize_prompt(prompt)
    if not args.raw:
        print(f"[info] 优化后提示词: {positive[:300]}...")

    kw = _build_image_kwargs(args)

    qr = generate_with_quality(
        build_flux_workflow, positive,
        min_score=args.min_score if not args.no_validate else 0.0,
        max_retries=args.retry,
        preset=args.preset,
        seed=args.seed,
        **kw,
    )

    prompt_id = qr.get("prompt_id", "")
    seed_actual = qr.get("seed", 0)
    images = qr.get("images", [])

    if images:
        from output_manager import save_workflow_outputs
        save_workflow_outputs(
            prompt_id,
            comfy_base_url(COMFY_URL),
            "run",
            {
                "prompt": positive,
                "seed": seed_actual,
                "model": args.model,
                "lora": args.lora,
                "lora_strength": args.lora_strength,
                "score": qr.get("score"),
                "retries": qr.get("retries", 0),
                "preset": args.preset,
            },
        )

    print(f"\n====================")
    print(f"Flux.2 Klein ({args.model}) 已提交")
    print(f"====================")
    print(f"  prompt_id: {prompt_id}")
    print(f"  seed:      {seed_actual}")
    if args.lora:
        print(f"  LoRA:      {args.lora} (strength={args.lora_strength})")
    score = qr.get("score")
    if score is not None:
        print(f"  CLIP 评分: {score:.3f}")
    retries = qr.get("retries", 0)
    if retries > 0:
        print(f"  重试次数:  {retries}")
    print(f"  正向:      {positive[:200]}")


def _run_video_mode(prompt: str, args: argparse.Namespace) -> None:
    """视频生成模式。"""
    from go_video import build_video_workflow

    positive = prompt if args.raw else optimize_prompt(prompt)

    kw = _build_video_kwargs(args)
    print(f"🎬 视频生成模式: {positive[:80]}{'...' if len(positive) > 80 else ''}")
    if args.ref:
        print(f"   参考图: {args.ref}")
    print(f"   帧数: {kw.get('frames', 49)} | 帧率: {kw.get('fps', 15)}fps")

    qr = generate_with_quality(build_video_workflow, positive, **kw)

    seed_actual = qr.get("seed", "?")
    video_paths = qr.get("images", [])
    print(f"\n====================")
    print(f"视频已{'提交' if not video_paths else '完成'}")
    print(f"====================")
    print(f"  prompt_id: {qr.get('prompt_id', '')}")
    print(f"  seed:      {seed_actual}")
    print(f"  模式:      {'I2V' if args.ref else 'T2V'}")
    if video_paths:
        print(f"  输出:      {video_paths[0][:100]}")
    print(f"  重试:      {qr.get('retries', 0)}")

    if video_paths:
        from output_manager import save_run
        save_run("run-video", video_paths, {
            "prompt": positive,
            "ref_image": args.ref,
            "seed": args.seed,
            "frames": kw.get("frames", 49),
            "fps": kw.get("fps", 15),
            "denoise": args.denoise,
        })


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "一句话提交 ComfyUI 文生图（默认经 Ollama 转写为英文提示词）。"
            " 用 --video 切换为视频生成模式。"
        ),
    )
    parser.add_argument("prompt", nargs="?", help="一句话画面描述；省略时从标准输入读取")
    parser.add_argument(
        "--raw", action="store_true",
        help="跳过 Ollama，将输入整段作为正向提示词",
    )

    # === 通用参数 ===
    parser.add_argument("--negative", default=None, help="负向提示词")
    parser.add_argument("--seed", type=int, default=-1, help="随机种子（-1 自动）")
    parser.add_argument("--steps", type=int, default=None, help="采样步数（预设自动）")
    parser.add_argument("--cfg", type=float, default=None, help="CFG 引导强度")
    parser.add_argument("--width", type=int, default=None, help="输出宽度")
    parser.add_argument("--height", type=int, default=None, help="输出高度")
    parser.add_argument("--sampler", default=None, help="采样器名称")
    parser.add_argument("--scheduler", default=None, help="调度器名称")
    parser.add_argument("--preset", default=None, help="质量/视频预设名（自动匹配）")
    parser.add_argument("--timeout", type=float, default=None, help="等待超时秒数")

    # === 图片专用参数 ===
    parser.add_argument(
        "--model", choices=["9b", "4b"], default="9b",
        help="Flux 模型变体（仅图片模式）",
    )
    parser.add_argument("--lora", default=None, help="LoRA 权重文件名（仅图片模式）")
    parser.add_argument("--lora-strength", type=float, default=1.0, help="LoRA 权重强度")
    parser.add_argument("--prefix", default="flux_klein", help="输出文件名前缀（图片模式）")
    parser.add_argument("--min-score", type=float, default=0.0,
                        help="最低 CLIP 评分（≤0 跳过验证）")
    parser.add_argument("--retry", type=int, default=0,
                        help="质量不合格时最大重试次数")
    parser.add_argument("--no-validate", action="store_true",
                        help="跳过质量验证")

    # === 视频专用参数 ===
    parser.add_argument("--video", action="store_true", help="视频生成模式（Wan2.2）")
    parser.add_argument("--ref", default=None, help="参考图路径（I2V 模式）")
    parser.add_argument("--frames", type=int, default=None, help="视频总帧数（默认 49）")
    parser.add_argument("--fps", type=int, default=None, help="视频帧率（默认 15）")
    parser.add_argument("--denoise", type=float, default=None, help="去噪强度（I2V 默认 0.85）")

    args = parser.parse_args()

    user = args.prompt
    if not user:
        user = input("请输入需求: ").strip()
    if not user:
        print("未输入内容，退出。", file=sys.stderr)
        sys.exit(1)

    if args.video or args.ref:
        _run_video_mode(user, args)
    else:
        _run_image_mode(user, args)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)
