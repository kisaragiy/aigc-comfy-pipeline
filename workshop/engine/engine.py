"""
Prompt 引擎 — 自然语言 → 专业绘画提示词。

核心能力:
  1. nls_to_prompt()       — 自然语言 → 专业 prompt（自动推测画风/构图/光照/镜头）
  2. ref_analyze_to_prompt() — 参考图 + 自然语言 → 分析角色画风特征 + 组合 prompt
  3. 多风格预设模板（anime/photoreal/cg/cosplay/cinematic/摄影/CG/油画等）
  4. Ollama 不可用时强模板兜底（比旧 _fallback_prompt 更智能）
"""

from __future__ import annotations

import re
import sys
from typing import Any

# ── 风格预设库 ──────────────────────────────────────────
STYLE_PRESETS: dict[str, dict[str, str]] = {
    "anime": {
        "quality": "masterpiece, best quality, ultra-detailed, anime key visual",
        "style": "anime style, cel shading, clean lineart, vibrant colors",
        "negative": "lowres, bad anatomy, bad hands, text, error, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry",
    },
    "photoreal": {
        "quality": "photorealistic, 8k, highly detailed, sharp focus, natural skin texture",
        "style": "realistic photography, natural lighting, subsurface scattering, skin pores visible",
        "negative": "anime, illustration, cartoon, 3d render, CG, painting, deformed, bad anatomy, disfigured, poorly drawn, extra limbs",
    },
    "cg": {
        "quality": "masterpiece, best quality, 8k, CG render, octane render, unreal engine",
        "style": "3D render style, subsurface scattering, global illumination, ray tracing, volumetric lighting",
        "negative": "anime, illustration, sketch, line art, flat colors, bad anatomy, ugly, deformed",
    },
    "cosplay": {
        "quality": "masterpiece, best quality, sharp focus, highly detailed, 8k",
        "style": "cosplay photography, professional studio lighting, costume detail close-up, fabric texture visible",
        "negative": "anime, illustration, cartoon, CG, 3d render, deformed, bad anatomy, disfigured",
    },
    "cinematic": {
        "quality": "masterpiece, cinematic, film grain, anamorphic, dramatic lighting, 8k",
        "style": "movie still, cinematic composition, volumetric fog, depth of field, rich shadows",
        "negative": "anime, illustration, flat lighting, snapshot, amateur, deformed, bad anatomy",
    },
    "photography": {
        "quality": "masterpiece, sharp focus, 8k, highly detailed, professional photography",
        "style": "portrait photography, studio lighting, shallow depth of field, bokeh background",
        "negative": "anime, illustration, painting, 3d render, CG, deformed, bad anatomy, cartoon",
    },
    "oil": {
        "quality": "masterpiece, oil on canvas, thick impasto, visible brush strokes, textured",
        "style": "oil painting style, painterly, classical composition, warm palette, chiaroscuro",
        "negative": "photograph, digital art, 3d render, anime, illustration, photorealistic",
    },
    "sketch": {
        "quality": "masterpiece, rough sketch, concept art, dynamic lines",
        "style": "pencil sketch, line art, minimal shading, gestural drawing, expressive strokes",
        "negative": "color, photograph, digital art, photorealistic, painting, 3d render",
    },
    "watercolor": {
        "quality": "masterpiece, beautiful watercolor painting, soft washes",
        "style": "watercolor style, pigment bleeding, wet on wet technique, paper texture visible",
        "negative": "photograph, digital art, sharp lines, photorealistic, oil painting, CG",
    },
}

# ── 构图/镜头预设 ──────────────────────────────────────
COMPOSITION_PRESETS: dict[str, str] = {
    "全身": "full body shot, standing pose, full figure in frame",
    "半身": "upper body, cowboy shot, waist up framing",
    "特写": "close-up, face focus, extreme close-up, detailed facial features",
    "大头": "close-up on face, headshot, face filling frame",
    "中景": "medium shot, waist to head, balanced framing",
    "远景": "wide shot, establishing shot, full environment visible",
    "俯视": "high angle, bird's eye view, looking down",
    "仰视": "low angle, worm's eye view, looking up, heroic perspective",
    "过肩": "over the shoulder shot, POV perspective, depth between subjects",
    "侧面": "side profile, profile view, silhouette visible",
    "背面": "from behind, back view, looking away",
}

