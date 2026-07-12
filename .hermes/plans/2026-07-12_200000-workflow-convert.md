# V0.19.0 — workflow API 格式转换 实现方案

> **Goal:** `python -m agents workflow convert <name>` — 将 UI 格式 workflow 转为 API 格式，让 workflows/ 下所有 JSON 都能被 CLI 提交。
>
> **Architecture:** 在 `workflow_manager.py` 新增 `convert_to_api()`，利用 ComfyUI `/object_info` 解析节点输入结构。
>
> **Reference:** `comfyui` skill 的 `references/manual-api-workflow.md`

---

## 用户交互

```
python -m agents workflow convert Flux.2+Klein+身份一致性引导+单图工作流
python -m agents workflow convert galgame_heroine_gacha_sdxl --output my_workflow.json
```

## 转换原理

UI 格式:
```json
{
  "nodes": [
    {"id": 1, "type": "KSampler", "widgets_values": [42, 20, 7.0, "euler", "normal"]},
    {"id": 2, "type": "CLIPTextEncode", "widgets_values": ["a cat"]}
  ],
  "links": [
    [0, 2, 0, 5, 0, "model"],  // link_id=0, from_node=2, from_slot=0, to_node=5, to_slot=0
  ]
}
```

API 格式:
```json
{
  "1": {"class_type": "KSampler", "inputs": {"seed": 42, "steps": 20, "cfg": 7.0}},
  "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "a cat"}}
}
```

**转换步骤：**
1. 从 ComfyUI `/object_info` 获取每个节点的输入结构
2. 将 `widgets_values[]` 按索引映射到对应输入名
3. 将 `inputs` 连接槽通过 `links` 数组转为 `["node_id", output_index]` 引用
4. 输出 API 格式 JSON

---

## 文件改动清单

| 操作 | 文件 | 说明 |
|------|------|------|
| Modify | `agents/workflow_manager.py` | +`convert_to_api()` 函数 |
| Modify | `agents/__main__.py` | `_run_workflow()` 加 `convert` action |
| Modify | `AGENTS.md` | 版本 V0.19.0 |

---

## Task 1: workflow_manager.py — +convert_to_api()

**核心逻辑:**

```python
def convert_to_api(
    name: str,
    *,
    comfy_url: str | None = None,
    output_path: str | None = None,
) -> dict | None:
    """将 UI 格式 workflow 转为 API 格式。

    Args:
        name: workflow 名称
        comfy_url: ComfyUI URL（用于 /object_info 查询节点结构）
        output_path: 输出路径（默认覆盖原文件）

    Returns:
        API 格式 workflow dict，或 None 表示失败
    """
    from comfy_utils import comfy_base_url
    import requests

    base = comfy_base_url(comfy_url)

    # 1. 加载 UI 格式 workflow
    wf_path = _find_ui_workflow_path(name)
    if wf_path is None:
        print(f"未找到 workflow: {name}", file=sys.stderr)
        return None

    with open(wf_path, encoding="utf-8") as f:
        data = json.load(f)

    nodes = data.get("nodes", [])
    links = data.get("links", [])

    if not nodes:
        print(f"workflow 没有 nodes 数组（可能已经是 API 格式）", file=sys.stderr)
        return None

    # 2. 获取节点输入结构
    try:
        r = requests.get(f"{base}/object_info", timeout=10)
        if r.status_code == 200:
            object_info = r.json()
        else:
            object_info = _NODE_CATALOG  # 使用内置备用目录
    except Exception:
        object_info = _NODE_CATALOG
        print("[warn] ComfyUI 未运行，使用内置节点目录（可能不完整）", file=sys.stderr)

    # 3. 构建 link 映射: (to_node, to_slot) → (from_node, from_slot)
    link_map = {}
    for link in links:
        if len(link) >= 6:
            link_id, from_node, from_slot, to_node, to_slot = link[:5]
            link_map[(str(to_node), str(to_slot))] = (str(from_node), str(from_slot))

    # 4. 转换每个节点
    api_wf = {}
    for node in nodes:
        nid = str(node.get("id", ""))
        ntype = node.get("type", "")
        if not nid or not ntype:
            continue
        if ntype == "Reroute":
            continue  # 跳过 Reroute 节点

        widgets = node.get("widgets_values", [])
        node_inputs = node.get("inputs", [])

        inputs = {}

        # 获取节点输入定义
        node_def = object_info.get(ntype, {})
        required_inputs = node_def.get("input", {}).get("required", {})
        optional_inputs = node_def.get("input", {}).get("optional", {})

        # 映射 widgets_values → 输入名
        widget_idx = 0
        for inp_name, inp_info in required_inputs.items():
            if widget_idx >= len(widgets):
                break
            # 检查这个输入是否是 "primary" widget（首个）
            # 从 object_info 可以知道输入类型
            inputs[inp_name] = widgets[widget_idx]
            widget_idx += 1

        # 映射连接
        for inp_name in list(required_inputs.keys()) + list(optional_inputs.keys()):
            link_key = (nid, str(node_inputs.index(inp_name))) if inp_name in node_inputs else None
            # 简化：从 node 的 inputs 数组和 links 推断连接
            for slot_idx, conn in enumerate(node.get("inputs", [])):
                if isinstance(conn, dict) and conn.get("name") == inp_name:
                    link_key = (nid, str(slot_idx))
                    break

            if link_key and link_key in link_map:
                from_nid, from_slot = link_map[link_key]
                inputs[inp_name] = [from_nid, int(from_slot)]
            elif inp_name not in inputs:
                # 使用默认值
                if inp_name in required_inputs:
                    default = _get_default(inp_name, required_inputs[inp_name])
                    if default is not None:
                        inputs[inp_name] = default

        api_wf[nid] = {"class_type": ntype, "inputs": inputs}

    # 5. 保存
    if output_path:
        out = Path(output_path)
    else:
        stem = Path(wf_path).stem
        out = Path(wf_path).parent / f"{stem}_api.json"

    out.write_text(json.dumps(api_wf, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ API 格式已保存: {out}")
    print(f"   节点数: {len(api_wf)}")

    return api_wf
```

