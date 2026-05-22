"""
角色 LoRA 文生图（Knives / Caster，默认 SDXL）。

用法示例：
  python go_knives_lora.py 穿白色连衣裙，海边日落
  python go_knives_lora.py --character caster 粉色战斗服，战斗姿势
  python go_knives_lora.py --count 4 --outfit "cyberpunk jacket, neon city"
  python go_knives_lora.py --sd15 --lora knives.safetensors   # 仅 Knives 旧版 SD1.5

环境变量：COMFY_URL、OLLAMA_URL、OLLAMA_MODEL（与 run.py 相同）
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sys
from pathlib import Path
from typing import Any

from comfy_utils import (
    AGENTS_DIR,
    bootstrap_agents_path,
    comfy_base_url,
    comfy_post_prompt,
    ollama_generate,
    resolve_comfy_root,
    wait_images,
)

bootstrap_agents_path()

HERE = AGENTS_DIR
WORKFLOW_SD15 = HERE / "workflow_knives_lora_sd15.json"
WORKFLOW_SDXL_KNIVES = HERE / "workflow_knives_lora_sdxl.json"
WORKFLOW_SDXL_CASTER = HERE / "workflow_caster_lora_sdxl.json"

COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188/prompt")

DEFAULT_PORTRAIT_TAGS = "upper body, cowboy shot, face focus, portrait"
DEFAULT_SDXL_WIDTH = 896
DEFAULT_SDXL_HEIGHT = 1152
DEFAULT_SDXL_LORA_STRENGTH = 0.9

CHARACTERS: dict[str, dict[str, Any]] = {
    "knives": {
        "display": "Knives",
        "trigger": "knives, closers",
        "workflow_sdxl": WORKFLOW_SDXL_KNIVES,
        "default_lora_sdxl": "knives_sdxl.safetensors",
        "default_lora_sd15": "knives.safetensors",
        "prefix_sdxl": "knives_lora_sdxl",
        "prefix_sd15": "knives_lora_sd15",
        "llm_role": "游戏 Closers 角色 Knives",
        "llm_skip": "knives、closers、1girl、solo、masterpiece",
        "hair_tags": (
            "long hair, straight hair, blunt bangs, hime cut, "
            "silver hair, grey hair, lavender hair, light purple hair"
        ),
        "eye_tags": (
            "gradient eyes, two-tone eyes, olive green eyes, green eyes, yellow-green eyes, "
            "small pupils, thick eyelashes, detailed eyes, thin eyebrows, symmetrical eyes, "
            "looking at viewer"
        ),
        "face_negative": (
            "asymmetric eyes, uneven eyes, mismatched eyes, crooked eyes, different eye heights, "
            "lazy eye, wonky eyes, cross-eyed, misaligned eyes, "
            "large pupils, round pupils, amber eyes, orange eyes, yellow eyes, solid yellow eyes, "
            "multicolored eyes, heterochromia, rainbow eyes"
        ),
        "sdxl_only": False,
    },
    "caster": {
        "display": "Caster",
        "trigger": "caster, closers",
        "workflow_sdxl": WORKFLOW_SDXL_CASTER,
        "default_lora_sdxl": "caster_sdxl.safetensors",
        "default_lora_sd15": None,
        "prefix_sdxl": "caster_lora_sdxl",
        "prefix_sd15": "caster_lora_sd15",
        "llm_role": "游戏 Closers 角色 Caster（粉毛、粉发、青蓝瞳）",
        "llm_skip": "caster、closers、1girl、solo、masterpiece、pink hair",
        "hair_tags": (
            "long hair, straight hair, blunt bangs, "
            "pink hair, light pink hair, pastel pink hair, bubblegum pink hair, "
            "salmon pink hair, cherry blossom pink hair"
        ),
        "eye_tags": (
            "blue eyes, cyan eyes, aqua eyes, bright blue eyes, gradient eyes, two-tone eyes, "
            "thick eyelashes, detailed eyes, thin eyebrows, symmetrical eyes, almond eyes, "
            "looking at viewer"
        ),
        "face_negative": (
            "asymmetric eyes, uneven eyes, mismatched eyes, crooked eyes, different eye heights, "
            "lazy eye, wonky eyes, cross-eyed, misaligned eyes, "
            "silver hair, grey hair, blonde hair, white hair, "
            "green eyes, yellow eyes, amber eyes, orange eyes, heterochromia, rainbow eyes"
        ),
        "sdxl_only": True,
    },
}

DEFAULT_NEGATIVE_SD15 = (
    "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, "
    "cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, "
    "username, blurry"
)
QUALITY_PREFIX_SDXL = "masterpiece, best quality, ultra detailed"
CHARACTER_BODY = "1girl, solo, character portrait, anime, game cg, high quality, {hair}, medium breasts, large breasts, curvy, slim waist"


def call_llm_outfit(user_text: str, char: dict[str, Any]) -> str:
    system = (
        f"你是 SDXL/动漫 LoRA 提示词助手。用户要生成{char['llm_role']}的图。\n"
        "只输出英文 danbooru 风格标签，用逗号分隔，不要编号、不要解释、不要加引号。\n"
        "必须描述：服装/outfit、姿势/pose、镜头/composition、背景/background、光线/lighting（若用户未提可合理补全）。\n"
        f"不要输出 {char['llm_skip']} 等（程序会自动加）。\n"
        "服装要具体（材质、颜色、款式），便于换装。\n"
    )
    text = ollama_generate(f"{system}\n\n用户描述：{user_text}")
    return ", ".join(part.strip() for part in text.replace("\n", ",").split(",") if part.strip())


def build_positive(outfit_tags: str, char: dict[str, Any], extra: str | None = None, sdxl: bool = False) -> str:
    quality = QUALITY_PREFIX_SDXL if sdxl else ""
    hair = char["hair_tags"]
    body = CHARACTER_BODY.format(hair=hair)
    face = f"eyes aligned, same eye level, balanced eyes, {char['eye_tags']}"
    parts = [quality, char["trigger"], body, face, outfit_tags]
    if extra:
        parts.append(extra.strip())
    return ", ".join(p for p in parts if p)


def default_negative(char: dict[str, Any], sdxl: bool) -> str:
    if not sdxl:
        return DEFAULT_NEGATIVE_SD15
    return (
        "worst quality, low quality, blurry, jpeg artifacts, bad anatomy, extra limbs, "
        "deformed hands, extra fingers, missing fingers, bad face, duplicate, watermark, text, "
        "logo, photorealistic, 3d render, western cartoon, multiple girls, boy, "
        + char["face_negative"]
    )


def submit(workflow: dict) -> str | None:
    body = comfy_post_prompt(workflow, prompt_url=COMFY_URL)
    return body.get("prompt_id")


def apply_workflow(
    workflow: dict,
    *,
    positive: str,
    negative: str,
    lora_name: str,
    strength: float,
    prefix: str,
    use_portrait: bool,
    use_sdxl: bool,
    ckpt: str | None,
    width: int | None,
    height: int | None,
    steps: int | None,
    cfg: float | None,
) -> None:
    workflow["6"]["inputs"]["text"] = positive
    workflow["7"]["inputs"]["text"] = negative
    workflow["12"]["inputs"]["lora_name"] = lora_name
    workflow["12"]["inputs"]["strength_model"] = strength
    workflow["12"]["inputs"]["strength_clip"] = strength
    workflow["3"]["inputs"]["seed"] = random.randint(1, 2**48 - 1)
    workflow["9"]["inputs"]["filename_prefix"] = prefix
    if ckpt:
        workflow["4"]["inputs"]["ckpt_name"] = ckpt
    if use_sdxl and width is None and height is None and use_portrait:
        workflow["5"]["inputs"]["width"] = DEFAULT_SDXL_WIDTH
        workflow["5"]["inputs"]["height"] = DEFAULT_SDXL_HEIGHT
    if width is not None:
        workflow["5"]["inputs"]["width"] = width
    if height is not None:
        workflow["5"]["inputs"]["height"] = height
    if steps is not None:
        workflow["3"]["inputs"]["steps"] = steps
    if cfg is not None:
        workflow["3"]["inputs"]["cfg"] = cfg


def copy_outputs(prompt_id: str, draft_dir: Path, prefix: str, index: int) -> int:
    base = comfy_base_url(COMFY_URL)
    out_comfy = resolve_comfy_root() / "output"
    copied = 0
    for sub, name in wait_images(prompt_id, base):
        if not name.lower().endswith((".png", ".webp", ".jpg", ".jpeg")):
            continue
        src = out_comfy / sub / name if sub else out_comfy / name
        if not src.is_file():
            continue
        dest = draft_dir / f"{prefix}_{index:02d}_{name}"
        shutil.copy2(src, dest)
        print(f"  已复制: {dest}")
        copied += 1
    return copied


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Closers 角色 LoRA 文生图（Knives / Caster，ComfyUI + 可选 Ollama）",
    )
    parser.add_argument(
        "--character",
        choices=sorted(CHARACTERS),
        default="knives",
        help="角色预设（默认 knives）",
    )
    parser.add_argument("prompt", nargs="?", help="服装/场景/姿势等自然语言描述")
    parser.add_argument("--outfit", default=None)
    parser.add_argument("--pose", default=None)
    parser.add_argument("--raw", action="store_true", help="跳过 Ollama，prompt 作换装 tag")
    parser.add_argument("--full-raw", action="store_true")
    parser.add_argument("--positive", default=None)
    parser.add_argument("--negative", default=None)
    parser.add_argument("--lora", default=None)
    parser.add_argument("--lora-strength", type=float, default=None)
    parser.add_argument("--ckpt", default=None)
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument("--steps", type=int, default=None)
    parser.add_argument("--cfg", type=float, default=None)
    parser.add_argument("--prefix", default=None)
    parser.add_argument("--sd15", action="store_true", help="SD1.5（仅 knives 支持）")
    parser.add_argument("--portrait", dest="portrait", action="store_true", default=None)
    parser.add_argument("--no-portrait", dest="portrait", action="store_false")
    parser.add_argument("--full-body", action="store_true")
    parser.add_argument("--count", type=int, default=1, help="连续提交张数（>1 时等待并复制到 --out）")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="批量出图复制目录（默认 C:\\DrawingLive\\ai生图草稿库）",
    )
    args = parser.parse_args()

    char = CHARACTERS[args.character]
    use_sdxl = not args.sd15
    if args.sd15:
        if char.get("sdxl_only"):
            print(f"提示: {char['display']} 无 SD1.5 LoRA，已改用 SDXL。", file=sys.stderr)
            use_sdxl = True
        else:
            print("提示: 使用 SD1.5 旧 LoRA；主流程请用 SDXL。", file=sys.stderr)

    user = args.prompt or ""
    if args.outfit:
        user = f"{user} {args.outfit}".strip() if user else args.outfit.strip()
    if not user and not args.positive:
        user = input("请输入服装/场景描述: ").strip()
    if not user and not args.positive:
        print("未输入描述，退出。", file=sys.stderr)
        sys.exit(1)

    if args.positive:
        positive = args.positive
    elif args.full_raw:
        positive = user
    elif args.raw:
        positive = build_positive(user, char, args.pose, sdxl=use_sdxl)
    else:
        try:
            positive = build_positive(call_llm_outfit(user, char), char, args.pose, sdxl=use_sdxl)
        except RuntimeError as exc:
            print(exc, file=sys.stderr)
            sys.exit(1)

    negative = args.negative or default_negative(char, use_sdxl)
    use_portrait = use_sdxl and not args.full_body
    if args.portrait is True:
        use_portrait = True
    elif args.portrait is False:
        use_portrait = False
    if use_portrait and "upper body" not in positive.lower():
        positive = positive + ", " + DEFAULT_PORTRAIT_TAGS

    lora_name = args.lora or (
        char["default_lora_sdxl"] if use_sdxl else (char["default_lora_sd15"] or "knives.safetensors")
    )
    strength = args.lora_strength
    if strength is None:
        strength = DEFAULT_SDXL_LORA_STRENGTH if use_sdxl else 0.8
    strength = max(0.0, min(2.0, strength))

    prefix_base = args.prefix or (char["prefix_sdxl"] if use_sdxl else char["prefix_sd15"])
    draft_dir = args.out or Path(r"C:\DrawingLive\ai生图草稿库")
    count = max(1, args.count)

    with open(
        char["workflow_sdxl"] if use_sdxl else WORKFLOW_SD15,
        encoding="utf-8",
    ) as f:
        template = json.load(f)

    total_copied = 0
    for i in range(count):
        workflow = json.loads(json.dumps(template))
        file_prefix = f"{prefix_base}_batch_{i+1:02d}" if count > 1 else prefix_base
        apply_workflow(
            workflow,
            positive=positive,
            negative=negative,
            lora_name=lora_name,
            strength=strength,
            prefix=file_prefix,
            use_portrait=use_portrait,
            use_sdxl=use_sdxl,
            ckpt=args.ckpt,
            width=args.width,
            height=args.height,
            steps=args.steps,
            cfg=args.cfg,
        )
        prompt_id = submit(workflow)
        if count > 1 and prompt_id:
            draft_dir.mkdir(parents=True, exist_ok=True)
            tag = prefix_base.replace("_lora_sdxl", "").replace("_lora_sd15", "")
            total_copied += copy_outputs(prompt_id, draft_dir, tag, i + 1)
            print(f"[{i+1}/{count}] prompt_id={prompt_id}")

    print("\n====================")
    print(f"已提交 {char['display']} LoRA 文生图" + (f" ×{count}" if count > 1 else ""))
    print("====================")
    print("正向：", positive)
    print("LoRA：", lora_name, f"strength={strength}")
    if count > 1:
        print(f"批量完成，共复制 {total_copied} 张到 {draft_dir}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, TimeoutError, FileNotFoundError, KeyError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)
