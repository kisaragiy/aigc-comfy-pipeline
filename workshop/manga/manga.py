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
import os
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
    batch_size: int = 0,
    max_shots: int = 8,
) -> list[dict[str, str]]:
    """自然语言剧本 → 八列分镜表。

    Args:
        script_text: 剧本/场景描述（自然语言）
        characters: 角色定义字典 {角色名: {服饰, 发型, 特征, ...}}
        ollama_available: 是否使用 Ollama
        batch_size: E1 逐批续写批大小（0=一次性全量生成，>0=逐批续写）
        max_shots: 目标格数上限（默认 8）

    Returns:
        分镜表列表，每个镜为一个 dict {镜号:str, 人物:str, 场景:str, ...}
    """
    if ollama_available:
        try:
            if batch_size > 0:
                return _ollama_generate_storyboard_batch(
                    script_text, characters or {},
                    url=ollama_url, model=ollama_model,
                    batch_size=batch_size, max_shots=max_shots,
                )
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
    model_type: str = "sdxl",
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
    # 构建角色锚定: 每个角色统一的视觉描述
    char_anchors: dict[str, str] = {}
    for name, info in characters.items():
        parts = [info.get(k, "") for k in ("服饰", "发型", "特征")]
        anchor = ", ".join(p for p in parts if p)
        if anchor:
            char_anchors[name] = anchor

    # 构建场景锚定: 同一场景使用一致的视觉描述
    scene_anchors: dict[str, str] = {}
    scene_names: dict[str, str] = {}  # 场景名 → 标准化描述
    for shot in storyboard:
        sc = shot.get("场景", "").strip()
        if sc and sc not in scene_names:
            # 对每个场景生成一致的描述词
            scene_names[sc] = sc

    for shot in storyboard:
        # 组装每格的 prompt
        character = shot.get("人物", "")
        scene = shot.get("场景", "")
        camera = shot.get("景别", "")
        visual = shot.get("画面描述", "")
        dialogue = shot.get("台词", "")

        # 角色特征注入 — 使用锚定确保跨格一致性
        char_prompt = char_anchors.get(character, "")

        # 场景锚定注入 — 同场景用一致的描述
        scene_anchor = scene_names.get(scene, scene)

        # 调用引擎生成 prompt
        full_desc_parts = [character, char_prompt, visual, scene_anchor, camera] if char_prompt else [character, visual, scene_anchor, camera]
        full_desc = ", ".join(p for p in full_desc_parts if p)
        if dialogue:
            full_desc += f", 正在说: {dialogue}"

        enhanced = nls_to_prompt(full_desc, style_hint=style_hint, ollama_available=False, model_type=model_type)

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
    max_retries: int = 0,
    char_refs: dict[str, str] | None = None,
    global_ref: str | None = None,
    ip_weight: float = 0.7,
    preset: str | None = None,
    color_anchor: float = 0.0,
    ckpt: str | None = None,
    negative_prompt: str = "",
    lora_name: str | None = None,
    lora_strength: float = 0.9,
) -> list[dict[str, Any]]:
    """逐格提交 ComfyUI 出图，失败可重试。

    Args:
        panel_list: storyboard_to_prompts() 的输出
        flux: 使用 Flux.2 Klein（否则 SDXL）
        dry_run: 预览模式（跳过提交）
        prefix: 文件前缀
        max_retries: 每格失败后最大重试次数（默认 0=不重试）
        char_refs: 角色名 → 参考图路径 映射
        global_ref: 全局参考图（角色无专属 ref 时使用）
        ip_weight: 参考图影响权重

    Returns:
        [{"shot": "S01", "prompt_id": "...", "images": [...], ...}, ...]
    """
    if dry_run:
        for panel in panel_list:
            panel["prompt_id"] = "dry-run"
            panel["images"] = []
        return panel_list

    results = []
    # Import once at the top
    from agents.comfy_utils import comfy_post_prompt, wait_images

    for panel in panel_list:
        print(f"  [{panel['shot']}] 提交 {panel['character']} — {panel['camera']}...")

        if flux:
            from agents.go_flux import build_flux_workflow
            # 选择该格角色的参考图（优先专属 ref，其次全局 ref）
            panel_ref = None
            char_name = panel.get("character", "")
            if char_refs and char_name in char_refs:
                panel_ref = char_refs[char_name]
            elif global_ref:
                panel_ref = global_ref

            from agents.comfy_utils import apply_preset
            base_params = {
                "steps": 20, "cfg": 3.5,
                "width": panel["width"], "height": panel["height"],
                "model_variant": "9b",
                "filename_prefix": f"{prefix}_{panel['shot']}",
                "ref_image": panel_ref, "ip_weight": ip_weight,
            }
            params = apply_preset(base_params, preset) if preset else base_params
            params["color_anchor"] = color_anchor
            workflow = build_flux_workflow(panel["prompt"], seed=panel["seed"], **params)
        else:
            from agents.go_knives_lora import build_sdxl_clean_workflow
            wf_neg = panel.get("negative", "") or negative_prompt
            workflow = build_sdxl_clean_workflow(
                panel["prompt"],
                seed=panel["seed"],
                steps=25,
                cfg=6.5,
                width=panel["width"],
                height=panel["height"],
                filename_prefix=f"{prefix}_{panel['shot']}",
                negative_prompt=wf_neg,
                ckpt=ckpt,
            )

        pid = ""
        images = []
        error = ""
        retry_count = 0
        while retry_count <= max_retries:
            try:
                from agents.comfy_utils import comfy_base_url
                resp = comfy_post_prompt(workflow)
                pid = resp.get("prompt_id", "")
                base = comfy_base_url()
                images = wait_images(pid, base)
                if images:
                    break  # 出图成功
                error = "空结果（无图片返回）"
            except Exception as exc:
                error = str(exc)
                print(f"    ❌ 尝试 {retry_count+1}/{max_retries+1} 失败: {exc}")
            retry_count += 1
            if retry_count <= max_retries:
                import time
                wait = 2 * retry_count
                print(f"    🔄 {wait}s 后重试...")
                time.sleep(wait)

        if error and not images:
            print(f"    ❌ 最终失败 ({retry_count} 次重试): {error}")

        results.append({
            "shot": panel["shot"],
            "prompt_id": pid,
            "images": images,
            "error": error,
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
    border_style: str = "sharp",
) -> str:
    """多格拼成一页 PNG。

    Args:
        panel_results: generate_panels() 的输出
        layout: 布局模式（auto=自动/4koma=四格/2x2=2x2网格）
        output_path: 输出路径（默认 workshop/output/manga_page.png）
        balloon: 是否添加台词语气球
        border_style: 分格边框样式（sharp 直角/round 圆角/slash 斜切——漫画风格化）

    Returns:
        输出路径
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
            # 绝对路径直接可用（测试/用户传入）；相对路径解析到 ComfyUI output
            if os.path.isabs(name):
                img_path = name
                break
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

    # 布局计算（E4: 自动按面板比例选模板，替代固定网格）
    n = len(panel_images)
    layout_name = ""
    if layout == "4koma" or layout == "2x2":
        cols, rows = 2, 2
    elif layout == "auto":
        # E4: 先算每格宽高比，自动选漫画布局模板
        ratios = [img.width / img.height for img in panel_images]
        layout_name = _match_layout(n, ratios)
        if layout_name:
            tmpl = _LAYOUT_TEMPLATES[layout_name]
            cols, rows = tmpl["cols"], tmpl["rows"]
            print(f"  📐 E4 布局: {layout_name}（面板比例自动匹配）")
        else:
            cols = max(2, int(n ** 0.5))
            rows = (n + cols - 1) // cols
    elif layout == "webtoon" or layout == "strip_v":
        # 条漫（webtoon 竖排）：角色神态放大，气泡密度补偿信息量
        n_web = n if n % 2 == 0 else n + 1  # 偶数格（webtoon 模板 4/6 格）
        layout_name = _match_layout(n_web, [1.0] * n_web, prefer="webtoon")
        tmpl = _LAYOUT_TEMPLATES[layout_name]
        cols, rows = tmpl["cols"], tmpl["rows"]
        print(f"  📐 条漫布局: {layout_name}（竖排，神态放大）")
    else:
        cols = max(2, int(n ** 0.5))
        rows = (n + cols - 1) // cols

    # 获取每格尺寸
    p_w = max(p.width for p in panel_images)
    p_h = max(p.height for p in panel_images)

    # 每格独立缩放（模板布局：大格放大，小格缩小——漫画节奏感）
    unit_w, unit_h = p_w, p_h
    resized = []
    if layout_name:
        tmpl = _LAYOUT_TEMPLATES[layout_name]
        for i, img in enumerate(panel_images):
            wr, hr = tmpl["panels"][i] if i < len(tmpl["panels"]) else (1.0, 1.0)
            tw, th = int(unit_w * wr), int(unit_h * hr)
            resized.append(img.resize((tw, th), Image.LANCZOS))
    else:
        target_size = (p_w, p_h)
        for img in panel_images:
            resized.append(img.resize(target_size, Image.LANCZOS))

    # 创建画布
    gap = 10
    canvas_w = cols * p_w + (cols + 1) * gap
    canvas_h = rows * p_h + (rows + 1) * gap
    canvas = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))

    # 粘贴（模板布局按每格实际尺寸流式放置；普通布局按网格）
    if layout_name:
        tmpl = _LAYOUT_TEMPLATES[layout_name]
        # 模板列宽 = 该列最大面板宽；逐格放置
        col_offsets = [0] * cols
        row_offsets = [0] * rows
        # 先算每列宽度 / 每行高度
        cell_w = [0] * cols
        cell_h = [0] * rows
        for i, img in enumerate(resized):
            c = i % cols
            r = i // cols
            cell_w[c] = max(cell_w[c], img.width)
            cell_h[r] = max(cell_h[r], img.height)
        # 累计偏移（列/行分开累计——共用 acc 会互相覆盖导致 canvas 变正方形）
        xs = [0] * cols
        ys = [0] * rows
        acc_w = gap
        for c in range(cols):
            xs[c] = acc_w
            acc_w += cell_w[c] + gap
        acc_h = gap
        for r in range(rows):
            ys[r] = acc_h
            acc_h += cell_h[r] + gap
        canvas_w = acc_w
        canvas_h = acc_h
        canvas = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))
        for i, img in enumerate(resized):
            c = i % cols
            r = i // cols
            x = xs[c]
            y = ys[r]
            # 格内居中（小格放在大格列内）
            x += (cell_w[c] - img.width) // 2
            y += (cell_h[r] - img.height) // 2
            canvas.paste(img, (x, y))
            # 分格边框（漫画风格化）
            _draw_panel_border(canvas, x, y, img.width, img.height, border_style)
            if balloon and i < len(panel_results) and panel_results[i].get("dialogue"):
                draw = ImageDraw.Draw(canvas)
                dlg = panel_results[i]["dialogue"]
                # 音效字优先（漫画表现力：砰！咚！不画气泡直接大字）
                if not _draw_sfx(draw, dlg, x, y, img.width, img.height):
                    _draw_balloon(draw, dlg, x, y,
                                  img.width, img.height,
                                  _balloon_type(panel_results[i], i))
    else:
        for i, img in enumerate(resized):
            col = i % cols
            row = i // cols
            x = gap + col * (p_w + gap)
            y = gap + row * (p_h + gap)
            canvas.paste(img, (x, y))
            # 分格边框（漫画风格化）
            _draw_panel_border(canvas, x, y, img.width, img.height, border_style)

            # 添加台词（B1 气泡 + 音效字）
            if balloon and i < len(panel_results) and panel_results[i].get("dialogue"):
                draw = ImageDraw.Draw(canvas)
                dlg = panel_results[i]["dialogue"]
                if not _draw_sfx(draw, dlg, x, y, img.width, img.height):
                    _draw_balloon(draw, dlg, x, y,
                                  img.width, img.height,
                                  _balloon_type(panel_results[i], i))

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
    char_names = list(characters.keys())
    char_a = char_names[0] if char_names else "A"
    char_b = char_names[1] if len(char_names) > 1 else "B"

    full_prompt = _STORYBOARD_TEMPLATE.format(
        script_text=script_text,
        character_a=char_a,
        character_b=char_b,
    )
    if characters:
        full_prompt += f"\n\n角色定义:\n"
        for name, info in characters.items():
            detail = ", ".join(v for v in info.values() if v)
            full_prompt += f"  {name}: {detail}\n"
        if len(char_names) > 2:
            extra = ", ".join(char_names[2:])
            full_prompt += f"\n提示：共有 {len(char_names)} 个角色（{extra}），请合理分配所有角色的出场镜号。\n"

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


# E1 逐批续写模板（业界最佳实践：AI Comic Factory predictNextPanels 机制）
# 核心：每次只生成 batch_size 格，把已有分镜表 JSON 喂回 LLM 续写——保证长故事连贯
_BATCH_CONTINUE_TEMPLATE = """你是一位漫画分镜师。故事已生成前 {done_count} 格，请**续写后续 {batch_size} 格**。

要求：
1. 严格衔接已有分镜（时间线/角色状态/场景延续，不许矛盾）
2. 按 焚诀八列分镜表格式输出
3. 镜头切换遵循景别差异化规则（相邻镜头景别不能相同）
4. 对话场景遵循乒乓镜头规则（正反打交替）
5. 每个角色必须覆盖形态五大要素（神态、动作、服饰、道具、肌理）
6. 战斗场景必须使用打斗物理化规则
7. 只输出 {batch_size} 格（镜号从 S{done_next:02d} 开始连续编号）

已有分镜（JSON）：
{existing_json}

故事大纲/剧本：
{script_text}

角色定义：
{characters_block}

输出格式（严格 CSV-like，不要额外文字）：
镜号|人物|场景|景别|音频提示|画面描述|台词|备注
S{done_next:02d}|角色|场景|景别|音频|画面|台词|备注
"""


def _parse_storyboard_lines(text: str) -> list[dict[str, str]]:
    """解析 CSV-like 分镜输出 → list[dict]（复用逻辑抽离）"""
    shots = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or "镜号" in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 6:
            shots.append({
                "镜号": parts[0] if len(parts) > 0 else "",
                "人物": parts[1] if len(parts) > 1 else "",
                "场景": parts[2] if len(parts) > 2 else "",
                "景别": parts[3] if len(parts) > 3 else "",
                "音频提示": parts[4] if len(parts) > 4 else "",
                "画面描述": parts[5] if len(parts) > 5 else "",
                "台词": parts[6] if len(parts) > 6 else "",
                "备注": parts[7] if len(parts) > 7 else "",
            })
    return shots


def _ollama_generate_storyboard_batch(
    script_text: str,
    characters: dict[str, dict[str, str]],
    *,
    url: str | None = None,
    model: str | None = None,
    batch_size: int = 2,
    max_shots: int = 8,
) -> list[dict[str, str]]:
    """E1 逐批续写：每次生成 batch_size 格，已有分镜 JSON 喂回 LLM 续写。

    业界对齐（AI Comic Factory predictNextPanels）：长故事一次性生成会前后矛盾，
    逐批续写保证时间线/角色/场景连贯。
    """
    from agents.comfy_utils import ollama_generate

    # 角色定义块
    chars_block = "\n".join(
        f"  {name}: {', '.join(v for v in info.values() if v)}"
        for name, info in characters.items()
    ) if characters else "  （无预定义角色）"

    all_shots: list[dict[str, str]] = []
    import json as _json

    while len(all_shots) < max_shots:
        done_count = len(all_shots)
        batch = min(batch_size, max_shots - done_count)
        if batch <= 0:
            break
        existing = _json.dumps(all_shots, ensure_ascii=False) if all_shots else "（无，这是第一格）"

        prompt = _BATCH_CONTINUE_TEMPLATE.format(
            done_count=done_count,
            batch_size=batch,
            done_next=done_count + 1,
            existing_json=existing,
            script_text=script_text,
            characters_block=chars_block,
        )
        result = ollama_generate(prompt, url=url, model=model)
        new_shots = _parse_storyboard_lines(result)

        if not new_shots:
            # 输出不可解析 → 防止死循环
            if all_shots:
                break
            # 首轮失败也降级模板
            return _template_storyboard(script_text, characters)

        # 重编号保证连续
        for i, s in enumerate(new_shots, done_count + 1):
            s["镜号"] = f"S{i:02d}"
        all_shots.extend(new_shots)

        if len(new_shots) < batch:
            # LLM 提前结束（故事讲完了）
            break

    return all_shots


def _template_storyboard(
    script_text: str,
    characters: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    """模板兜底分镜表，支持 1~4 个角色动态生成。"""
    names = list(characters.keys())
    n = len(names)

    # 动态基础镜：至少 2 个，至多 n+2 个
    shots: list[dict[str, str]] = [
        {"镜号": "S01", "人物": names[0] if n > 0 else "角色A",
         "场景": script_text, "景别": "全景",
         "音频提示": "", "画面描述": f"定场镜头，展示场景", "台词": "", "备注": ""},
        {"镜号": "S02", "人物": names[0] if n > 0 else "角色A",
         "场景": script_text, "景别": "中景",
         "音频提示": "", "画面描述": f"{names[0] if n > 0 else '角色A'} 在场景中",
         "台词": "", "备注": ""},
    ]

    if n >= 2:
        shots.append({"镜号": "S03", "人物": names[1], "场景": script_text, "景别": "过肩",
                      "音频提示": "", "画面描述": f"{names[1]} 出现，与 {names[0]} 互动",
                      "台词": "", "备注": ""})

    if n >= 3:
        shots.append({"镜号": f"S0{len(shots)+1}", "人物": names[2], "场景": script_text, "景别": "中景",
                      "音频提示": "", "画面描述": f"{names[2]} 加入场景",
                      "台词": "", "备注": "新角色登场"})

    if n >= 4:
        shots.append({"镜号": f"S0{len(shots)+1}", "人物": names[3], "场景": script_text, "景别": "全景",
                      "音频提示": "", "画面描述": f"四人同框，{', '.join(names)}",
                      "台词": "", "备注": "群像"})

    # 特写结尾
    last_char = names[min(1, n-1)] if n > 0 else "角色A"
    shots.append({"镜号": f"S0{len(shots)+1}", "人物": last_char, "场景": script_text, "景别": "特写",
                  "音频提示": "", "画面描述": f"{last_char} 表情特写",
                  "台词": "", "备注": "情绪节点"})

    return shots


# ── E4: 漫画布局模板库（业界对齐 AI Comic Factory Layout0-N）──
# 每个模板: 格数 + 每格相对尺寸 (w_ratio, h_ratio)，面板按模板放置
# 布局名含义: L=大格主导（漫画节奏感来源），grid=均分，strip=条状
_LAYOUT_TEMPLATES: dict[str, dict[str, Any]] = {
    "L4": {  # 4格 L 形：1大(横) + 3小
        "panels": [(2.0, 1.0), (1.0, 1.0), (1.0, 1.0), (1.0, 1.0)],
        "cols": 2, "rows": 2,
    },
    "L4_v": {  # 4格 L 形：1大(竖) + 3小
        "panels": [(1.0, 2.0), (1.0, 1.0), (1.0, 1.0), (1.0, 1.0)],
        "cols": 2, "rows": 2,
    },
    "grid2x2": {  # 2x2 均分
        "panels": [(1.0, 1.0)] * 4,
        "cols": 2, "rows": 2,
    },
    "strip4": {  # 4格横条（webtoon 风格）
        "panels": [(1.0, 1.0)] * 4,
        "cols": 4, "rows": 1,
    },
    "grid3": {  # 3格：1大横 + 2竖
        "panels": [(2.0, 1.0), (1.0, 1.0), (1.0, 1.0)],
        "cols": 2, "rows": 2,
    },
    "strip3": {  # 3格横条
        "panels": [(1.0, 1.0)] * 3,
        "cols": 3, "rows": 1,
    },
    "grid6": {  # 6格 3x2 均分
        "panels": [(1.0, 1.0)] * 6,
        "cols": 3, "rows": 2,
    },
    "webtoon": {  # 条漫（webtoon 竖排 1 列，角色神态放大；"信息量低"由气泡密度补偿）
        "panels": [(1.0, 1.45)] * 4,
        "cols": 1, "rows": 4,
    },
    "webtoon6": {  # 条漫 6 格版（更长故事）
        "panels": [(1.0, 1.45)] * 6,
        "cols": 1, "rows": 6,
    },
}


def _match_layout(n_panels: int, panel_ratios: list[float], prefer: str = "") -> str:
    """根据面板数 + 宽高比自动选布局模板（业界 parseLayoutFromStoryboards）。

    panel_ratios: 每格宽/高比（>1=横，<1=竖，≈1=方）。
    prefer: "webtoon" 强制条漫布局；空=自动匹配。
    """
    if prefer == "webtoon":
        return "webtoon6" if n_panels >= 6 else "webtoon"
    if n_panels not in (3, 4, 6):
        # 其他格数回退固定网格
        return ""
    candidates = {k: v for k, v in _LAYOUT_TEMPLATES.items()
                  if len(v["panels"]) == n_panels}
    if not candidates:
        return ""

    max_r = max(panel_ratios) if panel_ratios else 1.0
    min_r = min(panel_ratios) if panel_ratios else 1.0
    avg_r = sum(panel_ratios) / len(panel_ratios) if panel_ratios else 1.0

    if n_panels == 4:
        if max_r >= 1.3 and max_r >= min_r * 1.8:
            # 有明确大横格 → L4
            return "L4"
        if min_r <= 0.77 and max_r <= 1.3:
            # 有竖格主导 → L4_v
            return "L4_v"
        if avg_r >= 1.6:
            return "strip4"
        return "grid2x2"
    if n_panels == 3:
        if max_r >= 1.3:
            return "grid3"
        return "strip3"
    return "grid6"


# ── B1: 漫画台词气泡（业界 AI Comic Factory bubble 组件）──

def _draw_balloon(draw: "ImageDraw.ImageDraw", dialogue: str,
                  x: int, y: int, w: int, h: int,
                  bubble_type: str = "ellipse", font=None) -> None:
    """在面板内绘制真正的漫画气泡。

    bubble_type:
      ellipse — 圆角椭圆（普通对话）
      tail    — 椭圆 + 左下尖角（指向说话者）
      rect    — 矩形（旁白/解说）
    自适应：按台词长度计算气泡尺寸，white 底 + 黑边，文字居中。
    """
    if not dialogue:
        return
    try:
        from PIL import ImageFont
        # 中文字体优先（arial 不含中文字形→中文静默空白，2026-08-14 实测）
        for f in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyh.ttf",
                  r"C:\Windows\Fonts\simhei.ttf", "arial.ttf"):
            try:
                font = font or ImageFont.truetype(f, 16)
                break
            except OSError:
                continue
        else:
            font = font or ImageFont.load_default()
    except (OSError, ImportError):
        from PIL import ImageFont
        font = font or ImageFont.load_default()

    # 文字换行（按气泡宽上限 60% 面板宽）
    max_text_w = int(w * 0.5)
    chars_per_line = max(4, max_text_w // 12)
    lines = [dialogue[i:i + chars_per_line] for i in range(0, len(dialogue), chars_per_line)]
    lines = lines[:4]  # 最多 4 行

    line_h = 20
    text_h = line_h * len(lines)
    bw = min(max(max_text_w, max(len(l) for l in lines) * 12 + 20), int(w * 0.9))
    bh = text_h + 16

    # 气泡位置：面板上部（避开角色面部通常在下部/中部）
    bx = x + (w - bw) // 2
    by = y + 8

    if bubble_type == "rect":
        # 旁白矩形
        draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=6,
                               fill=(255, 255, 255), outline=(0, 0, 0), width=2)
    else:
        # 椭圆（普通/带尖角）
        draw.ellipse([bx, by, bx + bw, by + bh], fill=(255, 255, 255), outline=(0, 0, 0), width=2)
        if bubble_type == "tail":
            # 左下尖角（指向说话者）
            draw.polygon([(bx + 20, by + bh), (bx + 42, by + bh), (bx + 14, by + bh + 18)],
                         fill=(255, 255, 255), outline=(0, 0, 0))
            # 覆盖尖角与椭圆交界
            draw.ellipse([bx, by, bx + bw, by + bh], fill=None, outline=(0, 0, 0), width=2)

    # 文字（居中）
    text_y = by + (bh - text_h) // 2 - 2
    for i, line in enumerate(lines):
        tw = draw.textlength(line, font=font)
        tx = bx + (bw - tw) // 2
        draw.text((tx, text_y + i * line_h), line, fill=(0, 0, 0), font=font)


def _balloon_type(shot: dict[str, Any], idx: int) -> str:
    """决定气泡类型：备注列含"旁白/解说" → rect；否则 tail（对话）"""
    note = shot.get("备注", "") if isinstance(shot, dict) else ""
    if any(k in note for k in ("旁白", "解说", "叙事", "内心")):
        return "rect"
    return "tail"


# 漫画音效字（拟声词 → 爆炸样式渲染，DFS-6）
_SFX_WORDS = ("ドン", "ドン！", "砰", "砰！", "轰", "轰！", "咚", "咚！",
              "咻", "咻！", "啪", "啪！", "叮", "叮！", "BANG", "BOOM")


def _draw_sfx(draw: "ImageDraw.ImageDraw", text: str, x: int, y: int, w: int, h: int) -> bool:
    """检测音效字并渲染（粗体斜体+描边+斜向放置——漫画表现力）。

    Returns: 是否渲染了音效字
    """
    if not any(s in text for s in _SFX_WORDS):
        return False
    try:
        from PIL import ImageFont
        # 音效字大号粗体（微软雅黑 Bold）
        font = None
        for f in (r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc"):
            try:
                font = ImageFont.truetype(f, int(h * 0.14))
                break
            except OSError:
                continue
        if font is None:
            return False
    except (OSError, ImportError):
        return False

    sfx = text.strip()
    if len(sfx) > 4:
        sfx = sfx[:4]
    # 斜向大字（画布上 45° 旋转）
    from PIL import Image, ImageDraw
    layer = Image.new('RGBA', (int(w * 0.8), int(h * 0.35)), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    tw = ld.textlength(sfx, font=font)
    # 白字 + 黑描边（漫画音效经典样式）
    ld.text(((layer.width - tw) // 2, 10), sfx, fill=(255, 255, 255),
            font=font, stroke_width=6, stroke_fill=(0, 0, 0))
    # 旋转 15°
    layer = layer.rotate(-12, expand=True, resample=Image.BICUBIC)
    # 放在面板右上
    px = x + int(w * 0.45)
    py = y + int(h * 0.05)
    draw._image.paste(layer, (px, py), layer)
    return True


# ── B3: 多页漫画工作流（一句话 → 整本）──

def manga_book(
    script_text: str,
    characters: dict[str, dict[str, str]],
    *,
    pages: int = 1,
    shots_per_page: int = 4,
    batch_size: int = 2,
    output_dir: str | None = None,
    cover: bool = True,
    style_hint: str = "anime",
    model_type: str = "sdxl",
    webtoon: bool = False,
    ollama_url: str | None = None,
    ollama_model: str | None = None,
) -> dict[str, Any]:
    """一句话剧本 → 整本漫画（多页 + 封面）。

    流程：
      1. E1 逐批续写分镜（batch_size 保证故事连贯）
      2. 分镜按页分组（shots_per_page 格/页）
      3. 每页：storyboard_to_prompts → generate_panels → assemble_page（E4 布局）
      4. 封面（可选）：用剧本生成主视觉图
      5. 输出：page_01.png ... + cover.png + metadata.json

    Returns:
        {"cover": path, "pages": [path...], "storyboard": [...], "output_dir": str}
    """
    import time as _time

    out_dir = Path(output_dir or (PROJECT / "outputs" / f"manga_book_{_time.strftime('%Y%m%d_%H%M%S')}"))
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. E1 逐批续写分镜（总格数 = pages * shots_per_page）
    max_shots = pages * shots_per_page
    storyboard = script_to_storyboard(
        script_text, characters, ollama_available=True,
        ollama_url=ollama_url, ollama_model=ollama_model,
        batch_size=batch_size, max_shots=max_shots,
    )
    if not storyboard:
        raise RuntimeError("分镜生成失败")
    print(f"  📖 分镜 {len(storyboard)} 格（目标 {max_shots}）")

    # 2. 分页
    page_groups = [storyboard[i:i + shots_per_page]
                   for i in range(0, len(storyboard), shots_per_page)]
    print(f"  📄 共 {len(page_groups)} 页")

    # 3. 每页出图 + 拼版
    pages_out: list[str] = []
    from workshop.manga.manga import storyboard_to_prompts, generate_panels, assemble_page
    for p_idx, group in enumerate(page_groups, 1):
        print(f"  ── 第 {p_idx}/{len(page_groups)} 页 ──")
        panel_list = storyboard_to_prompts(group, characters, style_hint=style_hint, model_type=model_type)
        results = generate_panels(panel_list, flux=(model_type != "sdxl"), prefix=f"mb{p_idx:02d}")
        page_path = str(out_dir / f"page_{p_idx:02d}.png")
        assemble_page(results, layout="webtoon" if webtoon else "auto",
                      output_path=page_path, balloon=True)
        pages_out.append(page_path)

    # 4. 封面（用剧本生成主视觉）
    cover_path = None
    if cover:
        try:
            from workshop.create import create_from_nl
            cover_dir = out_dir / "cover"
            cover_dir.mkdir(exist_ok=True)
            cover_prompt = f"{script_text}, cover art, dramatic composition, title page"
            create_from_nl(cover_prompt, count=1, model_type=model_type,
                           prompt_ready=False, inspect=False, dry_run=False,
                           output_dir=str(cover_dir))
            import glob as _glob
            cands = sorted(_glob.glob(str(cover_dir / "**" / "best.png"), recursive=True))
            if cands:
                cover_path = cands[0]
                print(f"  🎨 封面: {cover_path}")
        except Exception as e:
            print(f"  ⚠️ 封面生成失败（跳过）: {str(e)[:100]}")

    # 5. 元数据
    meta = {
        "script": script_text,
        "characters": characters,
        "pages": len(pages_out),
        "shots": len(storyboard),
        "cover": cover_path,
        "page_files": pages_out,
        "storyboard": storyboard,
    }
    (out_dir / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n✅ 漫画完成: {out_dir}")
    if cover_path:
        print(f"   封面: {cover_path}")
    for p in pages_out:
        print(f"   页面: {p}")
    print(f"   元数据: {out_dir / 'metadata.json'}")
    return meta


# 分格边框样式（漫画风格化细节：sharp 直角 / round 圆角 / slash 斜切）
BORDER_STYLES = ("sharp", "round", "slash")


def _draw_panel_border(canvas: "Image.Image", x: int, y: int, w: int, h: int,
                       style: str = "sharp", gap: int = 8) -> None:
    """在面板区域画分格边框线（透明底板——不遮内容，黑框线分隔）。"""
    from PIL import ImageDraw
    d = ImageDraw.Draw(canvas)
    bx, by = x + gap, y + gap
    bw, bh = w - gap * 2, h - gap * 2
    if style == "round":
        d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=int(gap * 1.5),
                            outline=(0, 0, 0), width=3)
    elif style == "slash":
        # 斜切角（左上/右下切掉 45°）
        cut = int(gap * 2)
        d.polygon([(bx + cut, by), (bx + bw, by), (bx + bw, by + bh - cut),
                   (bx + bw - cut, by + bh), (bx, by + bh), (bx, by + cut)],
                  outline=(0, 0, 0), width=3)
    else:
        d.rectangle([bx, by, bx + bw, by + bh], outline=(0, 0, 0), width=3)


def _layout_size(camera: str) -> tuple[int, int]:
    """景别 → 画面尺寸（SDXL 原生分辨率）。"""
    if "特写" in camera or "大头" in camera:
        return 896, 896      # 1:1 方图
    elif "全身" in camera:
        return 768, 1344     # 9:16 竖版全身
    elif "远景" in camera or "远" in camera:
        return 1344, 768     # 16:9 横版风景
    elif "双人" in camera or "两人" in camera:
        return 1216, 832     # ~3:2 双人构图
    else:
        return 896, 1152     # 3:4 半身/中景默认


def _seed_from_shot(shot_id: str) -> int:
    """从镜号生成种子（保持画风一致）。"""
    nums = re.findall(r"\d+", shot_id)
    base = int(nums[0]) if nums else 1
    return hash(f"manga_{shot_id}") % (2 ** 31 - 1)


def generate_manga_gallery(
    output_dir: str,
    meta: dict[str, Any],
    panel_paths: dict[str, str],
    assembled_path: str | None = None,
    char_refs: dict[str, str] | None = None,
) -> str:
    """为漫画输出生成 HTML 画廊页。

    Args:
        output_dir: 输出目录（与 metadata.json 同级）
        meta: metadata.json 内容
        panel_paths: {镜号: 图片路径} 映射
        assembled_path: 拼页图片路径
        char_refs: 角色名 → 参考图路径 映射

    Returns:
        生成的 HTML 文件路径
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    panels_html = ""
    for shot_id, img_path in panel_paths.items():
        rel = Path(img_path).name
        panels_html += f"""
    <div class="panel">
        <img src="{rel}" loading="lazy">
        <div class="panel-label">镜号 {shot_id}</div>
    </div>"""

    assembled_html = ""
    if assembled_path:
        rel_ass = Path(assembled_path).name
        assembled_html = f"""
    <div class="section">
        <h2>拼页</h2>
        <img src="{rel_ass}" class="assembled">
    </div>"""

    char_html = ""
    chars = meta.get("角色", {})
    if chars:
        char_items = ""
        for name, info in chars.items():
            ref_img = ""
            if char_refs and name in char_refs:
                ref_src = Path(char_refs[name]).name
                try:
                    import shutil
                    shutil.copy2(char_refs[name], str(out_dir / ref_src))
                    ref_img = f'<img src="{ref_src}" class="char-ref" title="{name} 参考图"/>'
                except Exception:
                    pass
            char_items += f"""<li>
  {ref_img}
  <b>{name}</b>: {info.get("服饰","?")} / {info.get("发型","?")} / {info.get("特征","?")}
</li>"""
        char_html = f"""
    <div class="section">
        <h2>角色</h2>
        <ul>{char_items}</ul>
    </div>"""

    html = f"""<!DOCTYPE html><html lang="zh-CN">
<head><meta charset="utf-8"><title>漫画画廊</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:-apple-system,'Segoe UI',sans-serif;background:#f5f5f5;color:#333;padding:24px}}
  h1{{font-size:24px;margin-bottom:8px}}
  .meta{{color:#666;font-size:14px;margin-bottom:24px}}
  .meta span{{margin-right:16px}}
  .grid{{display:flex;flex-wrap:wrap;gap:16px;margin-bottom:24px}}
  .panel{{background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08);width:300px}}
  .panel img{{width:100%;height:auto;display:block}}
  .panel-label{{padding:8px;font-size:13px;color:#666;text-align:center}}
  .section{{margin-bottom:24px;background:#fff;border-radius:8px;padding:16px;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
  .section h2{{font-size:18px;margin-bottom:12px}}
  .assembled{{max-width:100%;height:auto}}
  ul{{list-style:none}}
  li{{padding:4px 0;font-size:14px}}
  .char-ref{{width:48px;height:48px;object-fit:cover;border-radius:4px;vertical-align:middle;margin-right:8px;border:1px solid #ddd}}
</style></head><body>
<h1>📖 漫画画廊</h1>
<div class="meta">
  <span>🎨 风格: {meta.get("风格", "?")}</span>
  <span>📐 布局: {meta.get("layout", "?")}</span>
  <span>📄 共 {len(panel_paths)} 格</span>
</div>
<div class="section">
  <h2>剧本</h2>
  <p style="font-size:14px;color:#555">{meta.get("脚本", "")}</p>
</div>{char_html}
<h2>逐格面板</h2>
<div class="grid">{panels_html}</div>{assembled_html}
</body></html>"""

    gallery_path = out_dir / "gallery.html"
    gallery_path.write_text(html, encoding="utf-8")
    print(f"  🖼️  画廊: {gallery_path}")
    return str(gallery_path.resolve())


def validate_storyboard(storyboard: list[dict[str, str]],
                        characters: dict[str, dict[str, str]]) -> list[str]:
    """验证分镜表连贯性，返回警告列表。"""
    warnings: list[str] = []
    names = set(characters.keys())
    seen_chars: set[str] = set()

    for i, shot in enumerate(storyboard):
        sid = shot.get("镜号", f"#{i+1}")
        char = shot.get("人物", "")
        scene = shot.get("场景", "").strip()
        camera = shot.get("景别", "")
        visual = shot.get("画面描述", "").strip()

        if char and char not in names:
            warnings.append(f"[{sid}] 角色 '{char}' 未在 --char 中定义")
        if not camera:
            warnings.append(f"[{sid}] 缺少景别")
        if not visual:
            warnings.append(f"[{sid}] 缺少画面描述")
        if char:
            seen_chars.add(char)

    for name in names:
        if name not in seen_chars:
            warnings.append(f"角色 '{name}' 在所有分镜中均未出场")

    return warnings
