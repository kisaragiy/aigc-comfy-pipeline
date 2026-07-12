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
                # 跳过 _meta 字段检查实际节点
                for key, val in data.items():
                    if isinstance(val, dict) and "class_type" in val:
                        is_api = True
                        break
            # 只统计有 class_type 的节点（跳过 _meta 等）
            nodes = {k: v for k, v in data.items()
                     if isinstance(v, dict) and "class_type" in v}
            results.append({
                "name": name,
                "path": str(fpath),
                "node_count": len(nodes),
                "is_api_format": is_api,
                "class_types": sorted(set(
                    v["class_type"] for v in nodes.values()
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


# ============================================================
# UI → API 格式转换
# ============================================================


def _load_ui_workflow(name: str) -> tuple[Path | None, dict | None]:
    """加载 UI 格式 workflow。返回 (path, data) 或 (None, None)。"""
    for wf_dir in WORKFLOW_DIRS:
        if not wf_dir.is_dir():
            continue
        for fpath in wf_dir.glob("*.json"):
            if fpath.stem == name or fpath.name == name:
                try:
                    data = json.loads(fpath.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                if isinstance(data, dict) and "nodes" in data:
                    return fpath, data
    return None, None


def convert_to_api(
    name: str,
    *,
    comfy_url: str | None = None,
    output_path: str | None = None,
) -> dict | None:
    """将 UI 格式 workflow 转为 API 格式。

    Args:
        name: workflow 名称
        comfy_url: ComfyUI URL（用于 /object_info）
        output_path: 输出路径（默认覆盖原文件）

    Returns:
        API 格式 workflow dict，或 None
    """
    import requests

    # 1. 加载 UI workflow
    wf_path, data = _load_ui_workflow(name)
    if wf_path is None:
        print(f"未找到 UI 格式 workflow: {name}")
        return None

    nodes = data.get("nodes", [])
    links = data.get("links", [])

    if not nodes:
        print(f"workflow 没有 nodes 数组（可能已是 API 格式）: {name}")
        return None

    # 2. 获取节点输入结构
    object_info = None
    base = (comfy_url or "http://127.0.0.1:8188").rstrip("/prompt").rstrip("/")
    try:
        r = requests.get(f"{base}/object_info", timeout=10)
        if r.status_code == 200:
            object_info = r.json()
            print(f"✅ 已从 ComfyUI 获取节点信息（{len(object_info)} 种节点类型）")
    except Exception:
        print("[warn] ComfyUI 未运行，无法查询节点输入结构")
        return None

    # 3. 构建 link 映射: (to_node_id, to_slot) → (from_node_id, from_slot)
    link_map: dict[tuple[str, int], tuple[str, int]] = {}
    for link in links:
        if len(link) >= 5:
            link_id, from_node, from_slot, to_node, to_slot = link[:5]
            link_map[(str(to_node), to_slot)] = (str(from_node), from_slot)

    # 4. 转换每个节点
    api_wf: dict[str, Any] = {}
    converted = 0
    skipped = 0

    for node in nodes:
        nid = str(node.get("id", ""))
        ntype = node.get("type", "")
        if not nid or not ntype:
            continue
        if ntype == "Reroute":
            skipped += 1
            continue

        widgets = node.get("widgets_values", [])
        node_input_conns = node.get("inputs", [])  # [{name, link, ...}]
        node_def = object_info.get(ntype, {})
        required_inputs = node_def.get("input", {}).get("required", {})
        optional_inputs = node_def.get("input", {}).get("optional", {})

        # 合并所有已知输入名（按顺序）
        all_known_inputs = list(required_inputs.keys()) + list(optional_inputs.keys())

        inputs: dict[str, Any] = {}
        widget_idx = 0

        # 对每个输入名：检查是连接还是 widget
        for inp_name in all_known_inputs:
            if inp_name not in inputs:
                # 检查是否有连接
                is_connected = False
                for conn_idx, conn in enumerate(node_input_conns):
                    if isinstance(conn, dict) and conn.get("name") == inp_name:
                        link_id = conn.get("link")
                        if link_id is not None and link_id >= 0:
                            # 查 link 表获取来源
                            from_info = link_map.get((nid, conn_idx))
                            if from_info:
                                inputs[inp_name] = [from_info[0], from_info[1]]
                                is_connected = True
                        break

                if not is_connected and widget_idx < len(widgets):
                    # 无连接 → 使用 widget 值
                    inputs[inp_name] = widgets[widget_idx]
                    widget_idx += 1

        api_wf[nid] = {"class_type": ntype, "inputs": inputs}
        converted += 1

    # 5. 保存
    if output_path:
        out = Path(output_path)
    else:
        stem = Path(wf_path).stem
        # 去掉可能重复的 _api
        stem = stem.replace("_api", "")
        out = Path(wf_path).parent / f"{stem}_api.json"

    out.write_text(
        json.dumps(api_wf, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n✅ 转换完成: {converted} 个节点转换, {skipped} 个跳过")
    print(f"   已保存: {out}")
    print(f"   现在可以通过 workflow schema/check/show 使用 API 格式")

    return api_wf
