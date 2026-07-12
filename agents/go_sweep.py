"""
参数网格扫描 — Flux.2 Klein / Wan2.2 批量迭代 + 自动对比拼图。
支持质量预设 (--preset) 和可选的 CLIP 品质门禁。

用法示例:
  python go_sweep.py "赛博朋克少女" --grid '{"steps":[20,30,40]}'
  python go_sweep.py "prompt" --grid '{"steps":[20,30],"cfg":[1.0,2.0]}'
  python go_sweep.py "prompt" --grid '{"steps":[20,30]}' --model 4b --lora knives_flux_lora.safetensors
  python go_sweep.py "prompt" --grid '{"steps":[20,30]}' --preset anime
  python go_sweep.py "prompt" --grid '{"type":"video","frames":[49,81]}'  # 视频参数扫描
"""
from __future__ import annotations

import json
import sys
from itertools import product
from pathlib import Path
from typing import Any

from comfy_utils import (
    QUALITY_PRESETS,
    VIDEO_PRESETS,
    bootstrap_agents_path,
    comfy_base_url,
    generate_with_quality,
    optimize_prompt,
    resolve_comfy_root,
)

bootstrap_agents_path()

from output_manager import save_run  # noqa: E402

# 动态导入的构建函数
_BUILD_FUNCTIONS: dict[str, Any] = {}


def _get_build_fn(sweep_type: str) -> Any:
    """按类型获取工作流构建函数。"""
    if sweep_type not in _BUILD_FUNCTIONS:
        if sweep_type == "video":
            from go_video import build_video_workflow as fn
            _BUILD_FUNCTIONS[sweep_type] = fn
        else:
            from go_flux import build_flux_workflow as fn
            _BUILD_FUNCTIONS[sweep_type] = fn
    return _BUILD_FUNCTIONS[sweep_type]


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
    sweep_type: str = "image",
    model_variant: str = "9b",
    lora_name: str | None = None,
    lora_strength: float = 1.0,
    negative: str = "",
    prefix: str = "sweep",
    ref_image: str | None = None,
    denoise: float = 1.0,
    sampler: str = "euler",
    scheduler: str = "normal",
    preset: str | None = None,
    min_score: float = 0.0,
    max_retries: int = 0,
    no_validate: bool = False,
    seed: int = -1,
) -> None:
    """执行网格扫描，归档并生成对比结果。

    每组合使用 generate_with_quality 提交，支持质量预设和可选 CLIP 门禁。
    """
    is_video = sweep_type == "video"
    build_fn = _get_build_fn(sweep_type)

    combinations = expand_grid(grid)
    n = len(combinations)
    type_label = "视频" if is_video else "图片"
    print(f"{type_label}网格扫描: {n} 个组合")
    print(f"  {f'预设: {preset}' if preset else '无预设'}"
          f"  {' 质量门禁: ' + str(min_score) if min_score > 0 else ''}"
          f"  {' 重试: ' + str(max_retries) if max_retries > 0 else ''}")
    for i, params in enumerate(combinations):
        print(f"  [{i+1}/{n}] {params}")

    results: list[dict[str, Any]] = []

    for i, params in enumerate(combinations):
        label = build_sweep_label(params)
        print(f"\n[{i+1}/{n}] 提交 {label}...")

        steps = params.get("steps", 20)
        cfg_v = params.get("cfg", 1.0)
        width_v = params.get("width", 1024)
        height_v = params.get("height", 1024)
        seed_v = params.get("seed", seed)

        if is_video:
            frames = params.get("frames", 49)
            fps = params.get("fps", 15)
            denoise_v = params.get("denoise", denoise)
            sampler_v = params.get("sampler", sampler)
            scheduler_v = params.get("scheduler", scheduler)
            fn_prefix = f"{prefix}_video_{label}"

            build_kw = dict(
                negative=negative,
                steps=steps,
                cfg=cfg_v,
                width=width_v,
                height=height_v,
                frames=frames,
                fps=fps,
                denoise=denoise_v,
                sampler=sampler_v,
                scheduler=scheduler_v,
                prefix=fn_prefix,
            )
            if ref_image:
                build_kw["ref_image"] = ref_image
        else:
            fn_prefix = f"{prefix}_{label}"
            build_kw = dict(
                negative_prompt=negative,
                steps=steps,
                cfg=cfg_v,
                width=width_v,
                height=height_v,
                model_variant=model_variant,
                lora_name=lora_name,
                lora_strength=lora_strength,
                filename_prefix=fn_prefix,
            )

        try:
            qr = generate_with_quality(
                build_fn, prompt,
                preset=preset,
                min_score=min_score,
                max_retries=max_retries,
                no_validate=no_validate,
                seed=seed_v,
                **build_kw,
            )
        except RuntimeError as exc:
            print(f"  错误: {exc}", file=sys.stderr)
            results.append({"params": params, "seed": 0, "prompt_id": "", "files": []})
            continue

        pid = qr.get("prompt_id", "")
        seed_actual = qr.get("seed", 0)
        file_paths = qr.get("images", [])

        if pid == "dry-run":
            print(f"  [dry-run] 跳过等待")
            results.append({"params": params, "seed": seed_actual, "prompt_id": pid, "files": []})
            continue

        for fp in file_paths:
            suffix = " (视频)" if Path(fp).suffix.lower() in (".mp4", ".webm", ".mov") else ""
            print(f"  输出: {Path(fp).name}{suffix}")

        score = qr.get("score")
        if score is not None:
            print(f"  CLIP 评分: {score:.3f}")
        retries_v = qr.get("retries", 0)
        if retries_v > 0:
            print(f"  重试次数: {retries_v}")

        results.append({
            "params": params,
            "seed": seed_actual,
            "prompt_id": pid,
            "files": file_paths,
        })

    # 归档全部产出
    all_files = [f for r in results for f in r["files"]]
    if all_files:
        run_cmd = f"sweep-{'video' if is_video else 'flux'}"
        save_run(run_cmd, all_files, {
            "prompt": prompt,
            "grid": grid,
            "type": sweep_type,
            "model": model_variant,
            "lora": lora_name,
            "preset": preset,
            "combinations": n,
        })
        print(f"\n✅ 共 {len(all_files)} 个{'视频' if is_video else '图片'}已归档")

    # 生成对比结果
    if all_files:
        if is_video:
            _make_video_html(results, prefix, prompt)
        else:
            _make_grid(results, prefix)
    else:
        print(f"\n⚠️  无有效{'视频' if is_video else '出图'}，跳过对比")


