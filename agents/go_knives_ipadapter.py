"""
Knives SDXL：LoRA 身份 + IPAdapter PLUS FACE 锁脸/锁眼（Plan A）。

参考图默认 ComfyUI input/knives_face_ref.png（运行 setup_knives_ipadapter.ps1 从眼图集复制）。

用法：
  python go_knives_ipadapter.py 白色连衣裙，海边日落，微笑
  python go_knives_ipadapter.py --ipa-weight 0.48 --portrait
  python go_knives_ipadapter.py --ref-image 2000028.png --raw 红色战斗服，战斗姿势
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

from comfy_utils import AGENTS_DIR, bootstrap_agents_path, comfy_post_prompt

bootstrap_agents_path()

from go_knives_lora import (
    CHARACTERS,
    DEFAULT_PORTRAIT_TAGS,
    DEFAULT_SDXL_HEIGHT,
    DEFAULT_SDXL_LORA_STRENGTH,
    DEFAULT_SDXL_WIDTH,
    build_positive,
    call_llm_outfit,
    default_negative,
)

_KNIVES = CHARACTERS["knives"]

HERE = AGENTS_DIR
WORKFLOW = HERE / "workflow_knives_lora_sdxl_ipadapter.json"
COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188/prompt")
DEFAULT_REF = "knives_face_ref.png"


def load_workflow() -> dict:
    with open(WORKFLOW, "r", encoding="utf-8") as f:
        return json.load(f)


def submit(workflow: dict) -> None:
    comfy_post_prompt(workflow, prompt_url=COMFY_URL)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Knives SDXL LoRA + IPAdapter 锁脸文生图",
    )
    parser.add_argument("prompt", nargs="?", help="服装/场景/表情等自然语言")
    parser.add_argument("--outfit", default=None)
    parser.add_argument("--pose", default=None)
    parser.add_argument("--raw", action="store_true", help="跳过 Ollama，prompt 作换装 tag")
    parser.add_argument("--full-raw", action="store_true")
    parser.add_argument("--positive", default=None)
    parser.add_argument("--negative", default=None)
    parser.add_argument("--lora", default="knives_sdxl.safetensors")
    parser.add_argument("--lora-strength", type=float, default=0.85)
    parser.add_argument("--ckpt", default=None)
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument("--steps", type=int, default=None)
    parser.add_argument("--cfg", type=float, default=None)
    parser.add_argument("--prefix", default=None)
    parser.add_argument("--portrait", action="store_true", default=True)
    parser.add_argument("--full-body", action="store_true", help="全身构图（默认半身锁眼）")
    parser.add_argument(
        "--ref-image",
        default=DEFAULT_REF,
        help=f"ComfyUI/input 下参考图文件名（默认 {DEFAULT_REF}）",
    )
    parser.add_argument(
        "--ipa-weight",
        type=float,
        default=0.48,
        help="IPAdapter 权重；默认偏低让 LoRA 瞳孔渐变主导，不像可升到 0.58",
    )
    parser.add_argument(
        "--ipa-end",
        type=float,
        default=1.0,
        help="IPAdapter end_at（<1 可略放松锁脸，便于改表情）",
    )
    parser.add_argument(
        "--ipa-preset",
        default="PLUS FACE (portraits)",
        help="IPAdapterUnifiedLoader 预设",
    )
    parser.add_argument(
        "--weight-type",
        default="prompt is more important",
        choices=["standard", "prompt is more important", "style transfer"],
        help="IPAdapter 权重类型；改表情建议 prompt is more important",
    )
    args = parser.parse_args()

    user = args.prompt or ""
    if args.outfit:
        user = f"{user} {args.outfit}".strip() if user else args.outfit.strip()
    if not user and not args.positive:
        user = input("请输入服装/场景/表情描述: ").strip()
    if not user and not args.positive:
        print("未输入描述，退出。", file=sys.stderr)
        sys.exit(1)

    if args.positive:
        positive = args.positive
    elif args.full_raw:
        positive = user
    elif args.raw:
        positive = build_positive(user, _KNIVES, args.pose, sdxl=True)
    else:
        outfit_tags = call_llm_outfit(user, _KNIVES)
        positive = build_positive(outfit_tags, _KNIVES, args.pose, sdxl=True)

    use_portrait = args.portrait and not args.full_body
    if use_portrait and "upper body" not in positive.lower():
        positive = positive + ", " + DEFAULT_PORTRAIT_TAGS

    negative = args.negative or default_negative(_KNIVES, sdxl=True)
    workflow = load_workflow()

    workflow["6"]["inputs"]["text"] = positive
    workflow["7"]["inputs"]["text"] = negative
    workflow["10"]["inputs"]["image"] = args.ref_image
    workflow["11"]["inputs"]["weight"] = max(-1.0, min(3.0, args.ipa_weight))
    workflow["11"]["inputs"]["end_at"] = max(0.0, min(1.0, args.ipa_end))
    workflow["11"]["inputs"]["weight_type"] = args.weight_type
    workflow["20"]["inputs"]["preset"] = args.ipa_preset

    strength = max(0.0, min(2.0, args.lora_strength or DEFAULT_SDXL_LORA_STRENGTH))
    workflow["12"]["inputs"]["lora_name"] = args.lora
    workflow["12"]["inputs"]["strength_model"] = strength
    workflow["12"]["inputs"]["strength_clip"] = strength
    workflow["3"]["inputs"]["seed"] = random.randint(1, 2**48 - 1)
    workflow["9"]["inputs"]["filename_prefix"] = args.prefix or "knives_ipa_sdxl"

    if args.ckpt:
        workflow["4"]["inputs"]["ckpt_name"] = args.ckpt
    if use_portrait and args.width is None and args.height is None:
        workflow["5"]["inputs"]["width"] = DEFAULT_SDXL_WIDTH
        workflow["5"]["inputs"]["height"] = DEFAULT_SDXL_HEIGHT
    if args.width is not None:
        workflow["5"]["inputs"]["width"] = args.width
    if args.height is not None:
        workflow["5"]["inputs"]["height"] = args.height
    if args.steps is not None:
        workflow["3"]["inputs"]["steps"] = args.steps
    if args.cfg is not None:
        workflow["3"]["inputs"]["cfg"] = args.cfg

    try:
        submit(workflow)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    print("\n====================")
    print("已提交 Knives LoRA + IPAdapter")
    print("====================")
    print("正向：", positive)
    print("参考图：", args.ref_image)
    print("IPAdapter：", args.ipa_preset, f"weight={args.ipa_weight}", f"type={args.weight_type}")
    print("LoRA：", args.lora, f"strength={strength}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)
