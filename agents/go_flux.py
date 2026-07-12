"""
Flux.2 Klein 文生图 — 程序化构建工作流 + CLI。

用法示例:
  python go_flux.py "赛博朋克少女，霓虹夜景，半身像"
  python go_flux.py --raw "cinematic, cyberpunk girl, portrait"
  python go_flux.py --lora knives_flux_lora.safetensors "白色连衣裙"
  python go_flux.py --model 4b "prompt"
  python go_flux.py --width 1280 --height 720 "prompt"
"""
from __future__ import annotations

import argparse
import os
import random
import sys
from pathlib import Path
from typing import Any

from comfy_utils import (
    AGENTS_DIR,
    bootstrap_agents_path,
    comfy_post_prompt,
    optimize_prompt,
)

bootstrap_agents_path()

HERE = AGENTS_DIR
COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188/prompt")

# 模型配置
MODEL_CONFIGS: dict[str, dict[str, str]] = {
    "9b": {
        "unet": "flux-2-klein-9b-fp8.safetensors",
        "clip": "qwen_3_8b_fp8mixed.safetensors",
        "vae": "flux2-vae.safetensors",
    },
    "4b": {
        "unet": "flux-2-klein-4b-fp8.safetensors",
        "clip": "qwen_3_06b_base.safetensors",
        "vae": "flux2-vae.safetensors",
    },
}


