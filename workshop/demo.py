"""面试样张管线 — 一键生成 5 场景角色展示 Gallery + 质量报告。"""

from __future__ import annotations
from typing import Any
from pathlib import Path
from datetime import datetime

# ── 5 面试场景预设 ──────────────────────────────────────

DEMO_SCENES: list[dict[str, Any]] = [
    {
        "id": 1,
        "name": "portrait",
        "title": "罗兹瓦尔宅邸肖像",
        "prompt_focus": "inside the Roswaal mansion, standing by a grand window with soft natural light filtering through, noble interior with ornate furniture, elegant aristocratic atmosphere, gentle expression",
        "outfit_detail": "signature white and violet gradient dress with golden trim, white four-petal flower hair ornament on left side of head",
        "style": "anime",
        "preset": "flux_portrait",
        "steps": 28,
        "cfg": 2.5,
        "model_type": "flux",
    },
    {
        "id": 2,
        "name": "halfbody",
        "title": "宅邸玫瑰花园",
        "prompt_focus": "in the mansion's rose garden at dawn, surrounded by blooming roses and morning mist, dewdrops on petals, warm golden hour sunlight filtering through trees, elegant standing pose",
        "outfit_detail": "full view of elegant white and violet gradient dress with golden ornaments, dress flowing gracefully, white flower hair ornament visible",
        "style": "anime",
        "preset": "flux_quality",
        "steps": 28,
        "cfg": 2.0,
        "model_type": "flux",
    },
    {
        "id": 3,
        "name": "action",
        "title": "冰魔法战斗",
        "prompt_focus": "casting ice magic, crystalline ice shards and snowflakes floating in mid-air, glowing aqua magic circle beneath feet, intense battle expression, dynamic combat pose, magical energy swirling, dramatic rim lighting",
        "outfit_detail": "dress flowing dynamically with motion, ice-blue magical energy swirling around the hem, white flower ornament in wind-blown hair",
        "style": "anime",
        "preset": "flux_balanced",
        "steps": 20,
        "cfg": 1.5,
        "model_type": "flux",
    },
    {
        "id": 4,
        "name": "fullbody_env",
        "title": "艾利奥尔大草原",
        "prompt_focus": "standing on the Meadow of Elior at sunset, vast grasslands stretching to horizon, gentle wind blowing through hair and dress, dramatic sky with clouds, golden and purple twilight atmosphere, elf homeland scenery",
        "outfit_detail": "complete view of elegant white and violet dress silhouette against the sunset sky, golden trim catching the last light",
        "style": "anime",
        "preset": "flux_quality",
        "steps": 28,
        "cfg": 2.0,
        "model_type": "flux",
    },
    {
        "id": 5,
        "name": "expression",
        "title": "王选厅",
        "prompt_focus": "in the royal selection hall, solemn dignified atmosphere, candlelit room with tall stained glass windows casting colored light, determined yet gentle expression, noble and resolute gaze, soft warm interior lighting",
        "outfit_detail": "intricate details of the white and violet dress visible, golden ornaments catching candlelight, white flower ornament softly lit",
        "style": "anime",
        "preset": "flux_quality",
        "steps": 28,
        "cfg": 2.5,
        "model_type": "flux",
    },
]


# ── 角色特征预设 ──────────────────────────────────────

CHARACTER_PRESETS: dict[str, str] = {
    "emilia": (
        "Emilia (Re:Zero), the silver-haired half-elf with amethyst-purple eyes, "
        "long silver hair with gentle waves, pointed elven ears, "
        "wearing her elegant white and violet gradient dress with golden trim and ornaments, "
        "a distinctive white four-petal flower hair ornament pinned on the left side of her head, "
        "noble and graceful aura, gentle expression, pale skin"
    ),
    "rem": (
        "Rem (Re:Zero), the blue-haired oni maid with light blue eyes, "
        "short blue bob-cut hair with a white flower hair ornament on the right side, "
        "wearing a black and white french maid uniform, "
        "gentle and devoted expression, pale skin"
    ),
    "ram": (
        "Ram (Re:Zero), the pink-haired oni maid with pink eyes, "
        "short pink hair with a red headband, "
        "wearing a pink and white french maid uniform, "
        "confident and sharp expression"
    ),
}


def _expand_character(char_desc: str) -> str:
    """If char_desc is a known short name, expand to full description."""
    key = char_desc.strip().lower().rstrip(".!,")
    # Handle "Emilia (Re:Zero)" -> look up "emilia"
    if "(" in key:
        key = key.split("(")[0].strip()
    return CHARACTER_PRESETS.get(key, char_desc)


