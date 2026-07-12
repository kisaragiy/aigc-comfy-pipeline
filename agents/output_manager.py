"""产出管理 — 保存出图副本 + 结构化元数据。"""
from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".avi", ".mkv"}


def _is_video(path: Path) -> bool:
    return path.suffix.lower() in _VIDEO_EXTENSIONS

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

    # 复制文件
    saved_images: list[str] = []
    saved_videos: list[str] = []
    for src_path in image_paths:
        src = Path(src_path)
        if not src.is_file():
            continue
        dst = img_dir / src.name
        shutil.copy2(src, dst)
        if _is_video(src):
            saved_videos.append(str(dst.name))
        else:
            saved_images.append(str(dst.name))

    # 写 metadata
    meta = {
        "run_id": run_id,
        "command": command,
        "timestamp": datetime.now().isoformat(),
        "images": saved_images,
        "videos": saved_videos,
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
        # 兼容旧版：无 videos 字段时补 0
        meta["video_count"] = len(meta.get("videos", []))
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


def save_workflow_outputs(
    prompt_id: str,
    comfy_base: str,
    command: str,
    metadata_extra: dict | None = None,
) -> str | None:
    """等待 ComfyUI 出图 → 保存到 outputs/。

    从 comfy_utils 取 wait_images() 和 resolve_comfy_root()。
    在 dry-run 模式下 prompt_id="dry-run" 时跳过等待。

    Args:
        prompt_id: comfy_post_prompt 返回的 prompt_id
        comfy_base: ComfyUI 基础 URL
        command: 命令名（run/lora/ipa/multi/flux）
        metadata_extra: 附加元数据（prompt/seed/params 等）

    Returns:
        run_id 或 None
    """
    from comfy_utils import resolve_comfy_root, wait_images

    if prompt_id == "dry-run":
        return None

    try:
        images = wait_images(prompt_id, comfy_base)
    except (TimeoutError, RuntimeError) as exc:
        print(f"[warn] 等待出图失败: {exc}", file=sys.stderr)
        return None

    if not images:
        return None

    comfy_root = resolve_comfy_root()
    image_paths: list[str] = []
    for sub, name in images:
        path = (comfy_root / "output" / sub / name).resolve()
        if path.is_file():
            image_paths.append(str(path))

    if not image_paths:
        return None

    meta = dict(metadata_extra or {})
    meta["prompt_id"] = prompt_id
    return save_run(command, image_paths, meta)
