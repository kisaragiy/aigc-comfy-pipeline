"""
模型兼容性检查器 + 结果记录器。
在提交 ComfyUI workflow 前自动检查，避免浪费时间和 GPU。

用法:
    from model_compat import check_workflow_compat, CompatReport
    report = check_workflow_compat(checkpoint="waiIllustriousSDXL_v160", lora="knives_sdxl")
    if not report.valid:
        print(report.message)  # 提前报错，不提交

    # 出图后记录结果
    from model_compat import record_recipe
    record_recipe(name="My Recipe", scores={"face": 0.85, "hand": 0.9}, ...)
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# registry 路径
_HERE = Path(__file__).resolve().parent
_REGISTRY_PATH = (_HERE / ".." / "workshop" / "models" / "registry.json").resolve()
_KNOWLEDGE_PATH = (_HERE / ".." / "workshop" / "models" / "knowledge.md").resolve()


# ─────────────────────────────────────────────
# 兼容性检查
# ─────────────────────────────────────────────

class CompatReport:
    """兼容性检查报告"""
    def __init__(self):
        self.valid: bool = True
        self.message: str = ""
        self.checks: list[dict] = []

    def fail(self, msg: str):
        self.valid = False
        self.message += f"❌ {msg}\n"
        self.checks.append({"status": "fail", "message": msg})

    def warn(self, msg: str):
        self.message += f"⚠️ {msg}\n"
        self.checks.append({"status": "warn", "message": msg})

    def ok(self, msg: str):
        self.checks.append({"status": "ok", "message": msg})


def _load_registry() -> dict:
    """加载 registry.json"""
    if not _REGISTRY_PATH.is_file():
        return {"models": {}, "compatibility_rules": []}
    try:
        with open(str(_REGISTRY_PATH), encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"models": {}, "compatibility_rules": []}


def _model_key(name: str) -> str | None:
    """根据文件名/模型名找到 registry 中的 key。"""
    registry = _load_registry()
    models = registry.get("models", {})

    # 1. 精确匹配 key
    if name in models:
        return name

    # 2. 根据文件名匹配
    for key, info in models.items():
        if "path" in info and info["path"].endswith(name):
            return key
        if "path" in info and name in info["path"]:
            return key

    return None


def _get_model(name: str) -> dict:
    """获取模型信息（格式化后便于比较）。"""
    models = _load_registry().get("models", {})
    key = _model_key(name)
    if key and key in models:
        return {"key": key, **models[key]}
    # 未注册的模型——尝试根据文件名推断 base
    base = _infer_base_from_name(name)
    return {"key": name, "base": base, "type": "unknown", "notes": "未在registry中的模型"}


def _infer_base_from_name(name: str) -> str:
    """从文件名推断 base 系列。"""
    low = name.lower()
    if "sdxl" in low or "illustrious" in low or "xl" in low:
        return "sdxl"
    if "sd15" in low or "sd_1.5" in low or "sd1.5" in low:
        return "sd15"
    if "flux" in low or "klein" in low:
        return "flux"
    if "anima" in low:
        return "unknown"
    return "unknown"


def check_workflow_compat(
    checkpoint: str | None = None,
    lora: str | None = None,
    vae: str | None = None,
    controlnet: str | None = None,
    ipadapter: str | None = None,
    clip_vision: str | None = None,
    instantid: str | None = None,
    face_detailer: bool = False,
    workflow: str | None = None,
    denoise: float = 1.0,
    **kwargs,
) -> CompatReport:
    """
    检查一组模型/参数是否兼容。
    在提交 ComfyUI 前调用，所有参数都是文件名或布尔值。

    Returns:
        CompatReport: 含 valid 布尔值和 message 详情
    """
    report = CompatReport()

    if not checkpoint:
        report.warn("未指定 checkpoint，跳过兼容性检查")
        return report

    checkpoint_info = _get_model(checkpoint)
    ckpt_base = checkpoint_info.get("base", "unknown")

    if ckpt_base == "unknown":
        report.warn(f"checkpoint '{checkpoint}' 的 base 未知，无法全面检查兼容性")
        return report

    report.ok(f"checkpoint: {checkpoint_info.get('key', checkpoint)} (base={ckpt_base})")

    # ── LoRA 检查 ──
    if lora:
        lora_info = _get_model(lora)
        lora_base = lora_info.get("base", _infer_base_from_name(str(lora)))
        if lora_base != ckpt_base:
            report.fail(
                f"LoRA '{lora}' (base={lora_base}) 与 checkpoint (base={ckpt_base}) 不兼容。"
                f" {ckpt_base} checkpoint 需要 {ckpt_base} LoRA。"
            )
        else:
            report.ok(f"LoRA '{lora}' base={lora_base} ✓")

        # 检查 LoRA 是否在兼容列表中
        compat_loras = checkpoint_info.get("compatible_loras", [])
        if compat_loras and lora_base not in compat_loras:
            report.warn(
                f"checkpoint '{checkpoint}' 兼容的 LoRA 系列为 {compat_loras}，"
                f"但传入的 LoRA base 为 {lora_base}（可能仍可用但未经测试）"
            )

    # ── VAE 检查 ──
    if vae:
        vae_info = _get_model(vae)
        vae_base = vae_info.get("base", _infer_base_from_name(str(vae)))
        if vae_base != ckpt_base:
            report.fail(
                f"VAE '{vae}' (base={vae_base}) 与 checkpoint (base={ckpt_base}) 不兼容。"
                f" 例如 Flux VAE 不能用于 SDXL checkpoint。"
            )
        else:
            report.ok(f"VAE '{vae}' base={vae_base} ✓")

    # ── ControlNet 检查 ──
    if controlnet:
        cn_info = _get_model(controlnet)
        cn_base = cn_info.get("base", _infer_base_from_name(str(controlnet)))
        if ckpt_base == "flux":
            report.fail(
                f"Flux (base=flux) 不支持 ControlNet。ControlNet '{controlnet}' 不可用于 Flux。"
                f" Flux 用 ReferenceLatent 做视觉参考。"
            )
        elif cn_base != ckpt_base and cn_base not in ("any", "unknown"):
            report.fail(
                f"ControlNet '{controlnet}' (base={cn_base}) 与 checkpoint (base={ckpt_base}) 不兼容。"
            )
        else:
            report.ok(f"ControlNet '{controlnet}' ✓")

    # ── IP-Adapter 检查 ──
    if ipadapter:
        ip_info = _get_model(ipadapter)
        ip_base = ip_info.get("base", _infer_base_from_name(str(ipadapter)))
        if ckpt_base == "flux":
            report.fail(
                f"Flux (base=flux) 不支持 IP-Adapter。IP-Adapter '{ipadapter}' 不可用于 Flux。"
                f" 用 ReferenceLatent + Flux2KleinRefLatentController 代替。"
            )
        elif ip_base != ckpt_base:
            report.fail(
                f"IP-Adapter '{ipadapter}' (base={ip_base}) 与 checkpoint (base={ckpt_base}) 不兼容。"
            )
        else:
            report.ok(f"IP-Adapter '{ipadapter}' base={ip_base} ✓")

        # ── CLIP Vision 检查（IP-Adapter 需要对应 CLIP Vision）──
        requires_clip = ip_info.get("requires_clip_vision")
        if requires_clip:
            if clip_vision:
                cv_info = _get_model(clip_vision)
                cv_key = cv_info.get("key", "")
                # 检查 clip_vision 是否匹配
                expected_key = _model_key(requires_clip)
                if expected_key and cv_key != expected_key:
                    report.fail(
                        f"IP-Adapter '{ipadapter}' 需要 CLIP Vision '{requires_clip}'，"
                        f"但提供了 '{clip_vision}'。"
                        f" 不匹配的 CLIP Vision 会导致 CLIPVisionLoader 报 value_not_in_list 错误。"
                    )
                else:
                    report.ok(f"CLIP Vision '{clip_vision}' ✓ 匹配 IP-Adapter 要求")
            else:
                report.fail(
                    f"IP-Adapter '{ipadapter}' 需要 CLIP Vision '{requires_clip}'，但未提供。"
                    f" 必须用 CLIPVisionLoader 加载正确的 CLIP Vision 模型。"
                )

    # ── InstantID 检查 ──
    if instantid:
        id_info = _get_model(instantid)
        id_dim = id_info.get("dim")
        if id_dim and id_dim != 1280:
            report.fail(
                f"InstantID 模型 '{instantid}' (dim={id_dim}) 与 comfyui_instantid 节点硬编码 (dim=1280) 不兼容。"
                f" 会报 size mismatch 错误。请用 ip-adapter.bin (dim=1280)。"
            )
        else:
            report.ok(f"InstantID '{instantid}' dim check ✓")
        requires_insight = id_info.get("requires_insightface", False)
        if requires_insight and ckpt_base != "sdxl":
            report.warn(
                f"InstantID '{instantid}' 依赖 InsightFace 人脸检测，"
                f"对非真人照片（如动漫卡牌角色）会报 'No face detected'。"
            )

    # ── FaceDetailer 检查 ──
    if face_detailer and ckpt_base == "flux":
        report.warn(
            f"FaceDetailer + Flux 在 12GB VRAM 下可能 OOM（Flux 约 8-10GB + FaceDetailer 约 2GB）。"
            f" 如果 OOM 请关掉 FaceDetailer。"
        )

    # ── Denoise + latent_image 检查 ──
    if denoise < 1.0:
        if workflow != "img2img":
            report.warn(
                f"denoise={denoise}<1.0 时 KSampler 的 latent_image 必须来自 VAEEncode（img2img），"
                f"不能来自 EmptyLatentImage（txt2img）。否则 denoise 会被忽略（实际按 1.0 跑）。"
                f" 请确认 workflow 为 img2img。"
            )
        else:
            report.ok(f"denoise={denoise} + img2img workflow ✓")

    if report.valid:
        report.message = report.message or "✅ 所有兼容性检查通过"

    return report


# ─────────────────────────────────────────────
# 结果记录
# ─────────────────────────────────────────────

def record_recipe(
    *,
    name: str,
    checkpoint: str,
    character: str = "",
    lora: str | None = None,
    workflow: str = "standard",
    params: dict | None = None,
    ref_method: str | None = None,
    scores: dict | None = None,
    filenames: list[str] | None = None,
    status: str = "untested",
    failure_reason: str = "",
    notes: str = "",
) -> bool:
    """
    将试跑结果记录到 registry.json。

    Args:
        name: 配置名称（如 \"卡牌白发少女 - IP-Adapter v2\"）
        checkpoint: checkpoint 文件名
        character: 角色描述
        lora: LoRA 文件名（可选）
        workflow: 工作流类型（standard/premium/img2img/flux/...）
        params: 参数字典（steps/cfg/denoise/seed/ref_image 等）
        ref_method: 参考方法（ip-adapter-plus/ip-adapter-standard/reference-latent/instantid/none）
        scores: 评分字典（face_score_avg/hand_score/blur_score/aesthetic_score/pixel_count）
        filenames: 输出文件名列表
        status: 状态（success/failed/untested/partial）
        failure_reason: 失败原因（如 \"InsightFace未检测到动漫人脸\"）
        notes: 补充说明

    Returns:
        写入成功 True，失败 False
    """
    registry = _load_registry()
    if "recipes" not in registry:
        registry["recipes"] = []

    entry = {
        "name": name,
        "character": character,
        "checkpoint": checkpoint,
        "lora": lora,
        "workflow": workflow,
        "params": params or {},
        "ref_method": ref_method,
        "scores": scores or {},
        "filenames": filenames or [],
        "status": status,
        "failure_reason": failure_reason,
        "notes": notes,
        "recorded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    registry["recipes"].append(entry)

    try:
        with open(str(_REGISTRY_PATH), "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2, ensure_ascii=False)
        print(f"[model_compat] ✅ 已记录 recipe '{name}' 到 registry")
        return True
    except OSError as e:
        print(f"[model_compat] ❌ 写入 registry 失败: {e}")
        return False


def find_recipe(character: str) -> list[dict]:
    """按角色名称查找已有 recipe。"""
    registry = _load_registry()
    recipes = registry.get("recipes", [])
    low_target = character.lower()
    results = []
    for r in recipes:
        if low_target in r.get("character", "").lower() or low_target in r.get("name", "").lower():
            results.append(r)
    return results


def get_last_recipe(checkpoint: str = None) -> dict | None:
    """获取最近一次 recipe（可选按 checkpoint 过滤）。"""
    registry = _load_registry()
    recipes = registry.get("recipes", [])
    if checkpoint:
        recipes = [r for r in recipes if r.get("checkpoint") == checkpoint]
    if not recipes:
        return None
    return recipes[-1]


# ─────────────────────────────────────────────
# 便捷入口
# ─────────────────────────────────────────────

def print_registry_summary():
    """打印 registry 摘要。"""
    registry = _load_registry()
    models = registry.get("models", {})
    recipes = registry.get("recipes", [])

    print(f"📦 模型数: {len(models)}")
    print(f"📋 Recipe 数: {len(recipes)}")
    print()
    print("模型分类:")
    for key, info in sorted(models.items()):
        base = info.get("base", "?")
        mtype = info.get("type", "?")
        print(f"  [{base:>6}] [{mtype:>15}] {key}")

    if recipes:
        print()
        print("最近 recipe:")
        for r in recipes[-3:]:
            score_str = ""
            if r.get("scores"):
                s = r["scores"]
                scores_avg = [v for v in s.values() if isinstance(v, (int, float))]
                if scores_avg:
                    score_str = f" | 均分: {sum(scores_avg)/len(scores_avg):.2f}"
            status_icon = {"success": "✅", "failed": "❌", "untested": "⏳", "partial": "⚠️"}.get(r.get("status", ""), "❓")
            print(f"  {status_icon} {r.get('name', '?')}{score_str}")


# 如果直接运行，打印摘要
if __name__ == "__main__":
    print_registry_summary()
