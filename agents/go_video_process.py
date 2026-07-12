"""
Video Post-processing — MP4 → GIF / 裁剪 / 变速 / 拼接 / 帧提取

用法示例:
  python go_video_process.py <video.mp4> --to-gif
  python go_video_process.py <video.mp4> --trim 00:05-00:15
  python go_video_process.py <video.mp4> --speed 2.0
  python go_video_process.py <video.mp4> --trim 00:05-00:15 --speed 1.5 --to-gif
  python go_video_process.py <video1> <video2> --concat --output merged.mp4
  python go_video_process.py --recent --to-gif
  python go_video_process.py --run-id 2026-07-12_153022-video --to-gif
  python go_video_process.py <video.mp4> --extract-frames
  python go_video_process.py <video.mp4> --extract-frames --every 10
  python go_video_process.py <video.mp4> --extract-frames --count 50
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

from comfy_utils import bootstrap_agents_path

bootstrap_agents_path()

from output_manager import list_runs  # noqa: E402


def _find_ffmpeg() -> str:
    """查找 ffmpeg 可执行文件路径。"""
    import shutil
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("错误: 未找到 ffmpeg。请安装 ffmpeg:", file=sys.stderr)
        print("  winget install ffmpeg", file=sys.stderr)
        print("  或从 https://ffmpeg.org/download.html 下载", file=sys.stderr)
        sys.exit(1)
    return ffmpeg


def _resolve_input(input_arg: str) -> Path:
    """解析输入参数为实际文件路径。

    支持:
      - 直接文件路径
      - 运行 ID（从 outputs/ 查找最新视频）
    """
    p = Path(input_arg)
    if p.is_file():
        return p.resolve()

    # 尝试作为 run_id 查找
    output_dir = Path(__file__).resolve().parents[1] / "outputs"
    run_dir = output_dir / input_arg
    if run_dir.is_dir():
        images_dir = run_dir / "images"
        if images_dir.is_dir():
            videos = sorted(images_dir.glob("*.mp4")) + sorted(images_dir.glob("*.webm"))
            if videos:
                return videos[0].resolve()
        # 也可能 run_id 本身就是具体的视频文件
        videos = sorted(run_dir.glob("*.mp4")) + sorted(run_dir.glob("*.webm"))
        if videos:
            return videos[0].resolve()

    print(f"错误: 找不到输入文件或运行 ID: {input_arg}", file=sys.stderr)
    sys.exit(1)


def _find_latest_video() -> Path:
    """查找 outputs/ 中最新生成的视频文件。"""
    output_dir = Path(__file__).resolve().parents[1] / "outputs"
    if not output_dir.is_dir():
        print("错误: outputs/ 目录不存在", file=sys.stderr)
        sys.exit(1)

    newest: Path | None = None
    newest_mtime = 0.0
    for p in output_dir.rglob("*"):
        if p.suffix.lower() in (".mp4", ".webm", ".mov") and p.is_file():
            mtime = p.stat().st_mtime
            if mtime > newest_mtime:
                newest_mtime = mtime
                newest = p

    if newest is None:
        print("错误: outputs/ 下未找到任何视频文件", file=sys.stderr)
        sys.exit(1)

    print(f"  使用最新视频: {newest}")
    return newest.resolve()


def _run_ffmpeg(cmd: list[str], description: str = "") -> None:
    """执行 ffmpeg 命令并打印输出。"""
    ffmpeg = _find_ffmpeg()
    full_cmd = [ffmpeg, "-y"] + cmd
    if description:
        print(f"  {description}...")
    try:
        result = subprocess.run(
            full_cmd, capture_output=True, text=True, timeout=600,
        )
        if result.returncode != 0:
            print(f"  ffmpeg 错误: {result.stderr.strip()}", file=sys.stderr)
            sys.exit(1)
    except subprocess.TimeoutExpired:
        print("  超时: ffmpeg 运行超过 600 秒", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("  错误: 找不到 ffmpeg 可执行文件", file=sys.stderr)
        sys.exit(1)


def to_gif(input_path: Path, output_path: Path, fps: int = 10, scale: str = "") -> Path:
    """转换视频为 GIF。"""
    if not output_path.suffix.lower() == ".gif":
        output_path = output_path.with_suffix(".gif")

    vf_parts: list[str] = [f"fps={fps}"]
    if scale:
        vf_parts.append(f"scale={scale}:flags=lanczos")
    vf = ",".join(vf_parts)

    cmd = ["-i", str(input_path), "-vf", vf, str(output_path)]
    _run_ffmpeg(cmd, f"GIF 转换: {output_path.name}")
    print(f"  ✅ GIF: {output_path} ({output_path.stat().st_size / 1024:.0f} KB)")
    return output_path


def trim_video(input_path: Path, trim_arg: str, output_path: Path) -> Path:
    """裁剪视频片段。trim_arg: '00:05-00:15' 格式"""
    parts = trim_arg.split("-", 1)
    if len(parts) != 2:
        print(f"错误: 裁剪参数格式错误: {trim_arg}，应为 START-END（如 00:05-00:15）", file=sys.stderr)
        sys.exit(1)
    start, end = parts

    cmd = ["-i", str(input_path), "-ss", start, "-to", end,
           "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", str(output_path)]
    _run_ffmpeg(cmd, f"裁剪: {start} → {end}")
    print(f"  ✅ 裁剪: {output_path}")
    return output_path


def change_speed(input_path: Path, speed: float, output_path: Path) -> Path:
    """变速处理。"""
    setpts = f"setpts={1.0/speed}*PTS"
    cmd = ["-i", str(input_path), "-filter:v", setpts,
           "-c:v", "libx264", "-preset", "fast", str(output_path)]

    # 如果有音频，也需要变速
    cmd.extend(["-af", f"atempo={min(speed, 2.0)}"])
    if speed > 2.0:
        # atempo 上限 2.0，多次应用
        atempo_filters = []
        remaining = speed
        while remaining > 2.0:
            atempo_filters.append("atempo=2.0")
            remaining /= 2.0
        if remaining > 0:
            atempo_filters.append(f"atempo={remaining}")
        cmd[-1] = f"[0:a]{','.join(atempo_filters)}[aout]"
        cmd.extend(["-map", "0:v", "-map", "[aout]"])

    _run_ffmpeg(cmd, f"变速 x{speed}")
    print(f"  ✅ 变速 x{speed}: {output_path}")
    return output_path


def concat_videos(input_paths: list[Path], output_path: Path) -> Path:
    """拼接多个视频。"""
    # 创建临时文件列表
    filelist = Path(output_path).parent / ".concat_filelist.txt"
    filelist.write_text(
        "\n".join(f"file '{p}'" for p in input_paths),
        encoding="utf-8",
    )

    try:
        cmd = ["-f", "concat", "-safe", "0", "-i", str(filelist),
               "-c:v", "libx264", "-preset", "fast",
               "-c:a", "aac", "-b:a", "128k", str(output_path)]
        _run_ffmpeg(cmd, f"拼接 {len(input_paths)} 个视频")
        print(f"  ✅ 拼接: {output_path}")
    finally:
        filelist.unlink(missing_ok=True)

    return output_path


def extract_frames(
    input_path: Path,
    output_dir: Path,
    every: int | None = None,
    count: int | None = None,
    quality: int = 2,
) -> list[Path]:
    """从视频中提取帧为 JPG。

    Args:
        input_path: 输入视频路径
        output_dir: 输出目录
        every: 每隔 N 帧提取一帧
        count: 均匀提取 N 帧（与 every 互斥）
        quality: JPEG 质量 1-31（1=最高, 31=最低, 默认 2）

    Returns:
        输出的 JPG 文件路径列表
    """
    import math

    output_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = _find_ffmpeg()
    stem = input_path.stem

    frames_out: list[Path] = []

    if every:
        # 每隔 N 帧提取
        # 使用 select filter: select='not(mod(n,N))'
        filter_expr = f"select='not(mod(n,{every}))'"
        out_pattern = str(output_dir / f"{stem}_frame_%05d.jpg")
        cmd = [
            "-i", str(input_path),
            "-vf", f"{filter_expr},setpts=N/FRAME_RATE/TB",
            "-vsync", "vfr",
            "-q:v", str(quality),
            out_pattern,
        ]
        _run_ffmpeg(cmd, f"帧提取: 每 {every} 帧一帧")

        # 列举生成的帧
        for f in sorted(output_dir.glob(f"{stem}_frame_*.jpg")):
            frames_out.append(f)
        print(f"  ✅ 提取 {len(frames_out)} 帧 → {output_dir}")

    elif count:
        # 均匀提取 N 帧：先用 ffprobe 获取总帧数
        ffprobe = _find_ffmpeg().replace("ffmpeg", "ffprobe")
        try:
            probe_result = subprocess.run(
                [ffprobe, "-v", "quiet", "-select_streams", "v:0",
                 "-count_packets", "-show_entries", "stream=nb_read_packets",
                 "-of", "csv=p=0", str(input_path)],
                capture_output=True, text=True, timeout=30,
            )
            total_frames = int(probe_result.stdout.strip())
        except (ValueError, subprocess.TimeoutExpired, OSError):
            # 回退：用 ffprobe 从时长和 fps 估算
            try:
                probe = subprocess.run(
                    [ffprobe, "-v", "quiet", "-print_format", "json",
                     "-show_streams", str(input_path)],
                    capture_output=True, text=True, timeout=30,
                )
                import json
                info = json.loads(probe.stdout)
                stream = info["streams"][0]
                duration = float(stream.get("duration", 0))
                fps_parts = stream.get("r_frame_rate", "30/1").split("/")
                fps_val = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else 30.0
                total_frames = int(duration * fps_val)
            except (json.JSONDecodeError, KeyError, IndexError, ValueError, OSError):
                total_frames = 300  # 兜底

        if total_frames <= 0:
            total_frames = 300

        # 计算均匀间隔
        step = max(1, total_frames // count)
        # 用 select filter 提取
        filter_expr = f"select='not(mod(n,{step}))'"
        out_pattern = str(output_dir / f"{stem}_frame_%05d.jpg")
        cmd = [
            "-i", str(input_path),
            "-vf", f"{filter_expr},setpts=N/FRAME_RATE/TB",
            "-vsync", "vfr",
            "-q:v", str(quality),
            out_pattern,
        ]
        _run_ffmpeg(cmd, f"帧提取: 均匀 {count} 帧")

        for f in sorted(output_dir.glob(f"{stem}_frame_*.jpg")):
            frames_out.append(f)

        # 如果提取太多（间隔估算不准），只保留前 N 帧
        if len(frames_out) > count:
            extra = sorted(frames_out)[count:]
            for f in extra:
                f.unlink(missing_ok=True)
            frames_out = sorted(frames_out)[:count]

        print(f"  ✅ 提取 {len(frames_out)}/{count} 帧 → {output_dir}")

    else:
        # 默认每隔 30 帧
        return extract_frames(input_path, output_dir, every=30, quality=quality)

    return frames_out


def auto_output_path(input_path: Path, suffix: str, ext: str | None = None) -> Path:
    """自动生成输出路径。"""
    stem = input_path.stem
    parent = input_path.parent
    if ext:
        return parent / f"{stem}_{suffix}.{ext}"
    return parent / f"{stem}_{suffix}{input_path.suffix}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="视频后处理 — GIF / 裁剪 / 变速 / 拼接",
    )
    parser.add_argument("inputs", nargs="*", help="输入文件路径或运行 ID")
    parser.add_argument("--to-gif", action="store_true", help="转换为 GIF")
    parser.add_argument("--trim", default=None,
                        help="裁剪片段: START-END (如 00:05-00:15)")
    parser.add_argument("--speed", type=float, default=None,
                        help="变速系数: 0.5=慢放, 2.0=快放")
    parser.add_argument("--concat", action="store_true",
                        help="拼接模式（所有 inputs 拼接为一个视频）")
    parser.add_argument("--output", default=None, help="输出文件路径")
    parser.add_argument("--recent", action="store_true",
                        help="使用 outputs/ 中最新视频")
    parser.add_argument("--run-id", default=None,
                        help="使用指定运行 ID 的视频")
    parser.add_argument("--gif-fps", type=int, default=10,
                        help="GIF 帧率（默认 10）")
    parser.add_argument("--scale", default="",
                        help="缩放目标（如 480:-1, 320:240）")
    parser.add_argument("--extract-frames", action="store_true",
                        help="从视频中提取帧为 JPG")
    parser.add_argument("--every", type=int, default=None,
                        help="每隔 N 帧提取一帧（与 --count 互斥）")
    parser.add_argument("--count", type=int, default=None,
                        help="均匀提取 N 帧（与 --every 互斥）")
    parser.add_argument("--quality", type=int, default=2,
                        help="JPEG 质量 1-31（1=最高, 31=最低, 默认 2）")
    parser.add_argument("--output-dir", default=None,
                        help="帧提取输出目录（默认: 输入文件同目录下 _frames 子目录）")
    args = parser.parse_args()

    # 解析输入
    input_paths: list[Path] = []

    if args.recent:
        input_paths = [_find_latest_video()]
    elif args.concat:
        if not args.inputs:
            print("错误: 拼接模式需要至少 2 个输入文件", file=sys.stderr)
            sys.exit(1)
        input_paths = [Path(p).resolve() if Path(p).is_file()
                       else _resolve_input(p) for p in args.inputs]
    elif args.run_id:
        input_paths = [_resolve_input(args.run_id)]
    elif args.inputs:
        input_paths = [Path(p).resolve() if Path(p).is_file()
                       else _resolve_input(p) for p in args.inputs]
    else:
        print("错误: 请指定输入文件、--run-id 或 --recent", file=sys.stderr)
        sys.exit(1)

    # 验证输入存在
    for p in input_paths:
        if not p.is_file():
            print(f"错误: 文件不存在: {p}", file=sys.stderr)
            sys.exit(1)

    # 帧提取模式（独立，不参与链式处理）
    if args.extract_frames:
        input_path = input_paths[0]
        if args.output_dir:
            out_dir = Path(args.output_dir)
        else:
            out_dir = input_path.parent / f"{input_path.stem}_frames"
        extract_frames(
            input_path, out_dir,
            every=args.every,
            count=args.count,
            quality=args.quality,
        )
        return

    # 确定输出路径
    if args.concat:
        # 拼接模式
        output_path = Path(args.output) if args.output else auto_output_path(
            input_paths[0], f"concat_{len(input_paths)}",
            ext="mp4",
        )
        concat_videos(input_paths, output_path)
        return

    # 单文件处理
    input_path = input_paths[0]
    current_path: Path | None = None

    # 链式处理: 先确定最终输出路径
    if args.output:
        final_output = Path(args.output)
    else:
        # 根据第一个操作确定默认后缀
        if args.to_gif and not args.trim and not args.speed:
            final_output = auto_output_path(input_path, "gif", ext="gif")
        elif args.to_gif:
            final_output = auto_output_path(input_path, "processed", ext="gif")
        elif args.trim:
            trim_s = args.trim.replace("-", "_").replace(":", "")
            final_output = auto_output_path(input_path, f"trim_{trim_s}")
        elif args.speed:
            final_output = auto_output_path(input_path, f"speed{args.speed}".replace(".", "_"))
        else:
            final_output = auto_output_path(input_path, "processed")

    # 链式处理
    if args.trim:
        trimmed = auto_output_path(input_path, "trimmed")
        trim_video(input_path, args.trim, trimmed)
        current_path = trimmed

    if args.speed is not None:
        src = current_path or input_path
        sped = auto_output_path(src, f"speed{args.speed}".replace(".", "_"))
        change_speed(src, args.speed, sped)
        current_path = sped

    if args.to_gif:
        src = current_path or input_path
        to_gif(src, final_output if not current_path else final_output,
               fps=args.gif_fps, scale=args.scale)
        current_path = final_output

    if current_path:
        print(f"\n✅ 处理完成: {current_path}")
    else:
        print("未指定任何操作（--to-gif / --trim / --speed / --concat）")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)
