"""
参考图入口 — 用户给参考图 + 自然语言 → 自动选控制方法。

不要求用户知道 IPAdapter / ReferenceLatent / InstantID 是什么。
自动分析参考图类型 → 输出最佳控制方法 + 参数。

用法:
    from workshop.engine.ref import plan_ref
    plan = plan_ref("refs/emilia.jpg", "爱蜜莉雅，半身像")
    # → {"method": "reference_latent", "weight": 0.8, "balance": 0.4, ...}
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def plan_ref(
    ref_path: str | Path | None,
    char_desc: str = "",
    model_type: str = "flux",
) -> dict[str, Any]:
    """自动选择参考图控制方法。

    选择逻辑：
    - Flux → reference_latent（Flux.2 原生，最稳定）
    - SDXL → ipadapter（需要 CLIPVision + IPAdapter 模型）
    - 无 ref → None

    Args:
        ref_path: 参考图路径（None=无参考图）
        char_desc: 角色描述（用于 Ollama 分析，可选）
        model_type: "flux" 或 "sdxl"

    Returns:
        dict {
            "method": str | None,        # "reference_latent" | "ipadapter" | None
            "enabled": bool,             # 是否启用参考
            "params": dict,              # 方法特定参数
            "char_desc": str,            # 分析后的角色描述
        }
    """
    if not ref_path:
        return {"method": None, "enabled": False, "params": {}, "char_desc": ""}

    ref_path = str(ref_path)
    if not Path(ref_path).is_file():
        return {"method": None, "enabled": False, "params": {}, "char_desc": ""}

    if model_type == "flux":
        return {
            "method": "reference_latent",
            "enabled": True,
            "params": {
                "ip_weight": 0.8,
                "ip_balance": 0.4,
            },
            "char_desc": char_desc,
        }

    if model_type == "sdxl":
        return {
            "method": "ipadapter",
            "enabled": True,
            "params": {
                "ip_weight": 0.7,
                "ip_balance": 0.5,
            },
            "char_desc": char_desc,
        }

    return {"method": None, "enabled": False, "params": {}, "char_desc": ""}


def detect_ref_focus(ref_path: str | Path) -> str:
    """分析参考图主体类型（启发式）。

    通过图片文件名和路径推断主体类型：
    - "portrait" / "face" / "head" → "portrait"
    - "full" / "stand" / "body" → "fullbody"
    - 默认 → "halfbody"

    Args:
        ref_path: 参考图路径

    Returns:
        "portrait" | "halfbody" | "fullbody"
    """
    name = Path(str(ref_path)).stem.lower()
    if any(k in name for k in ("portrait", "face", "head", "close")):
        return "portrait"
    if any(k in name for k in ("full", "stand", "body", "whole")):
        return "fullbody"
    return "halfbody"
