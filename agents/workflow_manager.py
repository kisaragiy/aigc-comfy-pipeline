"""工作流模板管理 — 扫描、解析、schema 提取、依赖检查。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
WORKFLOW_DIRS = [
    PROJECT_ROOT / "workflows",
    HERE,  # agents/ 也有 workflow JSON
]


# ============================================================
# 扫描
# ============================================================


def _scan_workflows() -> list[dict[str, Any]]:
    """扫描所有 workflow 目录，返回 {name, path, node_count, class_types}。"""
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for wf_dir in WORKFLOW_DIRS:
        if not wf_dir.is_dir():
            continue
        for fpath in sorted(wf_dir.glob("*.json")):
            name = fpath.stem
            if name in seen:
                continue
            seen.add(name)
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(data, dict):
                continue
            # 判断是 API 格式还是 UI 格式
            is_api = False
            if data:
                first_val = next(iter(data.values()), {})
                is_api = isinstance(first_val, dict) and "class_type" in first_val
            results.append({
                "name": name,
                "path": str(fpath),
                "node_count": len([v for v in data.values() if isinstance(v, dict)]),
                "is_api_format": is_api,
                "class_types": sorted(set(
                    v.get("class_type", "?") for v in data.values()
                    if isinstance(v, dict)
                )) if is_api else [],
            })
    return results


def list_workflows() -> list[dict[str, Any]]:
    """列出所有可用 workflow。"""
    return _scan_workflows()


def find_workflow(name: str) -> dict[str, Any] | None:
    """按名称查找 workflow JSON。"""
    for wf_dir in WORKFLOW_DIRS:
        if not wf_dir.is_dir():
            continue
        for fpath in wf_dir.glob("*.json"):
            if fpath.stem == name or fpath.name == name:
                try:
                    data = json.loads(fpath.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        return data
                except (json.JSONDecodeError, OSError):
                    pass
    return None


def get_workflow_path(name: str) -> str | None:
    """按名称查找 workflow 的文件路径。"""
    for wf_dir in WORKFLOW_DIRS:
        if not wf_dir.is_dir():
            continue
        for fpath in wf_dir.glob("*.json"):
            if fpath.stem == name or fpath.name == name:
                return str(fpath)
    return None


# ============================================================
# Schema 提取
# ============================================================

_CONTROLLABLE_KEYWORDS: dict[str, str] = {
    "text": "prompt",
    "seed": "seed",
    "steps": "steps",
    "cfg": "cfg",
    "lora_name": "lora",
    "strength_model": "lora_strength",
    "ckpt_name": "checkpoint",
    "width": "width",
    "height": "height",
    "denoise": "denoise",
    "filename_prefix": "output_prefix",
    "image": "input_image",
    "sampler_name": "sampler",
    "scheduler": "scheduler",
    "unet_name": "model",
    "clip_name": "clip",
    "vae_name": "vae",
    "noise_seed": "seed",
    "positive": "prompt",
    "negative": "negative",
}


def extract_schema(workflow: dict) -> dict[str, Any]:
    """提取 workflow 的可控参数信息。

    Returns:
        {
            "parameter_count": int,
            "has_prompt": bool,
            "has_seed": bool,
            "has_steps": bool,
            "has_cfg": bool,
            "has_lora": bool,
            "has_checkpoint": bool,
            "node_count": int,
            "class_types": [str],
            "parameters": [{"node_id", "class_type", "input_name", "input_type", "category"}]
        }
    """
    params: list[dict[str, Any]] = []
    has_prompt = False
    has_seed = False
    has_steps = False
    has_cfg = False
    has_lora = False
    has_checkpoint = False

    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        ct = node.get("class_type", "?")
        inputs = node.get("inputs", {})
        for inp_name, inp_value in inputs.items():
            # 只提取原始值（非节点引用）的参数
            if isinstance(inp_value, (str, int, float, bool)):
                cat = _CONTROLLABLE_KEYWORDS.get(inp_name, "other")
                params.append({
                    "node_id": node_id,
                    "class_type": ct,
                    "input_name": inp_name,
                    "input_type": type(inp_value).__name__,
                    "category": cat,
                })
                if cat == "prompt":
                    has_prompt = True
                elif cat == "seed":
                    has_seed = True
                elif cat == "steps":
                    has_steps = True
                elif cat == "cfg":
                    has_cfg = True
                elif cat == "lora":
                    has_lora = True
                elif cat == "checkpoint":
                    has_checkpoint = True

    class_types = sorted(set(
        v.get("class_type", "?") for v in workflow.values()
        if isinstance(v, dict)
    ))

    return {
        "parameter_count": len(params),
        "has_prompt": has_prompt,
        "has_seed": has_seed,
        "has_steps": has_steps,
        "has_cfg": has_cfg,
        "has_lora": has_lora,
        "has_checkpoint": has_checkpoint,
        "node_count": len([v for v in workflow.values() if isinstance(v, dict)]),
        "class_types": class_types,
        "parameters": params,
    }


# ============================================================
# 依赖检查
# ============================================================


def check_deps(workflow: dict, *, comfy_url: str | None = None) -> dict[str, Any]:
    """对照 ComfyUI /object_info 检查 workflow 依赖是否满足。

    Args:
        workflow: API 格式 workflow dict
        comfy_url: ComfyUI 基础 URL

    Returns:
        {comfy_online, total_nodes, unique_types, missing_nodes, all_nodes_ok}
    """
    import requests

    base_url = (comfy_url or "http://127.0.0.1:8188").rstrip("/prompt").rstrip("/")

    try:
        r = requests.get(f"{base_url}/object_info", timeout=10)
        if r.status_code != 200:
            return {"comfy_online": False, "missing_nodes": [], "total_nodes": 0, "all_nodes_ok": False}
        server_nodes: dict[str, Any] = r.json()
    except (requests.RequestException, json.JSONDecodeError) as exc:
        return {"comfy_online": False, "error": str(exc), "missing_nodes": [], "total_nodes": 0, "all_nodes_ok": False}

    required_types: list[str] = []
    for _node_id, node in workflow.items():
        if isinstance(node, dict):
            ct = node.get("class_type", "")
            if ct:
                required_types.append(ct)

    missing: list[str] = []
    for ct in sorted(set(required_types)):
        if ct not in server_nodes:
            missing.append(ct)

    return {
        "comfy_online": True,
        "total_nodes": len(required_types),
        "unique_types": len(set(required_types)),
        "missing_nodes": missing,
        "all_nodes_ok": len(missing) == 0,
    }


# ============================================================
# 节点图
# ============================================================


def show_graph(workflow: dict) -> str:
    """生成简单的节点连接图（文本）。"""
    lines: list[str] = []
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        ct = node.get("class_type", "?")
        inputs = node.get("inputs", {})
        refs = []
        for inp_name, inp_value in inputs.items():
            if isinstance(inp_value, list) and len(inp_value) == 2:
                refs.append(f"{inp_name}=[{inp_value[0]}:{inp_value[1]}]")
        if refs:
            lines.append(f"  [{node_id}] {ct}  ← {', '.join(refs)}")
        else:
            lines.append(f"  [{node_id}] {ct}")
    return "\n".join(lines)