LIGHTING_PRESETS: dict[str, str] = {
    "自然光": "natural lighting, soft sunlight, golden hour glow",
    "逆光": "backlighting, rim light, silhouette edge glow, backlit",
    "侧光": "side lighting, chiaroscuro, dramatic shadows on one side",
    "顶光": "top lighting, overhead light, harsh shadows below",
    "柔光": "soft lighting, diffused light, even illumination, shadowless",
    "霓虹": "neon lighting, colorful neon glow, cyberpunk lighting, street light reflection",
    "烛光": "candle light, warm orange glow, flickering firelight, intimate atmosphere",
    "舞台": "stage lighting, spotlight, dramatic contrast, colored gels on subject",
    "晨光": "morning light, cool blue hour, gentle sun rays through window",
    "黄昏": "sunset lighting, warm golden backlight, orange and pink sky, silhouette rim light",
    "月光": "moonlight, cool blue illumination, silver glow, night atmosphere",
    "体积光": "volumetric lighting, god rays, light beams through fog, crepuscular rays",
}

# ── 负向提示词检测库 ──────────────────────────────────────

NEGATIVE_KEYWORDS: dict[str, str] = {
    "模糊": "blurry, out of focus, soft focus",
    "崩手": "bad hands, deformed hands, extra fingers, missing fingers",
    "崩脸": "bad face, deformed face, asymmetric face",
    "畸变": "deformed, distorted, twisted, warped",
    "鬼影": "ghosting, double image, artifacts",
    "噪点": "noise, grainy, noisy",
    "水印": "watermark, signature",
    "签名": "watermark, signature",
    "文字": "text, letters, words, typography",
    "太暗": "dark, underexposed, shadowy, low light",
    "太亮": "overexposed, blown out, too bright, washed out",
    "紫边": "chromatic aberration, purple fringing",
}

STYLE_KEYWORDS: dict[str, str] = {
    "赛博朋克": "cyberpunk, futuristic city, neon lights, holographic displays, rain soaked streets, high tech low life",
    "蒸汽波": "vaporwave, retro 80s aesthetic, neon grids, purple and pink palette, synthwave",
    "奇幻": "fantasy, magical atmosphere, glowing elements, ethereal, enchanted forest, mythical",
    "末世": "post-apocalyptic, wasteland, ruins, abandoned, decay, desolate, survival gear",
    "古风": "traditional Chinese aesthetic, hanfu, classical architecture, ink wash atmosphere, gufeng",
    "日式": "japanese style, wabi-sabi, traditional japanese aesthetic, cherry blossoms, lanterns",
    "校园": "school setting, classroom, campus, youthful atmosphere, cherry blossom schoolyard",
    "都市": "urban cityscape, modern city, skyscrapers, street level, city life, concrete jungle",
    "田园": "rural, countryside, pastoral, wheat fields, farmhouse, idyllic village",
    "科幻": "sci-fi, futuristic technology, holographic interfaces, advanced civilization, starship",
    "哥特": "gothic, dark aesthetic, Victorian gothic, cathedral, ornate darkness, dramatic shadows",
    "洛可可": "rococo style, ornate decoration, pastel colors, aristocratic, elegant curves",
    "像素": "pixel art, 8-bit style, retro game aesthetic, blocky pixels, limited color palette",
    "水墨": "ink wash painting, sumi-e, minimal brush strokes, monochrome, flowing ink",
}

# ── 模板化系统 ──────────────────────────────────────────

