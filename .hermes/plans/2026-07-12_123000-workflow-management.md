# V0.8.0 — 工作流模板管理 + 依赖检查 实现方案

> **Goal:** 管理 workflows/ 目录、检查依赖完整性、提取参数 schema，让管线对新人也能上手。
>
> **Architecture:** 新模块 `agents/workflow_manager.py`，通过 ComfyUI `/object_info` API 检查节点和模型依赖。
>
> **Tech Stack:** Python, ComfyUI REST API (`/object_info`, `/queue`)

---

## 详细设计

### 用户交互

```
python -m agents workflow list              # 列出所有可用 workflow
python -m agents workflow show <name>        # 显示节点图 + 可控参数
python -m agents workflow schema <name>      # 提取参数 schema（JSON）
python -m agents workflow check <name>       # 检查节点/模型是否安装
```

### 核心模块

`agents/workflow_manager.py`：

| 函数 | 说明 |
|------|------|
| `list_workflows()` | 扫描 `workflows/` 和 `agents/` 下所有 `.json` 文件 |
| `load_workflow(name)` | 按名称加载 workflow JSON |
| `extract_schema(workflow)` | 提取可控参数（prompt/seed/steps/cfg/LoRA 等） |
| `check_deps(workflow)` | 对照 `/object_info` 检查 class_type 是否存在 |
| `show_graph(workflow)` | 打印节点连接图 |

### 文件改动清单

| 操作 | 文件 | 说明 |
|------|------|------|
| Create | `agents/workflow_manager.py` | 工作流管理模块 |
| Modify | `agents/__main__.py` | +workflow 子命令 |
| Modify | `AGENTS.md` | 版本 V0.8.0 + 更新 |

---

## Task 1: 创建 workflow_manager.py

**Objective:** 工作流模板管理，扫描、解析、schema 提取、依赖检查

**Files:**
- Create: `agents/workflow_manager.py`

### 核心代码：

```python
"""工作流模板管理 — 扫描、解析、schema 提取、依赖检查。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from comfy_utils import bootstrap_agents_path

bootstrap_agents_path()

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
WORKFLOW_DIRS = [
    PROJECT_ROOT / "workflows",
    HERE,  # agents/ also has workflow JSONs
]


# ============================================================
# 扫描
# ============================================================

WORKFLOW_CACHE: list[dict[str, Any]] | None = None


def _scan_workflows() -> list[dict[str, Any]]:
    """扫描所有 workflow 目录，返回 {name, path, node_count, class_types} 列表。"""
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
            is_api = "class_type" in next(iter(data.values()), {})
            results.append({
                "name": name,
                "path": str(fpath),
                "node_count": len(data),
                "is_api_format": is_api,
                "class_types": list({
                    v.get("class_type", "?") for v in data.values()
                    if isinstance(v, dict)
                }) if is_api else [],
            })
    return results


def list_workflows() -> list[dict[str, Any]]:
    """列出所有可用 workflow。"""
    return _scan_workflows()


def find_workflow(name: str) -> dict[str, Any] | None:
    """按名称（不带扩展名）查找 workflow JSON。"""
    for wf_dir in WORKFLOW_DIRS:
        if not wf_dir.is_dir():
            continue
        for ext in (".json",):
            path = wf_dir / f"{name}{ext}"
            if path.is_file():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        return data
                except (json.JSONDecodeError, OSError):
                    pass
        # 也搜索完整文件名（含路径）
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

# 常见可控参数的关键字映射
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
            if isinstance(inp_value, (str, int, float, bool, list)):
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
        comfy_url: ComfyUI 基础 URL（默认 127.0.0.1:8188）

    Returns:
        {
            "comfy_online": bool,
            "missing_nodes": [str],       # class_type 在服务器上不存在的节点
            "total_nodes": int,
            "all_nodes_ok": bool,
        }
    """
    import requests

    base_url = comfy_url or "http://127.0.0.1:8188"

    # 1. 检查 ComfyUI 是否在线
    try:
        r = requests.get(f"{base_url}/object_info", timeout=10)
        if r.status_code != 200:
            return {"comfy_online": False, "missing_nodes": [], "total_nodes": 0, "all_nodes_ok": False}
        server_nodes: dict[str, Any] = r.json()
    except (requests.RequestException, json.JSONDecodeError) as exc:
        return {"comfy_online": False, "error": str(exc), "missing_nodes": [], "total_nodes": 0, "all_nodes_ok": False}

    # 2. 收集 workflow 所需的 class_type
    required_types: list[str] = []
    for node_id, node in workflow.items():
        if isinstance(node, dict):
            ct = node.get("class_type", "")
            if ct:
                required_types.append(ct)

    # 3. 检查每个 class_type 是否存在
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


def show_graph(workflow: dict) -> str:
    """生成简单的节点连接图（文本来描述）。"""
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
```

**验证:**
```bash
python -c "
from agents.workflow_manager import list_workflows, extract_schema, check_deps, show_graph, find_workflow
wfs = list_workflows()
print(f'Found {len(wfs)} workflows')
if wfs:
    print(f'First: {wfs[0][\"name\"]} ({wfs[0][\"node_count\"]} nodes, API={wfs[0][\"is_api_format\"]})')
# schema 提取
wf = find_workflow('workflow_knives_lora_sdxl')
if wf:
    schema = extract_schema(wf)
    print(f'Schema: {schema[\"parameter_count\"]} params, has_prompt={schema[\"has_prompt\"]}')
# 依赖检查（ComfyUI 未运行时会显示 offline）
result = check_deps({})
print(f'Deps: online={result[\"comfy_online\"]}')
"
```

---

## Task 2: __main__.py — +workflow 子命令