def build_flux_workflow(
    prompt: str,
    *,
    negative_prompt: str = "",
    seed: int = -1,
    steps: int = 20,
    cfg: float = 1.0,
    width: int = 1024,
    height: int = 1024,
    model_variant: str = "9b",
    lora_name: str | None = None,
    lora_strength: float = 1.0,
    sampler: str = "euler",
    scheduler: str = "normal",
    filename_prefix: str = "flux_klein",
) -> tuple[dict[str, Any], int]:
    """构建 Flux.2 Klein API 格式工作流。

    Args:
        prompt: 正向提示词
        negative_prompt: 负向提示词
        seed: 随机种子（-1 自动生成）
        steps: 采样步数
        cfg: CFG 引导强度（Flux 建议 1.0）
        width/height: 输出尺寸（16 的倍数）
        model_variant: "9b" 或 "4b"
        lora_name: LoRA 权重文件名（可选）
        lora_strength: LoRA 权重强度
        sampler: 采样器名称
        scheduler: 调度器
        filename_prefix: 输出文件名前缀

    Returns:
        (workflow_dict, actual_seed)
    """
    config = MODEL_CONFIGS.get(model_variant, MODEL_CONFIGS["9b"])

    # 自动编号
    nid = [0]
    def nxt() -> str:
        nid[0] += 1
        return str(nid[0])

    wf: dict[str, Any] = {}

    # 1. UNETLoader
    n1 = nxt()
    wf[n1] = {"class_type": "UNETLoader", "inputs": {
        "unet_name": config["unet"], "weight_dtype": "default"}}

    # 2. CLIPLoader
    n2 = nxt()
    wf[n2] = {"class_type": "CLIPLoader", "inputs": {
        "clip_name": config["clip"], "type": "flux2"}}

    # 3. VAELoader
    n3 = nxt()
    wf[n3] = {"class_type": "VAELoader", "inputs": {
        "vae_name": config["vae"]}}

    # LoRA 注入（可选，插在 UNET/CLIP 之后）
    model_out = [n1, 0]
    clip_out = [n2, 0]
    if lora_name:
        nl = nxt()
        wf[nl] = {"class_type": "LoraLoader", "inputs": {
            "model": [n1, 0], "clip": [n2, 0],
            "lora_name": lora_name,
            "strength_model": lora_strength,
            "strength_clip": lora_strength}}
        model_out = [nl, 0]
        clip_out = [nl, 1]

    # 4. CLIPTextEncode (positive)
    n4 = nxt()
    wf[n4] = {"class_type": "CLIPTextEncode", "inputs": {
        "text": prompt, "clip": clip_out}}

    # 5. ConditioningZeroOut (negative conditioning)
    n5 = nxt()
    wf[n5] = {"class_type": "ConditioningZeroOut", "inputs": {
        "conditioning": [n4, 0]}}

    # 如果用户提供了 negative_prompt，单独编码并 zero-out
    neg_conditioning = [n5, 0]
    if negative_prompt:
        nn = nxt()
        wf[nn] = {"class_type": "CLIPTextEncode", "inputs": {
            "text": negative_prompt, "clip": clip_out}}
        nz = nxt()
        wf[nz] = {"class_type": "ConditioningZeroOut", "inputs": {
            "conditioning": [nn, 0]}}
        neg_conditioning = [nz, 0]

    # 6. EmptyFlux2LatentImage
    n6 = nxt()
    wf[n6] = {"class_type": "EmptyFlux2LatentImage", "inputs": {
        "width": width, "height": height, "batch_size": 1}}

    # 7. Flux2Scheduler
    n7 = nxt()
    wf[n7] = {"class_type": "Flux2Scheduler", "inputs": {
        "steps": steps, "width": width, "height": height}}

    # 8. KSamplerSelect
    n8 = nxt()
    wf[n8] = {"class_type": "KSamplerSelect", "inputs": {
        "sampler_name": sampler}}

    # 9. RandomNoise
    seed_actual = seed if seed != -1 else random.randint(1, 2**48 - 1)
    n9 = nxt()
    wf[n9] = {"class_type": "RandomNoise", "inputs": {
        "noise_seed": seed_actual}}

    # 10. CFGGuider
    n10 = nxt()
    wf[n10] = {"class_type": "CFGGuider", "inputs": {
        "model": model_out,
        "positive": [n4, 0],
        "negative": neg_conditioning,
        "cfg": cfg}}

    # 11. SamplerCustomAdvanced
    n11 = nxt()
    wf[n11] = {"class_type": "SamplerCustomAdvanced", "inputs": {
        "noise": [n9, 0], "guider": [n10, 0],
        "sampler": [n8, 0], "sigmas": [n7, 0],
        "latent_image": [n6, 0]}}

    # 12. VAEDecode
    n12 = nxt()
    wf[n12] = {"class_type": "VAEDecode", "inputs": {
        "samples": [n11, 0], "vae": [n3, 0]}}

    # 13. SaveImage
    n13 = nxt()
    wf[n13] = {"class_type": "SaveImage", "inputs": {
        "images": [n12, 0], "filename_prefix": filename_prefix}}

    return wf, seed_actual


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Flux.2 Klein 文生图 — 程序化构建工作流（9B/4B，支持 LoRA）",
    )
    parser.add_argument("prompt", nargs="?", help="画面描述（自然语言，经 Ollama 转写）")
    parser.add_argument("--raw", action="store_true", help="跳过 Ollama，prompt 作正向提示词")
    parser.add_argument("--negative", default="", help="负向提示词")
    parser.add_argument("--seed", type=int, default=-1, help="随机种子（-1 自动）")
    parser.add_argument("--steps", type=int, default=None, help="采样步数（预设自动）")
    parser.add_argument("--cfg", type=float, default=None, help="CFG 引导强度（预设自动）")
    parser.add_argument("--width", type=int, default=1024, help="输出宽度")
    parser.add_argument("--height", type=int, default=1024, help="输出高度")
    parser.add_argument("--model", choices=["9b", "4b"], default="9b", help="模型变体")
    parser.add_argument("--lora", default=None, help="LoRA 权重文件名")
    parser.add_argument("--lora-strength", type=float, default=1.0, help="LoRA 权重")
    parser.add_argument("--sampler", default=None, help="采样器（预设自动）")
    parser.add_argument("--scheduler", default=None, help="调度器（预设自动）")
    parser.add_argument("--prefix", default="flux_klein", help="输出文件名前缀")
    parser.add_argument("--preset", choices=["quality", "balanced", "fast", "portrait"],
                        default=None, help="质量预设")
    parser.add_argument("--min-score", type=float, default=0.0,
                        help="最低 CLIP 评分（≤0 跳过验证）")
    parser.add_argument("--retry", type=int, default=0,
                        help="质量不合格时最大重试次数")
    parser.add_argument("--no-validate", action="store_true",
                        help="跳过质量验证")
    args = parser.parse_args()

    user = args.prompt
    if not user:
        user = input("请输入描述: ").strip()
    if not user:
        print("未输入内容，退出。", file=sys.stderr)
        sys.exit(1)

    # 提示词处理：Ollama 优化或 raw
    if args.raw:
        positive = user
    else:
        positive = optimize_prompt(user)
        print(f"[info] 优化后提示词: {positive[:300]}...")

    # 使用质量预设 + 自动门禁
    from comfy_utils import generate_with_quality

    qr = generate_with_quality(
        build_flux_workflow, positive,
        min_score=args.min_score if not args.no_validate else 0.0,
        max_retries=args.retry,
        preset=args.preset,
        seed=args.seed,
        steps=args.steps,
        cfg=args.cfg,
        width=args.width,
        height=args.height,
        model_variant=args.model,
        lora_name=args.lora,
        lora_strength=args.lora_strength,
        sampler=args.sampler,
        scheduler=args.scheduler,
        filename_prefix=args.prefix,
        negative_prompt=args.negative,
    )

    prompt_id = qr.get("prompt_id", "")
    seed_actual = qr.get("seed", 0)
    images = qr.get("images", [])

    if images:
        from output_manager import save_workflow_outputs
        from comfy_utils import comfy_base_url

        save_workflow_outputs(
            qr.get("prompt_id", "?"),
            comfy_base_url(COMFY_URL),
            "flux",
            {
                "prompt": positive,
                "seed": seed_actual,
                "model": args.model,
                "lora": args.lora,
                "lora_strength": args.lora_strength,
                "score": qr.get("score"),
                "retries": qr.get("retries", 0),
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


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)