def _make_grid(results: list[dict[str, Any]], prefix: str) -> None:
    """生成带标注的对比拼图。"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("[warn] Pillow 未安装，跳过对比拼图。pip install pillow")
        return

    valid = [(r, r["files"][0]) for r in results if r["files"]]
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


def _make_video_html(results: list[dict[str, Any]], prefix: str, prompt: str) -> None:
    """生成视频对比 HTML 页面。"""
    from datetime import datetime

    valid = [(r, r["files"][0]) for r in results if r["files"]]
    if not valid:
        return

    cards: list[str] = []
    for r, path in valid:
        label = ", ".join(f"{k}={v}" for k, v in r["params"].items())
        cards.append(f"""<div class="card">
  <video controls preload="metadata" muted playsinline src="file:///{Path(path).as_posix()}" />
  <div class="label">{label}</div>
</div>""")

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Video Sweep — {prefix}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #0f1115; color: #e8eaed; font-family: sans-serif; padding: 1rem; }}
h1 {{ font-size: 1.2rem; margin-bottom: 0.5rem; }}
.prompt {{ color: #9aa0a6; font-size: 0.85rem; margin-bottom: 1rem; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 1rem; }}
.card {{ background: #1a1d24; border-radius: 12px; overflow: hidden; border: 1px solid #2a2f3a; }}
.card video {{ width: 100%; display: block; }}
.label {{ padding: 0.5rem; font-size: 0.8rem; color: #9aa0a6; }}
footer {{ margin-top: 1rem; color: #555; font-size: 0.75rem; text-align: center; }}
</style>
</head>
<body>
<h1>🎬 Video Sweep — {prefix}</h1>
<div class="prompt">{prompt}</div>
<div class="grid">{"".join(cards)}</div>
<footer>generated {datetime.now().strftime("%Y-%m-%d %H:%M")} · {len(valid)} videos</footer>
</body>
</html>"""

    out_path = f"{prefix}_video_sweep.html"
    Path(out_path).write_text(html, encoding="utf-8")
    print(f"视频对比页面: {out_path}")


def main() -> None:
    parser = __import__("argparse").ArgumentParser(
        description="参数网格扫描 — 支持图片(Flux)和视频(Wan2.2)，自动对比拼图，可选质量门禁",
    )
    parser.add_argument("prompt", nargs="?", help="画面描述")
    parser.add_argument(
        "--grid",
        required=True,
        help='JSON 网格参数: {"steps":[20,30],"cfg":[1.0,2.0]}',
    )
    parser.add_argument(
        "--type", choices=["image", "video"], default="image",
        help="扫描类型：image(Flux) / video(Wan2.2)",
    )
    parser.add_argument("--model", choices=["9b", "4b"], default="9b")
    parser.add_argument("--lora", default=None)
    parser.add_argument("--lora-strength", type=float, default=1.0)
    parser.add_argument("--negative", default="")
    parser.add_argument("--prefix", default="sweep")
    parser.add_argument("--raw", action="store_true", help="跳过 Ollama")

    # 质量预设 + 门禁（V0.43.0 新增）
    parser.add_argument("--preset", default=None, help="质量预设名（内置或自定义）")
    parser.add_argument("--seed", type=int, default=-1, help="随机种子（-1 自动）")
    parser.add_argument("--min-score", type=float, default=0.0,
                        help="最低 CLIP 评分（≤0 跳过，默认跳过）")
    parser.add_argument("--retry", type=int, default=0,
                        help="质量不合格时最大重试次数")
    parser.add_argument("--no-validate", action="store_true",
                        help="跳过质量验证")

    # 视频专用参数
    parser.add_argument("--ref", default=None, help="参考图（视频 I2V 模式）")
    parser.add_argument("--denoise", type=float, default=1.0, help="视频去噪强度")
    parser.add_argument("--sampler", default="euler", help="视频采样器")
    parser.add_argument("--scheduler", default="normal", help="视频调度器")
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
        sweep_type=args.type,
        model_variant=args.model,
        lora_name=args.lora,
        lora_strength=args.lora_strength,
        negative=args.negative,
        prefix=args.prefix,
        ref_image=args.ref,
        denoise=args.denoise,
        sampler=args.sampler,
        scheduler=args.scheduler,
        preset=args.preset,
        min_score=args.min_score,
        max_retries=args.retry,
        no_validate=args.no_validate,
        seed=args.seed,
    )


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)
