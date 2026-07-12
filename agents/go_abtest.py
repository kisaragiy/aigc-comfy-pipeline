"""
A/B 测试 — Prompt 对比 + Best of N 自动挑优。

用法示例:
  python go_abtest.py abtest --prompts "夕阳少女" "夜景少女" --seed 42
  python go_abtest.py bestof "赛博朋克城市" --count 4
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from comfy_utils import (
    bootstrap_agents_path,
    comfy_base_url,
    comfy_post_prompt,
    optimize_prompt,
    resolve_comfy_root,
    wait_images,
)

bootstrap_agents_path()

from go_flux import build_flux_workflow  # noqa: E402
from output_manager import save_run, save_workflow_outputs  # noqa: E402

COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188/prompt")


def _score_image(image_path: str, prompt: str) -> float | None:
    """尝试 CLIP 评分，失败返回 None。"""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from go_validate import validate_image
        result = validate_image(image_path, prompt)
        clip = result.get("clip_score", {})
        if clip.get("available") and clip.get("score") is not None:
            return clip["score"]
    except Exception:
        pass
    return None


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
            score = r.get("clip_score", "?")
            label = f"#{idx+1} seed={r.get('seed','?')} score={score}"
        else:
            label = f"Prompt {chr(65+idx)} seed={r.get('seed','?')}"
            if r.get("clip_score") is not None:
                label += f" score={r['clip_score']}"

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


def _submit_flux(
    prompt: str,
    seed: int,
    **kwargs: Any,
) -> tuple[str | None, int]:
    """提交 Flux 工作流，返回 (prompt_id, actual_seed)。"""
    wf, seed_actual = build_flux_workflow(
        prompt=prompt,
        seed=seed,
        steps=kwargs.get("steps", 20),
        cfg=kwargs.get("cfg", 1.0),
        width=kwargs.get("width", 1024),
        height=kwargs.get("height", 1024),
        model_variant=kwargs.get("model", "9b"),
        lora_name=kwargs.get("lora"),
        lora_strength=kwargs.get("lora_strength", 1.0),
        filename_prefix=f"abtest_{kwargs.get('label','')}",
    )
    result = comfy_post_prompt(wf, prompt_url=COMFY_URL)
    return result.get("prompt_id"), seed_actual


def _collect_image(prompt_id: str, base: str) -> str | None:
    """等待出图并返回图片路径。"""
    if prompt_id == "dry-run":
        return None
    try:
        images = wait_images(prompt_id, base)
    except (TimeoutError, RuntimeError):
        return None
    if not images:
        return None
    comfy_root = resolve_comfy_root()
    for sub, name in images:
        path = (comfy_root / "output" / sub / name).resolve()
        if path.is_file():
            return str(path)
    return None


def run_abtest(
    prompts: list[str],
    seed: int,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """A/B 测试：同 seed 不同 prompt。"""
    base = comfy_base_url(COMFY_URL)
    results: list[dict[str, Any]] = []

    for i, prompt_text in enumerate(prompts):
        label = chr(65 + i)  # A, B
        print(f"[{label}] 提交: {prompt_text[:60]}...")

        pid, seed_actual = _submit_flux(prompt_text, seed, label=label, **kwargs)
        img_path = _collect_image(pid, base)

        result: dict[str, Any] = {
            "prompt": prompt_text,
            "label": label,
            "seed": seed_actual,
            "image": img_path,
        }

        if img_path:
            score = _score_image(img_path, prompt_text)
            result["clip_score"] = score
            print(f"  {'✅' if score is not None else '⚠️'} seed={seed_actual}"
                  f"{f' score={score:.3f}' if score is not None else ''}")
        else:
            print(f"  {'[dry-run] 跳过' if pid == 'dry-run' else '❌ 无出图'}")

        results.append(result)

    # 对比图
    if any(r["image"] for r in results):
        grid_path = f"abtest_comparison.jpg"
        _make_grid(results, grid_path, mode="abtest")

    # 归档
    all_images = [r["image"] for r in results if r.get("image")]
    if all_images:
        meta = {
            "mode": "abtest",
            "prompts": prompts,
            "seed": seed,
            "results": [{"label": r["label"], "seed": r["seed"],
                         "clip_score": r.get("clip_score")}
                        for r in results],
        }
        save_run("abtest", all_images, meta)

    return results


def run_bestof(
    prompt: str,
    count: int,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Best of N：同 prompt 多 seed，按 CLIP 评分排名。"""
    import random
    base = comfy_base_url(COMFY_URL)
    results: list[dict[str, Any]] = []

    for i in range(count):
        seed = random.randint(1, 2**48 - 1)
        label = f"bo{i+1}"
        print(f"  [{i+1}/{count}] submit seed={seed}...")

        pid, seed_actual = _submit_flux(prompt, seed, label=label, **kwargs)
        img_path = _collect_image(pid, base)

        result: dict[str, Any] = {
            "prompt": prompt,
            "seed": seed_actual,
            "image": img_path,
        }

        if img_path:
            score = _score_image(img_path, prompt)
            result["clip_score"] = score
            print(f"    {'✅' if score is not None else '⚠️'} "
                  f"{f'score={score:.3f}' if score is not None else ''}")
        else:
            print(f"    {'[dry-run]' if pid == 'dry-run' else '❌'}")

        results.append(result)

    # 按 CLIP 评分排序（降序）
    valid = [r for r in results if r.get("clip_score") is not None]
    valid.sort(key=lambda r: r["clip_score"], reverse=True)
    for i, r in enumerate(valid):
        r["rank"] = i + 1

    # 排名图
    ranked = valid + [r for r in results if r.get("clip_score") is None]
    if any(r["image"] for r in ranked):
        grid_path = f"bestof_ranking.jpg"
        _make_grid(ranked, grid_path, mode="bestof")

    # 归档
    all_images = [r["image"] for r in results if r.get("image")]
    if all_images:
        meta = {
            "mode": "bestof",
            "prompt": prompt,
            "count": count,
            "results": [{"seed": r["seed"], "clip_score": r.get("clip_score"),
                         "rank": r.get("rank")}
                        for r in results],
        }
        save_run("bestof", all_images, meta)

    # 打印排名
    if valid:
        print(f"\n🏆 Best of {count} 排名:")
        for r in valid[:3]:
            print(f"  #{r['rank']} seed={r['seed']} score={r['clip_score']:.3f}")

    return results


