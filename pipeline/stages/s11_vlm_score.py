#!/usr/bin/env python3
"""VLM 美学评分工位（串行调度版）

解决资源冲突：ComfyUI(12G VRAM) 与 ollama qwen3-vl(8G) 不能同跑。
流程：等待 ComfyUI 队列空闲 → 启动 WSL ollama → 六维评分 → 停止 ollama 释放显存。

统一接口：pipeline/stages/s11_vlm_score.py --input <img> [--outdir ...]
输出：stdout 打印 6 维分数 + 总分；manifest 记录评分
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "agents"))
sys.path.insert(0, str(ROOT / "pipeline"))

from common import new_job, write_manifest  # noqa: E402

WSL_OLLAMA = Path(r"C:\Users\zwq\AppData\Local\hermes\scripts\wsl-ollama.py")


def _comfy_idle(timeout: int = 600) -> bool:
    """等 ComfyUI 队列空闲（VLM 需要显存，ComfyUI 不能在跑图）。"""
    import json
    import urllib.request
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            d = json.loads(opener.open("http://127.0.0.1:8188/queue", timeout=5).read())
            if not d.get("queue_running") and not d.get("queue_pending"):
                return True
        except Exception:
            pass
        time.sleep(5)
    return False


def _start_ollama() -> bool:
    """启动 WSL ollama 服务并等待就绪。

    2026-09-01: wsl-ollama.py 用 `setsid nohup ollama serve &` 在非交互 shell
    里会被回收（实测服务没起来）。改为：直接 wsl 命令拉起 + 轮询 /api/ps。
    """
    # 若已运行则跳过
    if _ollama_alive():
        return True
    subprocess.run(
        ["wsl.exe", "-e", "bash", "-lc",
         "OLLAMA_HOST=0.0.0.0:11434 nohup ollama serve >/tmp/ollama.log 2>&1 &"],
        capture_output=True, timeout=30)
    for _ in range(24):
        if _ollama_alive():
            return True
        time.sleep(5)
    print("⚠️ ollama 启动失败（/tmp/ollama.log 见 WSL）")
    return False


def _ollama_alive() -> bool:
    try:
        import urllib.request
        urllib.request.urlopen("http://172.22.175.253:11434/api/ps", timeout=3)
        return True
    except Exception:
        return False


def _stop_ollama() -> None:
    """卸载所有模型释放显存（不杀 WSL，只 unload）。"""
    subprocess.run(
        ["wsl.exe", "-e", "sh", "-c",
         "curl -s -X POST http://127.0.0.1:11434/api/generate -d '{\"keep_alive\":0}' >/dev/null; "
         "ollama list 2>/dev/null | tail -n +2 | awk '{print $1}' | while read m; do "
         "curl -s -X POST http://127.0.0.1:11434/api/generate -d '{\"model\":\"'$m'\",\"keep_alive\":0}' >/dev/null; "
         "done"],
        capture_output=True, timeout=60)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--outdir", default=str(ROOT / "outputs"))
    args = ap.parse_args()

    img = Path(args.input)
    if not img.is_file():
        print(f"❌ S11 输入不存在: {img}")
        return 1
    job = new_job("S11")

    if not _comfy_idle():
        print("❌ ComfyUI 队列未空闲（VLM 需要显存，无法同跑）")
        return 1
    print("[S11] ComfyUI 空闲 ✅")

    if not _start_ollama():
        print("❌ ollama 启动失败，跳过评分")
        return 2
    print("[S11] ollama 就绪")

    try:
        from aesthetic_scorer import AestheticScorer
        scorer = AestheticScorer(backend="ollama", verbose=True)
        result = scorer.score(str(img), timeout=120)
        print(f"[S11] {img.name}")
        for k, v in (result or {}).items():
            print(f"   {k}: {v}")
        # 六维子分数在 result 里，total/总分 键可能缺失 → 自己聚合
        dim_keys = ["composition_score", "color_score", "lighting_score",
                    "face_score", "emotional_score", "overall_score"]
        dims = {k: v for k, v in (result or {}).items() if k in dim_keys}
        if dims:
            total = round(sum(dims.values()) / len(dims), 2)
        else:
            total = result.get("total") or result.get("总分") or 0
        write_manifest(
            job, "S11", str(img), None, {"scores": dims, "total": total},
            gate=None, history=["S11"], status="ok")
        print(f"   TOTAL={total}")
        return 0
    except Exception as e:
        print(f"❌ S11 评分失败: {e}")
        return 1
    finally:
        _stop_ollama()
        print("[S11] ollama 已停止（显存释放）")


if __name__ == "__main__":
    sys.exit(main())
