# V0.11.0 — 输出管理深度集成 实现方案

> **Goal:** 每个出图命令（run/lora/ipa/multi/flux）提交后自动等待出图、归档到 `outputs/`，留下结构化 metadata.json。
>
> **Architecture:** 在 `output_manager.py` 新增 `save_workflow_outputs()`，各脚本在 submit 后调用它。每脚本改动 3-5 行。
>
> **Tech Stack:** Python, `wait_images()`, `resolve_comfy_root()`

---

## 用户可见效果

之前：
```
python -m agents lora "白色连衣裙"  →  只 print，产出在 ComfyUI/output/
```

之后：
```
python -m agents lora --dry-run "白色连衣裙"  →  [dry-run] 跳过
python -m agents lora "白色连衣裙"  →  提交 + 等待 + output_manager 归档
    📁 产出已保存: outputs/2026-07-12_143022-lora/
    ├── metadata.json   (prompt, seed, lora_name, character, timestamp)
    └── images/         (knives_lora_sdxl_batch_01_xxx.png)
```

`python -m agents outputs list` 就能列出所有历史产出。

---

## 新增函数

在 `agents/output_manager.py` 添加：

```python
def save_workflow_outputs(
    prompt_id: str,
    comfy_base: str,
    command: str,
    metadata_extra: dict | None = None,
) -> str | None:
    """等待 ComfyUI 出图 → 保存到 outputs/。

    从 comfy_utils 取 wait_images() 和 resolve_comfy_root()。
    在 dry-run 模式下 prompt_id="dry-run" 时跳过等待。

    Args:
        prompt_id: comfy_post_prompt 返回的 prompt_id
        comfy_base: ComfyUI 基础 URL（如 http://127.0.0.1:8188）
        command: 命令名（run/lora/ipa/multi/flux）
        metadata_extra: 附加元数据（prompt/seed/params 等）

    Returns:
        run_id 或 None
    """
    from comfy_utils import resolve_comfy_root, wait_images

    if prompt_id == "dry-run":
        return None

    try:
        images = wait_images(prompt_id, comfy_base)
    except (TimeoutError, RuntimeError) as exc:
        print(f"[warn] 等待出图失败: {exc}", file=sys.stderr)
        return None

    if not images:
        return None

    comfy_root = resolve_comfy_root()
    image_paths: list[str] = []
    for sub, name in images:
        path = (comfy_root / "output" / sub / name).resolve()
        if path.is_file():
            image_paths.append(str(path))

    if not image_paths:
        return None

    meta = dict(metadata_extra or {})
    meta["prompt_id"] = prompt_id
    return save_run(command, image_paths, meta)
```

---

## 各脚本改动

### run.py（不改，因为它是纯提交不等待，seed 来自 random）

看 `run.py` 结构：
- 第 58-62 行：`comfy_post_prompt(workflow)` 返回结果
- 没有捕获 prompt_id，不等待出图

改动：捕获 prompt_id，调用 `save_workflow_outputs`。

```python
# 第 58-62 行改为：
    result = comfy_post_prompt(workflow, prompt_url=COMFY_URL)
    prompt_id = result.get("prompt_id", "")
    if prompt_id:
        from output_manager import save_workflow_outputs
        save_workflow_outputs(prompt_id, comfy_base_url(COMFY_URL), "run", {
            "prompt": positive_prompt,
            "negative": negative_prompt,
            "seed": workflow["3"]["inputs"]["seed"],
        })
```

### go_knives_lora.py

submit() 在第 149-152 行，已被 `go_knives_ipadapter.py` 等调用。

改动：在 `submit()` 之后添加归档，或在 main() 中添加（不影响 batch 模式已有的 `copy_outputs`）。

```python
# 在 main() 的 submit(workflow) 之后（约第 324 行）加：
    prompt_id = submit(workflow)
    if prompt_id and count <= 1:
        from output_manager import save_workflow_outputs
        save_workflow_outputs(prompt_id, comfy_base_url(COMFY_URL), "lora", {
            "prompt": positive,
            "negative": negative,
            "seed": seed_value,
            "lora": lora_name,
            "lora_strength": strength,
            "character": args.character,
        })
```

