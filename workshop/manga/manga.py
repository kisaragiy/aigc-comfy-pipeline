"""
漫画/分镜生成 — 剧本 → 焚诀八列分镜表 → 逐格生图 → 拼页输出。

流程:
  1. script_to_storyboard()   — 自然语言剧本 → 八列分镜表
  2. storyboard_to_prompts()  — 分镜表 → 逐格专业提示词（含角色一致性）
  3. generate_panels()        — 逐格提交 ComfyUI 出图
  4. assemble_page()          — 多格拼成一页（PNG 输出）

分镜规范参见 docs/storyboard-spec.md:
  - 八列格式: 镜号 | 人物 | 场景 | 景别 | 音频 | 画面描述 | 台词 | 备注
  - 乒乓镜头规则（对话正反打交替）
  - 形态五大要素（神态/动作/服饰/道具/肌理）
  - 打斗物理化规则
  - 景别差异化规则
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

# ── 剧本 → 八列分镜表 ──────────────────────────────────

STORYBOARD_COLUMNS = ["镜号", "人物", "场景", "景别", "音频提示", "画面描述", "台词", "备注"]

# Ollama 分镜生成模板
_STORYBOARD_TEMPLATE = """你是一位漫画分镜师。请根据以下剧本/场景描述，生成规范的八列分镜表。

要求：
1. 按 焚诀八列分镜表格式输出
2. 每列用 | 分隔
3. 镜头切换遵循景别差异化规则（相邻镜头景别不能相同）
4. 对话场景遵循乒乓镜头规则（正反打交替）
5. 每个角色必须覆盖形态五大要素（神态、动作、服饰、道具、肌理）
6. 战斗场景必须使用打斗物理化规则（具体招式、粒子特效、受力反馈）
7. 输出 4-8 个镜头

输入：
{script_text}

