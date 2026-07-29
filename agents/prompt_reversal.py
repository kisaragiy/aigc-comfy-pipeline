"""
提示词反推引擎 — 图片→专业绘画提示词

用法:
    from agents.prompt_reversal import reverse_prompt
    result = reverse_prompt("character_ref.png")
    # → {"sdxl": "SDXL格式提示词", "flux": "Flux格式提示词", "anima": "自然语言描述"}

支持3种模型输出格式:
  - SDXL风格:  逗号分隔标签式, MASTERPIECE, best quality, ...
  - Flux风格:  自然语言段落式
  - Anima风格: 自然语言描述（偏向SDXL/动漫混合）
"""

from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any

import requests

OLLAMA_API = os.environ.get("OLLAMA_API", "http://127.0.0.1:11434")
VLM_MODEL = os.environ.get("VLM_MODEL", "qwen3-vl:8b")
TEXT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:14b")

# ── 反推提示词 — VLM 分析图片 → 结构化描述 ──

REVERSE_PROMPT = """You are an expert AI prompt engineer. Analyze this image and create professional prompts for 3 different AI models.

First, describe the image in detail (for prompt construction):
1. Subject: character appearance, clothing, expression, pose, age, gender
2. Scene: environment, background, time of day, weather
3. Composition: camera angle, shot type, framing
4. Lighting: light source, mood, atmosphere
5. Colors: dominant colors, color scheme
6. Style: art style, rendering technique

Then output EXACTLY this JSON structure (no markdown, no extra text):
{
  "subject": "主角色详细描述（外貌、服装、动作、表情、特征）",
  "scene": "场景环境描述",
  "composition": "构图和镜头描述",
  "lighting": "光线氛围描述",
  "colors": "色彩方案描述",
  "style_tags": ["anime style", "cel shading", "vibrant colors"],
  "extra_details": "其他值得注意的视觉细节"
}"""


def _call_vlm(prompt: str, image_path: str, timeout: float = 60) -> str:
    """调用 VLM 分析图片。"""
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "model": VLM_MODEL,
        "messages": [
            {"role": "user", "content": prompt, "images": [img_b64]},
        ],
        "options": {"temperature": 0.1, "max_tokens": 2048},
        "stream": False,
    }

    r = requests.post(f"{OLLAMA_API}/api/chat", json=payload, timeout=timeout)
    r.raise_for_status()
    content = r.json().get("message", {}).get("content", "").strip()

    # 清理 think 标签
    if "</think>" in content:
        content = re.sub(r'<think>.*?</think>\s*', '', content, flags=re.DOTALL).strip()
    elif "<think>" in content:
        idx = content.index("<think>")
        end = content.find("</think>", idx)
        content = content[:idx] + (content[end + 8:] if end > 0 else "")

    return content


def _extract_json(text: str) -> dict[str, Any]:
    """从 VLM 回复中提取 JSON。"""
    if "```" in text:
        for part in text.split("```"):
            c = part.strip().removeprefix("json").strip()
            if c.startswith("{") and c.endswith("}"):
                return json.loads(c)
    # 直接解析
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start >= 0 and brace_end > brace_start:
        return json.loads(text[brace_start:brace_end + 1])
    raise ValueError("No JSON found in VLM response")


def _analyze_image(image_path: str) -> dict[str, Any]:
    """分析图片返回结构化描述。"""
    raw = _call_vlm(REVERSE_PROMPT, image_path)
    try:
        data = _extract_json(raw)
        data["available"] = True
        return data
    except (json.JSONDecodeError, ValueError) as e:
        return {
            "available": False,
            "error": str(e),
            "raw_response": raw[:500],
        }


# ── 反推 → SDXL/Flux/Anima 三种格式 ──

SDXL_PROMPT_TEMPLATE = """MASTERPIECE, best quality, ultra-detailed, 8k,
{subject},
{scene},
{composition}, {lighting},
{colors},
{style_tags},
professional artwork, highres, absurdres"""

FLUX_PROMPT_TEMPLATE = """{subject}, {scene}. {composition} with {lighting}. The scene features {colors} color palette. {extra_details}"""

