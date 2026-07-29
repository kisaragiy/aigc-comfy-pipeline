"""
自动填料核心 — 自然语言 → 结构化 plan。

用法:
    from workshop.engine.planner import plan_from_nl
    plan = plan_from_nl("爱蜜莉雅，半身像，精细插画")
    # → {scene: "portrait", workflow: "flux_portrait", tier: "premium",
    #    face_detailer: True, upscale: 1.5, ...}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from workshop.engine.ref import plan_ref

_REGISTRY: dict[str, Any] | None = None


def _load_registry() -> dict[str, Any]:
    """加载 workflows/registry.json。"""
    global _REGISTRY
    if _REGISTRY is not None:
        return _REGISTRY
    registry_path = Path(__file__).parent.parent / "workflows" / "registry.json"
    if registry_path.is_file():
        with open(registry_path, encoding="utf-8") as f:
            _REGISTRY = json.load(f)
    else:
        _REGISTRY = {}
    return _REGISTRY


def _detect_scene(nl_text: str) -> str:
    """从 NL 文本推断场景类型。

    关键词匹配：
    - "全身" / "立绘" / "站立" / "站立" → "fullbody"
    - "肖像" / "特写" / "人脸" / "面部" / "close" → "portrait"
    - "双人" / "多人" / "百合" / "互动" / "拥抱" → "multi_char"
    - "战斗" / "动作" / "动态" / "战斗" / "impact" → "action"
    - "表情" / "情绪" / "表情" / "微笑" / "哭" → "expression"
    - 默认 → "halfbody"
    """
    text = nl_text.lower()
    if any(k in text for k in ("全身", "立绘", "站立", "full body", "fullbody")):
        return "fullbody"
    if any(k in text for k in ("双人", "多人", "百合", "互动", "拥抱", "two ", "together")):
        return "multi_char"
    if any(k in text for k in ("肖像", "特写", "人脸", "面部", "portrait", "close-up", "closeup")):
        return "portrait"
    if any(k in text for k in ("战斗", "动作", "动态", "action", "fighting")):
        return "action"
    if any(k in text for k in ("表情", "情绪", "微笑", "哭", "expression")):
        return "expression"
    return "halfbody"


def _detect_tier(nl_text: str) -> str:
    """从 NL 文本推断质量等级。

    - "草稿" / "草图" / "快速" / "draft" → "bare"（快，低质）
    - "精细" / "插画" / "高质" / "premium" / "高质量" → "premium"（慢，高质）
    - 默认 → "standard"
    """
    text = nl_text.lower()
    if any(k in text for k in ("草稿", "草图", "快速", "draft", "sketch")):
        return "bare"
    if any(k in text for k in ("精细", "插画", "高质", "premium", "高质量", "高品質", "成品")):
        return "premium"
    return "standard"


def _extract_character(nl_text: str, char_desc: str = "") -> str:
    """从 NL 文本提取角色名（用于 LoRA 匹配）。

    简单的关键词匹配：
    - "emilia" / "爱蜜莉雅" / "エミリア" → "emilia"
    - "rem" / "蕾姆" / "レム" → "rem"
    - "ram" / "拉姆" / "ラム" → "ram"
    - 如果 char_desc 参数有值，优先用它
    """
    if char_desc:
        return char_desc
    text = nl_text.lower()
    if any(k in text for k in ("emilia", "爱蜜莉雅", "エミリア", "emilia", "emt")):
        return "emilia"
    if any(k in text for k in ("rem", "蕾姆", "レム")):
        return "rem"
    if any(k in text for k in ("ram", "拉姆", "ラム")):
        return "ram"
    return ""


def _match_lora(char_key: str) -> dict[str, Any] | None:
    """从 registry 的 lora_map 查 LoRA 配置。"""
    if not char_key:
        return None
    registry = _load_registry()
    lora_map = registry.get("lora_map", {})
    if char_key in lora_map:
        return dict(lora_map[char_key])
    # 模糊匹配
    ck = char_key.lower()
    for key, config in lora_map.items():
        if ck in key or key in ck:
            return dict(config)
    return None


def plan_from_nl(
    nl_text: str,
    *,
    ref_path: str | None = None,
    char_desc: str = "",
    model_type: str = "flux",
    tier_override: str | None = None,
    scene_override: str | None = None,
) -> dict[str, Any]:
    """自然语言描述 → 完整生成计划。

    Args:
        nl_text: 用户描述（如 "爱蜜莉雅，半身像，精细插画"）
        ref_path: 参考图路径（可选）
        char_desc: 角色描述（可选，覆盖 NL 推断）
        model_type: "flux" (默认) 或 "sdxl"
        tier_override: 强制指定质量等级
        scene_override: 强制指定场景类型

    Returns:
        plan dict 包含 create_from_nl 所需全部参数
    """
    # 0. 扫描本地可用模型
    try:
        from workshop.engine.models import scan_available
        _available = scan_available()
    except Exception:
        _available = None

    _local_ckpts = []
    _local_loras = []
    if _available:
        _local_ckpts = [m["name"].lower() for m in _available.get("checkpoints", [])]
        _local_loras = [m["name"].lower() for m in _available.get("loras", [])]

    # 引擎选择：premium tier 优先 SDXL（支持 FaceDetailer），否则按默认
    _has_flux = any("flux" in n for n in _local_ckpts)
    _has_sdxl = any("sdxl" in n or "illustrious" in n for n in _local_ckpts)
    tier = tier_override or _detect_tier(nl_text)
    if model_type == "flux" and not _has_flux and _has_sdxl:
        model_type = "sdxl"
    elif model_type == "sdxl" and not _has_sdxl and _has_flux:
        model_type = "flux"
    elif _has_sdxl and tier == "premium":
        model_type = "sdxl"  # premium 用 SDXL（+FaceDetailer+Upscale 可行）
    elif _has_flux and not _has_sdxl:
        model_type = "flux"

    # 1. 推断场景和等级
    scene = scene_override or _detect_scene(nl_text)
    tier = tier_override or _detect_tier(nl_text)

    # 2. 从 registry 查 workflow 参数
    registry = _load_registry()
    scenes_config = registry.get("scenes", {})
    scene_config = scenes_config.get(scene)
    plan: dict[str, Any] = {
        "scene": scene,
        "tier": tier,
        "nl_text": nl_text,
    }

    if scene_config:
        model_configs = scene_config.get("models", {})
        model_cfg = model_configs.get(model_type, {})
        tier_cfg = model_cfg.get(tier) or model_cfg.get("standard") or {}

        plan.update({
            "preset": tier_cfg.get("workflow", "flux_general"),
            "face_detailer": tier_cfg.get("face_detailer", False),
            "hand_refiner": tier_cfg.get("hand_refiner", False),
            "upscale": tier_cfg.get("upscale", 1.0),
            "steps": tier_cfg.get("steps", 20),
            "cfg": tier_cfg.get("cfg", 2.0),
            "width": tier_cfg.get("width", 1024),
            "height": tier_cfg.get("height", 1024),
        })

        # 如果没有匹配到 tier，降级到 standard
        if tier not in model_cfg:
            plan["tier"] = "standard"
            fallback = model_cfg.get("standard", {})
            plan.update({
                "preset": fallback.get("workflow", plan["preset"]),
                "face_detailer": fallback.get("face_detailer", plan["face_detailer"]),
                "upscale": fallback.get("upscale", plan["upscale"]),
                "steps": fallback.get("steps", plan["steps"]),
                "cfg": fallback.get("cfg", plan["cfg"]),
            })
    else:
        # 场景不在 registry 中，用默认值
        plan.update({
            "preset": "flux_general",
            "face_detailer": tier == "premium",
            "upscale": 1.5 if tier == "premium" else 1.0,
            "steps": 28 if tier == "premium" else 20,
            "cfg": 2.0,
            "width": 1024,
            "height": 1024,
        })

    # 3. 参考图路由
    ref_plan = plan_ref(ref_path, char_desc or nl_text, model_type)
    plan.update({
        "ref_path": ref_path,
        "ref_method": ref_plan["method"],
        "ip_weight": ref_plan["params"].get("ip_weight", 0.7),
        "ip_balance": ref_plan["params"].get("ip_balance", 0.5),
    })

    # 4. LoRA 匹配（仅推荐本地实有的 LoRA）
    char_key = _extract_character(nl_text, char_desc)
    lora_config = _match_lora(char_key)
    if lora_config:
        lora_file = lora_config["file"]
        # 检查本地是否有这个 LoRA 文件
        lora_exists = any(lora_file.lower() in n for n in _local_loras)
        if not lora_exists:
            # 模糊匹配：从本地 LoRA 列表找文件名中包含角色名的
            local_match = None
            for ln in _local_loras:
                if char_key and char_key.lower() in ln:
                    local_match = ln
                    break
            if local_match:
                plan["lora_name"] = local_match
                plan["lora_strength"] = lora_config.get("strength", 0.8)
            else:
                plan["lora_name"] = None
                plan["lora_strength"] = 1.0
        else:
            plan["lora_name"] = lora_config["file"]
            plan["lora_strength"] = lora_config.get("strength", 0.8)
    else:
        plan["lora_name"] = None
        plan["lora_strength"] = 1.0

    # 5. 模型类型 + 显存/耗时预估
    plan["model_type"] = model_type
    plan["ref_method"] = registry.get("ref_methods", {}).get(model_type, "reference_latent")

    # 显存/耗时预估（基于 registry 记录 + 引擎类型）
    tier = plan.get("tier", "standard")
    if model_type == "sdxl":
        base_vram = 6.1
        if plan.get("face_detailer"):
            base_vram += 0.6
        if plan.get("upscale", 1.0) > 1.0:
            base_vram += 0.3
        if plan.get("lora_name"):
            base_vram += 0.1
        if plan.get("ip_weight", 0) > 0:
            base_vram += 0.8
        time_per_img = 10 if tier == "bare" else 15 if tier == "standard" else 25
    else:  # flux
        base_vram = 9.5
        if plan.get("face_detailer"):
            base_vram += 2.0  # YOLO + inpainting
        if plan.get("upscale", 1.0) > 1.0:
            base_vram += 0.5
        time_per_img = 60 if tier == "bare" else 120 if tier == "standard" else 300

    plan["vram_gb"] = round(base_vram, 1)
    plan["vram_available"] = 12.0
    plan["time_sec_per_img"] = time_per_img

    return plan
