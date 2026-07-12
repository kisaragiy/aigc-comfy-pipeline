"""
管线验收报告 — 一键展示管线全貌。

用法示例:
  python go_report.py
  python go_report.py --json
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def _get_env_info() -> dict[str, Any]:
    from agents import __version__

    return {
        "version": __version__,
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "comfy_url": os.environ.get("COMFY_URL", "http://127.0.0.1:8188/prompt"),
        "ollama_url": os.environ.get(
            "OLLAMA_URL", "http://127.0.0.1:11434/api/generate"
        ),
    }


def _get_comfyui_info() -> dict[str, Any]:
    from comfy_utils import check_comfy_health, comfy_base_url

    base = comfy_base_url()
    info: dict[str, Any] = {"online": check_comfy_health(), "base_url": base}
    if info["online"]:
        import requests

        try:
            r = requests.get(f"{base}/queue", timeout=5)
            queue = r.json() if r.status_code == 200 else {}
            info["queue_running"] = len(queue.get("queue_running", []))
            info["queue_pending"] = len(queue.get("queue_pending", []))
        except Exception:
            pass
        try:
            r = requests.get(f"{base}/system_stats", timeout=5)
            stats = r.json() if r.status_code == 200 else {}
            info["system"] = stats.get("system", {})
        except Exception:
            pass
    return info


def _get_ollama_info() -> dict[str, Any]:
    from comfy_utils import check_ollama_health, DEFAULT_OLLAMA_URL

    info: dict[str, Any] = {"online": check_ollama_health(), "models": []}
    if info["online"]:
        import requests

        try:
            base = DEFAULT_OLLAMA_URL.rstrip("/api/generate").rstrip("/")
            r = requests.get(f"{base}/api/tags", timeout=5)
            if r.status_code == 200:
                info["models"] = [m["name"] for m in r.json().get("models", [])]
        except Exception:
            pass
    return info


def _get_models_info() -> dict[str, Any]:
    models_total = 0
    models_by_cat: dict[str, int] = {}
    try:
        from model_manager import list_models

        all_models = list_models()
        models_total = len(all_models)
        for m in all_models:
            cat = m["category"]
            models_by_cat[cat] = models_by_cat.get(cat, 0) + 1
    except Exception:
        pass
    return {"total": models_total, "by_category": models_by_cat}


def _get_workflows_info() -> dict[str, Any]:
    wf_total = 0
    wf_api = 0
    try:
        from workflow_manager import list_workflows

        wfs = list_workflows()
        wf_total = len(wfs)
        wf_api = sum(1 for w in wfs if w["is_api_format"])
    except Exception:
        pass
    return {"total": wf_total, "api_format": wf_api, "ui_format": wf_total - wf_api}


def _get_outputs_info() -> dict[str, Any]:
    total = 0
    recent: list[dict[str, Any]] = []
    try:
        from output_manager import list_runs

        runs = list_runs()
        total = len(runs)
        recent = [
            {
                "run_id": r.get("run_id", ""),
                "command": r.get("command", ""),
                "timestamp": (r.get("timestamp") or "")[:19],
                "images": len(r.get("images", [])),
            }
            for r in runs[:5]
        ]
    except Exception:
        pass
    return {"total": total, "recent": recent}


def generate_report() -> dict[str, Any]:
    """生成完整管线报告。"""
    return {
        "report_time": datetime.now().isoformat()[:19],
        "environment": _get_env_info(),
        "comfyui": _get_comfyui_info(),
        "ollama": _get_ollama_info(),
        "models": _get_models_info(),
        "workflows": _get_workflows_info(),
        "outputs": _get_outputs_info(),
    }


def _print_report(data: dict[str, Any]) -> None:
    env = data["environment"]
    comfy = data["comfyui"]
    ollama = data["ollama"]
    models = data["models"]
    wfs = data["workflows"]
    outs = data["outputs"]

    print(f"\n{'='*55}")
    print(f"  AIGC ComfyUI Pipeline — 验收报告")
    print(f"{'='*55}")
    print(f"  版本:    v{env['version']}")
    print()

    # 📋 环境
    print("📋 环境信息")
    print(f"  Python:    {env['python']}")
    print(f"  平台:      {env['platform']}")
    print(f"  ComfyUI:   {env['comfy_url']}")
    print(f"  Ollama:    {env['ollama_url']}")
    print()

    # 🟢 ComfyUI
    c_icon = "✅ 在线" if comfy.get("online") else "❌ 离线"
    print(f"{'🟢' if comfy.get('online') else '🔴'} ComfyUI")
    print(f"  状态:   {c_icon}")
    if comfy.get("online"):
        print(f"  队列:   {comfy.get('queue_running', 0)} 运行中, "
              f"{comfy.get('queue_pending', 0)} 待处理")
    else:
        print("  处理: 启动 ComfyUI 或检查环境变量 COMFY_URL")
    print()

    # 🟡 Ollama
    o_icon = "✅ 在线" if ollama.get("online") else "❌ 离线"
    print(f"{'🟡' if ollama.get('online') else '🔴'} Ollama")
    print(f"  状态:   {o_icon}")
    if ollama.get("online") and ollama.get("models"):
        ml = ollama["models"]
        m_str = ", ".join(ml[:8])
        if len(ml) > 8:
            m_str += f" ... (+{len(ml)-8})"
        print(f"  模型:   {m_str}")
    print()

    # 📦 模型
    print("📦 模型")
    print(f"  总计:   {models['total']}")
    for cat, count in sorted(models.get("by_category", {}).items()):
        print(f"    {cat}: {count}")
    print()

    # 📋 工作流
    print("📋 工作流")
    print(f"  总数:   {wfs['total']}")
    if wfs["total"]:
        print(f"  API:    {wfs['api_format']}")
        print(f"  UI:     {wfs['ui_format']}")
    print()

    # 📊 产出
    print("📊 产出")
    print(f"  总运行: {outs['total']}")
    for r in outs.get("recent", []):
        print(f"    {r.get('timestamp', ''):22s} "
              f"{r.get('command', ''):10s} {r.get('run_id', '')}")
    print()

    # ✅ 总结
    comfy_ok = comfy.get("online", False)
    has_models = models["total"] > 0
    has_workflows = wfs["api_format"] > 0
    ready = comfy_ok and has_models and has_workflows

    print(f"{'='*55}")
    print(f"  {'✅ 管线就绪' if ready else '⚠️  管线未完全就绪'}")
    issues = []
    if not comfy_ok:
        issues.append("  ❌ ComfyUI 离线 — 启动 ComfyUI 或检查 COMFY_URL")
    if not has_models:
        issues.append("  ❌ 无模型 — 安装模型到 COMFY_ROOT/models/")
    if not has_workflows:
        issues.append("  ❌ 无可用 workflow")
    for issue in issues:
        print(issue)
    print(f"{'='*55}\n")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="管线验收报告")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    args = parser.parse_args()

    data = generate_report()

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        _print_report(data)


if __name__ == "__main__":
    main()