def _build_prompt(char_desc: str, scene: dict[str, Any]) -> str:
    """为场景构建自然语言描述（Flux 友好格式）。

    整合角色描述 + 场景焦点 + 服装细节。
    """
    char_desc = _expand_character(char_desc)
    focus = scene["prompt_focus"]
    outfit = scene.get("outfit_detail", "")

    pieces = [char_desc, focus]
    if outfit:
        pieces.append(outfit)
    return ". ".join(pieces) + "."


def run_demo(
    char_desc: str,
    output_dir: str,
    *,
    count_per_scene: int = 1,
    ref_path: str | None = None,
    use_ollama: bool = False,
    no_learn: bool = True,
    verbose: bool = True,
    model_type: str = "flux",
) -> dict[str, Any]:
    """面试样张管线：5 场景 × count_per_scene = 5~10 张成品。

    每场景单独生成 → 合入统一 Gallery → 一致性报告 → 质量报告 Markdown。

    Args:
        char_desc: 角色描述（如 "银发精灵 Alice, 蓝瞳, 白色长裙"）
        output_dir: 输出目录
        count_per_scene: 每场景生成数（默认 4）
        ref_path: 可选的参考图（角色特征参考）
        use_ollama: 是否用 Ollama 增强 prompt
        no_learn: 默认关闭自动学习（demo 场景非典型）
        verbose: 详细信息

    Returns:
        {"output_dir": str, "scenes": int, "total_images": int, "gallery_path": str, "report_path": str}
    """
    from workshop.create import create_from_nl

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    all_candidates: list[dict[str, Any]] = []
    scene_results: list[dict[str, Any]] = []

    print(f"\n{'='*50}")
    print(f"🎨 面试样张生成")
    print(f"{'='*50}")
    print(f"  角色: {char_desc}")
    if ref_path:
        print(f"  参考: {ref_path}")
    print(f"  场景数: {len(DEMO_SCENES)} × {count_per_scene} 张")
    print()

    for scene in DEMO_SCENES:
        prompt = _build_prompt(char_desc, scene)
        scene_dir = out / scene["name"]
        scene_dir.mkdir(parents=True, exist_ok=True)

        print(f"  📍 [{scene['id']}/{len(DEMO_SCENES)}] {scene['title']}")
        print(f"    步骤: {scene['steps']}  CFG: {scene['cfg']}  预设: {scene['preset']}")

        try:
            result = create_from_nl(
                prompt,
                count=count_per_scene,
                style_hint=scene["style"],
                preset=scene["preset"],
                ref_path=ref_path,
                output_dir=str(scene_dir),
                gallery_dir=str(scene_dir / "gallery"),
                steps=scene["steps"],
                cfg=scene["cfg"],
                use_ollama=use_ollama,
                no_learn=no_learn,
                verbose=verbose,
                prompt_ready=True,
                face_detailer=True,
                upscale=1.5 if model_type == "sdxl" else 1.0,
                model_type=model_type,
            )
        except Exception as exc:
            print(f"    ❌ 生成失败: {exc}")
            continue

        candidates = result.get("candidates", [])
        valid_candidates = [c for c in candidates if c.get("image") and not c.get("error")]

        # 标记场景来源
        for c in valid_candidates:
            c["_demo_scene"] = scene["title"]
            c["_demo_scene_id"] = scene["name"]

        all_candidates.extend(valid_candidates)
        scene_results.append({
            "scene": scene["title"],
            "scene_id": scene["name"],
            "image_count": len(valid_candidates),
            "best": result.get("best", {}),
        })

        if valid_candidates:
            best = valid_candidates[0]
            print(f"    ✅ {len(valid_candidates)} 张 (最优 seed={best.get('seed','?')})")
        else:
            print(f"    ⚠️ 0 张有效")

    # ── 全量 Gallery ──
    gallery_path = ""
    if all_candidates:
        gallery_path = _build_demo_gallery(all_candidates, out)
        if gallery_path:
            print(f"\n  🖼️  Gallery: {gallery_path}")

    # ── 一致性验证 ──
    report_path = ""
    if len(all_candidates) >= 2:
        from workshop.consistency import verify_consistency, print_verify_report
        report = verify_consistency(all_candidates, character_name=char_desc)
        print_verify_report(report)

        # 保存 HTML 一致性报告
        if report.get("html"):
            html_path = out / "consistency.html"
            html_path.write_text(report["html"], encoding="utf-8")
            report_path = str(html_path)
            print(f"  📊 一致性报告: {report_path}")

    # ── 面试样张 Markdown 报告 ──
    md_path = out / "demo_report.md"
    _write_demo_report(md_path, char_desc, scene_results, all_candidates, ref_path)

    print(f"\n{'='*50}")
    print(f"✅ 面试样张完成")
    print(f"  输出目录: {out.resolve()}")
    print(f"  Gallery: {gallery_path or '无'}")
    print(f"  报告: {md_path}")
    print(f"  📋 运行人工审核: python -m agents workshop review {out.resolve().name}/")
    print(f"{'='*50}\n")

    return {
        "output_dir": str(out.resolve()),
        "scenes": len(scene_results),
        "total_images": len(all_candidates),
        "gallery_path": gallery_path,
        "report_path": str(md_path),
    }


