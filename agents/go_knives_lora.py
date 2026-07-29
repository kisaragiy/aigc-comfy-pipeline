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
    generate_with_quality,
    ollama_generate_or_fallback,
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
    text = ollama_generate_or_fallback(f"{system}\n\n用户描述：{user_text}", fallback=user_text)
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


def build_lora_workflow(
    prompt: str,
    *,
    negative_prompt: str = "",
    seed: int = -1,
    steps: int | None = None,
    cfg: float | None = None,
    width: int | None = None,
    height: int | None = None,
    character: str = "knives",
    lora_name: str = "",
    lora_strength: float = 0.9,
    sd15: bool = False,
    portrait: bool = True,
    ckpt: str | None = None,
    filename_prefix: str = "",
    sampler: str | None = None,
    scheduler: str | None = None,
) -> tuple[dict[str, Any], int]:
    """构建 SDXL/SD1.5 + LoRA 工作流。"""
    char = CHARACTERS[character]
    use_sdxl = not sd15
    actual_prefix = filename_prefix or (char["prefix_sdxl"] if use_sdxl else char["prefix_sd15"])

    wf_path = char["workflow_sdxl"] if use_sdxl else WORKFLOW_SD15
    template = json.loads(wf_path.read_text(encoding="utf-8"))
    wf = json.loads(json.dumps(template))

    seed_actual = seed if seed != -1 else random.randint(1, 2**48 - 1)
    wf["6"]["inputs"]["text"] = prompt
    wf["7"]["inputs"]["text"] = negative_prompt
    wf["12"]["inputs"]["lora_name"] = lora_name
    wf["12"]["inputs"]["strength_model"] = max(0.0, min(2.0, lora_strength))
    wf["12"]["inputs"]["strength_clip"] = max(0.0, min(2.0, lora_strength))
    wf["3"]["inputs"]["seed"] = seed_actual
    wf["9"]["inputs"]["filename_prefix"] = actual_prefix
    if ckpt:
        wf["4"]["inputs"]["ckpt_name"] = ckpt
    if use_sdxl and portrait and width is None and height is None:
        wf["5"]["inputs"]["width"] = DEFAULT_SDXL_WIDTH
        wf["5"]["inputs"]["height"] = DEFAULT_SDXL_HEIGHT
    if width is not None:
        wf["5"]["inputs"]["width"] = width
    if height is not None:
        wf["5"]["inputs"]["height"] = height
    if steps is not None:
        wf["3"]["inputs"]["steps"] = steps
    if cfg is not None:
        wf["3"]["inputs"]["cfg"] = cfg
    return wf, seed_actual


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
    # 质量门禁参数
    parser.add_argument("--seed", type=int, default=-1, help="随机种子（-1 自动）")
    parser.add_argument("--preset", default=None, help="SDXL 质量预设（暂未实现）")
    parser.add_argument("--min-score", type=float, default=0.0,
                        help="最低 CLIP 评分（≤0 跳过验证）")
    parser.add_argument("--retry", type=int, default=0,
                        help="质量不合格时最大重试次数")
    parser.add_argument("--no-validate", action="store_true",
                        help="跳过质量验证")
    args = parser.parse_args()

    char = CHARACTERS[args.character]
    use_sdxl = not args.sd15
    if args.sd15:
        if char.get("sdxl_only"):
            print(f"提示: {char['display']} 无 SD1.5 LoRA，已改用 SDXL。", file=sys.stderr)
            use_sdxl = True
        else:
            print("提示: 使用 SD1.5 旧 LoRA；主流程请用 SDXL。", file=sys.stderr)

    # 提示词构建
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
        positive = build_positive(call_llm_outfit(user, char), char, args.pose, sdxl=use_sdxl)

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

    if count == 1:
        # 单张模式：使用 generate_with_quality（质量门禁 + 重试）
        qr = generate_with_quality(
            lambda prompt, **kw: build_lora_workflow(
                prompt,
                character=args.character,
                lora_name=lora_name,
                lora_strength=strength,
                sd15=args.sd15,
                portrait=use_portrait,
                ckpt=args.ckpt,
                filename_prefix=prefix_base,
                **{k: v for k, v in kw.items()
                   if k in ("seed", "steps", "cfg", "width", "height",
                            "negative_prompt", "sampler", "scheduler")},
            ),
            positive,
            min_score=args.min_score if not args.no_validate else 0.0,
            max_retries=args.retry,
            preset=args.preset,
            seed=args.seed,
            negative_prompt=negative,
            steps=args.steps,
            cfg=args.cfg,
            width=args.width,
            height=args.height,
        )

        prompt_id = qr.get("prompt_id", "")
        seed_actual = qr.get("seed", 0)
        images = qr.get("images", [])

        if images:
            from output_manager import save_workflow_outputs
            save_workflow_outputs(
                prompt_id,
                comfy_base_url(COMFY_URL),
                "lora",
                {
                    "prompt": positive,
                    "negative": negative,
                    "seed": seed_actual,
                    "lora": lora_name,
                    "lora_strength": strength,
                    "character": args.character,
                    "score": qr.get("score"),
                    "retries": qr.get("retries", 0),
                },
            )

        print("\n====================")
        print(f"已提交 {char['display']} LoRA 文生图")
        print("====================")
        print("正向：", positive)
        print("LoRA：", lora_name, f"strength={strength}")
        score = qr.get("score")
        if score is not None:
            print(f"  CLIP 评分: {score:.3f}")
        retries = qr.get("retries", 0)
        if retries > 0:
            print(f"  重试次数:  {retries}")
    else:
        # 批量模式：保持原有逻辑（直接提交 + 复制）
        total_copied = 0
        for i in range(count):
            wf, seed_actual = build_lora_workflow(
                positive,
                negative_prompt=negative,
                seed=args.seed if args.seed != -1 else -1,
                steps=args.steps,
                cfg=args.cfg,
                width=args.width,
                height=args.height,
                character=args.character,
                lora_name=lora_name,
                lora_strength=strength,
                sd15=args.sd15,
                portrait=use_portrait,
                ckpt=args.ckpt,
                filename_prefix=f"{prefix_base}_batch_{i+1:02d}" if count > 1 else prefix_base,
            )
            prompt_id_ = comfy_post_prompt(wf, prompt_url=COMFY_URL).get("prompt_id", "")
            if prompt_id_:
                draft_dir.mkdir(parents=True, exist_ok=True)
                tag = prefix_base.replace("_lora_sdxl", "").replace("_lora_sd15", "")
                total_copied += copy_outputs(prompt_id_, draft_dir, tag, i + 1)
                print(f"[{i+1}/{count}] prompt_id={prompt_id_}")

        print("\n====================")
        print(f"已提交 {char['display']} LoRA 文生图 ×{count}")
        print("====================")
        print("正向：", positive)
        print("LoRA：", lora_name, f"strength={strength}")
        print(f"批量完成，共复制 {total_copied} 张到 {draft_dir}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, TimeoutError, FileNotFoundError, KeyError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)


def build_sdxl_workflow(
    prompt: str,
    *,
    seed: int = -1,
    steps: int = 20,
    cfg: float = 7.0,
    width: int = 1024,
    height: int = 1024,
    filename_prefix: str = "pipeline_sdxl",
    ckpt: str | None = None,
    negative_prompt: str = "",
    lora_name: str | None = None,
    lora_strength: float = 0.9,
) -> dict[str, Any]:
    """构建 SDXL API 格式工作流。

    Args:
        lora_name: LoRA 文件名（不传=禁用 LoRA，传=使用指定 LoRA）
        lora_strength: LoRA 强度（默认 0.9）
    """
    # 选模板：有 LoRA 用 knives，无 LoRA 用 multi_char（比较干净）
    if lora_name:
        template_path = HERE / "workflow_knives_lora_sdxl.json"
    else:
        template_path = HERE / "workflow_multi_char_lora_sdxl.json"
    if not template_path.is_file():
        template_path = HERE / "workflow_knives_lora_sdxl.json"

    with open(template_path, encoding="utf-8") as f:
        wf = json.load(f)

    seed_actual = seed if seed != -1 else random.randint(1, 2**48 - 1)

    # ── 固定节点 ID 注入（SDXL 模板的约定） ──
    # Node 6 = 正向 prompt, Node 7 = 负向 prompt
    for nid in ("6", "7"):
        if nid in wf and wf[nid].get("class_type") in ("CLIPTextEncode", "CLIPTextEncodeSDXL"):
            wf[nid]["inputs"]["text"] = prompt if nid == "6" else (negative_prompt if negative_prompt else "")

    # Node 5 = EmptyLatentImage
    if "5" in wf and wf["5"].get("class_type") == "EmptyLatentImage":
        wf["5"]["inputs"]["width"] = width
        wf["5"]["inputs"]["height"] = height

    # Node 3 = KSampler
    if "3" in wf and wf["3"].get("class_type") in ("KSampler", "KSamplerAdvanced"):
        wf["3"]["inputs"]["seed"] = seed_actual
        wf["3"]["inputs"]["steps"] = steps
        wf["3"]["inputs"]["cfg"] = cfg

    # Node 9 = SaveImage
    if "9" in wf and wf["9"].get("class_type") == "SaveImage":
        wf["9"]["inputs"]["filename_prefix"] = filename_prefix

    # ── LoRA 处理 ──
    if lora_name:
        # 有 LoRA：找到第一个 LoraLoader 注入
        for nid, node in wf.items():
            if node.get("class_type") == "LoraLoader":
                node["inputs"]["lora_name"] = lora_name
                node["inputs"]["strength_model"] = lora_strength
                node["inputs"]["strength_clip"] = lora_strength
                break
    else:
        # 无 LoRA：所有 LoraLoader 禁用（用有效文件名+0强度）
        for nid, node in wf.items():
            if node.get("class_type") == "LoraLoader":
                node["inputs"]["lora_name"] = "caster_sdxl.safetensors"
                node["inputs"]["strength_model"] = 0.0
                node["inputs"]["strength_clip"] = 0.0

    # ── 覆盖 checkpoint ──
    if ckpt:
        for nid, node in wf.items():
            if node.get("class_type") in ("CheckpointLoaderSimple",):
                node["inputs"]["ckpt_name"] = ckpt
                break
    return wf


def build_anima_workflow(
    prompt: str,
    *,
    seed: int = -1,
    steps: int = 28,
    cfg: float = 6.5,
    width: int = 1024,
    height: int = 1024,
    filename_prefix: str = "pipeline_anima",
    negative_prompt: str = "",
    lora_name: str | None = None,
    lora_strength: float = 0.9,
) -> dict[str, Any]:
    """构建 Anima 工作流（UNETLoader + DualCLIPLoader）。"""
    wf = {}
    nid = [0]
    def nxt():
        nid[0] += 1
        return str(nid[0])
    seed_actual = seed if seed != -1 else random.randint(1, 2**48 - 1)

    n1 = nxt(); wf[n1] = {"class_type": "UNETLoader", "inputs": {"unet_name": "anima-base-v1.0.safetensors", "weight_dtype": "default"}}
    n2 = nxt(); wf[n2] = {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": "clip_l.safetensors", "clip_name2": "sd_xl_base_1.0.safetensors", "type": "sdxl"}}
    n3 = nxt(); wf[n3] = {"class_type": "VAELoader", "inputs": {"vae_name": "sdxl_vae.safetensors"}}

    mo, co = [n1, 0], [n2, 0]
    if lora_name:
        nl = nxt(); wf[nl] = {"class_type": "LoraLoader", "inputs": {"lora_name": lora_name, "strength_model": lora_strength, "strength_clip": lora_strength, "model": mo, "clip": co}}
        mo, co = [nl, 0], [nl, 1]

    n4 = nxt(); wf[n4] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": co}}
    n5 = nxt(); wf[n5] = {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt or "worst quality, low quality, blurry, bad anatomy, bad hands, ugly, deformed, extra limbs, fused fingers, missing fingers, extra fingers, mutated hands, poorly drawn face, bad eyes, cross-eyed, watermark, text", "clip": co}}
    n6 = nxt(); wf[n6] = {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}}
    n7 = nxt(); wf[n7] = {"class_type": "KSampler", "inputs": {"seed": seed_actual, "steps": steps, "cfg": cfg, "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1, "model": mo, "positive": [n4, 0], "negative": [n5, 0], "latent_image": [n6, 0]}}
    n8 = nxt(); wf[n8] = {"class_type": "VAEDecode", "inputs": {"samples": [n7, 0], "vae": [n3, 0]}}
    n9 = nxt(); wf[n9] = {"class_type": "SaveImage", "inputs": {"filename_prefix": filename_prefix, "images": [n8, 0]}}
    return wf


def build_sdxl_clean_workflow(
    prompt: str,
    *,
    seed: int = -1,
    steps: int = 25,
    cfg: float = 6.5,
    width: int = 1024,
    height: int = 1024,
    filename_prefix: str = "pipeline_sdxl",
    ckpt: str | None = None,
    negative_prompt: str = "",
    sampler: str = "dpmpp_2m",
    scheduler: str = "karras",
) -> dict[str, Any]:
    """纯净 SDXL 工作流 — 无FaceDetailer/无LoRA/无多余节点。

    仅包含: CheckpointLoaderSimple + CLIPTextEncode×2 + EmptyLatentImage
          + KSampler + VAEDecode + SaveImage
    """
    wf: dict[str, Any] = {}
    nid = [0]
    def nxt():
        nid[0] += 1
        return str(nid[0])

    seed_actual = seed if seed != -1 else __import__("random").randint(1, 2**48 - 1)

    # 1. CheckpointLoaderSimple
    n1 = nxt()
    wf[n1] = {"class_type": "CheckpointLoaderSimple", "inputs": {
        "ckpt_name": ckpt or "waiIllustriousSDXL_v160.safetensors"}}

    # 2. CLIPTextEncode (正向)
    n2 = nxt()
    wf[n2] = {"class_type": "CLIPTextEncode", "inputs": {
        "text": prompt, "clip": [n1, 1]}}

    # 3. CLIPTextEncode (负向)
    n3 = nxt()
    wf[n3] = {"class_type": "CLIPTextEncode", "inputs": {
        "text": negative_prompt, "clip": [n1, 1]}}

    # 4. EmptyLatentImage
    n4 = nxt()
    wf[n4] = {"class_type": "EmptyLatentImage", "inputs": {
        "width": width, "height": height, "batch_size": 1}}

    # 5. KSampler
    n5 = nxt()
    wf[n5] = {"class_type": "KSampler", "inputs": {
        "seed": seed_actual, "steps": steps, "cfg": cfg,
        "sampler_name": sampler, "scheduler": scheduler, "denoise": 1,
        "model": [n1, 0], "positive": [n2, 0], "negative": [n3, 0],
        "latent_image": [n4, 0]}}

    # 6. VAEDecode
    n6 = nxt()
    wf[n6] = {"class_type": "VAEDecode", "inputs": {
        "samples": [n5, 0], "vae": [n1, 2]}}

    # 7. SaveImage
    n7 = nxt()
    wf[n7] = {"class_type": "SaveImage", "inputs": {
        "filename_prefix": filename_prefix, "images": [n6, 0]}}

    return wf
