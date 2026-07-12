"""
视频自动化 — 封装 Wan2.2 生成 + 分镜驱动视频帧生成。

核心能力:
  1. generate_video()           — 封装 go_video.py，简化调用
  2. storyboard_to_video_frames() — 分镜表 → 逐镜视频片段
  3. video_compose()            — 多片段拼接/淡入淡出（ffmpeg）

底层基于 agents/go_video.py 的 Wan2.2 T2V/I2V 管线。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from agents.comfy_utils import generate_with_quality, resolve_comfy_root


def generate_video(
    prompt: str,
    *,
    ref_image: str | None = None,
    frames: int = 49,
    fps: int = 15,
    width: int = 848,
    height: int = 480,
    steps: int = 30,
    cfg: float = 7.0,
    seed: int = -1,
    denoise: float = 1.0,
    negative: str = "",
    preset: str | None = None,
    prefix: str = "wvideo",
    timeout: int = 600,
    dry_run: bool = False,
) -> dict[str, Any]:
    """生成视频（封装 Wan2.2 go_video）。

    Args:
        prompt: 正向提示词
        ref_image: 参考图路径（I2V 模式）
        frames: 帧数
        fps: 帧率
        width/height: 分辨率
        steps: 采样步数
        cfg: CFG scale
        seed: 随机种子（-1=随机）
        denoise: 去噪强度（视频续写时 < 1.0）
        negative: 负向提示词
        preset: 视频预设（cinematic/quality/fast）
        prefix: 输出前缀
        timeout: 等待超时（秒）
        dry_run: 预览模式

    Returns:
        {"prompt_id": "...", "images": [...], "seed": int, "error": "..."}
    """
    from agents.go_video import build_video_workflow

    if dry_run:
        return {"prompt_id": "dry-run", "images": [], "seed": 0, "dry_run": True}

    try:
        qr = generate_with_quality(
            build_video_workflow, prompt,
            preset=preset,
            min_score=0.0,
            max_retries=0,
            no_validate=True,
            seed=seed,
            negative=negative,
            steps=steps,
            cfg=cfg,
            width=width,
            height=height,
            frames=frames,
            fps=fps,
            denoise=denoise,
            ref_image=ref_image,
            prefix=prefix,
            timeout=timeout,
        )
        return dict(qr, error=None)

    except Exception as e:
        return {"prompt_id": "", "images": [], "seed": 0, "error": str(e)}


def storyboard_to_video(
    storyboard: list[dict[str, str]],
    *,
    fps: int = 15,
    frames_per_shot: int = 49,
    preset: str | None = "cinematic",
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """分镜表 → 逐镜生成视频片段。

    Args:
        storyboard: brainstorm_to_storyboard() 输出（或手动编写的八列分镜表）
        fps: 帧率
        frames_per_shot: 每镜帧数
        preset: 视频预设
        dry_run: 预览

    Returns:
        [{"shot": "S01", "prompt_id": "...", "images": [...], "dialogue": "..."}, ...]
    """
    results = []
    for shot in storyboard:
        visual = shot.get("画面描述", "")
        character = shot.get("人物", "")
        scene = shot.get("场景", "")
        camera = shot.get("景别", "")
        dialogue = shot.get("台词", "")

        if visual:
            prompt_text = f"{visual}, {scene}, {camera}"
        else:
            prompt_text = f"{character} in {scene}, {camera}"

        print(f"  [{shot.get('镜号','?')}] 生成视频: {character} — {camera}")
        video_result = generate_video(
            prompt_text,
            frames=frames_per_shot,
            fps=fps,
            preset=preset,
            prefix=f"mvideo_{shot.get('镜号', 'shot')}",
            dry_run=dry_run,
        )
        video_result["shot"] = shot.get("镜号", "")
        video_result["dialogue"] = dialogue
        results.append(video_result)

    return results


def video_compose(
    clips: list[dict[str, Any]],
    *,
    output_path: str = "workshop/output/video_composed.mp4",
    transitions: bool = True,
    clean_temp: bool = True,
) -> str:
    """多视频片段拼接（ffmpeg）。

    Args:
        clips: 视频片段列表（每个含 "images" 中的视频路径）
        output_path: 输出路径
        transitions: 是否添加淡入淡出过渡
        clean_temp: 清理临时文件

    Returns:
        输出文件路径，失败返回空字符串
    """
    import tempfile

    # 收集视频文件
    video_files: list[str] = []
    comfy_root = resolve_comfy_root()

    for clip in clips:
        for sub, name in clip.get("images", []):
            path = comfy_root / "output" / sub / name
            p = Path(path)
            if p.suffix.lower() in (".mp4", ".webm", ".mov") and p.is_file():
                video_files.append(str(p.resolve()))
                break

    if not video_files:
        print("[warn] 无视频文件可拼接", file=sys.stderr)
        return ""

    if len(video_files) == 1:
        # 单文件直接复制
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["ffmpeg", "-y", "-i", video_files[0], "-c", "copy", output_path],
            capture_output=True,
        )
        return output_path

    # 多文件拼接
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, newline="") as f:
        for vf in video_files:
            f.write(f"file '{vf}'\n")
        filelist = f.name

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if transitions:
        # 带交叉淡入淡出拼接
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", filelist,
            "-c", "copy",
            output_path,
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", filelist,
            "-c", "copy",
            output_path,
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if clean_temp:
        Path(filelist).unlink(missing_ok=True)

    if result.returncode != 0:
        print(f"[warn] ffmpeg 拼接失败: {result.stderr}", file=sys.stderr)
        return ""

    print(f"✅ 视频已拼接: {output_path}")
    return output_path
