"""
模型下载 — 从 HuggingFace / CivitAI / 直链下载模型到 ComfyUI 目录。

用法示例:
  python model_download.py <url> --type lora
  python model_download.py <url> --type checkpoint --hf-mirror
  python model_download.py <url> --type lora --name custom.safetensors --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import requests

from comfy_utils import bootstrap_agents_path

bootstrap_agents_path()

from model_manager import CATEGORY_DIR_MAP, resolve_models_root  # noqa: E402

# 反向映射：category → 优先目录名
CATEGORY_PREFERRED_DIR: dict[str, str] = {
    "checkpoint": "checkpoints",
    "lora": "loras",
    "vae": "vae",
    "clip": "text_encoders",
    "embedding": "embeddings",
    "controlnet": "controlnet",
    "ipadapter": "ipadapter",
    "upscale": "upscale_models",
    "style_model": "style_models",
}

# Wan2.2 视频模型预设下载链接 (Kijai 仓库，HF 镜像)
VIDEO_MODEL_URLS: list[dict[str, Any]] = [
    {
        "filename": "wan2.2_ti2v_5B_fp16.safetensors",
        "url": "https://huggingface.co/Kijai/Wan2.2_comfyui/resolve/main/wan2.2_ti2v_5B_fp16.safetensors",
        "subdir": "diffusion_models",
        "expected_gb": 9.5,
        "description": "Wan2.2 T2V 扩散模型 (5B)",
    },
    {
        "filename": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
        "url": "https://huggingface.co/Kijai/Wan2.2_comfyui/resolve/main/umt5_xxl_fp8_e4m3fn_scaled.safetensors",
        "subdir": "text_encoders",
        "expected_gb": 6.4,
        "description": "Wan2.2 文本编码器 (UMT5)",
    },
    {
        "filename": "wan2.2_vae.safetensors",
        "url": "https://huggingface.co/Kijai/Wan2.2_comfyui/resolve/main/wan2.2_vae.safetensors",
        "subdir": "vae",
        "expected_gb": 1.3,
        "description": "Wan2.2 VAE 解码器",
    },
]


def _resolve_target_dir(category: str) -> Path | None:
    """根据类型确定目标子目录。"""
    models_root = resolve_models_root()
    if models_root is None:
        return None

    preferred = CATEGORY_PREFERRED_DIR.get(category)
    if preferred:
        candidate = models_root / preferred
        if candidate.is_dir():
            return candidate
        # 尝试其他映射
        for dirname, cat in CATEGORY_DIR_MAP.items():
            if cat == category:
                candidate = models_root / dirname
                if candidate.is_dir():
                    return candidate
        # 取首选目录（即使不存在也创建）
        return models_root / preferred

    return models_root


def download_model(
    url: str,
    category: str = "checkpoint",
    *,
    filename: str | None = None,
    hf_mirror: bool = False,
    civitai_token: str | None = None,
    timeout: float = 600,
) -> Path | None:
    """下载模型到 ComfyUI 对应目录。返回文件路径或 None。"""
    target_dir = _resolve_target_dir(category)
    if target_dir is None:
        print("错误: 无法确定 ComfyUI models 目录", file=sys.stderr)
        return None

    target_dir.mkdir(parents=True, exist_ok=True)

    download_url = url
    headers: dict[str, str] = {}

    if "civitai.com" in url.lower() and civitai_token:
        headers["Authorization"] = f"Bearer {civitai_token}"

    if hf_mirror and "huggingface.co" in url.lower():
        download_url = url.replace("huggingface.co", "hf-mirror.com")

    if not filename:
        filename = url.split("/")[-1].split("?")[0]
        if not filename or filename.endswith("/"):
            filename = "model.safetensors"

    dest = target_dir / filename

    if dest.exists():
        size_mb = dest.stat().st_size / (1024 * 1024)
        print(f"⚠️  文件已存在: {dest} ({size_mb:.1f} MB)")
        print("   跳过下载。使用 --name 可保存为新文件名。")
        return dest

    print(f"\n下载: {filename}")
    print(f"类型: {category}")
    print(f"目标: {dest}\n")

    try:
        r = requests.get(download_url, headers=headers, stream=True, timeout=timeout)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"❌ 下载失败: {e}", file=sys.stderr)
        return None

    total = int(r.headers.get("content-length", 0))
    downloaded = 0

    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = downloaded * 100 / total
                    mb = downloaded / (1024 * 1024)
                    print(f"\r  进度: {pct:.0f}% ({mb:.1f} MB)", end="", flush=True)
                else:
                    print(f"\r  已下载: {downloaded / (1024 * 1024):.1f} MB",
                          end="", flush=True)

    print()
    size_mb = dest.stat().st_size / (1024 * 1024)
    print(f"\n✅ 下载完成: {size_mb:.1f} MB")

    # 刷新 model_manager 缓存
    try:
        from model_manager import _model_cache, _scan_models
        _model_cache = _scan_models()
    except Exception:
        pass

    return dest


def download_video_models(
    *,
    hf_mirror: bool = True,
    preview: bool = False,
    timeout: float = 3600,
) -> int:
    """下载 Wan2.2 视频生成所需的三件套模型。

    Returns:
        成功下载的数量（已存在的也算成功）。
    """
    from model_manager import resolve_models_root

    models_root = resolve_models_root()
    if models_root is None:
        print("错误: 无法确定 ComfyUI models 目录", file=sys.stderr)
        return 0

    success = 0
    total = len(VIDEO_MODEL_URLS)

    print(f"\n=== Wan2.2 视频模型下载 ({total} 个) ===\n")

    for item in VIDEO_MODEL_URLS:
        fn = item["filename"]
        dest_dir = models_root / item["subdir"]
        dest = dest_dir / fn

        exists = dest.exists()

        if preview:
            status = "✅ 已存在" if exists else "❌ 缺失"
            size_str = f"({dest.stat().st_size / (1024*1024):.0f} MB)" if exists else ""
            print(f"  [{status}] {fn:50s} {size_str}")
            print(f"          → {dest}")
            if exists:
                success += 1
            continue

        if exists:
            size_mb = dest.stat().st_size / (1024 * 1024)
            print(f"  ✅ {fn} 已存在 ({size_mb:.1f} MB)")
            success += 1
            continue

        print(f"\n  [{success+1}/{total}] {item['description']}")
        result = download_model(
            item["url"],
            "checkpoint",
            filename=fn,
            hf_mirror=hf_mirror,
            timeout=timeout,
        )
        if result:
            success += 1
        else:
            print(f"  ❌ {fn} 下载失败")

    print(f"\n结果: {success}/{total} 个模型可用")
    if preview:
        print(f"\n预览结果: {success}/{total} 个模型已存在")
        print("使用 python -m agents models download video 开始下载。")
    elif success == total:
        print("✅ Wan2.2 视频模型已就绪，可以开始视频生成。")
        print("   验证: python -m agents models check video")
    else:
        print(f"⚠️  缺少 {total - success} 个模型，视频生成可能不可用。")
        print("   重试: python -m agents models download video")
    return success


def download_cli(argv: list[str]) -> None:
    """CLI 入口，接收 argv 列表。"""
    # 特殊子命令: download video
    if argv and argv[0] == "video":
        preview = "--preview" in argv or "-p" in argv
        no_mirror = "--direct" in argv
        return download_video_models(
            hf_mirror=not no_mirror,
            preview=preview,
        )

    parser = argparse.ArgumentParser(
        prog="python -m agents models download",
        description="下载模型到 ComfyUI 目录",
    )
    parser.add_argument("url", help="下载 URL（HuggingFace / CivitAI / 直链），或使用 'video' 下载 Wan2.2 模型预设")
    parser.add_argument(
        "--type",
        choices=[
            "checkpoint", "lora", "vae", "clip",
            "embedding", "controlnet", "ipadapter", "upscale",
        ],
        default="checkpoint",
        help="模型类型",
    )
    parser.add_argument("--name", default=None, help="保存文件名（可选）")
    parser.add_argument(
        "--hf-mirror", action="store_true",
        help="使用 HF 镜像（hf-mirror.com）",
    )
    parser.add_argument(
        "--civitai-token", default=None,
        help="CivitAI API Token（从 https://civitai.com/user/account 获取）",
    )
    parser.add_argument(
        "--preview", action="store_true",
        help="预览模式，不实际下载",
    )
    args = parser.parse_args(argv)

    if args.preview:
        target_dir = _resolve_target_dir(args.type)
        filename = (
            args.name
            or args.url.split("/")[-1].split("?")[0]
            or "model.safetensors"
        )
        print(f"\n预览:")
        print(f"  URL:    {args.url}")
        print(f"  类型:   {args.type}")
        print(f"  保存到: {target_dir / filename}")
        if "civitai.com" in args.url.lower():
            has_token = "✅" if args.civitai_token else "❌ 未提供"
            print(f"  Token:  {has_token}（CivitAI 需要 API Token 才能下载）")
        if "huggingface.co" in args.url.lower():
            print(f"  镜像:   {'hf-mirror.com' if args.hf_mirror else '直接连接'}")
        return

    download_model(
        args.url,
        args.type,
        filename=args.name,
        hf_mirror=args.hf_mirror,
        civitai_token=args.civitai_token,
    )


def main() -> None:
    """独立运行入口。"""
    download_cli(sys.argv[1:])


if __name__ == "__main__":
    main()
