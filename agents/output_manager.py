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
