"""
ControlNet 引导生图 — Flux / SDXL 双架构，支持 Depth/OpenPose/SoftEdge/Tile/Inpaint/LineArt。
默认使用 Flux.2 Klein 架构，--model sdxl 回退到 SDXL 工作流。

用法示例:
  python go_control.py "prompt" --ref ref.png --type depth
  python go_control.py "prompt" --ref pose.png --type openpose --strength 0.6
  python go_control.py "prompt" --ref sketch.png --type softedge --raw
  python go_control.py "prompt" --ref ref.png --type depth --model 4b --preset anime
"""
from __future__ import annotations

import argparse
import os
import random
import sys
from pathlib import Path
from typing import Any

from comfy_utils import (
    bootstrap_agents_path,
    comfy_base_url,
    generate_with_quality,
    optimize_prompt,
)

bootstrap_agents_path()

# === ControlNet 模型映射 ===
# key=type: (sdxl_model, flux_model_hint)
# flux 模型需要用户自行下载（见 models download controlnet-flux）
CONTROLNET_MODELS: dict[str, tuple[str, str | None]] = {
    "depth":     ("controlnet-depth-sdxl-1.0.safetensors",             "flux-controlnet-depth-v1.safetensors"),
    "openpose":  ("OpenPoseXL2.safetensors",                           "flux-controlnet-openpose-v1.safetensors"),
    "softedge":  ("controlnet-sd-xl-1.0-softedge-dexined.safetensors",  "flux-controlnet-softedge-v1.safetensors"),
    "tile":      ("controlnet-tile-sdxl-1.0.safetensors",               "flux-controlnet-tile-v1.safetensors"),
    "inpaint":   ("controlnet_inpaint_sdxl1.safetensors",               "flux-controlnet-inpaint-v1.safetensors"),
    "lineart":   ("Kataragi_lineartXL-lora128.safetensors",             "flux-controlnet-lineart-v1.safetensors"),
}

# Flux 模型配置（同 go_flux.py）
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


def _find_model(
    control_type: str,
    model_variant: str,
    models_root: Path | None = None,
) -> str:
    """查找 ControlNet 模型文件。Flux 优先，回退到 SDXL。"""
    sdxl_model, flux_model = CONTROLNET_MODELS.get(
        control_type, (CONTROLNET_MODELS["depth"][0], CONTROLNET_MODELS["depth"][1]))

    if model_variant != "sdxl" and flux_model and models_root:
        cn_dir = models_root / "controlnet"
        if (cn_dir / flux_model).is_file():
            return flux_model

    # 回退到 SDXL 模型
    return sdxl_model


def build_controlnet_workflow(
    prompt: str,
    ref_image: str,
    control_type: str = "depth",
    *,
    negative: str = "",
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
    strength: float = 0.8,
    prefix: str = "control",
    ckpt: str = "NoobAI-XL-v1.1.safetensors",
) -> tuple[dict[str, Any], int]:
    """构建 Flux/SDXL + ControlNet 工作流。

    model_variant="sdxl" → SDXL 工作流（使用已安装的 SDXL ControlNet 模型）
    model_variant="9b|4b" → Flux.2 Klein 工作流（需要 Flux ControlNet 模型）
    """
    if model_variant == "sdxl":
        return _build_sdxl_controlnet_workflow(
            prompt, ref_image, control_type,
            negative=negative, seed=seed, steps=steps, cfg=cfg,
            sampler=sampler, scheduler=scheduler, strength=strength,
            width=width, height=height,
            lora_name=lora_name, lora_strength=lora_strength,
            prefix=prefix, ckpt=ckpt,
        )
    return _build_flux_controlnet_workflow(
        prompt, ref_image, control_type,
        negative=negative, seed=seed, steps=steps, cfg=cfg,
        width=width, height=height,
        model_variant=model_variant,
        lora_name=lora_name, lora_strength=lora_strength,
        sampler=sampler, scheduler=scheduler,
        strength=strength, prefix=prefix,
    )


