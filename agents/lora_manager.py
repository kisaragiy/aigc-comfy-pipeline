"""
LoRA 管理器 — 统一的 LoRA 元数据、兼容检查、叠加策略。

覆盖 6 大缺口：
  1. LoRA 类型记录 (lora_type)
  2. Block Weight 调节
  3. 底模兼容检查
  4. 多 LoRA 叠加策略
  5. Caption 风格记录
  6. 验证快照
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# ── 数据类型 ──────────────────────────────────────────

@dataclass
class LoraInfo:
    """单个 LoRA 的完整元数据"""
    name: str                         # 文件名（不含路径）
    path: str                         # 相对路径，如 "loras/knives_sdxl.safetensors"
    lora_type: str = "lora"           # lora / locon / loha / lokr
    base_model: str = "sdxl"          # sdxl / sdxl-pony / sdxl-illustrious / sdxl-noobai / flux1 / flux2-klein
    caption_format: str = "tags"      # tags / natural / hybrid / pony
    trigger_word: str = ""            # 触发词（如有记录）
    strength_default: float = 0.8     # 推荐强度
    block_weights: str = ""           # 推荐 block weights（逗号分隔 22 个值）
    best_checkpoint: str = ""         # 效果最好的 checkpoint 文件名
    best_score: float = 0.0           # 最佳 checkpiont 的 VLM 评分
    best_image: str = ""              # 效果图路径（相对输出目录）
    notes: str = ""                   # 备注

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LoraStackTemplate:
    """多 LoRA 叠加模板"""
    name: str                         # 模板名
    items: list[dict] = field(default_factory=list)  # [{name, weight, block_weights?}]
    description: str = ""


# ── 配置 ──────────────────────────────────────────────

LORA_DIR = "C:/DrawingLive/ComfyUI/models/loras"
REGISTRY_PATH = Path(__file__).parent.parent / "workshop" / "models" / "lora_registry.json"

# 如果 registry 不存在，创建默认
_DEFAULT_REGISTRY: dict[str, Any] = {
    "version": "1.0",
    "updated": "2026-07-17",
    "loras": {},
    "stack_templates": {},
}


# ── 加载 / 保存 Registry ─────────────────────────────────

def _load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return dict(_DEFAULT_REGISTRY)
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULT_REGISTRY)


def _save_registry(reg: dict[str, Any]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(
        json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── 1. LoRA 类型记录 ──────────────────────────────────────

def get_lora_info(lora_name: str) -> LoraInfo | None:
    """从 registry 读取 LoRA 元数据。"""
    reg = _load_registry()
    raw = reg.get("loras", {}).get(lora_name)
    if raw is None:
        return None
    return LoraInfo(name=lora_name, **raw)


def set_lora_info(lora_name: str, info: LoraInfo) -> None:
    """保存 LoRA 元数据到 registry。"""
    reg = _load_registry()
    reg.setdefault("loras", {})[lora_name] = info.to_dict()
    reg["updated"] = "2026-07-17"
    _save_registry(reg)


def scan_local_loras() -> list[dict[str, Any]]:
    """扫描本地 loras/ 目录，返回已安装的 LoRA 列表。"""
    lora_dir = Path(LORA_DIR)
    if not lora_dir.exists():
        return []
    results = []
    for f in sorted(lora_dir.iterdir()):
        if f.suffix in (".safetensors", ".pt", ".pth"):
            info = get_lora_info(f.name)
            results.append({
                "name": f.name,
                "path": str(f),
                "size_mb": round(f.stat().st_size / 1_048_576, 1),
                "lora_type": info.lora_type if info else "unknown",
                "base_model": info.base_model if info else "unknown",
                "caption_format": info.caption_format if info else "unknown",
                "strength_default": info.strength_default if info else 0.8,
            })
    return results


# ── 2. Block Weight 调节 ──────────────────────────────────

def parse_block_weights(weights_str: str) -> list[float]:
    """解析 block weights 字符串 → 浮点列表。
    支持格式: "0.8,0.8,1.0,1.2,..." (逗号分隔，22 个值)
    """
    parts = [w.strip() for w in weights_str.split(",") if w.strip()]
    try:
        return [float(p) for p in parts]
    except ValueError:
        return []


def format_block_weights(weights: list[float]) -> str:
    """浮点列表 → 逗号分隔字符串。"""
    return ",".join(f"{w:.2f}" for w in weights)


def block_weights_to_lora_params(weights_str: str) -> dict[str, Any]:
    """Block weights 字符串 → LoraLoader 可用的参数。
    目前 ComfyUI 原生 LoraLoader 不支持 block weights，
    此处返回自定义参数，供支持 block weight 的节点使用。
    """
    parsed = parse_block_weights(weights_str)
    if not parsed or len(parsed) < 22:
        return {}
    return {
        "block_weights": weights_str,
        "block_weights_count": len(parsed),
    }


# ── 3. 底模兼容检查 ──────────────────────────────────────

BASE_MODEL_COMPAT: dict[str, list[str]] = {
    # training_base_model → compatible inference base models
    "sdxl":                ["sdxl", "sdxl-pony", "sdxl-illustrious", "sdxl-noobai"],
    "sdxl-pony":           ["sdxl-pony", "sdxl-illustrious"],
    "sdxl-illustrious":    ["sdxl-illustrious", "sdxl-noobai"],
    "sdxl-noobai":         ["sdxl-noobai", "sdxl-illustrious"],
    "flux1":               ["flux1"],
    "flux2-klein":         ["flux2-klein"],
}


def check_compatibility(lora_name: str, current_base: str) -> dict[str, Any]:
    """检查 LoRA 与当前底模的兼容性。
    Returns: {"compatible": bool, "message": str, "recommended": bool}
    """
    info = get_lora_info(lora_name)
    if info is None:
        return {"compatible": True, "message": "未知 LoRA，跳过检查", "recommended": False}

    trained_on = info.base_model
    compatible = BASE_MODEL_COMPAT.get(trained_on, [])

    if current_base in compatible:
        return {"compatible": True, "message": f"✅ {trained_on} → {current_base} 兼容", "recommended": True}
    elif current_base.split("-")[0] == trained_on.split("-")[0]:
        # 同家族：sdxl → sdxl-pony
        return {"compatible": True, "message": f"⚠️ {trained_on} → {current_base} 同族，效果可能降级", "recommended": False}
    else:
        return {"compatible": False, "message": f"❌ {trained_on} → {current_base} 不兼容", "recommended": False}


def resolve_base_model(checkpoint_name: str) -> str:
    """从 checkpoint 名推测底模类型。"""
    name_lower = checkpoint_name.lower()
    if "flux" in name_lower:
        if "klein" in name_lower or "2" in name_lower:
            return "flux2-klein"
        return "flux1"
    if "pony" in name_lower:
        return "sdxl-pony"
    if "noobai" in name_lower:
        return "sdxl-noobai"
    if "illustrious" in name_lower or "wai" in name_lower:
        return "sdxl-illustrious"
    return "sdxl"


# ── 4. 多 LoRA 叠加策略 ──────────────────────────────────

PRESET_TEMPLATES: dict[str, LoraStackTemplate] = {
    "character_only": LoraStackTemplate(
        name="character_only",
        description="单一角色 LoRA，最高权重",
        items=[{"name": "<lora>", "weight": 0.8}],
    ),
    "char_style": LoraStackTemplate(
        name="char_style",
        description="角色 0.8 + 画风 0.5",
        items=[
            {"name": "<char_lora>", "weight": 0.8},
            {"name": "<style_lora>", "weight": 0.5},
        ],
    ),
    "char_scene": LoraStackTemplate(
        name="char_scene",
        description="角色 0.8 + 场景 0.4",
        items=[
            {"name": "<char_lora>", "weight": 0.8},
            {"name": "<scene_lora>", "weight": 0.4},
        ],
    ),
    "char_style_scene": LoraStackTemplate(
        name="char_style_scene",
        description="角色 0.8 + 画风 0.5 + 场景 0.3",
        items=[
            {"name": "<char_lora>", "weight": 0.8},
            {"name": "<style_lora>", "weight": 0.5},
            {"name": "<scene_lora>", "weight": 0.3},
        ],
    ),
    "dual_char": LoraStackTemplate(
        name="dual_char",
        description="双角色各 0.6（避免冲突）",
        items=[
            {"name": "<char_a>", "weight": 0.6},
            {"name": "<char_b>", "weight": 0.6},
        ],
    ),
}


def get_stack_template(name: str) -> LoraStackTemplate | None:
    """获取预设叠加模板。"""
    reg = _load_registry()
    raw = reg.get("stack_templates", {}).get(name)
    if raw:
        return LoraStackTemplate(**raw)
    return PRESET_TEMPLATES.get(name)


def apply_lora_stack(
    lora_spec: str | list[dict[str, Any]],
    template_name: str = "",
) -> list[dict[str, Any]]:
    """应用 LoRA 叠加策略。
    lora_spec: 可以是单个 LoRA 名（字符串）、已定义的 items 列表
    template_name: 可选预设模板名
    Returns: [{"name": str, "weight": float, "block_weights": str?}]
    """
    if isinstance(lora_spec, str):
        # 单个 LoRA
        if template_name:
            tmpl = get_stack_template(template_name)
            if tmpl:
                result = []
                for item in tmpl.items:
                    resolved = dict(item)
                    if resolved["name"].startswith("<") and resolved["name"].endswith(">"):
                        resolved["name"] = lora_spec
                    result.append(resolved)
                return result
        return [{"name": lora_spec, "weight": 0.8}]

    if isinstance(lora_spec, list):
        return lora_spec  # 已定义的 items

    return []


# ── 5. Caption 风格记录 ──────────────────────────────────

CAPTION_FORMAT_GUIDE = {
    "tags": {
        "description": "Danbooru 标签，逗号分隔",
        "example": "shm_character, 1girl, silver_hair, long_hair, purple_eyes",
        "suitable_for": ["sdxl-illustrious", "sdxl-pony"],
        "prompt_tip": "推理时用同样的 tag 风格写 prompt",
    },
    "natural": {
        "description": "自然语言句子",
        "example": "shm_character is a young woman with long silver hair and purple eyes.",
        "suitable_for": ["sdxl-noobai", "flux1", "flux2-klein"],
        "prompt_tip": "推理时用自然语言描述，不要用逗号 tag",
    },
    "hybrid": {
        "description": "Danbooru tags + 自然语言混合",
        "example": "shm_character, silver_hair, purple_eyes, standing outside in a garden",
        "suitable_for": ["sdxl", "sdxl-illustrious"],
        "prompt_tip": "开头几个词用 tag 定位特征，后面用自然语言描述场景",
    },
    "pony": {
        "description": "e621 标签，必须以 rating: 开头",
        "example": "rating: safe, shm_character, 1girl, silver_hair, purple_eyes",
        "suitable_for": ["sdxl-pony"],
        "prompt_tip": "推理时 prompt 也必须以 rating: 开头！否则不出效果",
    },
}


def get_caption_format_guide(fmt: str) -> dict:
    """获取 caption 格式的使用指南。"""
    return CAPTION_FORMAT_GUIDE.get(fmt, CAPTION_FORMAT_GUIDE["tags"])


# ── 6. 验证快照 ──────────────────────────────────────────

def update_best_checkpoint(
    lora_name: str,
    checkpoint_name: str,
    score: float,
    image_path: str = "",
) -> None:
    """更新 LoRA 的最佳 checkpoint 记录。"""
    info = get_lora_info(lora_name)
    if info is None:
        info = LoraInfo(name=lora_name, path=f"loras/{lora_name}")

    info.best_checkpoint = checkpoint_name
    info.best_score = score
    if image_path:
        info.best_image = image_path

    set_lora_info(lora_name, info)


# ── CLI 集成 ──────────────────────────────────────────

def list_loras(format: str = "table") -> str:
    """列出所有 LoRA 及其元数据。"""
    loras = scan_local_loras()
    if not loras:
        return "📭 未找到 LoRA 文件"

    lines = ["📦 LoRA 清单:\n"]
    lines.append("  {:<35s} {:>8s} {:>10s} {:>14s} {:>10s} {:>8s}".format(
        "名称", "大小(MB)", "类型", "底模", "caption", "推荐权重"))
    lines.append("  " + "-" * 95)

    for l in loras:
        lines.append("  {:<35s} {:>8.1f} {:>10s} {:>14s} {:>10s} {:>8.2f}".format(
            l["name"][:34],
            l["size_mb"],
            l["lora_type"],
            l["base_model"],
            l["caption_format"],
            l["strength_default"],
        ))

    return "\n".join(lines)


def show_lora_detail(lora_name: str) -> str:
    """显示单个 LoRA 的详细元数据。"""
    info = get_lora_info(lora_name)
    if info is None:
        return f"❌ LoRA '{lora_name}' 不在 registry 中"

    lines = [f"📋 LoRA: {info.name}", "=" * 40]
    lines.append(f"  路径:             {info.path}")
    lines.append(f"  类型:             {info.lora_type}")
    lines.append(f"  训练底模:         {info.base_model}")
    lines.append(f"  Caption 风格:     {info.caption_format}")
    lines.append(f"  触发词:           {info.trigger_word or '(未记录)'}")
    lines.append(f"  推荐强度:         {info.strength_default}")

    if info.block_weights:
        lines.append(f"  推荐 Block Weights: {info.block_weights}")
    if info.best_checkpoint:
        lines.append(f"  最佳 checkpoint:   {info.best_checkpoint} (score={info.best_score:.3f})")
    if info.best_image:
        lines.append(f"  效果图:            {info.best_image}")
    if info.notes:
        lines.append(f"  备注:              {info.notes}")

    # 兼容检查示例
    cg = get_caption_format_guide(info.caption_format)
    lines.append(f"\n  Caption 写法参考:\n    {cg['example'][:80]}")
    lines.append(f"  Prompt 注意: {cg['prompt_tip']}")

    return "\n".join(lines)


def main() -> None:
    """LoRA 管理 CLI。"""
    import argparse, sys, json
    parser = argparse.ArgumentParser(description="LoRA 管理器")
    parser.add_argument("action", choices=["list", "info", "scan"], help="list|info|scan")
    parser.add_argument("name", nargs="?", help="LoRA 文件名 (info 模式)")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parsed = parser.parse_args(sys.argv[1:])

    if parsed.action == "scan":
        results = scan_local_loras()
        if parsed.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            print(f"\n本地 LoRA ({len(results)} 个):")
            for r in results:
                print(f"  {r['name']:40s} {r['size_mb']:>6}MB  {r['base_model']}")
        return

    if parsed.action == "info" and parsed.name:
        info = get_lora_info(parsed.name)
        if not info:
            for r in scan_local_loras():
                if r["name"] == parsed.name:
                    print(f"LoRA: {parsed.name}\n  大小: {r['size_mb']}MB\n  类型: {r['lora_type']}\n  底模: {r['base_model']}")
                    return
            print(f"未找到: {parsed.name}")
            return
        if parsed.json:
            print(json.dumps(info.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(format_lora_info(info))
        return

    reg = _load_registry()
    loras = reg.get("loras", {})
    if parsed.json:
        print(json.dumps(loras, indent=2, ensure_ascii=False))
    else:
        print(f"\nRegistry LoRA ({len(loras)} 个):")
        for name, data in sorted(loras.items()):
            print(f"  {name:45s} {data.get('base_model','?'):20s} {data.get('notes','')[:40]}")