输出格式（严格按此 CSV-like 格式，不要额外文字）：
镜号|人物|场景|景别|音频提示|画面描述|台词|备注
S01|{character_a}|场景描述|景别|音频|画面描述|台词|备注
S02|{character_b}|...
"""


def script_to_storyboard(
    script_text: str,
    characters: dict[str, dict[str, str]] | None = None,
    *,
    ollama_available: bool = True,
    ollama_url: str | None = None,
    ollama_model: str | None = None,
) -> list[dict[str, str]]:
    """自然语言剧本 → 八列分镜表。

    Args:
        script_text: 剧本/场景描述（自然语言）
        characters: 角色定义字典 {角色名: {服饰, 发型, 特征, ...}}
        ollama_available: 是否使用 Ollama

    Returns:
        分镜表列表，每个镜为一个 dict {镜号:str, 人物:str, 场景:str, ...}
    """
    if ollama_available:
        try:
            return _ollama_generate_storyboard(
                script_text, characters or {}, url=ollama_url, model=ollama_model
            )
        except Exception:
            pass  # 降级到模板

    return _template_storyboard(script_text, characters or {})


def storyboard_to_prompts(
    storyboard: list[dict[str, str]],
    characters: dict[str, dict[str, str]],
    style_hint: str = "anime",
) -> list[dict[str, Any]]:
    """分镜表 → 逐格出图参数。

    每个镜生成:
      - prompt:         组合后的正向提示词
      - negative:       负向提示词
      - seed:           保持角色一致性的种子
      - width/height:   根据景别和分格数计算

    Args:
        storyboard: script_to_storyboard() 的输出
        characters: 角色定义 {角色名: {服饰, 发型, ...}}
        style_hint: 画风

    Returns:
        [{"shot": "S01", "prompt": "...", "negative": "...", "seed": 42, ...}, ...]
    """
    from workshop.engine import nls_to_prompt, STYLE_PRESETS

    preset = STYLE_PRESETS.get(style_hint, STYLE_PRESETS["anime"])
    base_negative = preset.get("negative", "")

    panel_list = []
    for shot in storyboard:
        # 组装每格的 prompt
        character = shot.get("人物", "")
        scene = shot.get("场景", "")
        camera = shot.get("景别", "")
        visual = shot.get("画面描述", "")
        dialogue = shot.get("台词", "")

        # 角色特征注入
        char_prompt = ""
        if character in characters:
            char_info = characters[character]
            char_prompt = ", ".join([
                char_info.get("服饰", ""),
                char_info.get("发型", ""),
                char_info.get("特征", ""),
            ])

        # 调用引擎生成 prompt
        full_desc = f"{character}, {visual}, {scene}, {camera}"
        if dialogue:
            full_desc += f", 正在说: {dialogue}"

        enhanced = nls_to_prompt(full_desc, style_hint=style_hint, ollama_available=False)

        # 景别 → 画面尺寸
        w, h = _layout_size(camera)

        panel_list.append({
            "shot": shot.get("镜号", ""),
            "prompt": enhanced,
            "negative": base_negative,
            "seed": _seed_from_shot(shot.get("镜号", "S01")),
            "width": w,
            "height": h,
            "character": character,
            "dialogue": dialogue,
            "scene": scene,
            "camera": camera,
        })

    return panel_list


def generate_panels(
    panel_list: list[dict[str, Any]],
    *,
    flux: bool = True,
    dry_run: bool = False,
    prefix: str = "manga",
) -> list[dict[str, Any]]:
    """逐格提交 ComfyUI 出图。

    Args:
        panel_list: storyboard_to_prompts() 的输出
        flux: 使用 Flux.2 Klein（否则 SDXL）
        dry_run: 预览模式（跳过提交）
        prefix: 文件前缀

    Returns:
        [{"shot": "S01", "prompt_id": "...", "images": [...], ...}, ...]
    """
    if dry_run:
        for panel in panel_list:
            panel["prompt_id"] = "dry-run"
            panel["images"] = []
        return panel_list

    results = []
    for panel in panel_list:
        print(f"  [{panel['shot']}] 提交 {panel['character']} — {panel['camera']}...")

        if flux:
            from agents.go_flux import build_flux_workflow
            from agents.comfy_utils import comfy_post_prompt, wait_images, resolve_comfy_root

            workflow = build_flux_workflow(
                panel["prompt"],
                seed=panel["seed"],
                steps=20,
                cfg=3.5,
                width=panel["width"],
                height=panel["height"],
                model_variant="9b",
                filename_prefix=f"{prefix}_{panel['shot']}",
            )
        else:
            # SDXL
            from agents.go_knives_lora import build_sdxl_workflow
            from agents.comfy_utils import comfy_post_prompt, wait_images, resolve_comfy_root

            workflow = build_sdxl_workflow(
                panel["prompt"],
                seed=panel["seed"],
                steps=20,
                cfg=7.0,
                width=panel["width"],
                height=panel["height"],
                filename_prefix=f"{prefix}_{panel['shot']}",
            )

        try:
            resp = comfy_post_prompt(workflow)
            pid = resp.get("prompt_id", "")
            images = wait_images(pid)
        except Exception as exc:
            print(f"    ❌ 失败: {exc}")
            images = []

        results.append({
            "shot": panel["shot"],
            "prompt_id": pid,
            "images": images,
            "seed": panel["seed"],
            "prompt": panel["prompt"],
            "dialogue": panel["dialogue"],
        })

    return results


def assemble_page(
    panel_results: list[dict[str, Any]],
    *,
    layout: str = "auto",
    output_path: str | None = None,
    balloon: bool = True,
) -> str:
    """多格拼成一页 PNG。

    Args:
        panel_results: generate_panels() 的输出
        layout: 布局模式（auto=自动/4koma=四格/2x2=2x2网格）
        output_path: 输出路径（默认 workshop/output/manga_page.png）
        balloon: 是否添加台词语气球

    Returns:
        输出文件路径
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("[warn] PIL 不可用，跳过拼页", file=sys.stderr)
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path + ".txt", "w") as f:
                for r in panel_results:
                    f.write(f"[{r['shot']}] {r['dialogue']}\n")
            return output_path + ".txt"
        return ""

    from agents.comfy_utils import resolve_comfy_root

    # 收集图片
    panel_images: list[Image.Image] = []
    for r in panel_results:
        img_path = None
        for sub, name in r.get("images", []):
            path = resolve_comfy_root() / "output" / sub / name
            if path.is_file():
                img_path = str(path)
                break
        if img_path:
            panel_images.append(Image.open(img_path).convert("RGB"))
        else:
            # 占位
            img = Image.new("RGB", (512, 512), (200, 200, 200))
            panel_images.append(img)

    if not panel_images:
        print("[warn] 无图片可拼页", file=sys.stderr)
        return ""

    # 布局计算
    n = len(panel_images)
    if layout == "4koma":
        cols, rows = 2, 2
    elif layout == "2x2":
        cols, rows = 2, 2
    else:
        # auto: 按 √N 取整
        cols = max(2, int(n ** 0.5))
        rows = (n + cols - 1) // cols

    # 获取每格尺寸
    p_w = max(p.width for p in panel_images)
    p_h = max(p.height for p in panel_images)

    # 统一缩放到相同尺寸（保持比例）
    target_size = (p_w, p_h)
    resized = []
    for img in panel_images:
        resized.append(img.resize(target_size, Image.LANCZOS))

    # 创建画布
    gap = 10
    canvas_w = cols * p_w + (cols + 1) * gap
    canvas_h = rows * p_h + (rows + 1) * gap
    canvas = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))

    # 粘贴
    for i, img in enumerate(resized):
        col = i % cols
        row = i // cols
        x = gap + col * (p_w + gap)
        y = gap + row * (p_h + gap)
        canvas.paste(img, (x, y))

        # 添加台词
        if balloon and i < len(panel_results) and panel_results[i].get("dialogue"):
            draw = ImageDraw.Draw(canvas)
            dialogue = panel_results[i]["dialogue"]
            try:
                font = ImageFont.truetype("arial.ttf", 18)
            except OSError:
                font = ImageFont.load_default()
            # 在图片底部添加台词
            text_y = y + p_h - 30
            # 台词背景
            draw.rectangle(
                [x + 5, text_y - 2, x + len(dialogue) * 10 + 15, text_y + 22],
                fill=(255, 255, 255),
                outline=(0, 0, 0),
            )
            draw.text((x + 10, text_y), dialogue, fill=(0, 0, 0), font=font)

    # 输出
    if output_path is None:
        output_path = "workshop/output/manga_page.png"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    print(f"✅ 漫画页已生成: {output_path}")
    return output_path