def _build_flux_controlnet_workflow(
    prompt: str,
    ref_image: str,
    control_type: str = "depth",
    *,
    negative: str = "",
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
    strength: float = 0.8,
    prefix: str = "control",
) -> tuple[dict[str, Any], int]:
    """构建 Flux.2 Klein + ControlNet 工作流。"""
    config = MODEL_CONFIGS.get(model_variant, MODEL_CONFIGS["9b"])

    # 查找模型
    models_root = None
    try:
        from comfy_utils import resolve_comfy_root
        r = resolve_comfy_root()
        if r:
            models_root = r / "models"
    except Exception:
        pass
    cn_model = _find_model(control_type, model_variant, models_root)

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

    # LoRA 注入
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

    # 5. ControlNetLoader
    n5 = nxt()
    wf[n5] = {"class_type": "ControlNetLoader", "inputs": {
        "control_net_name": cn_model}}

    # 6. LoadImage (reference)
    n6 = nxt()
    wf[n6] = {"class_type": "LoadImage", "inputs": {"image": ref_image}}

    # 7. ControlNetApplyAdvanced (Flux: 像素 image + 可选 vae 输入)
    n7 = nxt()
    wf[n7] = {"class_type": "ControlNetApplyAdvanced", "inputs": {
        "positive": [n4, 0], "negative": [n4, 0],
        "control_net": [n5, 0], "image": [n6, 0],
        "strength": strength, "start_percent": 0.0, "end_percent": 1.0,
        "vae": [n3, 0]}}

    # 8. ConditioningZeroOut (negative)
    n8 = nxt()
    wf[n8] = {"class_type": "ConditioningZeroOut", "inputs": {
        "conditioning": [n7, 0]}}

    neg_conditioning = [n8, 0]
    if negative:
        nn = nxt()
        wf[nn] = {"class_type": "CLIPTextEncode", "inputs": {
            "text": negative, "clip": clip_out}}
        nz = nxt()
        wf[nz] = {"class_type": "ConditioningZeroOut", "inputs": {
            "conditioning": [nn, 0]}}
        neg_conditioning = [nz, 0]

    # 9. EmptyFlux2LatentImage
    n9 = nxt()
    wf[n9] = {"class_type": "EmptyFlux2LatentImage", "inputs": {
        "width": width, "height": height, "batch_size": 1}}

    # 10. Flux2Scheduler
    n10 = nxt()
    wf[n10] = {"class_type": "Flux2Scheduler", "inputs": {
        "steps": steps, "width": width, "height": height}}

    # 11. KSamplerSelect
    n11 = nxt()
    wf[n11] = {"class_type": "KSamplerSelect", "inputs": {
        "sampler_name": sampler}}

    # 12. RandomNoise
    seed_actual = seed if seed != -1 else random.randint(1, 2**48 - 1)
    n12 = nxt()
    wf[n12] = {"class_type": "RandomNoise", "inputs": {
        "noise_seed": seed_actual}}

    # 13. CFGGuider (positive 来自 ControlNetApply 输出)
    n13 = nxt()
    wf[n13] = {"class_type": "CFGGuider", "inputs": {
        "model": model_out,
        "positive": [n7, 0],
        "negative": neg_conditioning,
        "cfg": cfg}}

    # 14. SamplerCustomAdvanced
    n14 = nxt()
    wf[n14] = {"class_type": "SamplerCustomAdvanced", "inputs": {
        "noise": [n12, 0], "guider": [n13, 0],
        "sampler": [n11, 0], "sigmas": [n10, 0],
        "latent_image": [n9, 0]}}

    # 15. VAEDecode
    n15 = nxt()
    wf[n15] = {"class_type": "VAEDecode", "inputs": {
        "samples": [n14, 0], "vae": [n3, 0]}}

    # 16. SaveImage
    n16 = nxt()
    wf[n16] = {"class_type": "SaveImage", "inputs": {
        "images": [n15, 0], "filename_prefix": f"{prefix}_{control_type}"}}

    return wf, seed_actual


