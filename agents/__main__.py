#!/usr/bin/env python3
"""AIGC ComfyUI Pipeline — Unified CLI Entry Point.

Usage:
    python -m agents run [--raw] [prompt]
    python -m agents lora [--character knives|caster] [options] [prompt]
    python -m agents ipa [options] [prompt]
    python -m agents multi [options] [prompt]
    python -m agents flux [--model 9b|4b] [--lora <name>] [options] [prompt]
    python -m agents sweep --grid '{"steps":[20,30],"cfg":[1.0,2.0]}' [options] [prompt]
    python -m agents caption --dir <path> --trigger <name>
    python -m agents train --dir <path> --trigger <name>
    python -m agents report [--json]
    python -m agents queue list|clear|interrupt|free
    python -m agents gallery [--output FILE] [--serve]
    python -m agents doctor [--fix] [--json]
    python -m agents outputs list|show <id>|clean [--days N]
    python -m agents workflow list|show <name>|schema <name>|check <name>
    python -m agents models list [category]|info <name>|check <workflow_name>
    python -m agents check
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


def _run_check() -> None:
    """Check ComfyUI + Ollama health."""
    from agents import comfy_utils

    print("环境检查:")
    comfy_ok = comfy_utils.check_comfy_health()
    print(f"  ComfyUI ({comfy_utils.DEFAULT_COMFY_URL}): {'✅' if comfy_ok else '❌ 未连接'}")
    if not comfy_ok:
        print("    处理: 启动 ComfyUI 或检查环境变量 COMFY_URL")

    ollama_ok = comfy_utils.check_ollama_health()
    print(
        f"  Ollama  ({comfy_utils.DEFAULT_OLLAMA_URL}): "
        f"{'✅' if ollama_ok else '❌ 未连接（将自动降级到原始输入模式）'}"
    )


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
        print(f"\n{'名称':40s} {'节点':5s} {'API':5s}  类型")
        print("-" * 70)
        for w in wfs:
            api = "✅" if w["is_api_format"] else "❌"
            types = ", ".join(w["class_types"][:3])
            if len(w["class_types"]) > 3:
                types += f" ... (+{len(w['class_types'])-3})"
            print(f"{w['name']:40s} {w['node_count']:5d} {api:5s}  {types}")

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
            print("处理: 使用 ComfyUI Manager 或 `comfy node install` 安装对应自定义节点。")

    elif action == "convert":
        if len(sys.argv) < 4:
            print("用法: python -m agents workflow convert <name> [--output <path>]")
            return
        name = sys.argv[3]
        output = None
        if "--output" in sys.argv:
            idx = sys.argv.index("--output")
            if idx + 1 < len(sys.argv):
                output = sys.argv[idx + 1]
        from agents.workflow_manager import convert_to_api

        convert_to_api(name, output_path=output)

    else:
        _show_workflow_help()


def _show_workflow_help() -> None:
    print("用法: python -m agents workflow list|show <name>|schema <name>|check <name>|convert <name>")


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
            for m in models:
                print(f"  {m['name']:45s} {m['size_mb']:>6.1f}MB")
        else:
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

    elif action == "download":
        from agents.model_download import download_cli
        download_cli(sys.argv[3:])

    else:
        _show_models_help()


def _show_models_help() -> None:
    print("用法: python -m agents models list [category]|info <name>|check <workflow_name>|download <url>")


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

    # Bootstrap path early — needed for dry-run import and target script imports
    _bootstrap_agents_path()

    # 全局 --dry-run 处理
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        import comfy_utils as _cu

        _cu.DRY_RUN = True
        sys.argv.remove("--dry-run")

    # python -m agents → sys.argv = ['.../__main__.py']
    # python -m agents run ... → sys.argv = ['.../__main__.py', 'run', ...]
    command = sys.argv[1] if len(sys.argv) > 1 else ""

    if command in ("--version", "-V"):
        _show_version()
        return

    if command == "--help" or command == "-h":
        _show_help()
        return

    if command == "check":
        _run_check()
        return

    if command == "outputs":
        _run_outputs()
        return

    if command == "workflow":
        _run_workflow()
        return

    if command == "models":
        _run_models()
        return

    script_map = {
        "run": "run.py",
        "lora": "go_knives_lora.py",
        "ipa": "go_knives_ipadapter.py",
        "multi": "go_multi_char_lora.py",
        "flux": "go_flux.py",
        "sweep": "go_sweep.py",
        "caption": "go_caption.py",
        "train": "go_train.py",
        "report": "go_report.py",
        "queue": "go_queue.py",
        "gallery": "go_gallery.py",
        "doctor": "go_doctor.py",
    }

    if command not in script_map:
        print(f"未知命令: {command}\n")
        _show_help()
        sys.exit(1)

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
        elif command == "flux":
            from agents.go_flux import main as target_main
        elif command == "sweep":
            from agents.go_sweep import main as target_main
        elif command == "caption":
            from agents.go_caption import main as target_main
        elif command == "train":
            from agents.go_train import main as target_main
        elif command == "report":
            from agents.go_report import main as target_main
        elif command == "queue":
            from agents.go_queue import main as target_main
        elif command == "gallery":
            from agents.go_gallery import main as target_main
        elif command == "doctor":
            from agents.go_doctor import main as target_main
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
        ("flux", "Flux.2 Klein 文生图（9B/4B，支持 LoRA 注入）"),
        ("sweep", "参数网格扫描（Flux.2 Klein，自动对比拼图）"),
        ("caption", "Ollama VL 自动标图（训练数据准备）"),
        ("train", "LoRA 训练编排（数据验证 + AutoDL 命令生成）"),
        ("report", "管线验收报告（ComfyUI/模型/workflow/产出全貌）"),
        ("queue", "ComfyUI 队列管理（list/clear/interrupt/free）"),
        ("gallery", "输出画廊（HTML 产出展示）"),
        ("doctor", "一键诊断修复（环境/依赖/模型检查）"),
        ("check", "环境检查（ComfyUI / Ollama 连通性）"),
        ("workflow", "工作流模板管理（list / show / schema / check）"),
        ("models", "模型管理（list / info / check）"),
        ("outputs", "产出管理（list / show / clean）"),
    ]:
        print(f"  {name:12s}  {desc}")
    print()
    print("更多信息:  python -m agents <子命令> --help")
    print("        或阅读 AGENTS.md")


if __name__ == "__main__":
    main()
