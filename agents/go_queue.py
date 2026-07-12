"""
ComfyUI 队列管理 — list/clear/interrupt/free。

用法示例:
  python go_queue.py list
  python go_queue.py clear
  python go_queue.py interrupt
  python go_queue.py free [--all]
"""
from __future__ import annotations

import sys
from typing import Any

import requests

from comfy_utils import bootstrap_agents_path, check_comfy_health, comfy_base_url

bootstrap_agents_path()

_VIDEO_NODE_TYPES = {"VideoCombine", "EmptyLatentVideo"}


def _detect_task_type(prompt_data: dict) -> str:
    """从 prompt 数据检测任务类型 (video / image / unknown)。"""
    if not isinstance(prompt_data, dict):
        return "unknown"
    for node in prompt_data.values():
        if isinstance(node, dict) and node.get("class_type") in _VIDEO_NODE_TYPES:
            return "video"
    return "image"


def get_queue(base: str) -> dict[str, Any]:
    """获取队列状态。"""
    r = requests.get(f"{base}/queue", timeout=5)
    r.raise_for_status()
    return r.json()


def clear_queue(base: str) -> bool:
    """清空待处理队列。"""
    r = requests.post(f"{base}/queue", json={"clear": True}, timeout=5)
    return r.status_code == 200


def interrupt(base: str) -> bool:
    """中断当前运行任务。"""
    r = requests.post(f"{base}/interrupt", timeout=5)
    return r.status_code == 200


def free_memory(base: str, unload_all: bool = False) -> bool:
    """释放显存。"""
    r = requests.post(
        f"{base}/free",
        json={"unload_models": True, "free_memory": True, "unload_all": unload_all},
        timeout=10,
    )
    return r.status_code == 200


def _do_list(base: str) -> None:
    data = get_queue(base)
    running = data.get("queue_running", [])
    pending = data.get("queue_pending", [])

    running_img = sum(1 for it in running if _detect_task_type(it[1]) == "image")
    running_vid = sum(1 for it in running if _detect_task_type(it[1]) == "video")
    pending_img = sum(1 for it in pending if _detect_task_type(it[1]) == "image")
    pending_vid = sum(1 for it in pending if _detect_task_type(it[1]) == "video")

    type_summary = []
    if running_img or pending_img:
        type_summary.append(f"🖼️ image: {running_img}r + {pending_img}q")
    if running_vid or pending_vid:
        type_summary.append(f"🎬 video: {running_vid}r + {pending_vid}q")

    print("\nComfyUI 队列状态:")
    print(f"  运行中: {len(running)}, 待处理: {len(pending)}")
    if type_summary:
        print(f"  类型:   {' | '.join(type_summary)}")
    print()

    if running:
        print("  正在运行:")
        for item in running:
            node_count = len(item[1]) if isinstance(item[1], dict) else 0
            style = _detect_task_type(item[1])
            emoji = "🎬" if style == "video" else "🖼️"
            print(f"    {emoji} [{item[0][:12]}] {style} ({node_count} nodes)")
    if pending:
        print("\n  待处理:")
        for item in pending:
            node_count = len(item[1]) if isinstance(item[1], dict) else 0
            style = _detect_task_type(item[1])
            emoji = "🎬" if style == "video" else "🖼️"
            print(f"    {emoji} [{item[0][:12]}] {style} ({node_count} nodes)")

    if not running and not pending:
        print("  队列为空。\n")


def _do_clear(base: str) -> None:
    if clear_queue(base):
        print("✅ 已清空待处理队列。")
    else:
        print("❌ 清空失败。", file=sys.stderr)
        sys.exit(1)


def _do_interrupt(base: str) -> None:
    if interrupt(base):
        print("✅ 已中断当前任务。")
    else:
        print("❌ 中断失败。", file=sys.stderr)
        sys.exit(1)


def _do_free(base: str, unload_all: bool = False) -> None:
    if free_memory(base, unload_all=unload_all):
        print("✅ 显存已释放。")
    else:
        print("❌ 释放失败。", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="ComfyUI 队列管理")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("list", help="查看队列状态")
    sub.add_parser("clear", help="清空待处理队列")
    sub.add_parser("interrupt", help="中断当前任务")
    p_free = sub.add_parser("free", help="释放显存")
    p_free.add_argument("--all", action="store_true", help="释放所有（包括当前运行）")
    args = parser.parse_args()

    if not check_comfy_health():
        print("ComfyUI 未运行，无法管理队列。", file=sys.stderr)
        print("请先启动 ComfyUI 再运行: python -m agents check")
        sys.exit(1)

    base = comfy_base_url()

    if args.action == "list":
        _do_list(base)
    elif args.action == "clear":
        _do_clear(base)
    elif args.action == "interrupt":
        _do_interrupt(base)
    elif args.action == "free":
        _do_free(base, unload_all=args.all)


if __name__ == "__main__":
    main()
