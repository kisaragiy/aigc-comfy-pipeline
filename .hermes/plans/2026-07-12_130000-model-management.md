# V0.9.0 — 模型管理 实现方案

> **Goal:** 列出已安装模型、检查 workflow 模型依赖、查询模型详情 — 解决"这个 workflow 缺什么模型"的问题
>
> **Architecture:** 新模块 `agents/model_manager.py`，扫描 `COMFY_ROOT/models/` 目录 + ComfyUI `/object_info` API
>
> **Tech Stack:** Python, Pathlib, ComfyUI `resolve_comfy_root()`

---

## 用户交互

```
python -m agents models list                    # 列出所有模型（按类型分组）
python -m agents models list checkpoints        # 只列出 checkpoints
python -m agents models list loras              # 只列出 LoRAs
python -m agents models info <name>             # 模型详情（路径/大小/类型）
python -m agents models check <workflow_name>   # 检查 workflow 需要的模型是否已安装
```

## 核心模块

`agents/model_manager.py`：

| 函数 | 说明 |
|------|------|
| `list_models(category=None)` | 扫描 `models/` 子目录，按类型分组，返回所有模型列表 |
| `get_model_info(name)` | 查询单个模型的路径/大小/修改时间/类型 |
| `check_workflow_models(workflow)` | 从 workflow JSON 提取模型引用，交叉检查本地安装 |
| `resolve_category_from_path(path)` | 根据子目录名推断模型类型 |

### 模型类型与目录映射

| 类型 | 子目录 | 扩展名 |
|------|--------|--------|
| checkpoint | `checkpoints/`, `diffusion_models/` | .safetensors, .ckpt |
| lora | `loras/` | .safetensors |
| vae | `vae/`, `vae_approx/` | .safetensors, .pt |
| clip | `clip/`, `text_encoders/` | .safetensors |
| embedding | `embeddings/` | .pt, .safetensors |
| upscale | `upscale_models/` | .pth |
| controlnet | `controlnet/` | .safetensors |
| ipadapter | `ipadapter/` | .safetensors |
| other | (其他) | — |

### Workflow 模型引用提取规则

从 workflow JSON 的节点 inputs 中提取模型文件名引用:

| Input 名 | 提取为 |
|----------|--------|
| `ckpt_name` | checkpoint |
| `unet_name` | diffusion_model |
| `lora_name` | lora |
| `vae_name` | vae |
| `clip_name` | clip / text_encoder |
| `control_net_name` | controlnet |

---

## 文件改动清单

| 操作 | 文件 | 说明 |
|------|------|------|
| Create | `agents/model_manager.py` | 模型管理模块 |
| Modify | `agents/__main__.py` | +`models` 子命令 |
| Modify | `AGENTS.md` | 版本 V0.9.0 + 更新 |

---

## Task 1: 创建 model_manager.py

**Objective:** 模型列表、查询、workflow 依赖检查

**Files:**
- Create: `agents/model_manager.py`

**代码:**

```python
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


def list_models(category: str | None = None) -> list[dict[str, Any]]:
    """列出模型。category 为 None 时返回全部，否则按类型过滤。"""
    global _model_cache
    if _model_cache is None:
        _model_cache = _scan_models()
    models = _model_cache
    if category:
        category_lower = category.lower().rstrip("s")
        models = [m for m in models if m["category"] == category_lower]
    return models


def get_model_info(name: str) -> dict[str, Any] | None:
    """按文件名查询模型详情（模糊匹配）。"""
    models = list_models()
    # 精确匹配
    for m in models:
        if m["name"] == name:
            return m
    # 模糊匹配
    name_lower = name.lower()
    for m in models:
        if name_lower in m["name"].lower():
            return m
    return None


def _extract_model_refs(workflow: dict) -> list[dict[str, str]]:
    """从 workflow 中提取所有模型引用。

    Returns:
        [{"input_name": "ckpt_name", "value": "sd_xl_base.safetensors", "category": "checkpoint"}]
    """
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


def check_workflow_models(workflow: dict) -> dict[str, Any]:
    """检查 workflow 所需的模型是否已安装。

    Returns:
        {
            "total_refs": int,
            "found": [{"value", "category", "path"}],
            "missing": [{"value", "category"}],
            "all_found": bool,
        }
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
```

