# V0.7.0 — 管线健壮性 + 验证 实现方案

> **Goal:** 管线能可靠运行，ComfyUI/Ollama 断连自动降级，支持 dry-run 验证参数，实际跑通所有脚本。
>
> **Architecture:** 在 `comfy_utils.py` 加共享健康检查与降级函数，各脚本调用点替换为容错版本。`--dry-run` 通过模块级全局变量实现零侵入。
>
> **Tech Stack:** Python, requests, 全局 DRY_RUN 标志

---

## 详细设计

### 1. 健康检查

`comfy_utils.py` 新增：
- `check_comfy_health() → bool` — GET `/queue`，5s 超时
- `check_ollama_health() → bool` — GET `/api/tags`，5s 超时

`__main__.py` 新增子命令：
- `python -m agents check` — 检查 ComfyUI + Ollama，简洁输出 √/✗

### 2. Ollama 自动降级

`comfy_utils.py` 新增：
- `ollama_generate_or_fallback(prompt, fallback=None) → str` — 尝试 Ollama，失败则 warn + 返回 fallback 或原始 prompt

各脚本改动点（替换 `ollama_generate()` → `ollama_generate_or_fallback()`，去掉 try/except）：

| 脚本 | 函数 | 改动 |
|------|------|------|
| `run.py:17` | `call_llm()` | `ollama_generate()` → `ollama_generate_or_fallback()` |
| `run.py:47-50` | main() | 去掉 try/except RuntimeError 包装 |
| `go_knives_lora.py:123` | `call_llm_outfit()` | `ollama_generate()` → `ollama_generate_or_fallback()` |
| `go_knives_lora.py:270-276` | main() | 去掉 try/except RuntimeError |
| `go_knives_ipadapter.py:119-125` | main() | 去掉 try/except RuntimeError |
| `go_multi_char_lora.py:55` | `call_llm_scene()` | `ollama_generate()` → `ollama_generate_or_fallback()` |
| `go_multi_char_lora.py:97-102` | main() | 去掉 try/except RuntimeError |

### 3. `--dry-run` 模式

`comfy_utils.py` 新增模块级变量：
```python
DRY_RUN = False
```

`comfy_post_prompt()` 顶部加短路：
```python
def comfy_post_prompt(workflow, *, prompt_url=None, timeout=60):
    if DRY_RUN:
        print("[dry-run] 跳过 ComfyUI 提交（参数已就绪，可检查输出）")
        return {"prompt_id": "dry-run"}
    # ... existing
```

`wait_images()` 加短路：
```python
def wait_images(prompt_id, base, timeout_s=900.0):
    if prompt_id == "dry-run":
        return []
    # ... existing
```

`__main__.py` 添加全局 `--dry-run`：
```python
# In main(), after parsing command:
dry_run = "--dry-run" in sys.argv
if dry_run:
    from comfy_utils import DRY_RUN as _DRY_RUN_FLAG
    comfy_utils.DRY_RUN = True
    sys.argv.remove("--dry-run")  # don't pass to target
```

### 4. 管线验证

每个命令实际跑一轮（需本地 ComfyUI + Ollama 运行中）：
- `python -m agents check` → 显示 ComfyUI/Ollama 状态
- `python -m agents run --dry-run "test"` → 显示构建的 prompt
- `python -m agents lora --dry-run --character knives "test"` → 显示参数
- `python -m agents ipa --dry-run "test"` → 显示参数
- `python -m agents multi --dry-run "test"` → 显示参数

有 ComfyUI 时的全面验证在 AGENTS.md checklist 中记录。

---

## 文件改动清单

| 操作 | 文件 | 说明 |
|------|------|------|
| Modify | `agents/comfy_utils.py` | +health check + fallback + DRY_RUN |
| Modify | `agents/run.py` | call_llm 降级，去 try/except |
| Modify | `agents/go_knives_lora.py` | call_llm_outfit 降级，去 try/except |
| Modify | `agents/go_knives_ipadapter.py` | 去 Ollama 调用的 try/except |
| Modify | `agents/go_multi_char_lora.py` | call_llm_scene 降级，去 try/except |
| Modify | `agents/__main__.py` | +check 子命令 +--dry-run |
| Modify | `AGENTS.md` | 版本 V0.7.0 + 更新 |

---

## Task 1: comfy_utils.py — 健康检查 + 降级 + DRY_RUN

**Objective:** 新增 3 个函数 + 1 个模块级标志，零侵入现有调用

**Files:**
- Modify: `agents/comfy_utils.py`

**新增函数:**

