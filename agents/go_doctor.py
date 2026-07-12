"""
一键诊断修复 — 检查管线常见问题并给出处理建议。

用法示例:
  python go_doctor.py
  python go_doctor.py --fix
  python go_doctor.py --json
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from comfy_utils import bootstrap_agents_path

bootstrap_agents_path()


# 延迟导入（在 bootstrap_agents_path 之后）
def _check_python():
    v = sys.version_info
    ok = v.major >= 3 and v.minor >= 10
    return ok, f"Python {v.major}.{v.minor}.{v.micro}"


def _check_comfyui():
    from comfy_utils import check_comfy_health

    ok = check_comfy_health()
    return ok, "启动 ComfyUI 或检查 COMFY_URL 环境变量" if not ok else ""


def _check_ollama():
    from comfy_utils import check_ollama_health

    ok = check_ollama_health()
    return ok, "启动 WSL Ollama: wsl sh -c 'ollama serve &'" if not ok else ""


def _check_comfy_root():
    from comfy_utils import resolve_comfy_root

    root = resolve_comfy_root()
    ok = root.is_dir() if root else False
    return ok, str(root) if root else "设置 COMFY_ROOT 环境变量"


def _check_models_dir(auto_fix: bool = False):
    from model_manager import resolve_models_root

    root = resolve_models_root()
    ok = root and root.is_dir()
    if not ok and auto_fix and root:
        root.mkdir(parents=True, exist_ok=True)
        ok = True
    return ok, str(root) if root else "ComfyUI 未安装模型"


def _check_models_installed():
    from model_manager import list_models

    models = list_models()
    ok = len(models) > 0
    return ok, f"{len(models)} 个模型" if ok else "下载模型到 models/ 目录"


def _check_workflows():
    from workflow_manager import list_workflows

    wfs = list_workflows()
    ok = len(wfs) > 0
    return ok, f"{len(wfs)} 个" if ok else "workflows/ 目录为空"


def _check_pip_deps():
    try:
        import requests  # noqa: F401

        return True, ""
    except ImportError:
        return False, "pip install -r requirements.txt"


def _check_disk():
    from comfy_utils import resolve_comfy_root

    root = resolve_comfy_root() or "."
    try:
        usage = shutil.disk_usage(root)
        free_gb = usage.free / (1024**3)
        ok = free_gb > 5
        detail = f"剩余 {free_gb:.0f} GB{' ⚠️ 不足 5GB' if not ok else ''}"
        return ok, detail
    except Exception:
        return True, "无法检查"


CHECKS = [
    ("Python 版本", _check_python, None),
    ("ComfyUI 在线", _check_comfyui, None),
    ("Ollama 在线", _check_ollama, None),
    ("ComfyUI 目录", _check_comfy_root, None),
    ("models/ 目录", _check_models_dir, "_check_models_dir_fix"),
    ("已安装模型", _check_models_installed, None),
    ("Workflow 文件", _check_workflows, None),
    ("pip 依赖", _check_pip_deps, None),
    ("磁盘空间", _check_disk, None),
]


def run_doctor(auto_fix: bool = False) -> list[dict]:
    """执行全面诊断。返回检查结果列表。"""
    results: list[dict] = []

    for name, check_fn, _ in CHECKS:
        try:
            ok, detail = check_fn()
        except Exception as e:
            ok = False
            detail = f"检查失败: {e}"

        fix_hint = detail if not ok else ""
        results.append({
            "name": name,
            "status": ok,
            "detail": detail if ok else detail,
            "fix_hint": fix_hint,
        })

    # 尝试修复
    if auto_fix:
        for r in results:
            if r["name"] == "models/ 目录" and not r["status"]:
                from model_manager import resolve_models_root
                root = resolve_models_root()
                if root:
                    root.mkdir(parents=True, exist_ok=True)
                    r["status"] = True
                    r["detail"] = "已创建"
                    r["fix_hint"] = ""

            if r["name"] == "pip 依赖" and not r["status"]:
                ret = os.system("pip install -r requirements.txt 2>/dev/null")
                if ret == 0:
                    r["status"] = True
                    r["detail"] = "已安装"
                    r["fix_hint"] = ""

    return results


def _print_report(results: list[dict]) -> None:
    """打印诊断报告。"""
    ok = sum(1 for r in results if r["status"])
    total = len(results)

    print(f"\n{'='*50}")
    print(f"  AIGC ComfyUI Pipeline — 诊断报告")
    print(f"{'='*50}")
    print()

    for r in results:
        icon = "✅" if r["status"] else "❌"
        detail = f" — {r['detail']}" if r["detail"] else ""
        print(f"  {icon} {r['name']}{detail}")
        if not r["status"] and r["fix_hint"]:
            print(f"     处理: {r['fix_hint']}")

    print(f"\n{'='*50}")
    print(f"  {ok}/{total} 项通过")
    if ok < total:
        print(f"  {total - ok} 项需要处理")
    print(f"{'='*50}\n")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="管线一键诊断修复")
    parser.add_argument("--fix", action="store_true", help="尝试自动修复")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    args = parser.parse_args()

    results = run_doctor(auto_fix=args.fix)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        _print_report(results)


if __name__ == "__main__":
    main()