def _build_demo_gallery(candidates: list[dict[str, Any]], out_dir: Path) -> str:
    """用现有 Gallery 工具构建全量 Gallery。"""
    from workshop.create import _generate_gallery_html
    try:
        result = {
            "prompt": candidates[0].get("prompt", "Demo Gallery"),
            "candidates": candidates,
            "best": candidates[0] if candidates else {},
        }
        gallery_dir = out_dir / "gallery"
        gallery_dir.mkdir(parents=True, exist_ok=True)
        path = _generate_gallery_html(result, str(gallery_dir), candidates)
        return path or ""
    except Exception as exc:
        print(f"  ⚠️ Gallery 生成失败: {exc}")
        # 兜底：手动写一个简单 HTML
        return _build_simple_gallery(candidates, out_dir)


def _build_simple_gallery(candidates: list[dict[str, Any]], out_dir: Path) -> str:
    """兜底 Gallery HTML（当 _generate_gallery_html 不可用时）。"""
    scenes_order = [s["name"] for s in DEMO_SCENES]
    html_parts = []
    for sid in scenes_order:
        group = [c for c in candidates if c.get("_demo_scene_id") == sid]
        if not group:
            continue
        scene_name = group[0].get("_demo_scene", sid)
        html_parts.append(f"<h2>{scene_name}</h2><div class='row'>")
        for c in group:
            img = c.get("image", "")
            seed = c.get("seed", "?")
            score = c.get("score") if c.get("score") is not None else -1
            score_display = f"{score:.2f}" if isinstance(score, (int, float)) and score >= 0 else "?"
            html_parts.append(
                f"<div class='card'><img src='{img}' loading='lazy'/>"
                f"<div class='label'>seed={seed} score={score_display}</div></div>"
            )
        html_parts.append("</div>")

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>面试样张 Gallery</title>
<style>
body {{ font-family: system-ui; max-width: 1200px; margin: 2em auto; padding: 0 1em; }}
h1 {{ color: #333; border-bottom: 2px solid #ddd; padding-bottom: 0.5em; }}
h2 {{ color: #555; margin-top: 1.5em; }}
.row {{ display: flex; flex-wrap: wrap; gap: 1em; }}
.card {{ max-width: 400px; }}
.card img {{ width: 100%; border-radius: 6px; }}
.label {{ font-size: 0.8em; color: #888; margin-top: 0.3em; }}
</style></head><body>
<h1>🎨 面试样张 Gallery</h1>
{chr(10).join(html_parts)}
</body></html>"""

    path = out_dir / "gallery" / "interview.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return str(path)


def _write_demo_report(
    md_path: Path,
    char_desc: str,
    scene_results: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    ref_path: str | None,
) -> None:
    """生成面试样张 Markdown 报告。"""
    lines = [
        f"# 面试样张报告",
        f"",
        f"- **角色**: {char_desc}",
        f"- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- **参考图**: {ref_path or '无'}",
        f"- **场景数**: {len(scene_results)}",
        f"- **总张数**: {len(candidates)}",
        f"",
        f"## 场景汇总",
        f"",
        f"| 序号 | 场景 | 生成数 | 最优 seed |",
        f"|------|------|--------|-----------|",
    ]
    for sr in scene_results:
        best_seed = sr.get("best", {}).get("seed", "?")
        lines.append(f"| {sr['scene_id']} | {sr['scene']} | {sr['image_count']} | {best_seed} |")

    lines.extend([
        f"",
        f"## 所用管线能力",
        f"",
        f"- **自然语言 prompt** → `create_from_nl`",
        f"- **参数自动优化**: `--auto` (QualityDB)",
        f"- **质量自检**: `inspect` (面部/手/脚/模糊)",
        f"- **Gallery 展示**: 前端集成",
        f"- **角色参考**: `--ref` (Flux ReferenceLatent)",
        f"- **自动重试**: `--auto-retry` (参数微调)",
        f"- **Cat 角色表**: `--cast` (多角色设计)",
        f"- **Gallery 筛选**: `--filter`",
        f"- **参数多样性**: `--variety` / Explore",
        f"- **一致性验证**: `workshop verify`",
        f"",
        f"## 技术栈",
        f"",
        f"- 框架: Python + ComfyUI API",
        f"- 模型: FLUX.2 Klein 9B",
        f"- 质检: OpenCV/YOLO/MediaPipe",
        f"- 管线: Hermes Agent + workshop 引擎",
    ])

    md_path.write_text("\n".join(lines), encoding="utf-8")