```python
DRY_RUN = False

def check_comfy_health(prompt_url: str | None = None) -> bool:
    """Check if ComfyUI is reachable and ready. Returns True if healthy."""
    base = comfy_base_url(prompt_url)
    try:
        r = requests.get(f"{base}/queue", timeout=5)
        return r.status_code == 200
    except requests.RequestException:
        return False


def check_ollama_health(url: str | None = None) -> bool:
    """Check if Ollama is reachable. Returns True if healthy."""
    ollama_url = url or DEFAULT_OLLAMA_URL
    base = ollama_url.rstrip("/api/generate").rstrip("/")
    try:
        r = requests.get(f"{base}/api/tags", timeout=5)
        return r.status_code == 200
    except requests.RequestException:
        return False


def ollama_generate_or_fallback(
    prompt: str,
    *,
    url: str | None = None,
    model: str | None = None,
    timeout: float = 120,
    fallback: str | None = None,
) -> str:
    """尝试 Ollama，不可用时 warn + 返回 fallback/原始 prompt。"""
    try:
        return ollama_generate(prompt, url=url, model=model, timeout=timeout)
    except (RuntimeError, requests.RequestException) as exc:
        print(f"[warn] Ollama 不可用，使用原始输入。{exc}", file=sys.stderr)
        return fallback if fallback is not None else prompt
```

**`comfy_post_prompt()` 修改 — 开头加：**

```python
def comfy_post_prompt(workflow, *, prompt_url=None, timeout=60):
    if DRY_RUN:
        print("[dry-run] 跳过 ComfyUI 提交（参数已就绪）")
        return {"prompt_id": "dry-run"}
    # ... rest unchanged
```

**`wait_images()` 修改 — 开头加：**

```python
def wait_images(prompt_id, base, timeout_s=900.0):
    if prompt_id == "dry-run":
        return []
    # ... rest unchanged
```

**验证:**
```bash
python -c "
from comfy_utils import check_comfy_health, check_ollama_health, DRY_RUN, comfy_post_prompt, wait_images
# 健康检查（预期 False，本环境没跑 ComfyUI）
print('ComfyUI:', check_comfy_health())
print('Ollama:', check_ollama_health())
# DRY_RUN
DRY_RUN = True
result = comfy_post_prompt({})
print('DRY:', result)
imgs = wait_images('dry-run', '')
print('DRY imgs:', imgs)
"
```

---

## Task 2: run.py — Ollama 降级

**Objective:** Ollama 断连时自动 fallback 到原始输入

**Files:**
- Modify: `agents/run.py`

**第 8 行 import 追加：**
```python
from comfy_utils import AGENTS_DIR, bootstrap_agents_path, comfy_post_prompt, ollama_generate_or_fallback
```

**第 17-18 行 `call_llm()` 改为：**
```python
def call_llm(prompt: str) -> str:
    return ollama_generate_or_fallback(f"把用户输入转换成SDXL提示词：{prompt}", fallback=prompt)
```

**第 46-51 行 main() 的 try/except 改为简单赋值：**
```python
    # 去掉 try/except RuntimeError，降级已在 call_llm 内部处理
    positive_prompt = user if args.raw else call_llm(user)
```

**验证:**
```bash
# --dry-run 验证参数透传
python -m agents run --dry-run "test" 2>&1
# 预期: [dry-run] 跳过... 正向提示词：test
```

---

## Task 3: go_knives_lora.py — Ollama 降级

**Objective:** call_llm_outfit 在 Ollama 断连时返回 raw input

**Files:**
- Modify: `agents/go_knives_lora.py`

**Import 行追加 ollama_generate_or_fallback：**
```python
from comfy_utils import (
    AGENTS_DIR, bootstrap_agents_path, comfy_base_url, comfy_post_prompt,
    ollama_generate_or_fallback, resolve_comfy_root, wait_images,
)
```
（替换 `ollama_generate` 为 `ollama_generate_or_fallback`）

**第 123 行 `call_llm_outfit()` 改为：**
```python
    text = ollama_generate_or_fallback(f"{system}\n\n用户描述：{user_text}", fallback=user_text)
```

**第 270-276 行 main() 的去 try/except RuntimeError：**
```python
    else:
        positive = build_positive(call_llm_outfit(user, char), char, args.pose, sdxl=use_sdxl)
```

**验证:**
```bash
python -m agents lora --dry-run --character knives "test" 2>&1
# 预期: [warn] Ollama 不可用... 正向：masterpiece, best quality...test...
```

---

## Task 4: go_knives_ipadapter.py — Ollama 降级

**Objective:** ipa 脚本同样去掉 try/except RuntimeError

**Files:**
- Modify: `agents/go_knives_ipadapter.py`

