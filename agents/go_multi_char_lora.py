"""
多角色 SDXL LoRA 同图：Knives + Caster（可扩展更多角色 LoRA）。

默认 workflow：双 LoRA + FaceDetailer 二次修脸（需 comfyui-impact-pack + face_yolov8m.pt）。

用法：
  python go_multi_char_lora.py Knives校服在左微笑，Caster粉毛连衣裙在右挥手，街道背景
  python go_multi_char_lora.py --raw 2girls, knives..., caster...
  python go_multi_char_lora.py --no-face-detail   # 跳过 FaceDetailer（无 impact-pack 时）
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import uuid
from pathlib import Path

from comfy_utils import AGENTS_DIR, bootstrap_agents_path, comfy_post_prompt, ollama_generate

bootstrap_agents_path()

HERE = AGENTS_DIR
WORKFLOW = HERE / "workflow_multi_char_lora_sdxl.json"
WORKFLOW_SIMPLE = HERE / "workflow_multi_char_lora_sdxl_simple.json"
COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188/prompt")

DEFAULT_POSITIVE = (
    "masterpiece, best quality, ultra detailed, 2girls, multiple girls, closers, anime, game cg, "
    "high quality, full body, wide shot, dynamic composition, different outfits, different poses, "
    "different expressions, "
    "(knives, closers, silver hair, grey hair, lavender hair, blunt bangs, hime cut, gradient eyes, "
    "two-tone eyes, olive green eyes, school uniform, on the left, smiling:1.2), "
    "(caster, closers, pink hair, light pink hair, bubblegum pink hair, blue eyes, cyan eyes, "
    "gradient eyes, dress, on the right, confident expression:1.2), detailed background, soft lighting"
)
DEFAULT_NEGATIVE = (
    "worst quality, low quality, blurry, jpeg artifacts, bad anatomy, extra limbs, deformed hands, "
    "bad face, watermark, text, 1girl, solo, boy, fused bodies, merged characters, same outfit, clone, "
    "silver hair on caster, pink hair on knives, wrong eye color"
)


def call_llm_scene(user_text: str) -> str:
    system = (
        "你是 SDXL 多角色 LoRA 提示词助手。画面中有 Closers 的 Knives（银灰发、橄榄绿渐变瞳）"
        "和 Caster（粉发粉毛、青蓝瞳），可能还有其他女角色。\n"
        "输出一整段英文 danbooru 标签（含 2girls/multiple girls、构图、每人服装姿势表情、左右位置）。\n"
        "每人用括号权重如 (knives, silver hair, ...:1.2) 与 (caster, pink hair, blue eyes, ...:1.2)。\n"
        "不要解释，不要编号。保留 knives/caster 触发词与发色瞳色约束。\n"
    )
    text = ollama_generate(f"{system}\n\n用户描述：{user_text}").strip().replace("\n", ", ")
    if not text.lower().startswith("masterpiece"):
        text = "masterpiece, best quality, ultra detailed, " + text
    return text


def load_workflow(use_face_detail: bool) -> dict:
    path = WORKFLOW if use_face_detail else WORKFLOW_SIMPLE
    if not path.is_file():
        path = WORKFLOW
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description="多角色 LoRA 同图（Knives + Caster + FaceDetailer）")
    parser.add_argument("prompt", nargs="?", help="场景/服装/姿势自然语言")
    parser.add_argument("--raw", action="store_true", help="prompt 作为完整正向词")
    parser.add_argument("--positive", default=None)
    parser.add_argument("--negative", default=None)
    parser.add_argument("--knives-lora", default="knives_sdxl.safetensors")
    parser.add_argument("--caster-lora", default="caster_sdxl.safetensors")
    parser.add_argument("--lora-strength", type=float, default=0.72)
    parser.add_argument("--width", type=int, default=1344)
    parser.add_argument("--height", type=int, default=896)
    parser.add_argument("--steps", type=int, default=32)
    parser.add_argument("--cfg", type=float, default=7.0)
    parser.add_argument("--prefix", default="multi_char_lora_sdxl")
    parser.add_argument("--no-face-detail", action="store_true", help="保存 VAEDecode 结果，不用 FaceDetailer")
    args = parser.parse_args()

    user = (args.prompt or "").strip()
    if not user and not args.positive:
        user = input("请输入多角色场景描述: ").strip()
    if not user and not args.positive:
        print("未输入描述，退出。", file=sys.stderr)
        sys.exit(1)

    if args.positive:
        positive = args.positive
    elif args.raw:
        positive = user
    else:
        try:
            positive = call_llm_scene(user)
        except RuntimeError as exc:
            print(exc, file=sys.stderr)
            sys.exit(1)

    negative = args.negative or DEFAULT_NEGATIVE
    use_fd = not args.no_face_detail
    wf = load_workflow(use_fd)

    wf["6"]["inputs"]["text"] = positive
    wf["7"]["inputs"]["text"] = negative
    wf["12"]["inputs"]["lora_name"] = args.knives_lora
    wf["13"]["inputs"]["lora_name"] = args.caster_lora
    s = max(0.0, min(1.2, args.lora_strength))
    wf["12"]["inputs"]["strength_model"] = s
    wf["12"]["inputs"]["strength_clip"] = s
    wf["13"]["inputs"]["strength_model"] = s
    wf["13"]["inputs"]["strength_clip"] = s
    wf["3"]["inputs"]["seed"] = random.randint(1, 2**48 - 1)
    wf["3"]["inputs"]["steps"] = args.steps
    wf["3"]["inputs"]["cfg"] = args.cfg
    wf["5"]["inputs"]["width"] = args.width
    wf["5"]["inputs"]["height"] = args.height
    wf["9"]["inputs"]["filename_prefix"] = args.prefix

    if use_fd and "30" in wf:
        wf["30"]["inputs"]["seed"] = random.randint(1, 2**48 - 1)
    elif not use_fd:
        wf["9"]["inputs"]["images"] = ["8", 0]

    try:
        comfy_post_prompt(wf, prompt_url=COMFY_URL)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    print("\n已提交多角色 LoRA 生图")
    print("正向：", positive[:500], "..." if len(positive) > 500 else "")
    print("FaceDetailer:", use_fd)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)
