"""模型管理 — 列出、查询、检查 ComfyUI 模型依赖。"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

# 模型目录 → 类型映射
CATEGORY_DIR_MAP: dict[str, str] = {
    "checkpoints": "checkpoint",
    "diffusion_models": "checkpoint",
    "unet": "checkpoint",
    "loras": "lora",
    "vae": "vae",
    "vae_approx": "vae",
    "clip": "clip",
    "text_encoders": "clip",
    "embeddings": "embedding",
    "upscale_models": "upscale",
    "controlnet": "controlnet",
    "ipadapter": "ipadapter",
    "style_models": "style_model",
    "gligen": "gligen",
    "photomaker": "photomaker",
    "animatediff_models": "animatediff",
    "hypernetworks": "hypernetwork",
}

MODEL_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".patch"}


def resolve_models_root() -> Path | None:
    """查找 ComfyUI models 目录。"""
    try:
        from comfy_utils import resolve_comfy_root

        root = resolve_comfy_root()
        if root:
            models_dir = root / "models"
            if models_dir.is_dir():
                return models_dir
        return None
    except Exception:
        return None


def _scan_models() -> list[dict[str, Any]]:
    """扫描 models/ 下所有模型文件。"""
    models_root = resolve_models_root()
    if models_root is None:
        return []

    results: list[dict[str, Any]] = []
    for subdir in sorted(models_root.iterdir()):
        if not subdir.is_dir():
            continue
        category = CATEGORY_DIR_MAP.get(subdir.name, "other")
        for fpath in sorted(subdir.rglob("*")):
            if not fpath.is_file():
                continue
            if fpath.suffix.lower() not in MODEL_EXTENSIONS:
                continue
            if fpath.name.startswith("."):
                continue
            size_mb = fpath.stat().st_size / (1024 * 1024)
            mtime = fpath.stat().st_mtime
            results.append({
                "name": fpath.name,
                "path": str(fpath),
                "category": category,
                "size_mb": round(size_mb, 1),
                "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime)),
                "subdir": subdir.name,
            })
    return results


_model_cache: list[dict[str, Any]] | None = None


def refresh_cache() -> None:
    """清除并重新扫描模型缓存。"""
    global _model_cache
    _model_cache = None
    _model_cache = _scan_models()
    print(f"✅ 模型缓存已刷新，共 {len(_model_cache)} 个模型。")


def list_models(category: str | None = None, no_cache: bool = False) -> list[dict[str, Any]]:
    """列出模型。category 为 None 返回全部，否则按类型过滤。"""
    global _model_cache
    if no_cache or _model_cache is None:
        _model_cache = _scan_models()
    models = _model_cache
    if category:
        cat = category.lower().rstrip("s")
        models = [m for m in models if m["category"] == cat]
    return models


def get_model_info(name: str) -> dict[str, Any] | None:
    """按文件名查询模型详情（先精确后模糊）。"""
    models = list_models()
    name_lower = name.lower()
    # 精确匹配
    for m in models:
        if m["name"].lower() == name_lower:
            return m
    # 模糊匹配
    for m in models:
        if name_lower in m["name"].lower():
            return m
    # 子串反向匹配（如 "knives" 匹配 "knives_sdxl.safetensors"）
    for m in models:
        if m["name"].lower()[:len(name_lower)] == name_lower:
            return m
    return None


def _extract_model_refs(workflow: dict) -> list[dict[str, str]]:
    """从 workflow 中提取所有模型引用。"""
    MODEL_INPUT_KEYS = {
        "ckpt_name": "checkpoint",
        "unet_name": "checkpoint",
        "lora_name": "lora",
        "vae_name": "vae",
        "clip_name": "clip",
        "control_net_name": "controlnet",
        "controlnet_name": "controlnet",
        "emb_name": "embedding",
    }

    refs: list[dict[str, str]] = []
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs", {})
        for inp_name, inp_value in inputs.items():
            if inp_name in MODEL_INPUT_KEYS and isinstance(inp_value, str):
                cat = MODEL_INPUT_KEYS[inp_name]
                refs.append({
                    "node_id": node_id,
                    "input_name": inp_name,
                    "value": inp_value,
                    "category": cat,
                })
    return refs


# Wan2.2 视频模型定义：(子目录, 文件名, 最小预期大小 MB, 说明)
VIDEO_MODELS: list[tuple[str, str, float, str]] = [
    ("diffusion_models", "wan2.2_ti2v_5B_fp16.safetensors", 9000, "Wan2.2 T2V 扩散模型 (5B)"),
    ("text_encoders", "umt5_xxl_fp8_e4m3fn_scaled.safetensors", 6000, "Wan2.2 文本编码器 (UMT5)"),
    ("vae", "wan2.2_vae.safetensors", 1000, "Wan2.2 VAE 解码器"),
]


def check_video_models() -> dict[str, Any]:
    """检查 Wan2.2 视频生成所需模型是否完整。

    Returns:
        {found: [{name, subdir, size_mb, expected_min, ok, description}],
         missing: [{name, subdir, description}],
         all_found, has_corruption}
    """
    models_root = resolve_models_root()
    found: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []

    for subdir, filename, min_size_mb, desc in VIDEO_MODELS:
        fpath: Path | None = None
        if models_root:
            candidate = models_root / subdir / filename
            if candidate.is_file():
                fpath = candidate
        status = {"name": filename, "subdir": subdir, "description": desc}
        if fpath:
            size_mb = fpath.stat().st_size / (1024 * 1024)
            ok = size_mb >= min_size_mb
            found.append({**status, "size_mb": round(size_mb, 1),
                          "expected_min": min_size_mb, "ok": ok})
        else:
            missing.append(status)

    all_found = len(missing) == 0
    has_corruption = any(
        f for f in found if isinstance(f.get("ok"), bool) and not f["ok"]
    )

    return {
        "found": found,
        "missing": missing,
        "all_found": all_found,
        "all_healthy": all_found and not has_corruption,
        "has_corruption": has_corruption,
    }


def check_workflow_models(workflow: dict) -> dict[str, Any]:
    """检查 workflow 所需的模型是否已安装。

    Returns:
        {total_refs, found: [{value, category, path}], missing: [{value, category}], all_found}
    """
    refs = _extract_model_refs(workflow)
    models = list_models()
    installed_names = {m["name"].lower(): m["path"] for m in models}

    found: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []

    for ref in refs:
        val_lower = ref["value"].lower()
        if val_lower in installed_names:
            found.append({**ref, "path": installed_names[val_lower]})
        else:
            # 尝试模糊匹配
            match = None
            for installed_name, installed_path in installed_names.items():
                if val_lower in installed_name or installed_name in val_lower:
                    match = installed_path
                    break
            if match:
                found.append({**ref, "path": match})
            else:
                missing.append({"value": ref["value"], "category": ref["category"]})

    return {
        "total_refs": len(refs),
        "found": found,
        "missing": missing,
        "all_found": len(missing) == 0,
    }
