# V0.6.0 — 统一 CLI + 输出管理 实现方案

> **Goal:** 提供统一的 `python -m agents` CLI 入口 + 结构化输出管理，让面试演示更专业
>
> **Architecture:** 在现有 scripts 上叠加轻量 CLI 层，不破坏向后兼容。新增 `output_manager.py` 管理输出元数据。
>
> **Tech Stack:** Python argparse (stdlib), JSON 元数据, 时间戳目录

---

## 详细设计

### 统一 CLI (`python -m agents <command>`)

```
python -m agents run "赛博朋克少女"          # → run.py
python -m agents lora --character knives ... # → go_knives_lora.py
python -m agents ipa --ref ref.png ...       # → go_knives_ipadapter.py
python -m agents multi "场景描述"            # → go_multi_char_lora.py
python -m agents outputs list                # 列出产出
python -m agents outputs show <id>           # 查看单次产出详情
```

`__main__.py` 做 arg 分派，保留原脚本的完整参数集。通过 `sys.argv` 透传保持零侵入。

### 输出管理

输出目录结构：
```
outputs/
  YYYY-MM-DD_HHMMSS-<command>/
    metadata.json     # 提示词、seed、参数、时间
    images/           # 出图副本（软链接或复制）
```

`output_manager.py`：
- `save_run(command, images, metadata)` → 创建目录、复制图片、写 metadata.json
- `list_runs()` → 按时间倒序列出所有产出
- `show_run(run_id)` → 打印单次 metadata
- `clean_runs(days)` → 清理 N 天前的产出

### 文件改动清单

| 操作 | 文件 | 说明 |
|------|------|------|
| Create | `agents/__init__.py` | 包标识，export version |
| Create | `agents/__main__.py` | 统一 CLI 入口，argparse 分派 |
| Create | `agents/output_manager.py` | 输出管理模块 |
| Modify | `AGENTS.md` | 更新版本至 V0.6.0，追加 CLI 用法 |

**不改动现有脚本**（保持向后兼容）。

---

## Task 1: 创建 agents/ 包结构

**Objective:** 把 agents/ 变成可运行的 Python package

**Files:**
- Create: `agents/__init__.py`
- Read (ref): `agents/comfy_utils.py` — 已有 `AGENTS_DIR`

**代码:**

```python
# agents/__init__.py
"""AIGC ComfyUI Pipeline — Python 编排 ComfyUI · LoRA 训练 · 批量生图 · 模型管理"""
from __future__ import annotations

__version__ = "0.6.0"
__all__ = ["__version__"]
```

**验证:**
```bash
cd /c/Users/zwq/aigc-comfy-pipeline
python -c "from agents import __version__; print(__version__)"
# 预期: 0.6.0
```

---

## Task 2: 创建 output_manager.py

**Objective:** 产出管理模块，保存结构化元数据

**Files:**
- Create: `agents/output_manager.py`

**代码:**