def _build_sdxl_controlnet_workflow(
    prompt: str,
    ref_image: str,
    control_type: str = "depth",
    *,
    negative: str = "",
    seed: int = -1,
    steps: int = 20,
    cfg: float = 5.0,
    sampler: str = "dpmpp_2m",
    scheduler: str = "karras",
    strength: float = 0.8,
    width: int = 1024,
    height: int = 1024,
    lora_name: str | None = None,
    lora_strength: float = 0.9,
    prefix: str = "control",
    ckpt: str = "NoobAI-XL-v1.1.safetensors",
) -> tuple[dict[str, Any], int]:
    """构建 SDXL + ControlNet 工作流（原版回退）。"""
    sdxl_model, _ = CONTROLNET_MODELS.get(control_type, (CONTROLNET_MODELS["depth"][0], None))
    seed_actual = seed if seed != -1 else random.randint(1, 2**48 - 1)

    wf: dict[str, Any] = {}

    # 1. CheckpointLoader
    wf["1"] = {"class_type": "CheckpointLoaderSimple", "inputs": {
        "ckpt_name": ckpt}}

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
        "control_net_name": sdxl_model}}

    # 6. ControlNetApply
    wf["6"] = {"class_type": "ControlNetApply", "inputs": {
        "conditioning": ["2", 0], "control_net": ["5", 0],
        "image": ["4", 0], "strength": strength}}

    # 7. KSampler
    wf["7"] = {"class_type": "KSampler", "inputs": {
        "seed": seed_actual, "steps": steps, "cfg": cfg,
        "sampler_name": sampler, "scheduler": scheduler, "denoise": 1.0,
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
        description="ControlNet 引导生图（Depth/OpenPose/SoftEdge/Tile/Inpaint/LineArt）— 默认 Flux 架构",
    )
    parser.add_argument("prompt", nargs="?", help="画面描述")
    parser.add_argument("--ref", required=True, help="参考图文件名（ComfyUI/input/ 下）")
    parser.add_argument(
        "--type", choices=list(CONTROLNET_MODELS.keys()), default="depth",
        help="ControlNet 类型",
    )
    parser.add_argument("--strength", type=float, default=0.8, help="ControlNet 强度")
    parser.add_argument("--model", choices=["9b", "4b", "sdxl"], default="9b",
                        help="模型架构：9b/4b(Flux) / sdxl")
    parser.add_argument("--ckpt", default="NoobAI-XL-v1.1.safetensors",
                        help="SDXL 模式下的 checkpoint 文件名（默认 NoobAI-XL-v1.1）")
    parser.add_argument("--negative", default="", help="负向提示词")
    parser.add_argument("--seed", type=int, default=-1)
    parser.add_argument("--steps", type=int, default=None, help="采样步数（预设自动）")
    parser.add_argument("--cfg", type=float, default=None, help="CFG 引导强度（预设自动）")
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--raw", action="store_true", help="跳过 Ollama")
    parser.add_argument("--sampler", default=None, help="采样器（预设自动）")
    parser.add_argument("--scheduler", default=None, help="调度器（预设自动）")
    parser.add_argument("--lora", default=None, help="LoRA 权重文件名")
    parser.add_argument("--lora-strength", type=float, default=1.0)
    parser.add_argument("--prefix", default="control")

    # 质量预设 + 门禁
    parser.add_argument("--preset", default=None, help="质量预设（anime/photoreal 等）")
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

    prompt = user if args.raw else optimize_prompt(user)

    qr = generate_with_quality(
        build_controlnet_workflow, prompt,
        min_score=args.min_score if not args.no_validate else 0.0,
        max_retries=args.retry,
        preset=args.preset,
        seed=args.seed,
        ref_image=args.ref,
        control_type=args.type,
        strength=args.strength,
        steps=args.steps, cfg=args.cfg,
        sampler=args.sampler, scheduler=args.scheduler,
        width=args.width, height=args.height,
        model_variant=args.model,
        ckpt=args.ckpt,
        negative=args.negative,
        lora_name=args.lora, lora_strength=args.lora_strength,
        prefix=args.prefix,
    )

    wf = qr["workflow"]
    seed_actual = qr["seed"]

    sdxl_model, flux_model = CONTROLNET_MODELS[args.type]
    cn_name = flux_model if args.model != "sdxl" and flux_model else sdxl_model

    print(f"\n====================")
    print(f"ControlNet ({args.type}) — 架构: {args.model}")
    print(f"====================")
    print(f"  prompt_id: {qr.get('prompt_id', '')}")
    print(f"  seed:      {seed_actual}")
    print(f"  参考图:    {args.ref}")
    print(f"  模型:      {cn_name} (strength={args.strength})")
    if args.lora:
        print(f"  LoRA:      {args.lora} (strength={args.lora_strength})")
    if args.model != "sdxl":
        print(f"  Unet:      {MODEL_CONFIGS.get(args.model, MODEL_CONFIGS['9b'])['unet']}")
    print(f"  节点数:    {len(wf)}")
    score = qr.get("score")
    if score is not None and score > 0:
        print(f"  质量评分:  {score:.3f}")
    if qr.get("retries", 0) > 0:
        print(f"  重试次数:  {qr['retries']}")

    if args.model != "sdxl" and not flux_model:
        print(f"\n💡 提示: Flux ControlNet 模型下载:")
        print(f"   python -m agents models download <flux-{args.type}-model-url>")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)