**第 119-125 行改为直接调用（去掉 try/except）：**
```python
    else:
        outfit_tags = call_llm_outfit(user, _KNIVES)
        positive = build_positive(outfit_tags, _KNIVES, args.pose, sdxl=True)
```
（call_llm_outfit 已在 Task 3 中降级，ipadapter 复用它）

**验证:**
```bash
python -m agents ipa --dry-run "test" 2>&1
```

---

## Task 5: go_multi_char_lora.py — Ollama 降级

**Objective:** call_llm_scene 降级 + 去 try/except

**Files:**
- Modify: `agents/go_multi_char_lora.py`

**Import 行追加 ollama_generate_or_fallback：**
```python
from comfy_utils import AGENTS_DIR, bootstrap_agents_path, comfy_post_prompt, ollama_generate_or_fallback
```
（替换 `ollama_generate`）

**第 55 行 `call_llm_scene()` 改为：**
```python
    text = ollama_generate_or_fallback(f"{system}\n\n用户描述：{user_text}", fallback=user_text).strip().replace("\n", ", ")
```

**第 97-102 行 main() 的去 try/except RuntimeError：**
```python
    else:
        positive = call_llm_scene(user)
```

**验证:**
```bash
python -m agents multi --dry-run "Knives校服在左，Caster在右" 2>&1
```

---

## Task 6: __main__.py — check 子命令 + --dry-run

**Objective:** `python -m agents check` + 全局 `--dry-run`

**Files:**
- Modify: `agents/__main__.py`

**新增 `_run_check()` 函数：**
```python
def _run_check() -> None:
    """Check ComfyUI + Ollama health."""
    from agents.comfy_utils import check_comfy_health, check_ollama_health, DEFAULT_COMFY_URL, DEFAULT_OLLAMA_URL
    
    print("环境检查:")
    comfy_ok = check_comfy_health()
    print(f"  ComfyUI ({DEFAULT_COMFY_URL}): {'✅' if comfy_ok else '❌ 未连接'}")
    if not comfy_ok:
        print("    处理: 启动 ComfyUI 或检查环境变量 COMFY_URL")
    
    ollama_ok = check_ollama_health()
    print(f"  Ollama  ({DEFAULT_OLLAMA_URL}): {'✅' if ollama_ok else '❌ 未连接（将自动降级到 --raw 模式）'}")
```

**main() 开头加 `--dry-run` 处理：**
```python
def main() -> None:
    # 全局 --dry-run 处理
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        import comfy_utils
        comfy_utils.DRY_RUN = True
        sys.argv.remove("--dry-run")
    
    # ... existing code, plus:
    if command == "check":
        _run_check()
        return
```

**`_show_help()` 加 check 子命令说明。**

**验证:**
```bash
python -m agents check
# 预期: ComfyUI: ❌, Ollama: ❌

python -m agents check --help
# 预期: 显示用法
```

---

## Task 7: 更新 AGENTS.md + 提交

**Objective:** 版本 V0.7.0 + 新增 check/dry-run 说明

**AGENTS.md 改动：**
- 版本 V0.6.0 → V0.7.0，V0.6.0 变为上一版
- 核心能力表加一行 check/dry-run
- Verification Checklist 追加 health check + dry-run 验证项

**提交:**
```bash
cd /c/Users/zwq/aigc-comfy-pipeline
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
git add -A
git commit -m "feat: V0.7.0 管线健壮性 + 验证

- comfy_utils.py: check_comfy_health / check_ollama_health
- comfy_utils.py: ollama_generate_or_fallback 自动降级
- comfy_utils.py: DRY_RUN 全局标志（零侵入）
- python -m agents check 健康检查子命令
- python -m agents --dry-run 跳过 ComfyUI 提交
- 4 个脚本 Ollama 断连自动降级（去掉 try/except RuntimeError）
- 完全向后兼容"
git push origin main
```

---

## 验证清单

- [ ] `python -c "from comfy_utils import check_comfy_health, check_ollama_health, DRY_RUN; print('ok')"` → ok
- [ ] `python -m agents check` → 显示 ComfyUI/Ollama 状态
- [ ] `python -m agents run --dry-run "test"` → [dry-run] 跳过，正向提示词显示
- [ ] `python -m agents lora --dry-run --character knives "test"` → 参数可见
- [ ] `python -m agents ipa --dry-run "test"` → 参数可见
- [ ] `python -m agents multi --dry-run "test"` → 参数可见
- [ ] 无 ComfyUI 时运行不崩溃（应有 warn 而不是 traceback）
- [ ] AGENTS.md 版本已更新
