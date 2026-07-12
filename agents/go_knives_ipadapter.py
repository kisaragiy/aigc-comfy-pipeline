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
from typing import Any

from comfy_utils import AGENTS_DIR, bootstrap_agents_path, comfy_post_prompt, generate_with_quality

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


def build_ipa_workflow(
    prompt: str,
    *,
    negative_prompt: str = "",
    seed: int = -1,
    steps: int | None = None,
    cfg: float | None = None,
    width: int | None = None,
    height: int | None = None,
    ref_image: str = DEFAULT_REF,
    ipa_weight: float = 0.48,
    ipa_end: float = 1.0,
    ipa_preset: str = "PLUS FACE (portraits)",
    weight_type: str = "prompt is more important",
    lora_name: str = "knives_sdxl.safetensors",
    lora_strength: float = 0.85,
    portrait: bool = True,
    ckpt: str | None = None,
    filename_prefix: str = "knives_ipa_sdxl",
    sampler: str | None = None,
    scheduler: str | None = None,
) -> tuple[dict[str, Any], int]:
    """构建 SDXL + LoRA + IPAdapter 工作流。"""
    template = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    wf = json.loads(json.dumps(template))

    seed_actual = seed if seed != -1 else random.randint(1, 2**48 - 1)
    strength = max(0.0, min(2.0, lora_strength))

    wf["6"]["inputs"]["text"] = prompt
    wf["7"]["inputs"]["text"] = negative_prompt
    wf["10"]["inputs"]["image"] = ref_image
    wf["11"]["inputs"]["weight"] = max(-1.0, min(3.0, ipa_weight))
    wf["11"]["inputs"]["end_at"] = max(0.0, min(1.0, ipa_end))
    wf["11"]["inputs"]["weight_type"] = weight_type
    wf["20"]["inputs"]["preset"] = ipa_preset
    wf["12"]["inputs"]["lora_name"] = lora_name
    wf["12"]["inputs"]["strength_model"] = strength
    wf["12"]["inputs"]["strength_clip"] = strength
    wf["3"]["inputs"]["seed"] = seed_actual
    wf["9"]["inputs"]["filename_prefix"] = filename_prefix
    if ckpt:
        wf["4"]["inputs"]["ckpt_name"] = ckpt
    if portrait and width is None and height is None:
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

    qr = generate_with_quality(
        lambda prompt, **kw: build_ipa_workflow(
            prompt,
            ref_image=args.ref_image,
            ipa_weight=args.ipa_weight,
            ipa_end=args.ipa_end,
            ipa_preset=args.ipa_preset,
            weight_type=args.weight_type,
            lora_name=args.lora,
            lora_strength=args.lora_strength,
            portrait=use_portrait,
            ckpt=args.ckpt,
            filename_prefix=args.prefix or "knives_ipa_sdxl",
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
        from comfy_utils import comfy_base_url

        save_workflow_outputs(
            prompt_id,
            comfy_base_url(COMFY_URL),
            "ipa",
            {
                "prompt": positive,
                "reference": args.ref_image,
                "ipa_weight": args.ipa_weight,
                "lora": args.lora,
                "seed": seed_actual,
                "score": qr.get("score"),
                "retries": qr.get("retries", 0),
            },
        )

    print("\n====================")
    print("已提交 Knives LoRA + IPAdapter")
    print("====================")
    print("正向：", positive)
    print("参考图：", args.ref_image)
    print("IPAdapter：", args.ipa_preset, f"weight={args.ipa_weight}", f"type={args.weight_type}")
    print("LoRA：", args.lora, f"strength={max(0.0, min(2.0, args.lora_strength))}")
    score = qr.get("score")
    if score is not None:
        print(f"  CLIP 评分: {score:.3f}")
    retries = qr.get("retries", 0)
    if retries > 0:
        print(f"  重试次数:  {retries}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)
