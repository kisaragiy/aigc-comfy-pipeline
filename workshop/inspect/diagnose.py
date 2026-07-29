"""失败诊断 — 区分 prompt 问题 vs workflow 问题 vs 质量不足。

质检不通过时，自动判断根因：

- **prompt 问题**：图能看但不对题（内容/构图/角色不对）
- **workflow 问题**：图有严重 artifact（崩色/崩结构/重复纹理/模型不兼容）
- **质量不足**：图基本对但模糊/细节差/平庸
"""
from __future__ import annotations

import re
from typing import Any


def diagnose(
    inspect_result: dict[str, Any],
    *,
    prompt: str = "",
    model_name: str = "",
    upscale_factor: float = 1.0,
    face_detailer_used: bool = False,
) -> dict[str, Any]:
    """分析质检结果，判断失败原因。

    Args:
        inspect_result: inspector.inspect_image() 的返回
        prompt: 生成时使用的 prompt
        model_name: 使用的底模
        upscale_factor: 放大倍数（1.0 = 未放大）
        face_detailer_used: 是否启用了 FaceDetailer

    Returns:
        {
            "root_cause": "prompt" | "workflow" | "quality" | "unknown",
            "confidence": 0.0~1.0,
            "details": ["问题1", "问题2", ...],
            "suggestion": "建议..."
        }
    """
    parts = inspect_result.get("parts", {})
    scores = inspect_result.get("scores", {})
    status = inspect_result.get("status", "issues_found")

    clues: list[str] = []
    issues: list[str] = []

    # ── 1. 检查 workflow 级别的问题 ──
    # 严重崩脸 + 全身只有1张脸检测到 = workflow 问题
    face_info = parts.get("脸", {})
    if face_info.get("status") == "崩了" and face_info.get("count", 1) == 1:
        if face_info.get("confidence", 1.0) < 0.3:
            clues.append("face_detection_very_low")
            issues.append("脸检测置信度极低（<0.3），模型可能不兼容")

    # 手部异常计数（0只手或 >4 只手往往是 workflow 问题）
    hand_info = parts.get("手", {})
    hand_count = hand_info.get("count", -1)
    if hand_count == 0:
        clues.append("zero_hands")
        issues.append("没检测到任何手部，可能是模型生成了崩手或画面不对")
    elif hand_count is not None and hand_count > 4:
        clues.append("extra_hands")
        issues.append(f"检测到 {hand_count} 只手，明显异常")

    # 极度模糊 → 可能 workflow 参数不对
    blur_info = parts.get("模糊", {})
    lap_var = blur_info.get("laplacian_var", 0)
    if lap_var > 0 and lap_var < 2.0:
        clues.append("extreme_blur")
        issues.append(f"极度模糊（Laplacian={lap_var:.1f}），可能是 model/VAE 不兼容")
    elif lap_var > 0 and lap_var < 5.0:
        clues.append("blurry")
        issues.append(f"模糊（Laplacian={lap_var:.1f}），可能是 upscale 参数或去噪强度不对")

    # ── 2. 检查 prompt 级别的问题 ──
    prompt_lower = prompt.lower()

    # 检查 prompt 关键词是否匹配（简单的关键词存在性检查）
    prompt_keywords = _extract_keywords(prompt_lower)
    missing_keywords = _check_missing_keywords(prompt_keywords, parts)

    if missing_keywords:
        clues.append("prompt_keyword_missing")
        for kw in missing_keywords[:3]:
            issues.append(f"prompt 中提到的「{kw}」在图上未检测到对应特征")

    # 综合分数低但没有严重 artifact → prompt 问题
    total_score = scores.get("总评", scores.get("overall", 0))
    if total_score > 0 and total_score < 0.4 and "extreme_blur" not in clues:
        clues.append("low_score_no_artifact")
        issues.append("综合分低但无明显 artifact，可能是 prompt 描述不准确或风格不匹配")

    # ── 3. 判断根因 ──
    workflow_weight = len([c for c in clues if c in (
        "face_detection_very_low", "zero_hands", "extra_hands", "extreme_blur")])
    prompt_weight = len([c for c in clues if c in ("prompt_keyword_missing", "low_score_no_artifact")])
    quality_weight = len([c for c in clues if c == "blurry"])

    if workflow_weight > prompt_weight and workflow_weight > quality_weight:
        root_cause = "workflow"
        confidence = min(0.5 + 0.15 * workflow_weight, 0.95)
        suggestion = _suggest_workflow(model_name, face_detailer_used, clues)
    elif prompt_weight >= workflow_weight and prompt_weight >= quality_weight:
        root_cause = "prompt"
        confidence = min(0.5 + 0.15 * prompt_weight, 0.9)
        suggestion = _suggest_prompt(prompt, clues)
    elif quality_weight > 0:
        root_cause = "quality"
        confidence = 0.5 + 0.1 * quality_weight
        suggestion = _suggest_quality(upscale_factor, clues)
    else:
        root_cause = "unknown"
        confidence = 0.3
        suggestion = "无法确定根因，建议检查 prompt、模型和参数"

    return {
        "root_cause": root_cause,
        "confidence": round(confidence, 2),
        "details": issues,
        "suggestion": suggestion,
    }