实际上，由于 `/object_info` 提供了完整的输入结构，转换可以更精确。让我重新设计：

```python
def convert_to_api(name, *, comfy_url=None, output_path=None):
    """将 UI 格式 workflow 转为 API 格式。"""
    # ... (加载 + 解析)
    
    # 对每个节点：
    for node in nodes:
        nid = str(node["id"])
        ntype = node["type"]
        
        api_node = {"class_type": ntype, "inputs": {}}
        
        # 从 object_info 获取该节点的输入定义
        info = object_info.get(ntype, {})
        inp_defs = info.get("input", {}).get("required", {})
        
        # widget_values 按输入定义顺序映射
        # object_info 的输入顺序就是 widgets 的顺序
        widget_idx = 0
        for inp_name, inp_config in inp_defs.items():
            if widget_idx < len(widgets):
                api_node["inputs"][inp_name] = widgets[widget_idx]
                widget_idx += 1
        
        # 处理连接（从 links 表）
        for slot_idx, inp_slot in enumerate(node.get("inputs", [])):
            if isinstance(inp_slot, dict) and "name" in inp_slot:
                inp_name = inp_slot["name"]
                # 查找这个槽对应的 link
                link_key = (nid, slot_idx)
                if link_key in link_map:
                    from_id, from_slot = link_map[link_key]
                    api_node["inputs"][inp_name] = [from_id, from_slot]
        
        if ntype != "Reroute":
            api_wf[nid] = api_node
    
    # 保存
    ...
```

**验证:**
```bash
python -m agents workflow convert galgame_heroine_gacha_sdxl
# → 生成 galgame_heroine_gacha_sdxl_api.json
```

---

## Task 2: __main__.py — workflow convert

```python
# 在 _run_workflow() 的 action == "check" 之后加:
    elif action == "convert":
        if len(sys.argv) < 4:
            print("用法: python -m agents workflow convert <name>")
            return
        from agents.workflow_manager import convert_to_api
        name = sys.argv[3]
        output = sys.argv[5] if len(sys.argv) > 5 and sys.argv[4] == "--output" else None
        convert_to_api(name, output_path=output)

# _show_workflow_help() 加 convert
```

---

## Task 3: AGENTS.md + commit

- 版本 V0.18.0 → V0.19.0
- Checklist 追加

---

## 验证清单

- [ ] `python -m agents workflow convert <name>` 将 UI 格式转为 API 格式
- [ ] 生成的 API 格式可被 `workflow_manager.extract_schema()` 识别
- [ ] `python -m agents workflow convert <api_name>` 提示已是 API 格式