```python
"""产出管理 — 保存出图副本 + 结构化元数据。"""
from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# 默认产出目录（可被环境变量 AIGC_OUTPUT_DIR 覆盖）
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "outputs"


def _get_output_dir() -> Path:
    env = os.environ.get("AIGC_OUTPUT_DIR")
    if env:
        return Path(env).resolve()
    return DEFAULT_OUTPUT_DIR


def _make_run_dir(command: str) -> tuple[Path, str]:
    """创建带时间戳的产出目录，返回 (dir_path, run_id)。"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    run_id = f"{timestamp}-{command}"
    out_dir = _get_output_dir() / run_id
    img_dir = out_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    return out_dir, run_id


def save_run(
    command: str,
    image_paths: list[str | Path],
    metadata: dict[str, Any],
) -> str:
    """保存一次产出的副本与元数据。
    
    Args:
        command: 命令名称（如 'lora', 'ipa'）
        image_paths: 出图文件路径列表
        metadata: 元数据字典（prompt, seed, params 等）
    
    Returns:
        run_id: 产出标识（如 '2026-07-12_153022-lora'）
    """
    out_dir, run_id = _make_run_dir(command)
    img_dir = out_dir / "images"

    # 复制图片
    saved_images: list[str] = []
    for src_path in image_paths:
        src = Path(src_path)
        if not src.is_file():
            continue
        dst = img_dir / src.name
        shutil.copy2(src, dst)
        saved_images.append(str(dst.name))

    # 写 metadata
    meta = {
        "run_id": run_id,
        "command": command,
        "timestamp": datetime.now().isoformat(),
        "images": saved_images,
        "params": metadata,
    }
    (out_dir / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  📁 产出已保存: {out_dir}")
    return run_id


def list_runs() -> list[dict[str, Any]]:
    """按时间倒序列出所有产出。"""
    base = _get_output_dir()
    if not base.is_dir():
        return []
    runs = []
    for entry in sorted(base.iterdir(), key=lambda p: p.name, reverse=True):
        meta_file = entry / "metadata.json"
        if not meta_file.is_file():
            continue
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        runs.append(meta)
    return runs


def show_run(run_id: str) -> dict[str, Any] | None:
    """查看单次产出详情。"""
    base = _get_output_dir() / run_id
    meta_file = base / "metadata.json"
    if not meta_file.is_file():
        return None
    return json.loads(meta_file.read_text(encoding="utf-8"))


def clean_runs(days: int = 30) -> int:
    """清理 N 天前的产出目录。返回删除数。"""
    base = _get_output_dir()
    if not base.is_dir():
        return 0
    cutoff = time.time() - days * 86400
    removed = 0
    for entry in list(base.iterdir()):
        if not entry.is_dir():
            continue
        meta_file = entry / "metadata.json"
        if meta_file.is_file():
            mtime = meta_file.stat().st_mtime
        else:
            mtime = entry.stat().st_mtime
        if mtime < cutoff:
            shutil.rmtree(entry, ignore_errors=True)
            removed += 1
    return removed
```

**验证:**
```python
python -c "
from agents.output_manager import save_run, list_runs, show_run
# 模拟保存
import tempfile, pathlib
t = pathlib.Path(tempfile.mkstemp()[1])
t.write_text('mock')
rid = save_run('test', [str(t)], {'prompt': 'test', 'seed': 42})
print('run_id:', rid)
runs = list_runs()
print('runs:', len(runs))
meta = show_run(rid)
print('meta prompt:', meta['params']['prompt'])
t.unlink()
"
```

---

## Task 3: 创建 __main__.py — 统一 CLI

**Objective:** `python -m agents <command>` 统一入口

**Files:**
- Create: `agents/__main__.py`

**核心逻辑:**
- `python -m agents run "prompt"` → 转发到 `run.py` 的 main()
- `python -m agents lora --character knives ...` → 转发到 `go_knives_lora.py` 的 main()
- `python -m agents outputs list/show/clean` → 用 output_manager 处理
- 未知子命令 → 打印 help

**代码:**

