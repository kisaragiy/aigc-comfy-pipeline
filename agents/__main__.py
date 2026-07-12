#!/usr/bin/env python3
"""AIGC ComfyUI Pipeline — Unified CLI Entry Point.

Usage:
    python -m agents run [--raw] [prompt]
    python -m agents lora [--character knives|caster] [options] [prompt]
    python -m agents ipa [options] [prompt]
    python -m agents multi [options] [prompt]
    python -m agents outputs list|show <id>|clean [--days N]
    python -m agents --version
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _bootstrap_agents_path() -> None:
    """Add agents/ to sys.path so target scripts can find comfy_utils."""
    root = str(HERE)
    if root not in sys.path:
        sys.path.insert(0, root)


def _show_version() -> None:
    from agents import __version__

    print(f"AIGC ComfyUI Pipeline v{__version__}")


def _run_outputs() -> None:
    """Handle 'outputs list|show|clean' subcommands."""
    from agents.output_manager import clean_runs, list_runs, show_run

    if len(sys.argv) < 3:
        print("用法: python -m agents outputs list|show <id>|clean [--days N]")
        return

    action = sys.argv[2]

    if action == "list":
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

    elif action == "show":
        if len(sys.argv) < 4:
            print("用法: python -m agents outputs show <run_id>")
            return
        run_id = sys.argv[3]
        meta = show_run(run_id)
        if meta is None:
            print(f"未找到产出: {run_id}")
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

    elif action == "clean":
        days = 30
        if "--days" in sys.argv:
            idx = sys.argv.index("--days")
            if idx + 1 < len(sys.argv):
                try:
                    days = int(sys.argv[idx + 1])
                except ValueError:
                    pass
        n = clean_runs(days=days)
        print(f"已清理 {n} 个旧产出目录。")

    else:
        print(f"未知的 outputs 子命令: {action}")
        print("可用: list, show <id>, clean [--days N]")
        sys.exit(1)


def main() -> None:
    if len(sys.argv) < 2:
        _show_help()
        return

    # python -m agents → sys.argv = ['.../__main__.py']
    # python -m agents run ... → sys.argv = ['.../__main__.py', 'run', ...]
    command = sys.argv[1] if len(sys.argv) > 1 else ""

    if command in ("--version", "-V"):
        _show_version()
        return

    if command == "--help" or command == "-h":
        _show_help()
        return

    if command == "outputs":
        _run_outputs()
        return

    script_map = {
        "run": "run.py",
        "lora": "go_knives_lora.py",
        "ipa": "go_knives_ipadapter.py",
        "multi": "go_multi_char_lora.py",
    }

    if command not in script_map:
        print(f"未知命令: {command}\n")
        _show_help()
        sys.exit(1)

    # Bootstrap path BEFORE importing target modules (they use from comfy_utils import ...)
    _bootstrap_agents_path()

    # Rebuild argv so the target script sees its own args
    # python -m agents run --raw "prompt"
    #   → sys.argv = ['agents/run.py', '--raw', 'prompt']
    script_path = str(HERE / script_map[command])
    new_argv = [script_path] + sys.argv[2:]

    old_argv = sys.argv
    sys.argv = new_argv
    try:
        if command == "run":
            from agents.run import main as target_main
        elif command == "lora":
            from agents.go_knives_lora import main as target_main
        elif command == "ipa":
            from agents.go_knives_ipadapter import main as target_main
        elif command == "multi":
            from agents.go_multi_char_lora import main as target_main
        else:
            raise ValueError(f"Unknown command: {command}")
        target_main()
    finally:
        sys.argv = old_argv


def _show_help() -> None:
    print(__doc__.strip())
    print()
    print("子命令:")
    for name, desc in [
        ("run", "一句话提交 ComfyUI 文生图（自然语言 → Ollama → 出图）"),
        ("lora", "角色 LoRA 文生图（Knives / Caster，支持批量）"),
        ("ipa", "IPAdapter 锁脸文生图（参考图驱动面部一致性）"),
        ("multi", "多角色 LoRA 同图（Knives + Caster + FaceDetailer）"),
        ("outputs", "产出管理（list / show / clean）"),
    ]:
        print(f"  {name:12s}  {desc}")
    print()
    print("更多信息:  python -m agents <子命令> --help")
    print("        或阅读 AGENTS.md")


if __name__ == "__main__":
    main()
