"""
模型管理 — 扫描本地模型，为 planner 提供可用资源信息。

用法:
    from workshop.engine.models import scan_available, recommend
    available = scan_available()
    rec = recommend("爱蜜莉雅，精细插画")
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# ── 模型类型分组 ──

CHECKPOINT_DIRS = {"checkpoints", "diffusion_models", "unet"}
LORA_DIRS = {"loras"}
IPADAPTER_DIRS = {"ipadapter"}
UPSCALE_DIRS = {"upscale_models"}
CLIP_DIRS = {"clip", "text_encoders"}
VAE_DIRS = {"vae", "vae_approx"}
CONTROLNET_DIRS = {"controlnet"}

# Flux 模型识别（文件名关键词）
FLUX_KEYWORDS = ["flux", "flux2"]
SDXL_KEYWORDS = ["sdxl", "illustrious", "animagine", "pony"]


def scan_available() -> dict[str, list[dict[str, Any]]]:
    """扫描 ComfyUI models/ 下所有模型，按类型分组。

    Returns:
        {
            "checkpoints": [{"name": ..., "path": ..., "size_mb": ..., "type": "flux"|"sdxl"|"sd15"}],
            "loras": [...],
            "ipadapter": [...],
            "upscale": [...],
        }
    """
    try:
        from agents.model_manager import _scan_models
    except ImportError:
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agents"))
        from agents.model_manager import _scan_models

    all_models = _scan_models()
    result: dict[str, list[dict[str, Any]]] = {
        "checkpoints": [],
        "loras": [],
        "ipadapter": [],
        "upscale": [],
        "clip": [],
        "vae": [],
        "controlnet": [],
        "other": [],
    }

    for m in all_models:
        subdir = m.get("subdir", "")
        cat = m.get("category", "other")
        name = m.get("name", "")

        # 判断引擎类型
        name_lower = name.lower()
        if any(k in name_lower for k in FLUX_KEYWORDS):
            engine = "flux"
        elif any(k in name_lower for k in SDXL_KEYWORDS):
            engine = "sdxl"
        else:
            engine = "sd15" if cat == "checkpoint" else "unknown"

        entry = {
            "name": name,
            "path": m.get("path", ""),
            "size_mb": m.get("size_mb", 0),
            "modified": m.get("modified", ""),
            "engine": engine,
            "subdir": subdir,
        }

        if subdir in CHECKPOINT_DIRS:
            result["checkpoints"].append(entry)
        elif subdir in LORA_DIRS:
            result["loras"].append(entry)
        elif subdir in IPADAPTER_DIRS:
            result["ipadapter"].append(entry)
        elif subdir in UPSCALE_DIRS:
            result["upscale"].append(entry)
        elif subdir in CLIP_DIRS:
            result["clip"].append(entry)
        elif subdir in VAE_DIRS:
            result["vae"].append(entry)
        elif subdir in CONTROLNET_DIRS:
            result["controlnet"].append(entry)
        else:
            result["other"].append(entry)

    return result


def print_model_list(available: dict[str, list[dict[str, Any]]] | None = None) -> None:
    """打印模型列表到终端。"""
    if available is None:
        available = scan_available()

    print("📦 可用模型:\n")

    ckpts = available.get("checkpoints", [])
    if ckpts:
        print("  SDXL 底模:" if any(m["engine"] == "sdxl" for m in ckpts) else "  底模:")
        for m in ckpts:
            engine_tag = f"[{m['engine'].upper()}]" if m["engine"] != "unknown" else ""
            rec = " ← 推荐" if m["engine"] == "sdxl" else ""
            print(f"    ✅ {m['name']}  ({m['size_mb']:.0f}MB) {engine_tag}{rec}")

    loras = available.get("loras", [])
    if loras:
        print("\n  LoRA:")
        for m in loras:
            engine_tag = f"[{m['engine'].upper()}]" if m["engine"] != "unknown" else ""
            print(f"    🔗 {m['name']}  ({m['size_mb']:.0f}MB) {engine_tag}")

    ipas = available.get("ipadapter", [])
    if ipas:
        print("\n  IPAdapter:")
        for m in ipas:
            compat = ""
            if "flux" in m["name"].lower():
                compat = " (⚠️ 不兼容 Flux.2)"
            elif "sdxl" in m["name"].lower():
                compat = " (SDXL)"
            print(f"    🧩 {m['name']}  ({m['size_mb']:.0f}MB){compat}")

    us = available.get("upscale", [])
    if us:
        print("\n  Upscale:")
        for m in us:
            print(f"    🔍 {m['name']}  ({m['size_mb']:.0f}MB)")

    total = sum(len(v) for v in available.values())
    print(f"\n  共 {total} 个模型文件")


def recommend(
    nl_text: str = "",
    *,
    engine_pref: str | None = None,
    available: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """根据用户描述推荐最佳模型方案。

    Args:
        nl_text: 用户描述
        engine_pref: 引擎偏好 (flux/sdxl/None)
        available: 模型列表（自动扫描如果为 None）

    Returns:
        {"engine": "sdxl"|"flux", "checkpoint": "...", "lora": ..., "ipadapter": ..., "reason": "..."}
    """
    if available is None:
        available = scan_available()

    ckpts = available.get("checkpoints", [])
    loras = available.get("loras", [])
    ipas = available.get("ipadapter", [])
    text_lower = nl_text.lower()

    # 引擎选择
    engine = engine_pref or "sdxl"  # 默认 SDXL（更快，支持 FaceDetailer）
    if not any(m["engine"] == engine for m in ckpts):
        # 如果首选引擎没有对应底模，尝试另一个
        alt = "flux" if engine == "sdxl" else "sdxl"
        if any(m["engine"] == alt for m in ckpts):
            engine = alt

    # 找最佳底模
    checkpoint = None
    for m in ckpts:
        if m["engine"] == engine:
            checkpoint = m["name"]
            break
    if not checkpoint and ckpts:
        checkpoint = ckpts[0]["name"]

    # LoRA 推荐（匹配角色名）
    matched_lora = None
    for m in loras:
        m_lower = m["name"].lower()
        # 检查是否有角色名匹配
        for keyword in ["emilia", "爱蜜莉雅", "エミリア", "rem", "蕾姆", "レム",
                        "ram", "拉姆", "ラム", "knives"]:
            if keyword in m_lower or keyword in text_lower:
                matched_lora = {"name": m["name"], "strength": 0.8}
                break
        if matched_lora:
            break

    # IPAdapter 推荐
    matched_ipa = None
    for m in ipas:
        if engine == "sdxl" and "sdxl" in m["name"].lower():
            matched_ipa = m["name"]
            break
        elif engine == "flux" and "flux" in m["name"].lower():
            # Flux IPAdapter 不兼容 Flux.2，备注
            matched_ipa = None
            break

    reason = f"推荐 {engine.upper()}"
    if checkpoint:
        reason += f" + {checkpoint}"
    if matched_lora:
        reason += f" + LoRA({matched_lora['name']})"
    if matched_ipa:
        reason += f" + IPAdapter"

    return {
        "engine": engine,
        "checkpoint": checkpoint,
        "lora": matched_lora,
        "ipadapter": matched_ipa,
        "reason": reason,
    }