# ── 内部函数 ────────────────────────────────────────────


def _ollama_generate_storyboard(
    script_text: str,
    characters: dict[str, dict[str, str]],
    *,
    url: str | None = None,
    model: str | None = None,
) -> list[dict[str, str]]:
    """Ollama 生成八列分镜表。"""
    from agents.comfy_utils import ollama_generate

    # 角色定义注入
    char_a = list(characters.keys())[0] if characters else "A"
    char_b = list(characters.keys())[1] if len(characters) > 1 else "B"

    full_prompt = _STORYBOARD_TEMPLATE.format(
        script_text=script_text,
        character_a=char_a,
        character_b=char_b,
    )
    if characters:
        full_prompt += f"\n\n角色定义:\n"
        for name, info in characters.items():
            full_prompt += f"  {name}: {info}\n"

    result = ollama_generate(full_prompt, url=url, model=model)

    # 解析 CSV-like 输出
    shots = []
    for line in result.strip().split("\n"):
        line = line.strip()
        if not line or "镜号" in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 6:
            shot = {
                "镜号": parts[0] if len(parts) > 0 else "",
                "人物": parts[1] if len(parts) > 1 else "",
                "场景": parts[2] if len(parts) > 2 else "",
                "景别": parts[3] if len(parts) > 3 else "",
                "音频提示": parts[4] if len(parts) > 4 else "",
                "画面描述": parts[5] if len(parts) > 5 else "",
                "台词": parts[6] if len(parts) > 6 else "",
                "备注": parts[7] if len(parts) > 7 else "",
            }
            shots.append(shot)

    return shots if shots else _template_storyboard(script_text, characters)


def _template_storyboard(
    script_text: str,
    characters: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    """模板兜底分镜表。"""
    char_a = list(characters.keys())[0] if characters else "角色A"
    char_b = list(characters.keys())[1] if len(characters) > 1 else "角色B"

    shots = [
        {"镜号": "S01", "人物": char_a, "场景": script_text, "景别": "全景",
         "音频提示": "", "画面描述": f"定场镜头，展示场景", "台词": "", "备注": ""},
        {"镜号": "S02", "人物": char_a, "场景": script_text, "景别": "中景",
         "音频提示": "", "画面描述": f"{char_a} 在场景中", "台词": "", "备注": ""},
        {"镜号": "S03", "人物": char_b, "场景": script_text, "景别": "过肩",
         "音频提示": "", "画面描述": f"{char_b} 出现，与 {char_a} 互动", "台词": "", "备注": ""},
        {"镜号": "S04", "人物": char_a, "场景": script_text, "景别": "特写",
         "音频提示": "", "画面描述": f"{char_a} 表情特写", "台词": "", "备注": "情绪节点"},
    ]
    return shots


def _layout_size(camera: str) -> tuple[int, int]:
    """景别 → 画面尺寸。"""
    if "特写" in camera or "大头" in camera:
        return 768, 768
    elif "全身" in camera:
        return 768, 1152
    elif "远景" in camera:
        return 1152, 768
    else:
        return 768, 1024  # 半身/中景默认


def _seed_from_shot(shot_id: str) -> int:
    """从镜号生成种子（保持画风一致）。"""
    nums = re.findall(r"\d+", shot_id)
    base = int(nums[0]) if nums else 1
    return hash(f"manga_{shot_id}") % (2 ** 31 - 1)