_OLLAMA_TEMPLATE = """You are a professional AI prompt engineer for Stable Diffusion / Flux. Convert the user's natural language description into a high-quality English prompt.

Requirements:
1. Analyze the implied STYLE (anime, photoreal, CG, cosplay, cinematic, oil painting, etc.)
2. Analyze the COMPOSITION (close-up, half-body, full-body, wide shot, low/high angle, etc.)
3. Analyze the LIGHTING (natural, backlight, side light, neon, stage, etc.)
4. Analyze the MOOD / COLOR TONE (warm, cool, cyberpunk, etc.)
5. Infer defaults for any missing elements using best practices
6. Output ONLY the English prompt — no explanations, no notes, no markup

User description:
{user_input}

Output format (English only, comma-separated tags):
MASTERPIECE, best quality, [detailed English description], [composition], [lighting], [color/mood terms]"""

_FALLBACK_TEMPLATE = """你是一位专业的 AI 绘画提示词工程师。请将用户的自然语言描述，转化为高质量的英文绘画提示词。

用户描述（中文）：
{user_input}

请直接输出英文提示词，包含：主体、细节、环境、构图、光照、质量词。用英文逗号分隔关键词。"""


def nls_to_prompt(
    nl_text: str,
    style_hint: str | None = None,
    *,
    ollama_available: bool = True,
    ollama_url: str | None = None,
    ollama_model: str | None = None,
) -> str:
    """自然语言描述 → 专业绘画提示词。

    Args:
        nl_text: 用户自然语言描述（比如"一个银发少女穿着校服在教室窗边看书，逆光"）
        style_hint: 可选风格提示（anime/photoreal/cg/cosplay/…，或任意关键词）
        ollama_available: Ollama 是否可用
        ollama_url: Ollama API 地址
        ollama_model: Ollama 模型名

    Returns:
        优化后的英文提示词
    """
    if ollama_available:
        try:
            result = _ollama_enhance(nl_text, style_hint, url=ollama_url, model=ollama_model)
            return result
        except Exception:
            pass  # 降级到模板
    return _template_fallback(nl_text, style_hint)


def ref_analyze_to_prompt(
    ref_path: str,
    nl_text: str,
    *,
    ollama_available: bool = True,
    ollama_url: str | None = None,
    ollama_model: str | None = None,
) -> dict[str, Any]:
    """参考图 + 自然语言 → 分析角色/画风特征 + 组合 prompt。

    使用 Ollama VL 模型（qwen2.5vl:7b）分析参考图，然后结合用户描述生成 prompt。

    Returns:
        包含以下键的字典:
          prompt:         组合后的完整提示词
          character_desc: 分析出的角色特征描述
          style_desc:     分析出的画风特征描述
          ref_prompt:     单独用于参考图的 prompt（IPAdapter 使用）
    """
    character_desc = ""
    style_desc = ""
    ref_prompt = ""
    composition = ""
    lighting = ""
    colors = ""
    background = ""

    # 1. 分析参考图（需要 VL 模型）
    if ollama_available:
        try:
            analysis = _ollama_vl_analyze(ref_path, url=ollama_url, model=ollama_model or "qwen2.5vl:7b")
            character_desc = analysis.get("character", "")
            style_desc = analysis.get("style", "")
            composition = analysis.get("composition", "")
            lighting = analysis.get("lighting", "")
            colors = analysis.get("colors", "")
            background = analysis.get("background", "")
        except Exception:
            pass  # 分析失败后纯用 NL

    if not character_desc:
        # 无法分析图片时，提取 NL 中可能的人物描述
        character_desc = nl_text

    # 2. 组合 prompt — 优先使用 IP-Adapter 视觉条件，文字只需补充特征
    base_prompt = nls_to_prompt(nl_text, ollama_available=ollama_available)

    # 角色锚定描述（不含构图/光照等 — IP-Adapter 处理视觉，文字只做辅助）
    anchor_desc = character_desc[:300]  # 保持紧凑
    if style_desc:
        anchor_desc = f"{anchor_desc}, {style_desc}"

    # 视觉增强描述（构图/光照/颜色 — 帮助 Flux 理解意图）
    vision_terms = []
    if lighting:
        vision_terms.append(lighting[:80])
    if composition:
        vision_terms.append(composition[:80])
    if colors:
        vision_terms.append(colors[:120])
    if vision_terms:
        anchor_desc = f"{anchor_desc}, {', '.join(vision_terms)}"

    # 合并用户 NL + 角色锚定
    ref_prompt = f"{character_desc[:200]}, {base_prompt}"

    # 3. 提取风格用语
    style_terms = ", ".join(_extract_keywords(nl_text))

    return {
        "prompt": ref_prompt,
        "character_desc": character_desc,
        "style_desc": style_desc or style_terms,
        "ref_prompt": f"{anchor_desc}, masterpiece, best quality",
        "composition": composition,
        "lighting": lighting,
        "colors": colors,
        "background": background,
    }


