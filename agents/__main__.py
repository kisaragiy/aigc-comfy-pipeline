#!/usr/bin/env python3
"""AIGC ComfyUI Pipeline — Unified CLI Entry Point.

Usage:
    python -m agents run [--raw] [prompt]
    python -m agents run --video [--ref img] [--frames N] [options] [prompt]
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
    python -m agents control --ref <image> --type depth|openpose|... [options] [prompt]
    python -m agents video [--frames N] [--fps N] [options] [prompt]
    python -m agents video-process <file> [--to-gif] [--trim ...] [--speed ...]
    python -m agents validate --image <path> [--prompt "text"]
    python -m agents abtest --prompts "A" "B" [--seed N]
    python -m agents bestof <prompt> --count N
    python -m agents serve [--port PORT]
    python -m agents outputs list|show <id> [--info]|clean [--days N]
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
        category = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else None
        no_cache = "--no-cache" in sys.argv
        show_disk = "--disk" in sys.argv
        models = list_models(category, no_cache=no_cache)
        if not models:
            msg = f"未找到 {category} 模型。" if category else "未找到模型。"
            print(msg)
            print("处理: 确认 ComfyUI 已安装模型到 COMFY_ROOT/models/ 目录下。")
            return

        if category:
            total = sum(m["size_mb"] for m in models)
            print(f"\n{category} 模型 ({len(models)} 个, {total:.0f}MB):")
            for m in models:
                disk_tag = f"  {m['size_mb']:>6.1f}MB" if show_disk else ""
                print(f"  {m['name']:45s}{disk_tag}")
        else:
            by_cat: dict[str, list] = {}
            for m in models:
                by_cat.setdefault(m["category"], []).append(m)
            total_all = sum(m["size_mb"] for m in models)
            print(f"\n共 {len(models)} 个模型 (合计 {total_all:.0f}MB):\n")
            for cat in sorted(by_cat):
                items = by_cat[cat]
                cat_total = sum(m["size_mb"] for m in items)
                cat_info = f"  [{cat_total:.0f}MB]" if show_disk else ""
                print(f"  📁 {cat} ({len(items)}) {cat_info}:")
                for m in items:
                    disk_tag = f"  {m['size_mb']:>7.1f}MB" if show_disk else ""
                    print(f"    {m['name']:45s}{disk_tag}")
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
        target = sys.argv[3]

        if target == "video":
            from agents.model_manager import check_video_models as _cvm

            result = _cvm()
            print(f"\n=== Wan2.2 视频模型完整性检查 ===\n")
            print(f"ComfyUI:  {result['all_found'] and '✅ 已连接' or '❌ 未连接'}")
            for f in result.get("found", []):
                mark = "✅" if f["ok"] else "⚠️ 文件过小"
                print(f"  {mark} {f['name']:50s} {f['size_mb']:>7.1f}MB  [{f['subdir']}]")
            for m in result.get("missing", []):
                print(f"  ❌ {m['name']:50s} 缺失  [{m['subdir']}]")
            if result["all_healthy"]:
                print(f"\n✅ 所有 3 个视频模型完整且健康。")
            elif result["has_corruption"]:
                print(f"\n⚠️ 部分模型文件可能损坏（文件过小）:")
                for f in result.get("found", []):
                    if not f["ok"]:
                        print(f"   - {f['name']} ({f['size_mb']}MB < 预期 {f['expected_min']}MB)")
            else:
                print(f"\n❌ 缺少 {len(result['missing'])} 个视频模型，视频生成不可用。")
                print("处理: 从 HuggingFace 下载对应模型到 ComfyUI models 目录。")
            return

        wf_name = target
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

    elif action == "refresh":
        from agents.model_manager import refresh_cache
        refresh_cache()

    elif action == "prune":
        from agents.model_manager import prune_models
        dry_run = "--force" not in sys.argv
        result = prune_models(dry_run=dry_run)
        if not dry_run:
            import os
            for m in result["orphaned"]:
                try:
                    os.remove(m["path"])
                    print(f"  已删除: {m['name']}")
                except OSError as e:
                    print(f"  删除失败 {m['name']}: {e}")
            print(f"\n✅ 已清理 {result['orphan_count']} 个孤立模型，释放 {result['total_mb']:.0f}MB。")
        elif result["orphan_count"] > 0:
            print(f"\n提示: 用 --force 确认删除 {result['orphan_count']} 个孤立模型（释放 {result['total_mb']:.0f}MB）。")

    else:
        _show_models_help()


def _show_models_help() -> None:
    print("用法: python -m agents models list [category] [--disk]|info <name>|check <workflow_name>|check video|download <url>|download video|refresh|prune [--force]")


def _get_video_duration_str(video_path: Path) -> str:
    """用 ffprobe 获取视频时长可读字符串。"""
    import json
    import shutil
    import subprocess

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return ""
    try:
        result = subprocess.run(
            [ffprobe, "-v", "quiet", "-print_format", "json",
             "-show_format", str(video_path)],
            capture_output=True, text=True, timeout=15,
        )
        data = json.loads(result.stdout)
        duration = float(data.get("format", {}).get("duration", 0))
        if duration > 0:
            mins, secs = divmod(int(duration), 60)
            return f" · {mins:02d}:{secs:02d}"
    except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError, ValueError, OSError):
        pass
    return ""


def _run_outputs() -> None:
    """Handle 'outputs list|show|clean' subcommands."""
    from agents.output_manager import clean_runs, list_runs, show_run, _get_output_dir
    from pathlib import Path

    if len(sys.argv) < 3:
        print("用法: python -m agents outputs list|show <id> [--info]|clean [--days N]")
        return

    action = sys.argv[2]

    if action == "list":
        show_images = "--images" in sys.argv
        runs = list_runs()
        if not runs:
            print("暂无产出记录。")
            return
        header = f"{'运行 ID':30s} {'命令':10s} {'时间':22s} {'图片':6s} {'视频':6s}"
        if show_images:
            header += "  预览"
        print(f"\n{header}")
        print("-" * (88 if show_images else 80))
        for r in runs:
            rid = r.get("run_id", "?")
            cmd = r.get("command", "?")
            ts = (r.get("timestamp") or "?")[:19]
            n_img = len(r.get("images", []))
            n_vid = r.get("video_count", 0)
            preview = ""
            if show_images:
                imgs = r.get("images", [])
                vids = r.get("videos", [])
                first = (imgs + vids)[0] if (imgs + vids) else ""
                preview = f"  {first[:40]}" if first else ""
            print(f"{rid:30s} {cmd:10s} {ts:22s} {n_img:6d} {n_vid:6d}{preview}")

    elif action == "show":
        if len(sys.argv) < 4:
            print("用法: python -m agents outputs show <run_id> [--info] [--open]")
            return
        run_id = sys.argv[3]
        show_info = "--info" in sys.argv
        open_dir = "--open" in sys.argv
        meta = show_run(run_id)
        if meta is None:
            print(f"未找到产出: {run_id}")
            sys.exit(1)
        output_dir = Path(_get_output_dir()) / run_id
        print(f"\n运行 ID:   {meta.get('run_id', '?')}")
        print(f"命令:      {meta.get('command', '?')}")
        print(f"时间:      {(meta.get('timestamp') or '?')[:19]}")
        if output_dir.is_dir():
            print(f"目录:      {output_dir}")
        images = meta.get("images", [])
        videos = meta.get("videos", [])
        if images:
            print(f"图片 ({len(images)}):")
            for fn in images:
                print(f"  - {fn}")
        if videos:
            print(f"视频 ({len(videos)}):")
            img_dir = Path(_get_output_dir()) / run_id / "images"
            for fn in videos:
                size_str = ""
                dur_str = ""
                fp = img_dir / fn
                if fp.is_file():
                    sz_kb = fp.stat().st_size / 1024
                    size_str = f" ({sz_kb:.0f} KB)" if sz_kb < 1024 else f" ({sz_kb / 1024:.1f} MB)"
                    if show_info:
                        dur_str = _get_video_duration_str(fp)
                print(f"  - {fn}{size_str}{dur_str}")
        if not images and not videos:
            print("文件:      (无)")
        params = meta.get("params", {})
        if params:
            print("\n参数:")
            for k, v in params.items():
                print(f"  {k}: {v}")
        if videos and show_info:
            print("\n💡 提示: 使用 gallery 浏览视频，或 video-process 后处理")
        if open_dir and output_dir.is_dir():
            import subprocess
            subprocess.Popen(["start", str(output_dir)], shell=True)
            print(f"📂 已打开目录: {output_dir}")

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


def _run_workshop() -> None:
    """Handle 'workshop create|engine|inspect|manga|video' subcommands."""
    if len(sys.argv) < 3:
        print("用法: python -m agents workshop <subcommand> [args...]")
        print()
        print("子命令:")
        print("  create  \"描述\"   — 一句话出图（引擎 → 多张生成 → 质检 → 选最优）")
        print("  engine  \"描述\"   — 测试 prompt 引擎（显示优化后提示词）")
        print("  inspect <图片>   — 逐部位质检")
        print("  manga   \"剧本\"   — 漫画/分镜生成")
        print("  video   \"描述\"   — 视频生成")
        print()
        print("示例:")
        print('  python -m agents workshop create "银发少女校服教室窗边逆光" --count 6 --inspect')
        print('  python -m agents workshop create "prompt" --style anime --ref ref.png')
        print('  python -m agents workshop engine "赛博朋克少女，霓虹雨夜"')
        print('  python -m agents workshop inspect output.png')
        return

    sub = sys.argv[2]
    args = sys.argv[3:]

    if sub == "create":
        _workshop_create(args)
    elif sub == "engine":
        _workshop_engine(args)
    elif sub == "inspect":
        _workshop_inspect(args)
    elif sub == "manga":
        _workshop_manga(args)
    elif sub == "video":
        from agents.go_video import main as video_main
        sys.argv = [sys.argv[0]] + args
        video_main()
    else:
        print(f"未知 workshop 子命令: {sub}")
        _run_workshop()


def _workshop_create(args: list[str]) -> None:
    """python -m agents workshop create <nl_text> [options]"""
    import argparse

    parser = argparse.ArgumentParser(description="一句话出图：引擎 → 多张生成 → 质检 → 选最优")
    parser.add_argument("nl_text", nargs="*", help="自然语言描述")
    parser.add_argument("--count", type=int, default=4, help="生成候选数（默认: 4）")
    parser.add_argument("--style", default=None, help="画风提示 (anime/photoreal/cg/cosplay/...)")
    parser.add_argument("--ref", default=None, help="参考图路径（角色特征分析）")
    parser.add_argument("--preset", default=None, help="质量预设 (quality/balanced/fast/...)")
    parser.add_argument("--min-score", type=float, default=0.0, help="最低 CLIP 分")
    parser.add_argument("--retry", type=int, default=0, help="失败重试次数")
    parser.add_argument("--no-inspect", action="store_true", help="跳过质检")
    parser.add_argument("--preview", action="store_true", help="预览模式（跳过生成）")
    parser.add_argument("--ollama", action="store_true", help="使用 Ollama 优化 prompt")
    parser.add_argument("--output", default=None, help="结果输出目录（保存 metadata.json + best.png）")
    parser.add_argument("--verbose", action="store_true", help="详细信息")
    parsed = parser.parse_args(args)

    nl_text = " ".join(parsed.nl_text) if parsed.nl_text else ""
    if not nl_text:
        parser.print_help()
        return

    from workshop.create import create_from_nl

    result = create_from_nl(
        nl_text,
        count=parsed.count,
        style_hint=parsed.style,
        ref_path=parsed.ref,
        preset=parsed.preset,
        min_score=parsed.min_score,
        retry=parsed.retry,
        inspect=not parsed.no_inspect,
        dry_run=parsed.preview,
        use_ollama=parsed.ollama,
        output_dir=parsed.output,
        verbose=parsed.verbose,
    )

    if parsed.preview:
        print(f"\n📝 Prompt: {result['prompt']}")
        print(f"  候选数: {parsed.count}")
        print("  (dry-run 模式，未提交)")
        return

    if result.get("error"):
        print(f"\n❌ {result['error']}")
        print("  请确认: ComfyUI 已启动，浏览器可打开 http://127.0.0.1:8188")
        return

    print(f"\n{'='*50}")
    print(f"📝 最终 Prompt: {result['prompt']}")
    if parsed.ollama:
        print(f"  (Ollama 增强)")
    print(f"  候选: {len(result['candidates'])} 张")

    best = result.get("best", {})
    if best and best.get("image"):
        print(f"\n🏆 最优:")
        print(f"  图片: {best['image']}")
        print(f"  Seed: {best.get('seed', '?')}")
        print(f"  CLIP Score: {best.get('score', -1)}")
        ins = best.get("inspect", {})
        if ins:
            from workshop.inspect import format_report
            print(f"\n{format_report(ins)}")

    if parsed.output:
        print(f"\n📁 已保存: {parsed.output}/")

    print(f"\n📊 排名:")
    for i, c in enumerate(result.get("candidates", [])):
        ins_sum = c.get("inspect", {}).get("summary", "")
        err_tag = " ❌" if c.get("error") else ""
        print(f"  #{i+1} seed={c.get('seed','?')} score={c.get('score', -1)}{err_tag} {ins_sum}")

    had_err = result.get("had_errors", False)
    if had_err:
        print(f"\n⚠️ 部分候选生成失败（ComfyUI 可能不稳定）")


def _workshop_engine(args: list[str]) -> None:
    """python -m agents workshop engine <nl_text> [--style STYLE]"""
    import argparse

    parser = argparse.ArgumentParser(description="测试 Prompt 引擎")
    parser.add_argument("nl_text", nargs="*", help="自然语言描述")
    parser.add_argument("--style", default=None, help="画风提示")
    parser.add_argument("--list-presets", action="store_true", help="列出可用预设")
    parsed = parser.parse_args(args)

    if parsed.list_presets:
        from workshop.engine import list_presets
        presets = list_presets()
        print("可用预设:")
        print(f"  风格: {', '.join(presets['styles'])}")
        print(f"  构图: {', '.join(presets['compositions'])}")
        print(f"  光照: {', '.join(presets['lighting'])}")
        print(f"  风格关键词: {', '.join(presets['style_keywords'])}")
        return

    nl_text = " ".join(parsed.nl_text) if parsed.nl_text else ""
    if not nl_text:
        parser.print_help()
        return

    from workshop.engine import nls_to_prompt, STYLE_PRESETS

    # 模板兜底结果
    result = nls_to_prompt(nl_text, style_hint=parsed.style, ollama_available=False)
    print(f"\n📝 原始描述: {nl_text}")
    print(f"\n🔧 风格: {parsed.style or '(自动推测)'}")
    print(f"\n✅ 优化后 Prompt:")
    print(f"  {result}")

    # 显示推测
    from workshop.engine.engine import _detect_style, _detect_composition, _detect_lighting
    detected = _detect_style(nl_text, parsed.style)
    comp = _detect_composition(nl_text)
    light = _detect_lighting(nl_text)
    print(f"\n📋 引擎推测: 风格={detected} | 构图={comp[:30]}... | 光照={light[:30]}...")


def _workshop_inspect(args: list[str]) -> None:
    """python -m agents workshop inspect <image_path> [--verbose]"""
    import argparse

    parser = argparse.ArgumentParser(description="逐部位质检")
    parser.add_argument("image_path", help="图片路径")
    parser.add_argument("--verbose", action="store_true", help="详细信息")
    parsed = parser.parse_args(args)

    from workshop.inspect import inspect_image, format_report
    result = inspect_image(parsed.image_path, verbose=parsed.verbose)
    report = format_report(result)
    print(report)


def _workshop_manga(args: list[str]) -> None:
    """python -m agents workshop manga <script_text> [options]"""
    import argparse

    parser = argparse.ArgumentParser(description="漫画/分镜生成")
    parser.add_argument("script_text", nargs="*", help="剧本/场景描述")
    parser.add_argument("--style", default="anime", help="画风")
    parser.add_argument("--preview", action="store_true", help="预览")
    parser.add_argument("--layout", default="auto", help="拼页布局 (auto/4koma)")
    parser.add_argument("--char", action="append", default=None,
                        help='角色定义 (可重复): "名:服饰:发型:特征" 例：--char "Knives:白校服:银发:猫耳红瞳"')
    parsed = parser.parse_args(args)

    script = " ".join(parsed.script_text) if parsed.script_text else ""
    if not script:
        parser.print_help()
        return

    from workshop.manga import script_to_storyboard, storyboard_to_prompts, generate_panels, assemble_page

    # 解析角色定义
    if parsed.char:
        chars = {}
        for c in parsed.char:
            parts = [p.strip() for p in c.split(":")]
            name = parts[0]
            chars[name] = {
                "服饰": parts[1] if len(parts) > 1 else "",
                "发型": parts[2] if len(parts) > 2 else "",
                "特征": parts[3] if len(parts) > 3 else "",
            }
    else:
        chars = {
            "Knives": {"服饰": "白色校服", "发型": "银白长发", "特征": "猫耳, 红瞳"},
            "Caster": {"服饰": "黑色连衣裙", "发型": "粉色短发", "特征": "蓝瞳"},
        }

    char_names = list(chars.keys())
    print(f"📖 剧本: {script}")
    print(f"👤 角色 ({len(chars)}):")
    for name, info in chars.items():
        print(f"   {name}: {info.get('服饰','?')} / {info.get('发型','?')} / {info.get('特征','?')}")

    print("\n📋 生成分镜表...")
    storyboard = script_to_storyboard(script, characters=chars, ollama_available=False)
    for shot in storyboard:
        print(f"  {shot.get('镜号','?')} | {shot.get('人物','?')} | {shot.get('景別','?')} | {shot.get('台词','')[:30]}")

    print("\n🎨 生成逐格 Prompt...")
    panels = storyboard_to_prompts(storyboard, chars, style_hint=parsed.style)

    if parsed.preview:
        for p in panels:
            print(f"  {p['shot']}: {p['prompt'][:80]}...")
        return

    print("\n🖼️  逐格生图...")
    results = generate_panels(panels, dry_run=parsed.preview)

    print("\n📄 拼页...")
    output = assemble_page(results)
    print(f"✅ 漫画页: {output}")


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

    if command == "workshop":
        _run_workshop()
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
        "control": "go_control.py",
        "video": "go_video.py",
        "video-process": "go_video_process.py",
        "validate": "go_validate.py",
        "abtest": "go_abtest.py",
        "bestof": "go_abtest.py",
        "serve": "go_serve.py",
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
        elif command == "control":
            from agents.go_control import main as target_main
        elif command == "video":
            from agents.go_video import main as target_main
        elif command == "video-process":
            from agents.go_video_process import main as target_main
        elif command == "validate":
            from agents.go_validate import main as target_main
        elif command == "abtest":
            from agents.go_abtest import main_abtest as target_main
        elif command == "bestof":
            from agents.go_abtest import main_bestof as target_main
        elif command == "serve":
            from agents.go_serve import main as target_main
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
        ("run", "一句话提交 ComfyUI 文生图（--video 可切换视频生成）"),
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
        ("control", "ControlNet 引导生图（depth/openpose/softedge/tile）"),
        ("video", "Wan2.2 视频生成（T2V/I2V + 批量 + 预览）"),
        ("video-process", "视频后处理（GIF / 裁剪 / 变速 / 拼接）"),
        ("validate", "出图质量评估（CLIP score / 崩脸检测）"),
        ("abtest", "Prompt A/B 对比测试（同 seed 控制变量）"),
        ("bestof", "多 seed 自动挑优（CLIP 评分排名）"),
        ("serve", "REST API 服务（FastAPI，异步作业队列）"),
        ("check", "环境检查（ComfyUI / Ollama 连通性）"),
        ("workflow", "工作流模板管理（list / show / schema / check）"),
        ("models", "模型管理（list / info / check / download / refresh）"),
        ("outputs", "产出管理（list / show <id> [--info] / clean）"),
    ]:
        print(f"  {name:12s}  {desc}")
    print()
    print("更多信息:  python -m agents <子命令> --help")
    print("        或阅读 AGENTS.md")


if __name__ == "__main__":
    main()