### go_knives_ipadapter.py

submit() 在第 49-51 行。main() 中第 159-163 行调用。

```python
# 第 159-163 行改为：
    result = submit(workflow)  # 改 submit 返回 prompt_id
    if result:
        from output_manager import save_workflow_outputs
        save_workflow_outputs(result, comfy_base_url(COMFY_URL), "ipa", {
            "prompt": positive,
            "reference": args.ref_image,
            "ipa_weight": args.ipa_weight,
            "lora": args.lora,
        })
```

### go_multi_char_lora.py

第 129-132 行：`comfy_post_prompt(wf)` 直接调用。

```python
# 第 129-132 行改为：
    result = comfy_post_prompt(wf, prompt_url=COMFY_URL)
    prompt_id = result.get("prompt_id", "")
    if prompt_id:
        from output_manager import save_workflow_outputs
        save_workflow_outputs(prompt_id, comfy_base_url(COMFY_URL), "multi", {
            "prompt": positive,
            "negative": negative,
            "knives_lora": args.knives_lora,
            "caster_lora": args.caster_lora,
        })
```

### go_flux.py

第 148-152 行已经有 prompt_id 捕获。

```python
# 在 print 之前加：
    if prompt_id and prompt_id != "dry-run":
        from output_manager import save_workflow_outputs
        from comfy_utils import comfy_base_url
        save_workflow_outputs(prompt_id, comfy_base_url(COMFY_URL), "flux", {
            "prompt": positive,
            "seed": seed_actual,
            "model": args.model,
            "lora": args.lora,
            "lora_strength": args.lora_strength,
        })
```

---

## 文件改动清单

| 操作 | 文件 | 说明 |
|------|------|------|
| Modify | `agents/output_manager.py` | +`save_workflow_outputs()` |
| Modify | `agents/run.py` | 提交后归档 |
| Modify | `agents/go_knives_lora.py` | 提交后归档 |
| Modify | `agents/go_knives_ipadapter.py` | submit() 返回 prompt_id + 归档 |
| Modify | `agents/go_multi_char_lora.py` | 提交后归档 |
| Modify | `agents/go_flux.py` | 提交后归档 |
| Modify | `AGENTS.md` | 版本 V0.11.0 + 更新 |

---

## Task 1: output_manager.py — +save_workflow_outputs

**验证:**
```bash
python -c "
from agents.output_manager import save_workflow_outputs
# dry-run 模式：prompt_id='dry-run' 时返回 None
result = save_workflow_outputs('dry-run', 'http://127.0.0.1:8188', 'test')
print(f'dry-run result: {result}')
# 注意：真实 ComfyUI prompt_id 需要 ComfyUI 运行
"
```

---

## Task 2-6: 各脚本改动

每个脚本改动模式相同。验证方式：
```bash
python -m agents run --dry-run "test"          # 不归档（dry-run 跳过）
python -m agents lora --dry-run "test"         # 不归档
python -m agents ipa --dry-run "test"          # 不归档
python -m agents multi --dry-run "test"         # 不归档
python -m agents flux --dry-run "test"          # 不归档
```

有 ComfyUI 时：
```bash
python -m agents flux "test"                   # 提交 → 等待 → 归档到 outputs/
python -m agents outputs list                    # 看到新产出
python -m agents outputs show <run_id>           # metadata 完整
```

---

## Task 7: AGENTS.md + commit

**AGENTS.md：**
- 版本 V0.10.0 → V0.11.0
- 产出管理说明更新（自动归档）
- Verification Checklist 追加

---

## 验证清单

- [ ] `python -c "from agents.output_manager import save_workflow_outputs; print('ok')"`
- [ ] `python -m agents run --dry-run "test"` → 不归档
- [ ] `python -m agents lora --dry-run "test"` → 不归档
- [ ] `python -m agents ipa --dry-run "test"` → 不归档
- [ ] `python -m agents multi --dry-run "test"` → 不归档
- [ ] `python -m agents flux --dry-run "test"` → 不归档
- [ ] 有 ComfyUI 时 `python -m agents flux "test"` → 产出出现在 `outputs/` + `outputs list` 可见