ANIMA_PROMPT_TEMPLATE = """{subject}, {scene}. {composition}, {lighting} atmosphere, {colors} tones. {extra_details}. Anime style, detailed illustration."""


def reverse_prompt(
    image_path: str,
    targeted: str = "",
) -> dict[str, Any]:
    """反推图片的提示词。

    Args:
        image_path: 图片路径
        targeted: 针对性描述（可选），如 "同样的角色，换一身战斗服"

    Returns:
        {
            "sdxl": "SDXL 格式提示词",
            "flux": "Flux 格式提示词",
            "anima": "Anima 格式提示词",
            "analysis": {结构化分析结果},
            "available": True/False,
        }
    """
    if not Path(image_path).is_file():
        return {"available": False, "error": f"File not found: {image_path}"}

    analysis = _analyze_image(image_path)
    if not analysis.get("available"):
        return {"available": False, "error": analysis.get("error", "分析失败")}

    fmt = lambda x: x.replace("\n", ", ") if x else ""
    tags = ", ".join(analysis.get("style_tags", ["anime style"]))

    # 构建3种格式
    sdxl = SDXL_PROMPT_TEMPLATE.format(
        subject=fmt(analysis.get("subject", "")),
        scene=fmt(analysis.get("scene", "")),
        composition=fmt(analysis.get("composition", "")),
        lighting=fmt(analysis.get("lighting", "")),
        colors=fmt(analysis.get("colors", "")),
        style_tags=tags,
    )

    flux = FLUX_PROMPT_TEMPLATE.format(
        subject=analysis.get("subject", ""),
        scene=analysis.get("scene", ""),
        composition=analysis.get("composition", ""),
        lighting=analysis.get("lighting", ""),
        colors=analysis.get("colors", ""),
        extra_details=analysis.get("extra_details", ""),
    )

    anima = ANIMA_PROMPT_TEMPLATE.format(
        subject=analysis.get("subject", ""),
        scene=analysis.get("scene", ""),
        composition=analysis.get("composition", ""),
        lighting=analysis.get("lighting", ""),
        colors=analysis.get("colors", ""),
        extra_details=analysis.get("extra_details", ""),
    )

    # 如果有针对性描述，用文本 LLM 把该描述融合进去
    if targeted:
        merged = _merge_targeted(sdxl, flux, targeted, analysis)
        if merged.get("sdxl"):
            sdxl = merged["sdxl"]
        if merged.get("flux"):
            flux = merged["flux"]
        if merged.get("anima"):
            anima = merged["anima"]

    # 清理多余的空白
    sdxl = re.sub(r',\s*,', ',', sdxl).strip()
    sdxl = re.sub(r'\s{2,}', ' ', sdxl)

    return {
        "available": True,
        "sdxl": sdxl,
        "flux": flux.strip(),
        "anima": anima.strip(),
        "analysis": analysis,
    }


def _merge_targeted(
    sdxl_prompt: str, flux_prompt: str,
    targeted: str, analysis: dict[str, Any],
) -> dict[str, str]:
    """用文本 LLM 将针对性描述融合到提示词中。"""
    prompt = f"""Original SDXL prompt: {sdxl_prompt}
Original Flux prompt: {flux_prompt}

User request: {targeted}

Task: Modify BOTH prompts to incorporate the user's request while keeping the character's appearance consistent.
- SDXL format: comma-separated tags with MASTERPIECE, best quality
- Flux format: flowing natural language paragraph

Output:
SDXL: <modified sdxl prompt>
Flux: <modified flux prompt>"""

    payload = {
        "model": TEXT_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "options": {"temperature": 0.2, "max_tokens": 1024},
        "stream": False,
    }

    try:
        r = requests.post(f"{OLLAMA_API}/api/chat", json=payload, timeout=30)
        r.raise_for_status()
        content = r.json().get("message", {}).get("content", "").strip()

        sdxl_new = ""
        flux_new = ""
        for line in content.split("\n"):
            if line.startswith("SDXL:"):
                sdxl_new = line[5:].strip()
            elif line.startswith("Flux:"):
                flux_new = line[5:].strip()

        return {"sdxl": sdxl_new, "flux": flux_new, "anima": flux_new}
    except Exception:
        return {}
