"""一句话提交 ComfyUI 文生图（默认经 Ollama 转写）或视频生成（--video）。

用法示例:
  python -m agents run "赛博朋克少女"
  python -m agents run "猫" --raw
  python -m agents run "城市夜景" --video
  python -m agents run "行走的人物" --video --ref start.png --frames 49
"""
from __future__ import annotations

import argparse
import random
import sys

from comfy_utils import (
    VIDEO_PRESETS,
    bootstrap_agents_path,
    comfy_post_prompt,
    generate_with_quality,
    ollama_generate_or_fallback,
    optimize_prompt,
)

bootstrap_agents_path()

from output_manager import save_run, save_workflow_outputs  # noqa: E402
from comfy_utils import comfy_base_url  # noqa: E402

COMFY_URL_DEFAULT = "http://127.0.0.1:8188/prompt"


def _call_llm(prompt: str) -> str:
    return ollama_generate_or_fallback(
        f"把用户输入转换成SDXL提示词：{prompt}", fallback=prompt,
    )


def _run_image_mode(user: str, args: argparse.Namespace) -> None:
    """原有文生图模式。"""
    import json
    import random
    from pathlib import Path

    from comfy_utils import AGENTS_DIR

    try:
        positive_prompt = user if args.raw else _call_llm(user)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    negative_prompt = "worst quality, blurry, low quality"
    workflow_file = AGENTS_DIR / "workflow.json"
    workflow = json.loads(workflow_file.read_text(encoding="utf-8"))
    workflow["6"]["inputs"]["text"] = positive_prompt
    workflow["7"]["inputs"]["text"] = negative_prompt
    workflow["3"]["inputs"]["seed"] = random.randint(1, 999999999)

    try:
        result = comfy_post_prompt(workflow, prompt_url=COMFY_URL_DEFAULT)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    prompt_id = result.get("prompt_id", "")
    if prompt_id and prompt_id != "dry-run":
        save_workflow_outputs(prompt_id, comfy_base_url(COMFY_URL_DEFAULT), "run", {
            "prompt": positive_prompt,
            "negative": negative_prompt,
            "seed": workflow["3"]["inputs"]["seed"],
        })

    print("\n====================")
    print("已向 ComfyUI 提交任务")
    print("====================")
    print("正向提示词：", positive_prompt)


def _run_video_mode(user: str, args: argparse.Namespace) -> None:
    """视频生成模式。"""
    from go_video import build_video_workflow

    prompt = user if args.raw else optimize_prompt(user)

    kw = {
        "no_validate": True,
        "wait_timeout": args.timeout or 1800,
        "preset": args.preset,
        "seed": args.seed or -1,
        "steps": args.steps,
        "cfg": args.cfg,
        "width": args.width,
        "height": args.height,
        "frames": args.frames or 49,
        "fps": args.fps or 15,
        "sampler": args.sampler,
        "scheduler": args.scheduler,
        "denoise": args.denoise if args.ref else 1.0,
        "ref_image": args.ref,
        "negative": args.negative or "",
    }
    # 去掉 None 参数（让 generate_with_quality 用预设默认）
    kw = {k: v for k, v in kw.items() if v is not None}

    print(f"🎬 视频生成模式: {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
    if args.ref:
        print(f"   参考图: {args.ref}")
    print(f"   帧数: {kw.get('frames', 49)} | 帧率: {kw.get('fps', 15)}fps")

    qr = generate_with_quality(build_video_workflow, prompt, **kw)

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
        save_run("run-video", video_paths, {
            "prompt": prompt,
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
            "用 --video 切换为视频生成模式。"
        ),
    )
    parser.add_argument(
        "--raw", action="store_true",
        help="跳过 Ollama，将输入整段作为正向提示词",
    )
    parser.add_argument("prompt", nargs="?", help="一句话画面描述；省略时从标准输入读取")

    # 视频模式切换
    parser.add_argument("--video", action="store_true", help="视频生成模式（Wan2.2 T2V/I2V）")
    parser.add_argument("--ref", default=None, help="参考图（视频 I2V 模式，提供时自动启用）")
    parser.add_argument("--frames", type=int, default=None, help="视频总帧数（默认 49）")
    parser.add_argument("--fps", type=int, default=None, help="视频帧率（默认 15）")
    parser.add_argument("--steps", type=int, default=None, help="采样步数")
    parser.add_argument("--cfg", type=float, default=None, help="CFG 强度")
    parser.add_argument("--width", type=int, default=None, help="视频宽度")
    parser.add_argument("--height", type=int, default=None, help="视频高度")
    parser.add_argument("--seed", type=int, default=-1, help="随机种子")
    parser.add_argument("--negative", default=None, help="负向提示词")
    parser.add_argument("--denoise", type=float, default=0.85, help="去噪强度（I2V 默认 0.85）")
    parser.add_argument("--sampler", default=None, help="采样器名称")
    parser.add_argument("--scheduler", default=None, help="调度器名称")
    parser.add_argument(
        "--preset",
        choices=list(VIDEO_PRESETS.keys()),
        default=None,
        help="视频预设（quality/balanced/fast/cinematic）",
    )
    parser.add_argument("--timeout", type=float, default=1800, help="等待超时秒数")

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
