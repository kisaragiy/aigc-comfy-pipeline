"""
Wan2.2 视频生成 — Text-to-Video / Image-to-Video。

用法示例:
  python go_video.py "赛博朋克城市，霓虹灯闪烁，雨夜" --frames 49
  python go_video.py "prompt" --frames 81 --fps 15 --width 848 --height 480
  python go_video.py "人物行走" --ref start.png --frames 49
"""
from __future__ import annotations

import argparse
import os
import random
import sys
from typing import Any

from comfy_utils import (
    apply_preset,
    VIDEO_PRESETS,
    bootstrap_agents_path,
    comfy_base_url,
    comfy_post_prompt,
    optimize_prompt,
)

bootstrap_agents_path()

COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188/prompt")

# Wan2.2 模型文件
WAN_UNET = "wan2.2_ti2v_5B_fp16.safetensors"
WAN_CLIP = "umt5_xxl_fp8_e4m3fn_scaled.safetensors"
WAN_VAE = "wan2.2_vae.safetensors"

# 默认视频参数
DEFAULT_WIDTH = 848
DEFAULT_HEIGHT = 480
DEFAULT_FRAMES = 49
DEFAULT_FPS = 15
DEFAULT_STEPS = 30
DEFAULT_CFG = 7.0


def build_video_workflow(
    prompt: str,
    *,
    negative: str = "",
    seed: int = -1,
    steps: int = DEFAULT_STEPS,
    cfg: float = DEFAULT_CFG,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    frames: int = DEFAULT_FRAMES,
    fps: int = DEFAULT_FPS,
    ref_image: str | None = None,
    prefix: str = "wan_video",
) -> tuple[dict[str, Any], int]:
    """构建 Wan2.2 视频生成工作流。

    Args:
        prompt: 正向提示词
        negative: 负向提示词
        seed: 随机种子（-1 自动）
        steps: 采样步数
        cfg: CFG 强度
        width/height: 视频分辨率
        frames: 总帧数
        fps: 帧率
        ref_image: 参考图（I2V 模式）
        prefix: 输出文件名前缀

    Returns:
        (workflow_dict, actual_seed)
    """
    seed_actual = seed if seed != -1 else random.randint(1, 2**48 - 1)
    wf: dict[str, Any] = {}

    # 1. UNETLoader — Wan2.2 视频模型
    wf["1"] = {"class_type": "UNETLoader", "inputs": {
        "unet_name": WAN_UNET, "weight_dtype": "default"}}

    # 2. CLIPLoader — umt5 文本编码器
    wf["2"] = {"class_type": "CLIPLoader", "inputs": {
        "clip_name": WAN_CLIP, "type": "wan"}}

    # 3. CLIPTextEncode — 正向/负向提示词
    wf["3a"] = {"class_type": "CLIPTextEncode", "inputs": {
        "text": prompt, "clip": ["2", 0]}}
    wf["3b"] = {"class_type": "CLIPTextEncode", "inputs": {
        "text": negative or "", "clip": ["2", 0]}}

    # 4. VAELoader — Wan2.2 VAE
    wf["4"] = {"class_type": "VAELoader", "inputs": {
        "vae_name": WAN_VAE}}

    # 5. 视频潜空间
    latent_id = "7"
    wf[latent_id] = {"class_type": "EmptyLatentVideo", "inputs": {
        "width": width, "height": height,
        "frames": frames, "batch_size": 1}}

    # 6. KSampler
    wf["5"] = {"class_type": "KSampler", "inputs": {
        "seed": seed_actual, "steps": steps, "cfg": cfg,
        "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
        "model": ["1", 0], "positive": ["3a", 0],
        "negative": ["3b", 0], "latent_image": [latent_id, 0]}}

    # 7. VAEDecode
    wf["6"] = {"class_type": "VAEDecode", "inputs": {
        "samples": ["5", 0], "vae": ["4", 0]}}

    # 8. VideoCombine — 输出视频
    wf["8"] = {"class_type": "VideoCombine", "inputs": {
        "images": ["6", 0], "frame_rate": fps,
        "filename_prefix": prefix, "format": "video/h264-mp4",
        "pingpong": False, "save_output": True}}

    return wf, seed_actual


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Wan2.2 视频生成（Text-to-Video / Image-to-Video）",
    )
    parser.add_argument("prompt", nargs="?", help="画面描述")
    parser.add_argument("--ref", default=None, help="参考图（I2V 模式，文件名）")
    parser.add_argument("--frames", type=int, default=None, help="总帧数（预设自动）")
    parser.add_argument("--fps", type=int, default=None, help="帧率（预设自动）")
    parser.add_argument("--width", type=int, default=None, help="视频宽度（预设自动）")
    parser.add_argument("--height", type=int, default=None, help="视频高度（预设自动）")
    parser.add_argument("--steps", type=int, default=None, help="采样步数（预设自动）")
    parser.add_argument("--cfg", type=float, default=None, help="CFG 强度（预设自动）")
    parser.add_argument("--seed", type=int, default=-1)
    parser.add_argument("--negative", default="", help="负向提示词")
    parser.add_argument("--raw", action="store_true", help="跳过 Ollama")
    parser.add_argument("--prefix", default="wan_video", help="输出文件名前缀")
    parser.add_argument("--preset", choices=list(VIDEO_PRESETS.keys()),
                        default=None, help="视频预设（quality/balanced/fast/cinematic）")
    args = parser.parse_args()

    user = args.prompt
    if not user:
        user = input("请输入描述: ").strip()
    if not user:
        print("未输入内容，退出。", file=sys.stderr)
        sys.exit(1)

    prompt = user if args.raw else optimize_prompt(user)

    vparams = apply_preset(
        dict(
            seed=args.seed, steps=args.steps, cfg=args.cfg,
            width=args.width, height=args.height,
            frames=args.frames, fps=args.fps,
        ),
        preset=args.preset,
        presets=VIDEO_PRESETS,
    )

    wf, seed_actual = build_video_workflow(
        prompt,
        negative=args.negative,
        seed=vparams.get("seed", -1),
        steps=vparams.get("steps", DEFAULT_STEPS),
        cfg=vparams.get("cfg", DEFAULT_CFG),
        width=vparams.get("width", DEFAULT_WIDTH),
        height=vparams.get("height", DEFAULT_HEIGHT),
        frames=vparams.get("frames", DEFAULT_FRAMES),
        fps=vparams.get("fps", DEFAULT_FPS),
        ref_image=args.ref,
        prefix=args.prefix,
    )

    try:
        result = comfy_post_prompt(wf, prompt_url=COMFY_URL)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    prompt_id = result.get("prompt_id", "")

    print(f"\n====================")
    print(f"Wan2.2 视频已提交")
    print(f"====================")
    print(f"  prompt_id: {prompt_id}")
    print(f"  seed:      {seed_actual}")
    print(f"  分辨率:    {args.width}x{args.height}")
    print(f"  帧数:      {args.frames} @ {args.fps}fps = {args.frames // args.fps}s")
    print(f"  节点数:    {len(wf)}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)