# ── 内部函数 ────────────────────────────────────────────


def _ollama_enhance(
    nl_text: str,
    style_hint: str | None = None,
    *,
    url: str | None = None,
    model: str | None = None,
) -> str:
    """使用 Ollama 增强提示词。

    自动探测可用 Ollama 地址（优先环境变量 → 默认 → WSL 地址），
    全部不可用则抛异常由调用方降级。
    """
    from agents.comfy_utils import ollama_generate

    # 自动探测可用 Ollama 地址
    candidates = []
    if url:
        candidates.append(url)
    env_url = __import__("os").environ.get("OLLAMA_URL")
    if env_url:
        candidates.append(env_url)
    # 默认（git-bash 下 env 可能未传递）
    from agents.comfy_utils import DEFAULT_OLLAMA_URL
    candidates.append(DEFAULT_OLLAMA_URL)
    # WSL 备用地址
    candidates.append("http://172.18.9.126:11434/api/generate")

    model_name = model or __import__("os").environ.get("OLLAMA_MODEL") or "qwen3:14b"

    template = _OLLAMA_TEMPLATE
    if style_hint:
        template = f"(User-specified style direction: {style_hint})\n\n" + template

    prompt = template.format(user_input=nl_text)

    # 逐个尝试
    last_err = None
    for try_url in dict.fromkeys(candidates):  # dedup preserving order
        try:
            result = ollama_generate(prompt, url=try_url, model=model_name, timeout=30)
            if result:
                return _clean_ollama_output(result)
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(f"所有 Ollama 地址均不可用: {last_err}")


def _clean_ollama_output(result: str) -> str:
    """清理 Ollama 输出：去空白/引号/中文行/尾随分隔符。"""
    result = result.strip().strip("，,。、")
    # 去掉引号包裹
    if (result.startswith('"') and result.endswith('"')) or \
       (result.startswith("'") and result.endswith("'")):
        result = result[1:-1]
    # 去掉可能的中文说明行（包含中文的行）
    lines = result.split("\n")
    cleaned_lines = [l for l in lines if not re.search(r"[\u4e00-\u9fff]", l)]
    if cleaned_lines:
        result = cleaned_lines[0].strip().strip("，,。、")
    else:
        result = result.strip()

    return result