**验证:**
```bash
python -c "
from agents.model_manager import list_models, get_model_info, check_workflow_models
models = list_models()
print(f'Total models: {len(models)}')
if models:
    cats = set(m['category'] for m in models)
    print(f'Categories: {sorted(cats)}')
    print(f'First: {models[0][\"name\"]} ({models[0][\"size_mb\"]}MB, {models[0][\"category\"]})')
# get_model_info
info = get_model_info('knives_sdxl.safetensors')
if info:
    print(f'Found: {info[\"name\"]} @ {info[\"path\"]}')
# check_workflow_models with empty dict
result = check_workflow_models({})
print(f'Check empty workflow: {result}')
"
```

---

## Task 2: __main__.py — +models 子命令

**Objective:** `python -m agents models list|info|check`

在 `_run_workflow()` 之后新增 `_run_models()` 函数，在 main() 中添加路由，在 help 中添加说明。

**代码（_run_models）：**

```python
def _run_models() -> None:
    """Handle 'models list|info|check' subcommands."""
    from agents.model_manager import check_workflow_models, get_model_info, list_models
    from agents.workflow_manager import find_workflow

    if len(sys.argv) < 3:
        _show_models_help()
        return

    action = sys.argv[2]

    if action == "list":
        category = sys.argv[3] if len(sys.argv) > 3 else None
        models = list_models(category)
        if not models:
            msg = f"未找到 {category} 模型。" if category else "未找到模型。"
            print(msg)
            print("处理: 确认 ComfyUI 已安装模型到 COMFY_ROOT/models/ 目录下。")
            return

        if category:
            print(f"\n{category} 模型 ({len(models)} 个):")
        else:
            # 按类型分组显示
            by_cat: dict[str, list] = {}
            for m in models:
                by_cat.setdefault(m["category"], []).append(m)
            print(f"\n共 {len(models)} 个模型:\n")
            for cat in sorted(by_cat):
                items = by_cat[cat]
                print(f"  📁 {cat} ({len(items)}):")
                for m in items:
                    print(f"    {m['name']:45s} {m['size_mb']:>6.1f}MB")
                print()

    elif action == "info":
        if len(sys.argv) < 4:
            print("用法: python -m agents models info <name>")
            return
        name = sys.argv[3]
        info = get_model_info(name)
        if info is None:
            print(f"未找到模型: {name}")
            return
        print(f"\n名称:     {info['name']}")
        print(f"类型:     {info['category']}")
        print(f"子目录:   {info['subdir']}")
        print(f"大小:     {info['size_mb']} MB")
        print(f"修改:     {info['modified']}")
        print(f"路径:     {info['path']}")

    elif action == "check":
        if len(sys.argv) < 4:
            print("用法: python -m agents models check <workflow_name>")
            return
        wf_name = sys.argv[3]
        wf = find_workflow(wf_name)
        if wf is None:
            print(f"未找到 workflow: {wf_name}")
            return
        result = check_workflow_models(wf)
        print(f"\nWorkflow: {wf_name}")
        if result["all_found"]:
            print(f"✅ 所有 {result['total_refs']} 个模型引用已安装。")
        else:
            print(f"❌ 缺少 {len(result['missing'])} 个模型:")
            for m in result["missing"]:
                print(f"   - [{m['category']}] {m['value']}")
            print("\n已安装的模型:")
            for m in result["found"]:
                print(f"   ✅ [{m['category']}] {m['value']}")

    else:
        _show_models_help()


def _show_models_help() -> None:
    print("用法: python -m agents models list [category]|info <name>|check <workflow_name>")
```

**main() 中新增路由：**
```python
    if command == "models":
        _run_models()
        return
```

**help 中新增说明：**
```python
    ("models", "模型管理（list / info / check）"),
```

**验证:**
```bash
python -m agents models list              # 按类型分组列出
python -m agents models info knives_sdxl  # 单个模型详情
python -m agents models check workflow_knives_lora_sdxl  # workflow 模型检查
```

---

## Task 3: AGENTS.md 更新 + 提交

**AGENTS.md 改动：**
- 版本 V0.8.0 → V0.9.0
- 核心能力表加一行模型管理
- 项目结构更新
- Verification Checklist 追加

---

## 验证清单

- [ ] `python -c "from agents.model_manager import list_models, get_model_info, check_workflow_models; print('ok')"`
- [ ] `python -m agents models list` → 按类型列出模型（ComfyUI 未运行时友好提示）
- [ ] `python -m agents models info <name>` → 显示详情
- [ ] `python -m agents models check <workflow>` → 检查模型依赖
- [ ] `python -m agents --help` → 显示 models 子命令