**Objective:** `python -m agents workflow list|show|schema|check`

**Files:**
- Modify: `agents/__main__.py`

在 `_run_outputs()` 之后新增 `_run_workflow()` 函数：

```python
def _run_workflow() -> None:
    """Handle 'workflow list|show|schema|check' subcommands."""
    from agents.workflow_manager import (
        check_deps,
        extract_schema,
        find_workflow,
        get_workflow_path,
        list_workflows,
        show_graph,
    )

    if len(sys.argv) < 3:
        _show_workflow_help()
        return

    action = sys.argv[2]

    if action == "list":
        wfs = list_workflows()
        if not wfs:
            print("未找到 workflow 文件。")
            return
        print(f"\n{'名称':40s} {'节点':5s} {'API':5s} {'类型'}")
        print("-" * 70)
        for w in wfs:
            api = "✅" if w["is_api_format"] else "❌"
            types = ", ".join(w["class_types"][:3])
            if len(w["class_types"]) > 3:
                types += f" ... (+{len(w['class_types'])-3})"
            print(f"{w['name']:40s} {w['node_count']:5d} {api:5s} {types}")

    elif action == "show":
        if len(sys.argv) < 4:
            print("用法: python -m agents workflow show <name>")
            return
        name = sys.argv[3]
        wf = find_workflow(name)
        if wf is None:
            print(f"未找到 workflow: {name}")
            return
        path = get_workflow_path(name)
        print(f"\nWorkflow: {name}")
        print(f"路径:     {path}")
        print()
        print("节点图:")
        print(show_graph(wf))

    elif action == "schema":
        if len(sys.argv) < 4:
            print("用法: python -m agents workflow schema <name>")
            return
        name = sys.argv[3]
        wf = find_workflow(name)
        if wf is None:
            print(f"未找到 workflow: {name}")
            return
        schema = extract_schema(wf)
        print(f"\nWorkflow: {name}")
        print(f"参数数:   {schema['parameter_count']}")
        print(f"节点数:   {schema['node_count']}")
        print(f"有提示词: {schema['has_prompt']}")
        print(f"有 Seed:  {schema['has_seed']}")
        print(f"有 Steps: {schema['has_steps']}")
        print(f"有 CFG:   {schema['has_cfg']}")
        print(f"有 LoRA:  {schema['has_lora']}")
        print(f"有 Checkpoint: {schema['has_checkpoint']}")
        print()
        print("可控参数:")
        for p in schema["parameters"]:
            print(f"  [{p['node_id']}] {p['class_type']}.{p['input_name']} ({p['category']})")

    elif action == "check":
        if len(sys.argv) < 4:
            print("用法: python -m agents workflow check <name>")
            return
        name = sys.argv[3]
        wf = find_workflow(name)
        if wf is None:
            print(f"未找到 workflow: {name}")
            return
        result = check_deps(wf)
        if not result.get("comfy_online"):
            print("ComfyUI 未运行，无法检查依赖。")
            print("请先启动 ComfyUI 再运行: python -m agents check")
            return
        if result["all_nodes_ok"]:
            print(f"✅ 所有 {result['total_nodes']} 个节点依赖满足。")
        else:
            print(f"❌ 缺少 {len(result['missing_nodes'])} 个节点:")
            for ct in result["missing_nodes"]:
                print(f"   - {ct}")
            print("处理: 使用 ComfyUI Manager 或 comfy node install 安装对应自定义节点。")

    else:
        _show_workflow_help()


def _show_workflow_help() -> None:
    print("用法: python -m agents workflow list|show <name>|schema <name>|check <name>")
```

在 `main()` 中添加 `workflow` 命令路由：
```python
    if command == "workflow":
        _run_workflow()
        return
```

在 `_show_help()` 中添加 workflow 子命令说明：
```python
    ("workflow", "工作流模板管理（list / show / schema / check）"),
```

**验证:**
```bash
python -m agents workflow list          # 显示所有 workflow
python -m agents workflow show workflow_knives_lora_sdxl  # 显示节点图
python -m agents workflow schema workflow_knives_lora_sdxl  # 参数 schema
python -m agents workflow check workflow_knives_lora_sdxl  # 依赖检查（ComfyUI 需运行）
```

---

## Task 3: 更新 AGENTS.md + 提交

**Objective:** 版本 V0.8.0 + workflow 管理说明

**AGENTS.md 改动：**
- 版本 V0.7.0 → V0.8.0
- 核心能力表加一行 workflow 管理
- 项目结构更新
- Verification Checklist 追加

**提交:**
```bash
cd /c/Users/zwq/aigc-comfy-pipeline
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
git add -A
git commit -m "feat: V0.8.0 工作流模板管理 + 依赖检查

- agents/workflow_manager.py: list/show/schema/check 四功能
- extract_schema(): 提取 workflow 可控参数
- check_deps(): 对照 ComfyUI /object_info 检查节点依赖
- show_graph(): 节点连接图可视化
- python -m agents workflow 子命令
- AGENTS.md 版本 V0.8.0"
git push origin main
```

---

## 验证清单

- [ ] `python -c "from agents.workflow_manager import list_workflows, extract_schema, check_deps; print('ok')"`
- [ ] `python -m agents workflow list` → 列出所有 workflow（含 AI 格式标识）
- [ ] `python -m agents workflow show workflow_knives_lora_sdxl` → 显示节点图
- [ ] `python -m agents workflow schema workflow_knives_lora_sdxl` → 参数 schema
- [ ] `python -m agents workflow check workflow_knives_lora_sdxl` → ComfyUI 离线时友好提示
- [ ] `python -m agents --help` → 显示 workflow 子命令