def main_abtest() -> None:
    """A/B 测试入口。"""
    parser = argparse.ArgumentParser(
        description="A/B 测试 — Prompt A vs B 同 seed 对比",
    )
    parser.add_argument("--prompts", nargs=2, required=True,
                        help="两个 prompt（A vs B）")
    parser.add_argument("--seed", type=int, default=-1)
    parser.add_argument("--model", choices=["9b", "4b"], default="9b")
    parser.add_argument("--lora", default=None)
    parser.add_argument("--lora-strength", type=float, default=1.0)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--cfg", type=float, default=1.0)
    parser.add_argument("--raw", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    prompts = [p if args.raw else optimize_prompt(p) for p in args.prompts]
    run_abtest(prompts, args.seed, model=args.model, lora=args.lora,
               lora_strength=args.lora_strength, steps=args.steps, cfg=args.cfg)


def main_bestof() -> None:
    """Best of N 入口。"""
    parser = argparse.ArgumentParser(
        description="Best of N — 多 seed 自动挑优",
    )
    parser.add_argument("prompt", help="画面描述")
    parser.add_argument("--count", type=int, default=4, help="生成张数")
    parser.add_argument("--model", choices=["9b", "4b"], default="9b")
    parser.add_argument("--lora", default=None)
    parser.add_argument("--lora-strength", type=float, default=1.0)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--cfg", type=float, default=1.0)
    parser.add_argument("--raw", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    prompt = args.prompt if args.raw else optimize_prompt(args.prompt)
    run_bestof(prompt, args.count, model=args.model, lora=args.lora,
               lora_strength=args.lora_strength, steps=args.steps, cfg=args.cfg)


def main() -> None:
    """旧版入口（通过 python go_abtest.py 直接运行）。"""
    parser = argparse.ArgumentParser(
        description="A/B 测试 — Prompt 对比 / Best of N 自动挑优",
    )
    sub = parser.add_subparsers(dest="mode", required=True)
    p_ab = sub.add_parser("abtest", help="Prompt A vs B 同 seed 对比")
    p_ab.add_argument("--prompts", nargs=2, required=True)
    p_ab.add_argument("--seed", type=int, default=-1)
    p_ab.add_argument("--model", choices=["9b", "4b"], default="9b")
    p_ab.add_argument("--lora", default=None)
    p_ab.add_argument("--dry-run", action="store_true")
    p_bo = sub.add_parser("bestof", help="多 seed 自动挑优")
    p_bo.add_argument("prompt")
    p_bo.add_argument("--count", type=int, default=4)
    p_bo.add_argument("--model", choices=["9b", "4b"], default="9b")
    p_bo.add_argument("--lora", default=None)
    p_bo.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.mode == "abtest":
        main_abtest()
    else:
        main_bestof()


if __name__ == "__main__":
    main()
