"""
参数网格扫描 — Flux.2 Klein 批量迭代 + 自动对比拼图。

用法示例:
  python go_sweep.py "赛博朋克少女" --grid '{"steps":[20,30,40]}'
  python go_sweep.py "prompt" --grid '{"steps":[20,30],"cfg":[1.0,2.0]}'
  python go_sweep.py "prompt" --grid '{"steps":[20,30]}' --model 4b --lora knives_flux_lora.safetensors
"""
from __future__ import annotations

import json
import sys
from itertools import product
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

from output_manager import save_run  # noqa: E402


def expand_grid(grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """展开网格参数为平面组合列表。

    输入: {"steps": [20, 30], "cfg": [1.0, 2.0]}
    输出: [{"steps": 20, "cfg": 1.0}, {"steps": 20, "cfg": 2.0}, ...]
    """
    if not grid:
        return [{}]
    keys = list(grid.keys())
    values = list(grid.values())
    combinations = []
    for combo in product(*values):
        combinations.append(dict(zip(keys, combo)))
    return combinations


def build_sweep_label(params: dict[str, Any]) -> str:
    """从参数组合生成文件标签。"""
    return "_".join(f"{k}{v}" for k, v in params.items())


def run_sweep(
    prompt: str,
    grid: dict[str, list[Any]],
    *,
    model_variant: str = "9b",
    lora_name: str | None = None,
    lora_strength: float = 1.0,
    negative: str = "",
    prefix: str = "sweep",
) -> None:
    """执行网格扫描，归档并生成对比拼图。"""
    combinations = expand_grid(grid)
    n = len(combinations)
    print(f"网格扫描: {n} 个组合")
    for i, params in enumerate(combinations):
        print(f"  [{i+1}/{n}] {params}")

    base = comfy_base_url()
    results: list[dict[str, Any]] = []

    for i, params in enumerate(combinations):
        label = build_sweep_label(params)
        print(f"\n[{i+1}/{n}] 提交 {label}...")

        steps = params.get("steps", 20)
        cfg_v = params.get("cfg", 1.0)
        seed_v = params.get("seed", -1)
        width_v = params.get("width", 1024)
        height_v = params.get("height", 1024)

        wf, seed_actual = build_flux_workflow(
            prompt=prompt,
            negative_prompt=negative,
            seed=seed_v,
            steps=steps,
            cfg=cfg_v,
            width=width_v,
            height=height_v,
            model_variant=model_variant,
            lora_name=lora_name,
            lora_strength=lora_strength,
            filename_prefix=f"{prefix}_{label}",
        )

        try:
            result = comfy_post_prompt(wf)
        except RuntimeError as exc:
            print(f"  错误: {exc}", file=sys.stderr)
            continue

        pid = result.get("prompt_id", "")
        if pid == "dry-run":
            print(f"  [dry-run] 跳过等待")
            results.append({"params": params, "seed": seed_actual, "prompt_id": pid, "images": []})
            continue

        print(f"  prompt_id={pid}，等待出图...")
        try:
            images = wait_images(pid, base)
        except (TimeoutError, RuntimeError) as exc:
            print(f"  等待失败: {exc}", file=sys.stderr)
            images = []

        image_paths = []
        for sub, name in images:
            path = (resolve_comfy_root() / "output" / sub / name).resolve()
            if path.is_file():
                image_paths.append(str(path))
                print(f"  出图: {name}")

        results.append({
            "params": params,
            "seed": seed_actual,
            "prompt_id": pid,
            "images": image_paths,
        })

    # 归档全部产出
    all_images = [img for r in results for img in r["images"]]
    if all_images:
        save_run("sweep-flux", all_images, {
            "prompt": prompt,
            "grid": grid,
            "model": model_variant,
            "lora": lora_name,
            "combinations": n,
        })
        print(f"\n✅ 共 {len(all_images)} 张图已归档")

    # 生成对比拼图
    if all_images:
        _make_grid(results, prefix)
    else:
        print("\n⚠️  无有效出图，跳过对比拼图")


def _make_grid(results: list[dict[str, Any]], prefix: str) -> None:
    """生成带标注的对比拼图。"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("[warn] Pillow 未安装，跳过对比拼图。pip install pillow")
        return

    valid = [(r, r["images"][0]) for r in results if r["images"]]
    if not valid:
        return

    n = len(valid)
    cols = min(4, n)
    rows = (n + cols - 1) // cols

    samples_img = [Image.open(im).convert("RGB") for _, im in valid]
    cell_w = max(im.width for im in samples_img)
    cell_h = max(im.height for im in samples_img)
    label_h = 40

    grid_img = Image.new("RGB", (cell_w * cols, (cell_h + label_h) * rows), (32, 32, 32))
    draw = ImageDraw.Draw(grid_img)

    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font = ImageFont.load_default()

    for idx, (r, im_path) in enumerate(valid):
        col = idx % cols
        row = idx // cols
        x = col * cell_w
        y = row * (cell_h + label_h)

        # 标注
        label = ", ".join(f"{k}={v}" for k, v in r["params"].items())
        draw.rectangle([x, y, x + cell_w, y + label_h], fill=(48, 48, 48))
        draw.text((x + 4, y + 4), label, fill=(255, 255, 255), font=font)

        # 图片
        im = Image.open(im_path).convert("RGB")
        im.thumbnail((cell_w, cell_h), Image.LANCZOS)
        paste_y = y + label_h
        grid_img.paste(
            im,
            (x + (cell_w - im.width) // 2, paste_y + (cell_h - im.height) // 2),
        )

    grid_path = f"{prefix}_grid_comparison.jpg"
    grid_img.save(grid_path, quality=92)
    print(f"对比拼图: {grid_path}")


def main() -> None:
    parser = __import__("argparse").ArgumentParser(
        description="参数网格扫描 — Flux.2 Klein（自动对比拼图）",
    )
    parser.add_argument("prompt", nargs="?", help="画面描述")
    parser.add_argument(
        "--grid",
        required=True,
        help='JSON 网格参数: {"steps":[20,30],"cfg":[1.0,2.0]}',
    )
    parser.add_argument("--model", choices=["9b", "4b"], default="9b")
    parser.add_argument("--lora", default=None)
    parser.add_argument("--lora-strength", type=float, default=1.0)
    parser.add_argument("--negative", default="")
    parser.add_argument("--prefix", default="sweep")
    parser.add_argument("--raw", action="store_true", help="跳过 Ollama")
    args = parser.parse_args()

    user = args.prompt or input("请输入描述: ").strip()
    if not user:
        print("未输入内容，退出。", file=sys.stderr)
        sys.exit(1)

    prompt = user if args.raw else optimize_prompt(user)

    try:
        grid = json.loads(args.grid)
    except json.JSONDecodeError as e:
        print(f"网格参数 JSON 格式错误: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(grid, dict) or not grid:
        print("网格参数必须是非空 JSON 对象", file=sys.stderr)
        sys.exit(1)

    run_sweep(
        prompt,
        grid,
        model_variant=args.model,
        lora_name=args.lora,
        lora_strength=args.lora_strength,
        negative=args.negative,
        prefix=args.prefix,
    )


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)
