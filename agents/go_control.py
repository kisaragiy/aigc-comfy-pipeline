"""
ControlNet 引导生图 — Depth/OpenPose/SoftEdge/Tile/Inpaint/LineArt。

用法示例:
  python go_control.py "prompt" --ref ref.png --type depth
  python go_control.py "prompt" --ref pose.png --type openpose --strength 0.6
  python go_control.py "prompt" --ref sketch.png --type softedge --raw
"""
from __future__ import annotations

import argparse
import os
import random
import sys
from typing import Any

from comfy_utils import (
    bootstrap_agents_path,
    comfy_base_url,
    comfy_post_prompt,
    optimize_prompt,
)

bootstrap_agents_path()

COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188/prompt")

CONTROLNET_MODELS: dict[str, str] = {
    "depth": "controlnet-depth-sdxl-1.0.safetensors",
    "openpose": "OpenPoseXL2.safetensors",
    "softedge": "controlnet-sd-xl-1.0-softedge-dexined.safetensors",
    "tile": "controlnet-tile-sdxl-1.0.safetensors",
    "inpaint": "controlnet_inpaint_sdxl1.safetensors",
    "lineart": "Kataragi_lineartXL-lora128.safetensors",
}


def build_controlnet_workflow(
    prompt: str,
    ref_image: str,
    control_type: str = "depth",
    *,
    negative: str = "",
    seed: int = -1,
    steps: int = 28,
    cfg: float = 6.5,
    strength: float = 0.8,
    width: int = 1024,
    height: int = 1024,
    lora_name: str | None = None,
    lora_strength: float = 0.9,
    prefix: str = "control",
) -> tuple[dict[str, Any], int]:
    """构建 SDXL + ControlNet 工作流。"""
    model = CONTROLNET_MODELS.get(control_type, CONTROLNET_MODELS["depth"])
    seed_actual = seed if seed != -1 else random.randint(1, 2**48 - 1)

    wf: dict[str, Any] = {}

    # 1. CheckpointLoader
    wf["1"] = {"class_type": "CheckpointLoaderSimple", "inputs": {
        "ckpt_name": "sd_xl_base.safetensors"}}

    # 可选 LoRA 注入
    model_out = ["1", 0]
    clip_out = ["1", 1]
    if lora_name:
        wf["11"] = {"class_type": "LoraLoader", "inputs": {
            "model": ["1", 0], "clip": ["1", 1],
            "lora_name": lora_name,
            "strength_model": lora_strength, "strength_clip": lora_strength}}
        model_out = ["11", 0]
        clip_out = ["11", 1]

    # 2. CLIPTextEncode (positive)
    wf["2"] = {"class_type": "CLIPTextEncode", "inputs": {
        "text": prompt, "clip": clip_out}}

    # 3. CLIPTextEncode (negative)
    neg = negative or "worst quality, blurry, low quality"
    wf["3"] = {"class_type": "CLIPTextEncode", "inputs": {
        "text": neg, "clip": clip_out}}

    # 4. LoadImage (reference)
    wf["4"] = {"class_type": "LoadImage", "inputs": {"image": ref_image}}

    # 5. ControlNetLoader
    wf["5"] = {"class_type": "ControlNetLoader", "inputs": {
        "control_net_name": model}}

    # 6. ControlNetApply (正提示词 + ControlNet → 修正 conditioning)
    wf["6"] = {"class_type": "ControlNetApply", "inputs": {
        "conditioning": ["2", 0], "control_net": ["5", 0],
        "image": ["4", 0], "strength": strength}}

    # 7. KSampler
    wf["7"] = {"class_type": "KSampler", "inputs": {
        "seed": seed_actual, "steps": steps, "cfg": cfg,
        "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0,
        "model": model_out, "positive": ["6", 0], "negative": ["3", 0],
        "latent_image": ["8", 0]}}

    # 8. EmptyLatentImage
    wf["8"] = {"class_type": "EmptyLatentImage", "inputs": {
        "width": width, "height": height, "batch_size": 1}}

    # 9. VAEDecode
    wf["9"] = {"class_type": "VAEDecode", "inputs": {
        "samples": ["7", 0], "vae": ["1", 2]}}

    # 10. SaveImage
    wf["10"] = {"class_type": "SaveImage", "inputs": {
        "images": ["9", 0], "filename_prefix": f"{prefix}_{control_type}"}}

    return wf, seed_actual


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ControlNet 引导生图（Depth/OpenPose/SoftEdge/Tile/Inpaint/LineArt）",
    )
    parser.add_argument("prompt", nargs="?", help="画面描述")
    parser.add_argument("--ref", required=True, help="参考图文件名（ComfyUI/input/ 下）")
    parser.add_argument(
        "--type", choices=list(CONTROLNET_MODELS.keys()), default="depth",
        help="ControlNet 类型",
    )
    parser.add_argument("--strength", type=float, default=0.8, help="ControlNet 强度")
    parser.add_argument("--negative", default="", help="负向提示词")
    parser.add_argument("--seed", type=int, default=-1)
    parser.add_argument("--steps", type=int, default=28)
    parser.add_argument("--cfg", type=float, default=6.5)
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--raw", action="store_true", help="跳过 Ollama")
    parser.add_argument("--lora", default=None, help="LoRA 权重文件名")
    parser.add_argument("--lora-strength", type=float, default=0.9)
    parser.add_argument("--prefix", default="control")
    args = parser.parse_args()

    user = args.prompt
    if not user:
        user = input("请输入描述: ").strip()
    if not user:
        print("未输入内容，退出。", file=sys.stderr)
        sys.exit(1)

    prompt = user if args.raw else optimize_prompt(user)

    wf, seed_actual = build_controlnet_workflow(
        prompt, args.ref, args.type,
        negative=args.negative, seed=args.seed,
        steps=args.steps, cfg=args.cfg,
        strength=args.strength,
        width=args.width, height=args.height,
        lora_name=args.lora, lora_strength=args.lora_strength,
        prefix=args.prefix,
    )

    try:
        result = comfy_post_prompt(wf, prompt_url=COMFY_URL)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    prompt_id = result.get("prompt_id", "")

    print(f"\n====================")
    print(f"ControlNet ({args.type}) 已提交")
    print(f"====================")
    print(f"  prompt_id: {prompt_id}")
    print(f"  seed:      {seed_actual}")
    print(f"  参考图:    {args.ref}")
    print(f"  ControlNet: {CONTROLNET_MODELS[args.type]} (strength={args.strength})")
    if args.lora:
        print(f"  LoRA:      {args.lora} (strength={args.lora_strength})")
    print(f"  节点数:    {len(wf)}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)