# ── 内部函数 ──

_COMMON_KEYWORDS = {
    "face": ["face", "portrait", "headshot", "close-up"],
    "hand": ["hand", "hand", "holding", "clutching", "grasp"],
    "full_body": ["full body", "standing", "fullbody", "全身"],
    "anime": ["anime", "illustration", "artwork", "manga", "2d"],
    "realistic": ["photorealistic", "photograph", "realistic", "cinematic"],
}


def _extract_keywords(text: str) -> dict[str, str]:
    """从 prompt 中提取每组关键词。"""
    result: dict[str, str] = {}
    for category, keywords in _COMMON_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                result[category] = kw
                break
    return result


def _check_missing_keywords(
    prompt_keywords: dict[str, str],
    parts: dict[str, Any],
) -> list[str]:
    """检查 prompt 关键词是否在检测结果中有对应。"""
    missing = []

    if "face" in prompt_keywords or "portrait" in prompt_keywords:
        face = parts.get("脸", {})
        if face.get("count", 0) == 0 and face.get("status") != "unknown":
            missing.append("脸/肖像")

    if "hand" in prompt_keywords:
        hand = parts.get("手", {})
        if hand.get("count", 0) == 0:
            missing.append("手部")

    return missing


def _suggest_workflow(
    model_name: str,
    face_detailer_used: bool,
    clues: list[str],
) -> str:
    parts: list[str] = []
    if "extreme_blur" in clues:
        parts.append("试试换 VAE 或调低 denoise")
    if "face_detection_very_low" in clues:
        parts.append("模型与当前检测器不兼容，试试不用 FaceDetailer 或换底模")
    if not face_detailer_used:
        parts.append("启用 --face-detailer 试试")
    if "zero_hands" in clues or "extra_hands" in clues:
        parts.append("手部异常频繁，试试在 prompt 加「perfect hands」或换模型")
    return "；".join(parts) if parts else "检查 workflow 参数（steps/CFG/denoise）"


def _suggest_prompt(prompt: str, clues: list[str]) -> str:
    parts: list[str] = []
    if "prompt_keyword_missing" in clues:
        parts.append("增加更多视觉描述词（材质/颜色/姿态），不只是概念词")
    if "low_score_no_artifact" in clues:
        parts.append("尝试不同 prompt 风格或加质量词（masterpiece, best quality）")
    parts.append("尝试用 workshop engine 自动优化 prompt")
    return "；".join(parts)


def _suggest_quality(upscale_factor: float, clues: list[str]) -> str:
    parts: list[str] = []
    if "blurry" in clues:
        if upscale_factor <= 1.0:
            parts.append("试试 --upscale 2 放大后出图更锐利")
        parts.append("调高 steps 或换 sampler")
    return "；".join(parts) if parts else "试试 premium 质量预设"