def _ollama_vl_analyze(
    ref_path: str,
    *,
    url: str | None = None,
    model: str = "qwen2.5vl:7b",
) -> dict[str, str]:
    """使用 Ollama VL 模型分析参考图，提取角色/画风特征。"""
    import json
    import requests
    import os

    # 自动探测 Ollama 地址
    env_url = url or os.environ.get("OLLAMA_URL", "http://172.18.9.126:11434/api/generate")
    ollama_url = env_url
    if not ollama_url.endswith("/api/generate"):
        ollama_url = ollama_url.rstrip("/") + "/api/generate"
    prompt = (
        "Analyze this image in detail. Return ONLY valid JSON, no extra text.\\n"
        "JSON keys (ALL required):\\n"
        '  "character": VERY DETAILED English description of the character — '
        'face_shape (oval/round/square/heart), eye_shape (big/almond/slant/narrow), '
        'eyebrow_style (thin/thick/arched/straight), nose_shape (small/pointed/bridge), '
        'lip_style (full/thin/small/smirk), hair_style (long/short/braided/twintails/ponytail/straight/wavy/curly/bangs), '
        'hair_color, eye_color, skin_tone (fair/light/tan/dark), '
        'outfit_top (type/color/collar/sleeves/patterns), '
        'outfit_bottom (type/color/length), '
        'footwear (type/color), '
        'accessories (headwear/necklace/earrings/glasses/gloves/belt), '
        'distinctive_features (birthmarks/scars/tattoos/unusual markings/unique props). '
        'Be as specific as possible (e.g. "long straight silver hair with blunt bangs framing the face, large round crimson eyes, fair skin, wearing a white military-style coat with gold trim and red accents, black gloves, distinctive blue gem pendant on a silver chain")\\n'
        '  "style":    Art style in English (realistic / 2D anime / cel-shaded / CG render / oil painting / watercolor / sketch / pixel art) + artist references if recognizable\\n'
        '  "composition": Composition in English (full body / half body / close-up / bust / waist-up / cowgirl / worm-eye / dutch angle / symmetrical / rule of thirds)\\n'
        '  "lighting":  Lighting in English (backlight / rim light / side light / soft diffused / dramatic / natural window light / stage spotlight / volumetric / neon)\\n'
        '  "colors":    Dominant color palette in English (e.g. "cool tones: silver, cyan, dark blue, with warm gold accents. High contrast between white uniform and dark background")\\n'
        '  "background": Background description (solid color / gradient / scenery / abstract / dark / light / blurred)\\n'
    )

    # Ollama VL 支持 base64 图片
    import base64

    with open(ref_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "model": model,
        "prompt": prompt,
        "images": [b64],
        "stream": False,
    }
    resp = requests.post(ollama_url, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    text = data.get("response", "").strip()

    # 尝试解析 JSON
    try:
        # 找 JSON 块
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except (json.JSONDecodeError, ValueError):
        pass

    return {"character": text, "style": "", "composition": "", "lighting": ""}


def _template_fallback(nl_text: str, style_hint: str | None = None) -> str:
    """强模板兜底 — 比旧 _fallback_prompt 更智能。

    使用关键词匹配 + 风格预设合成专业提示词，而不是简单拼接。
    """
    # 1. 推测画风
    detected_style = _detect_style(nl_text, style_hint)
    preset = STYLE_PRESETS.get(detected_style, STYLE_PRESETS["photoreal"])

    # 2. 推测构图
    composition = _detect_composition(nl_text)

    # 3. 推测光照
    lighting = _detect_lighting(nl_text)

    # 4. 提取风格关键词
    style_terms = _extract_keywords(nl_text)

    # 5. 合成主题
    subject = _clean_subject(nl_text)

    # 6. 组合
    parts = [
        preset["quality"],
        preset["style"],
        subject,
        composition,
        lighting,
    ]
    # 风格附加词
    if style_terms:
        parts.append(", ".join(style_terms))

    # 去重
    seen: set[str] = set()
    unique_parts: list[str] = []
    for p in parts:
        p_stripped = p.strip().strip(",")
        if p_stripped and p_stripped not in seen:
            seen.add(p_stripped)
            unique_parts.append(p_stripped)

    return ", ".join(unique_parts)


def _detect_style(text: str, hint: str | None = None) -> str:
    """从描述中推测画风。"""
    if hint and hint.lower() in STYLE_PRESETS:
        return hint.lower()

    text_lower = text.lower()
    style_map: list[tuple[str, str]] = [
        ("二次元", "anime"),
        ("动漫", "anime"),
        ("动画", "anime"),
        ("日系", "anime"),
        ("写实", "photoreal"),
        ("真人", "photoreal"),
        ("摄影", "photography"),
        ("照片", "photography"),
        ("写真", "photography"),
        ("cos", "cosplay"),
        ("c服", "cosplay"),
        ("cg", "cg"),
        ("3d", "cg"),
        ("渲染", "cg"),
        ("电影", "cinematic"),
        ("镜头", "cinematic"),
        ("油画", "oil"),
        ("素描", "sketch"),
        ("草图", "sketch"),
        ("线稿", "sketch"),
        ("水彩", "watercolor"),
        ("像素", "pixel"),
        ("水墨", "ink"),
    ]
    for kw, style in style_map:
        if kw in text_lower:
            return style
    return "anime"  # 默认 anime（用户常用画风）


def _detect_composition(text: str) -> str:
    """从描述中推测构图。"""
    for cn_key, en_val in COMPOSITION_PRESETS.items():
        if cn_key in text:
            return en_val
    # 默认中景
    return "medium shot, balanced composition, eye level"


def _detect_lighting(text: str) -> str:
    """从描述中推测光照。"""
    for cn_key, en_val in LIGHTING_PRESETS.items():
        if cn_key in text:
            return en_val
    return "soft natural lighting, diffused illumination"


# ── 负向提示词自动检测 ────────────────────────────────────

_NEGATIVE_PATTERNS: list[str] = [
    r"不要(.*?)(?:[，。、！？；：\s]|$)",
    r"别(.*?)(?:[，。、！？；：\s]|$)",
    r"没有(.*?)(?:[，。、！？；：\s]|$)",
    r"不能有(.*?)(?:[，。、！？；：\s]|$)",
    r"排除(.*?)(?:[，。、！？；：\s]|$)",
]


def _detect_negative(text: str) -> str:
    """从自然语言描述中自动提取负向提示词。

    支持:
      - "不要模糊背景" / "别崩手" / "没有文字" 等句式 → 匹配关键词库
      - "模糊" / "崩手" / "水印" 等直接关键词 → 映射英文负向词

    Returns:
        逗号分隔的英文负向 tag，无匹配返回 ""
    """
    if not text or not text.strip():
        return ""

    parts: list[str] = []
    found_cn: set[str] = set()
    found_en: set[str] = set()

    # 1. 句式匹配：提取 "不要X" 等结构中的关键词
    for pat in _NEGATIVE_PATTERNS:
        for match in re.finditer(pat, text):
            term = match.group(1).strip()
            if not term:
                continue
            for cn_kw, en_tag in NEGATIVE_KEYWORDS.items():
                if cn_kw in term and cn_kw not in found_cn and en_tag not in found_en:
                    parts.append(en_tag)
                    found_cn.add(cn_kw)
                    found_en.add(en_tag)

    # 2. 直接关键词匹配（句式未覆盖的）
    for cn_kw, en_tag in NEGATIVE_KEYWORDS.items():
        if cn_kw in text and cn_kw not in found_cn and en_tag not in found_en:
            parts.append(en_tag)
            found_cn.add(cn_kw)
            found_en.add(en_tag)

    return ", ".join(parts)


def _extract_keywords(text: str) -> list[str]:
    """提取描述中的风格/氛围关键词。"""
    result: list[str] = []
    for cn_key, en_val in STYLE_KEYWORDS.items():
        if cn_key in text:
            result.append(en_val)
    return result


def _clean_subject(text: str) -> str:
    """从原始描述中提取主体描述（去除已知关键词）。"""
    # 去除所有已匹配的关键词
    known = list(COMPOSITION_PRESETS.keys()) + list(LIGHTING_PRESETS.keys()) + list(STYLE_KEYWORDS.keys())
    cleaned = text
    for kw in known:
        cleaned = cleaned.replace(kw, "")
    # 去除标点和多余空格
    cleaned = re.sub(r"[，。！？、；：""''【】《》「」『』（）、\s]+", " ", cleaned)
    cleaned = cleaned.strip()
    # 如果清理后为空，用原始文本
    if not cleaned or len(cleaned) < 2:
        cleaned = text
    return cleaned


def list_presets() -> dict[str, list[str]]:
    """列出可用预设和关键词。"""
    return {
        "styles": sorted(STYLE_PRESETS.keys()),
        "compositions": sorted(COMPOSITION_PRESETS.keys()),
        "lighting": sorted(LIGHTING_PRESETS.keys()),
        "style_keywords": sorted(STYLE_KEYWORDS.keys()),
    }
