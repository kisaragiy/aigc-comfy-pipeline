# V0.15.0 — ComfyUI 队列管理 实现方案

> **Goal:** `python -m agents queue list|clear|interrupt|free` — 管理 ComfyUI 队列和显存
>
> **Architecture:** 新建 `agents/go_queue.py`，调用 ComfyUI REST API
>
> **Endpoints:**
> - `GET /queue` — 队列状态
> - `POST /queue {"clear": true}` — 清空待处理
> - `POST /interrupt` — 中断当前任务
> - `POST /free {"unload_models": true, "free_memory": true}` — 释放显存
>
> **Reference:** `comfyui-api` skill 的 Queue & System Management 节

---

## 用户交互

```
python -m agents queue list         # 查看队列状态
python -m agents queue clear        # 清空待处理队列
python -m agents queue interrupt    # 中断当前运行任务
python -m agents queue free         # 释放显存（卸载模型）
python -m agents queue free --all   # 强制释放所有
```

## 输出示例

```
$ python -m agents queue list

ComfyUI 队列状态:
  运行中: 1
  待处理: 3

  正在运行:
    [job_1] Flux.2 Klein, 步骤 12/20

  待处理:
    [job_2] SDXL LoRA — 白色连衣裙
    [job_3] IPAdapter 锁脸
```

---

## 文件改动清单

| 操作 | 文件 | 说明 |
|------|------|------|
| Create | `agents/go_queue.py` | 队列管理 |
| Modify | `agents/__main__.py` | +`queue` 子命令 |
| Modify | `AGENTS.md` | 版本 V0.15.0 |

---

## Task 1: 创建 go_queue.py

**核心函数:**

```python
import json, requests
from comfy_utils import comfy_base_url

BASE = comfy_base_url()


def get_queue() -> dict:
    """获取队列状态。"""
    r = requests.get(f"{BASE}/queue", timeout=5)
    r.raise_for_status()
    return r.json()


def clear_queue() -> bool:
    """清空待处理队列。"""
    r = requests.post(f"{BASE}/queue", json={"clear": True}, timeout=5)
    return r.status_code == 200


def interrupt() -> bool:
    """中断当前运行任务。"""
    r = requests.post(f"{BASE}/interrupt", timeout=5)
    return r.status_code == 200


def free_memory(unload_models: bool = True, free_memory: bool = True) -> bool:
    """释放显存。"""
    r = requests.post(f"{BASE}/free",
        json={"unload_models": unload_models, "free_memory": free_memory},
        timeout=10)
    return r.status_code == 200
```

**CLI main():**

```python
def main() -> None:
    import argparse, sys
    from comfy_utils import check_comfy_health

    parser = argparse.ArgumentParser(description="ComfyUI 队列管理")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("list", help="查看队列状态")
    sub.add_parser("clear", help="清空待处理队列")
    sub.add_parser("interrupt", help="中断当前任务")
    p_free = sub.add_parser("free", help="释放显存")
    p_free.add_argument("--all", action="store_true", help="强制释放所有")
    args = parser.parse_args()

    if not check_comfy_health():
        print("ComfyUI 未运行。", file=sys.stderr)
        sys.exit(1)

    if args.action == "list":
        _do_list()
    elif args.action == "clear":
        _do_clear()
    elif args.action == "interrupt":
        _do_interrupt()
    elif args.action == "free":
        _do_free(unload_all=args.all)
```

**验证:**
```bash
python -m agents queue list          # ComfyUI 离线时友好提示
python -m agents queue clear
python -m agents queue interrupt
python -m agents queue free
```

---

## Task 2: __main__.py — +queue 子命令

```python
# script_map 加:
"queue": "go_queue.py",

# elif 加:
elif command == "queue":
    from agents.go_queue import main as target_main

# _show_help() 加:
("queue", "ComfyUI 队列管理（list/clear/interrupt/free）"),
```

---

## Task 3: AGENTS.md + commit

- 版本 V0.14.0 → V0.15.0
- Checklist 追加

---

## 验证清单

- [ ] `python -m agents queue list` ComfyUI 离线时友好提示
- [ ] `python -m agents queue --help` 显示 4 个子命令
- [ ] `python -m agents --help` 显示 queue 子命令