```python
#!/usr/bin/env python3
"""AIGC ComfyUI Pipeline — Unified CLI Entry Point.

Usage:
    python -m agents run [--raw] [prompt]
    python -m agents lora [--character knives|caster] [options] [prompt]
    python -m agents ipa [options] [prompt]
    python -m agents multi [options] [prompt]
    python -m agents outputs list|show <id>|clean [--days N]
    python -m agents --help
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _run_outputs(args: argparse.Namespace) -> None:
    from agents.output_manager import clean_runs, list_runs, show_run

    if args.outputs_action == "list":
        runs = list_runs()
        if not runs:
            print("暂无产出记录。")
            return
        print(f"\n{'运行 ID':30s} {'命令':10s} {'时间':22s} {'图片':6s}")
        print("-" * 72)
        for r in runs:
            rid = r.get("run_id", "?")
            cmd = r.get("command", "?")
            ts = (r.get("timestamp") or "?")[:19]
            n = len(r.get("images", []))
            print(f"{rid:30s} {cmd:10s} {ts:22s} {n:6d}")

    elif args.outputs_action == "show":
        meta = show_run(args.run_id)
        if meta is None:
            print(f"未找到产出: {args.run_id}")
            sys.exit(1)
        print(f"\n运行 ID:   {meta.get('run_id', '?')}")
        print(f"命令:      {meta.get('command', '?')}")
        print(f"时间:      {(meta.get('timestamp') or '?')[:19]}")
        print(f"图片:      {', '.join(meta.get('images', [])) or '(无)'}")
        params = meta.get("params", {})
        if params:
            print("\n参数:")
            for k, v in params.items():
                print(f"  {k}: {v}")

    elif args.outputs_action == "clean":
        n = clean_runs(days=args.days)
        print(f"已清理 {n} 个旧产出目录。")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m agents",
        description="AIGC ComfyUI Pipeline — 统一 CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- run ---
    p_run = sub.add_parser("run", help="一句话提交 ComfyUI 文生图")
    p_run.add_argument("--raw", action="store_true", help="跳过 Ollama")
    p_run.add_argument("prompt", nargs="?", help="画面描述")

    # --- lora ---
    p_lora = sub.add_parser("lora", help="角色 LoRA 文生图")
    p_lora.add_argument("--character", choices=["knives", "caster"], default="knives")
    p_lora.add_argument("--raw", action="store_true")
    p_lora.add_argument("--full-raw", action="store_true")
    p_lora.add_argument("--positive", default=None)
    p_lora.add_argument("--negative", default=None)
    p_lora.add_argument("--lora", default=None)
    p_lora.add_argument("--lora-strength", type=float, default=None)
    p_lora.add_argument("--ckpt", default=None)
    p_lora.add_argument("--width", type=int, default=None)
    p_lora.add_argument("--height", type=int, default=None)
    p_lora.add_argument("--steps", type=int, default=None)
    p_lora.add_argument("--cfg", type=float, default=None)
    p_lora.add_argument("--count", type=int, default=1)
    p_lora.add_argument("--out", type=Path, default=None)
    p_lora.add_argument("--prefix", default=None)
    p_lora.add_argument("--sd15", action="store_true")
    p_lora.add_argument("--portrait", dest="portrait", action="store_true", default=None)
    p_lora.add_argument("--no-portrait", dest="portrait", action="store_false")
    p_lora.add_argument("--full-body", action="store_true")
    p_lora.add_argument("prompt", nargs="?", help="服装/场景描述")

    # --- ipa ---
    p_ipa = sub.add_parser("ipa", help="IPAdapter 锁脸文生图")
    p_ipa.add_argument("--ref-image", default="knives_face_ref.png")
    p_ipa.add_argument("--ipa-weight", type=float, default=0.48)
    p_ipa.add_argument("--ipa-end", type=float, default=1.0)
    p_ipa.add_argument("--ipa-preset", default="PLUS FACE (portraits)")
    p_ipa.add_argument("--weight-type", default="prompt is more important")
    p_ipa.add_argument("--raw", action="store_true")
    p_ipa.add_argument("--full-raw", action="store_true")
    p_ipa.add_argument("--positive", default=None)
    p_ipa.add_argument("--negative", default=None)
    p_ipa.add_argument("--lora", default="knives_sdxl.safetensors")
    p_ipa.add_argument("--lora-strength", type=float, default=0.85)
    p_ipa.add_argument("--ckpt", default=None)
    p_ipa.add_argument("--width", type=int, default=None)
    p_ipa.add_argument("--height", type=int, default=None)
    p_ipa.add_argument("--steps", type=int, default=None)
    p_ipa.add_argument("--cfg", type=float, default=None)
    p_ipa.add_argument("--prefix", default=None)
    p_ipa.add_argument("--portrait", action="store_true", default=True)
    p_ipa.add_argument("--full-body", action="store_true")
    p_ipa.add_argument("prompt", nargs="?")

    # --- multi ---
    p_multi = sub.add_parser("multi", help="多角色 LoRA 同图")
    p_multi.add_argument("--raw", action="store_true")
    p_multi.add_argument("--positive", default=None)
    p_multi.add_argument("--negative", default=None)
    p_multi.add_argument("--knives-lora", default="knives_sdxl.safetensors")
    p_multi.add_argument("--caster-lora", default="caster_sdxl.safetensors")
    p_multi.add_argument("--lora-strength", type=float, default=0.72)
    p_multi.add_argument("--width", type=int, default=1344)
    p_multi.add_argument("--height", type=int, default=896)
    p_multi.add_argument("--steps", type=int, default=32)
    p_multi.add_argument("--cfg", type=float, default=7.0)
    p_multi.add_argument("--prefix", default="multi_char_lora_sdxl")
    p_multi.add_argument("--no-face-detail", action="store_true")
    p_multi.add_argument("prompt", nargs="?")

    # --- outputs ---
    p_out = sub.add_parser("outputs", help="产出管理")
    p_out_sub = p_out.add_subparsers(dest="outputs_action", required=True)
    p_out_list = p_out_sub.add_parser("list", help="列出所有产出")
    p_out_show = p_out_sub.add_parser("show", help="查看单次产出")
    p_out_show.add_argument("run_id", help="运行 ID")
    p_out_clean = p_out_sub.add_parser("clean", help="清理旧产出")
    p_out_clean.add_argument("--days", type=int, default=30, help="保留天数")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "outputs":
        _run_outputs(args)
        return

    # 透传剩余参数到原脚本
    # python -m agents run "prompt" → python agents/run.py "prompt"
    # python -m agents lora --count 2 "desc" → python agents/go_knives_lora.py --count 2 "desc"
    script_map = {
        "run": "run.py",
        "lora": "go_knives_lora.py",
        "ipa": "go_knives_ipadapter.py",
        "multi": "go_multi_char_lora.py",
    }
    script_name = script_map[args.command]

    # 重建 argv: [脚本路径, ...剩余参数]
    new_argv = [str(HERE / script_name)] + sys.argv[2:]  # skip 'agents' and subcommand

    # Save old argv, patch, call, restore
    old_argv = sys.argv
    sys.argv = new_argv
    try:
        if args.command == "run":
            from agents.run import main as target_main
        elif args.command == "lora":
            from agents.go_knives_lora import main as target_main
        elif args.command == "ipa":
            from agents.go_knives_ipadapter import main as target_main
        elif args.command == "multi":
            from agents.go_multi_char_lora import main as target_main
        else:
            raise ValueError(f"Unknown command: {args.command}")
        target_main()
    finally:
        sys.argv = old_argv


if __name__ == "__main__":
    main()
```

