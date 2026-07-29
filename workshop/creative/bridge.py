"""
创意知识桥接 — 将 popular_plots / character_design / fashion_depth /
background_depth 的知识注入到 prompt 引擎中。

用法:
    from workshop.creative.bridge import creative_enrich
    enriched = creative_enrich("校园樱花树下偶遇银发少女")
    # → "校园scene: 樱花树下, 校服, 夕阳, 银发少女(
"""

from __future__ import annotations

import re
import sys
from typing import Any

# 导入创意模块
from workshop.creative.popular_plots import PLOT_TEMPLATES
from workshop.creative.character_design import (
    CharacterArchetype,
    ARCHETYPES,
)

# ── 情节匹配 ──

# 关键词→情节模板映射
PLOT_KEYWORDS: dict[str, str] = {
    # 校园类
    "校园": "樱花树下的偶遇",
    "教室": "樱花树下的偶遇",
    "校服": "樱花树下的偶遇",
    "同桌": "樱花树下的偶遇",
    "学姐": "校园屋顶的约定",
    "学妹": "校园屋顶的约定",
    "放学后": "校园屋顶的约定",
    "天台": "校园屋顶的约定",
    "告白": "祭典之夜的告白",
    "祭典": "祭典之夜的告白",
    "夏祭": "祭典之夜的告白",
    "花火": "祭典之夜的告白",
    # 治愈类
    "治愈": "雨天的花店",
    "花店": "雨天的花店",
    "下雨": "雨天的花店",
    "咖啡馆": "街角的温暖",
    "咖啡": "街角的温暖",
    # 奇幻/战斗
    "战斗": "黄昏的决战",
    "决斗": "黄昏的决战",
    "魔法": "魔法少女变身",
    "变身": "魔法少女变身",
    "魔女": "魔法少女变身",
    "异世界": "魔王的邀请",
    "魔王": "魔王的邀请",
    # 悬疑
    "悬疑": "镜像迷宫",
    "侦探": "镜像迷宫",
    "迷宫": "镜像迷宫",
    "推理": "镜像迷宫",
    # 温馨
    "日常": "街角的温暖",
    "温馨": "雨天的花店",
}


def match_plot_template(nl_text: str) -> dict[str, Any] | None:
    """匹配自然语言描述到情节模板。"""
    text_lower = nl_text.lower()
    best_match = None
    best_score = 0

    for keyword, plot_name in PLOT_KEYWORDS.items():
        if keyword.lower() in text_lower:
            score = len(keyword)  # 越长关键词越精确
            if plot_name in PLOT_TEMPLATES:
                if score > best_score:
                    best_score = score
                    best_match = PLOT_TEMPLATES[plot_name]

    if best_match:
        return {
            "plot_name": best_match.name,
            "genre": best_match.genre,
            "summary": best_match.summary,
            "scenes": best_match.scenes,
            "panel_count": best_match.panel_count,
            "arcs": best_match.arcs,
            "characters": best_match.characters,
            "beats": best_match.beats,
        }
    return None


# ── 角色 archetype 匹配 ──

CHARACTER_ARCHETYPES = ARCHETYPES  # dict[str, CharacterArchetype]

ARCHETYPE_KEYWORDS: dict[str, str] = {
    "傲娇": "Tsundere",
    "ツンデレ": "Tsundere",
    "无口": "Kuudere",
    "冷酷": "Kuudere",
    "病娇": "Yandere",
    "病嬌": "Yandere",
    "妹系": "Imouto",
    "妹": "Imouto",
    "姐姐": "Onee-san",
    "姐系": "Onee-san",
    "青梅竹马": "Childhood Friend",
    "幼馴染": "Childhood Friend",
    "魔法少女": "Magical Girl",
    "天然呆": "Airhead",
    "元气": "Genki",
    "活泼": "Genki",
    "猫娘": "Catgirl / Nekomimi",
    "兽耳": "Catgirl / Nekomimi",
}


def match_character_archetype(nl_text: str) -> dict[str, Any] | None:
    """匹配自然语言中的角色类型词，返回视觉设计指导。"""
    text_lower = nl_text.lower()
    for keyword, en_name in ARCHETYPE_KEYWORDS.items():
        if keyword.lower() in text_lower:
            return {
                "archetype_name": keyword,
                "archetype_en": en_name,
            }
    return None


# ── 主桥接函数 ──


def creative_enrich(
    nl_text: str,
    *,
    style_hint: str | None = None,
) -> dict[str, Any]:
    """分析 NL 描述，返回创意知识增强信息。

    Returns:
        {
            "plot": {...} | None,        # 匹配到的情节模板
            "character_archetype": {...} | None,
            "scene_hints": [...],         # 场景提示词
            "prompt_additions": str,     # 可直接追加到 prompt 的英文文本
            "enriched": bool,            # 是否有增强
        }
    """
    plot = match_plot_template(nl_text)
    archetype = match_character_archetype(nl_text)

    additions = []
    scene_hints = []
    enriched = False

    if plot:
        enriched = True
        scene_hints = plot.get("scenes", [])
        # 从 beats 提取场景描述和镜头指示
        for beat in plot.get("beats", [])[:3]:
            cam = beat.get("camera", "")
            scene = beat.get("scene", "")
            emotion = beat.get("emotion", "")
            if cam:
                additions.append(cam)
            if scene:
                scene_hints.append(scene)

    if archetype:
        enriched = True
        en_name = archetype.get("archetype_en", "")
        if en_name:
            additions.append(f"{en_name} personality, {archetype.get('archetype_name', '')}")

    # 组合 prompt 增强片段
    prompt_additions = ""
    if additions:
        prompt_additions = ", ".join(additions)

    return {
        "plot": plot,
        "character_archetype": archetype,
        "scene_hints": scene_hints,
        "prompt_additions": prompt_additions,
        "enriched": enriched,
    }
