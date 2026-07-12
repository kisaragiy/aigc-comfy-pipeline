"""
A/B 测试 — Prompt 对比 + Best of N 自动挑优，升级 generate_with_quality。

用法示例:
  python -m agents abtest --prompts "夕阳少女" "夜景少女" --seed 42
  python -m agents abtest --prompts "A prompt" "B prompt" --preset anime --min-score 0.2
  python -m agents bestof "赛博朋克城市" --count 4 --preset quality
  python -m agents bestof "prompt" --count 6 --retry 2 --min-score 0.25
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from comfy_utils import (
    bootstrap_agents_path,
    generate_with_quality,
    optimize_prompt,
)

bootstrap_agents_path()

from go_flux import build_flux_workflow  # noqa: E402
from output_manager import save_run  # noqa: E402


def _make_grid(
    results: list[dict[str, Any]],
    output_path: str,
    mode: str = "abtest",
) -> None:
    """生成对比/排名网格图。"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("[warn] Pillow 未安装，跳过网格图生成")
        return

    valid = [(r, r["image"]) for r in results if r.get("image")]
    if not valid:
        return

    n = len(valid)
    if mode == "abtest":
        cols = min(2, n)
        rows = (n + 1) // 2
    else:
        cols = min(3, n)
        rows = (n + cols - 1) // cols

    samples = [Image.open(img).convert("RGB") for _, img in valid]
    cell_w = max(im.width for im in samples)
    cell_h = max(im.height for im in samples)
    label_h = 50

    grid = Image.new("RGB", (cell_w * cols, (cell_h + label_h) * rows), (32, 32, 32))
    draw = ImageDraw.Draw(grid)

    try:
        font = ImageFont.truetype("arial.ttf", 13)
    except OSError:
        font = ImageFont.load_default()

    for idx, (r, img_path) in enumerate(valid):
        col = idx % cols
        row = idx // cols
        x = col * cell_w
        y = row * (cell_h + label_h)

        # 标注
        if mode == "bestof":
            score = r.get("score", "?")
            label = f"#{idx+1} seed={r.get('seed','?')} score={score}"
        else:
            label = f"Prompt {chr(65+idx)} seed={r.get('seed','?')}"
            if r.get("score") is not None:
                label += f" score={r['score']}"

        draw.rectangle([x, y, x + cell_w, y + label_h], fill=(48, 48, 48))
        draw.text((x + 6, y + 6), label[:60], fill=(255, 255, 255), font=font)

        # 图片
        im = Image.open(img_path).convert("RGB")
        im.thumbnail((cell_w, cell_h), Image.LANCZOS)
        paste_y = y + label_h
        grid.paste(
            im,
            (x + (cell_w - im.width) // 2, paste_y + (cell_h - im.height) // 2),
        )

    grid.save(output_path, quality=92)
    print(f"  对比图: {output_path}")


def run_abtest(
    prompts: list[str],
    seed: int,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """A/B 测试：同 seed 不同 prompt（走 generate_with_quality）。

    Args:
        prompts: 两个 prompt
        seed: 统一 seed（-1=随机）
        kwargs: 透传给 generate_with_quality 的参数（preset, min_score, retry, steps, cfg 等）
    """
    results: list[dict[str, Any]] = []

    # AB 测试用同一个 seed 公平对比
    ab_seed = seed if seed != -1 else None  # 由 generate_with_quality 随机化

    for i, prompt_text in enumerate(prompts):
        label = chr(65 + i)  # A, B
        print(f"[{label}] 提交: {prompt_text[:60]}...")

        # 从 kwargs 中提取 quality 参数
        quality_kwargs = {
            k: kwargs[k] for k in ("preset", "min_score", "retry", "no_validate")
            if k in kwargs and kwargs[k] is not None
        }

        result = generate_with_quality(
            build_flux_workflow,
            prompt_text,
            seed=ab_seed,
            model=kwargs.get("model", "9b"),
            lora=kwargs.get("lora"),
            lora_strength=kwargs.get("lora_strength", 1.0),
            steps=kwargs.get("steps", 20),
            cfg=kwargs.get("cfg", 1.0),
            width=kwargs.get("width", 1024),
            height=kwargs.get("height", 1024),
            filename_prefix=f"abtest_{label.lower()}",
            **quality_kwargs,
        )

        images = result.get("images", [])
        seed_actual = result.get("seed", 0)
        score = result.get("score")

        entry: dict[str, Any] = {
            "prompt": prompt_text,
            "label": label,
            "seed": seed_actual,
            "image": images[0] if images else None,
            "score": score,
        }
        results.append(entry)

        if entry["image"]:
            s = f" score={score:.3f}" if score is not None else ""
            print(f"  {'✅' if score is not None else '⚠️'} seed={seed_actual}{s}")
        else:
            print(f"  {'[dry-run] 跳过' if seed_actual == 'dry-run' else '❌ 无出图'}")

    # 对比图
    if any(r["image"] for r in results):
        grid_path = "abtest_comparison.jpg"
        _make_grid(results, grid_path, mode="abtest")

    # 归档
    all_images = [r["image"] for r in results if r.get("image")]
    if all_images:
        meta = {
            "mode": "abtest",
            "prompts": prompts,
            "quality_params": {k: kwargs.get(k) for k in ("preset", "min_score", "retry") if kwargs.get(k) is not None},
            "results": [{"label": r["label"], "seed": r["seed"], "score": r.get("score")} for r in results],
        }
        save_run("abtest", all_images, meta)

    return results


def run_bestof(
    prompt: str,
    count: int,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Best of N：同 prompt 多 seed，按评分排名（走 generate_with_quality）。

    Args:
        prompt: 提示词
        count: 生成张数
        kwargs: 透传给 generate_with_quality 的参数
    """
    results: list[dict[str, Any]] = []

    quality_kwargs = {
        k: kwargs[k] for k in ("preset", "min_score", "retry", "no_validate")
        if k in kwargs and kwargs[k] is not None
    }

    for i in range(count):
        print(f"  [{i+1}/{count}] 提交 (seed=随机)...")

        result = generate_with_quality(
            build_flux_workflow,
            prompt,
            seed=-1,  # 每次随机
            model=kwargs.get("model", "9b"),
            lora=kwargs.get("lora"),
            lora_strength=kwargs.get("lora_strength", 1.0),
            steps=kwargs.get("steps", 20),
            cfg=kwargs.get("cfg", 1.0),
            width=kwargs.get("width", 1024),
            height=kwargs.get("height", 1024),
            filename_prefix=f"bestof_{i+1}",
            **quality_kwargs,
        )

        images = result.get("images", [])
        seed_actual = result.get("seed", 0)
        score = result.get("score")

        entry: dict[str, Any] = {
            "prompt": prompt,
            "seed": seed_actual,
            "image": images[0] if images else None,
            "score": score,
        }
        results.append(entry)

        if entry["image"]:
            s = f" score={score:.3f}" if score is not None else ""
            print(f"    {'✅' if score is not None else '⚠️'} seed={seed_actual}{s}")
        else:
            print(f"    {'[dry-run]' if seed_actual == 'dry-run' else '❌'}")

    # 按评分排序（降序）
    valid = [r for r in results if r.get("score") is not None]
    valid.sort(key=lambda r: r["score"], reverse=True)
    for i, r in enumerate(valid):
        r["rank"] = i + 1

    # 排名图
    ranked = valid + [r for r in results if r.get("score") is None]
    if any(r["image"] for r in ranked):
        grid_path = "bestof_ranking.jpg"
        _make_grid(ranked, grid_path, mode="bestof")

    # 归档
    all_images = [r["image"] for r in results if r.get("image")]
    if all_images:
        meta = {
            "mode": "bestof",
            "prompt": prompt,
            "count": count,
            "quality_params": {k: kwargs.get(k) for k in ("preset", "min_score", "retry") if kwargs.get(k) is not None},
            "results": [{"seed": r["seed"], "score": r.get("score"), "rank": r.get("rank")} for r in results],
        }
        save_run("bestof", all_images, meta)

    # 打印排名
    if valid:
        print(f"\n🏆 Best of {count} 排名:")
        for r in valid[:3]:
            print(f"  #{r['rank']} seed={r['seed']} score={r['score']:.3f}")

    return results


def _add_quality_args(parser: argparse.ArgumentParser) -> None:
    """添加质量门禁相关 CLI 参数。"""
    parser.add_argument("--preset", default=None,
                        help="质量预设 (quality/balanced/fast/portrait/anime/photoreal)")
    parser.add_argument("--min-score", type=float, default=0.0,
                        help="CLIP 评分阈值（0=跳过验证）")
    parser.add_argument("--retry", type=int, default=0,
                        help="不合格时最大重试次数")
    parser.add_argument("--no-validate", action="store_true",
                        help="强制跳过质量验证")


def main_abtest() -> None:
    """A/B 测试入口。"""
    parser = argparse.ArgumentParser(
        description="A/B 测试 — Prompt A vs B 同 seed 对比（走质量门禁）",
    )
    parser.add_argument("--prompts", nargs=2, required=True,
                        help="两个 prompt（A vs B）")
    parser.add_argument("--seed", type=int, default=-1, help="统一 seed（-1=随机）")
    parser.add_argument("--model", choices=["9b", "4b"], default="9b")
    parser.add_argument("--lora", default=None)
    parser.add_argument("--lora-strength", type=float, default=1.0)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--cfg", type=float, default=1.0)
    parser.add_argument("--raw", action="store_true")
    _add_quality_args(parser)
    args = parser.parse_args()

    prompts = [p if args.raw else optimize_prompt(p) for p in args.prompts]
    run_abtest(
        prompts, args.seed,
        model=args.model, lora=args.lora,
        lora_strength=args.lora_strength,
        steps=args.steps, cfg=args.cfg,
        preset=args.preset, min_score=args.min_score,
        retry=args.retry, no_validate=args.no_validate,
    )


def main_bestof() -> None:
    """Best of N 入口。"""
    parser = argparse.ArgumentParser(
        description="Best of N — 多 seed 自动挑优（走质量门禁）",
    )
    parser.add_argument("prompt", help="画面描述")
    parser.add_argument("--count", type=int, default=4, help="生成张数")
    parser.add_argument("--model", choices=["9b", "4b"], default="9b")
    parser.add_argument("--lora", default=None)
    parser.add_argument("--lora-strength", type=float, default=1.0)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--cfg", type=float, default=1.0)
    parser.add_argument("--raw", action="store_true")
    _add_quality_args(parser)
    args = parser.parse_args()

    prompt = args.prompt if args.raw else optimize_prompt(args.prompt)
    run_bestof(
        prompt, args.count,
        model=args.model, lora=args.lora,
        lora_strength=args.lora_strength,
        steps=args.steps, cfg=args.cfg,
        preset=args.preset, min_score=args.min_score,
        retry=args.retry, no_validate=args.no_validate,
    )


def main() -> None:
    """旧版入口（通过 python go_abtest.py 直接运行）。"""
    parser = argparse.ArgumentParser(
        description="A/B 测试 — Prompt 对比 / Best of N 自动挑优（质量门禁）",
    )
    sub = parser.add_subparsers(dest="mode", required=True)
    p_ab = sub.add_parser("abtest", help="Prompt A vs B 同 seed 对比")
    p_ab.add_argument("--prompts", nargs=2, required=True)
    p_ab.add_argument("--seed", type=int, default=-1)
    p_ab.add_argument("--model", choices=["9b", "4b"], default="9b")
    p_ab.add_argument("--lora", default=None)
    p_ab.add_argument("--dry-run", action="store_true")
    _add_quality_args(p_ab)
    p_bo = sub.add_parser("bestof", help="多 seed 自动挑优")
    p_bo.add_argument("prompt")
    p_bo.add_argument("--count", type=int, default=4)
    p_bo.add_argument("--model", choices=["9b", "4b"], default="9b")
    p_bo.add_argument("--lora", default=None)
    p_bo.add_argument("--dry-run", action="store_true")
    _add_quality_args(p_bo)
    args = parser.parse_args()
    if args.mode == "abtest":
        main_abtest()
    else:
        main_bestof()


if __name__ == "__main__":
    main()