**验证:**
```bash
cd /c/Users/zwq/aigc-comfy-pipeline
# help
python -m agents --help
python -m agents run --help
python -m agents lora --help
python -m agents outputs --help
python -m agents outputs list --help

# outputs 命令不需要 ComfyUI
python -m agents outputs list
python -m agents outputs clean --days 1
```

---

## Task 4: 更新 AGENTS.md

**Objective:** 版本号 V0.6.0，追加统一 CLI 用法

**Files:**
- Modify: `AGENTS.md`

改动：
1. 版本从 V0.5.0 → V0.6.0
2. "核心能力"表新增一列 "统一 CLI"
3. "如何工作"节追加 CLI 用法说明
4. "Verification Checklist" 追加 CLI 验证项

---

## Task 5: 提交

```bash
cd /c/Users/zwq/aigc-comfy-pipeline
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
git add -A
git commit -m "feat: V0.6.0 统一 CLI + 输出管理

- python -m agents 统一入口（run / lora / ipa / multi / outputs）
- agents/output_manager.py 结构化产出管理
- agents/__init__.py 包标识 + 版本
- 完全向后兼容，旧脚本不变"
git push origin main
```

---

## 验证清单

- [ ] `python -c "from agents import __version__; print(__version__)"` → 0.6.0
- [ ] `python -m agents --help` → 显示所有子命令
- [ ] `python -m agents lora --help` → 显示完整 LoRA 参数
- [ ] `python -m agents outputs list` → 无产出时显示"暂无产出记录"
- [ ] `python -m agents outputs clean --days 1` → 清理执行成功
- [ ] `python -m agents run "test"` → 尝试连接 ComfyUI（预期错误，说明调通了 run.py）
