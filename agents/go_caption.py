"""
Ollama VL 自动标图 — 调用 WSL Ollama 视觉模型生成训练数据 .txt 标注。

用法示例:
  python go_caption.py --dir ./training_images --trigger "Ha Eun"
  python go_caption.py --dir ./training_images --trigger "Knives" --dry-run
  python go_caption.py --dir ./images --model qwen3.5:9b --trigger "Caster"
"""
from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path
from urllib import request as urllib_request
from urllib.error import URLError

CAPTION_PROMPT = (
    'Describe this character image in danbooru style tags: '
    '"{trigger}", 1girl, {{pose}}, {{expression}}, {{gaze}}, {{framing}}. '
    'No hair/eye/clothing colors. Keep under 20 words.'
)

IMG_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def _check_ollama_health(ollama_url: str) -> bool:
    """检查 Ollama 是否在运行。"""
    base = ollama_url.rstrip("/api/generate").rstrip("/")
    try:
        req = urllib_request.Request(f"{base}/api/tags", method="GET")
        with urllib_request.urlopen(req, timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def _get_available_models(ollama_url: str) -> list[str]:
    """列出 Ollama 已安装的模型。"""
    base = ollama_url.rstrip("/api/generate").rstrip("/")
    try:
        req = urllib_request.Request(f"{base}/api/tags", method="GET")
        with urllib_request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def caption_image(
    model: str,
    image_path: Path,
    trigger: str,
    ollama_url: str = "http://127.0.0.1:11434/api/generate",
    timeout: float = 120,
) -> str:
    """调用 Ollama VL 生成单张图片的标注。"""
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    prompt = CAPTION_PROMPT.format(trigger=trigger)
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "images": [b64],
        "stream": False,
        "options": {"num_predict": 30},
    }).encode()

    req = urllib_request.Request(
        ollama_url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    with urllib_request.urlopen(req, timeout=timeout) as r:
        resp = json.loads(r.read())
        text = resp.get("response", "").strip()

    # 清理：合并多行、去多余空格
    text = " ".join(text.replace("\n", " ").replace("\r", "").split())
    return text


def run_captioning(
    image_dir: Path,
    trigger: str,
    *,
    model: str = "qwen3.5:9b",
    ollama_url: str = "http://127.0.0.1:11434/api/generate",
    dry_run: bool = False,
) -> dict:
    """对目录中所有图片执行标图。返回统计信息。"""
    if not image_dir.is_dir():
        print(f"目录不存在: {image_dir}", file=sys.stderr)
        return {"total": 0, "success": 0, "failed": 0}

    files = sorted([
        p for p in image_dir.iterdir()
        if p.suffix.lower() in IMG_EXTENSIONS and p.is_file()
    ])

    if not files:
        print(f"未找到图片文件在: {image_dir}")
        return {"total": 0, "success": 0, "failed": 0}

    existing = sum(1 for f in files if f.with_suffix(".txt").exists())
    print(f"\n图片: {len(files)} 张")
    print(f"触发词: {trigger}")
    print(f"模型: {model}")
    print(f"已有标注: {existing}/{len(files)}")

    if dry_run:
        print("\n[dry-run] 预览模式，不实际调用 API:")
        for f in files[:5]:
            txt = f.with_suffix(".txt")
            status = "✅" if txt.exists() else "📄"
            print(f"  {status} {f.name}")
        if len(files) > 5:
            print(f"  ... 还有 {len(files)-5} 张")
        return {"total": len(files), "success": existing, "dry_run": True}

    # 检查 Ollama
    if not _check_ollama_health(ollama_url):
        print("\n❌ Ollama 未运行。请先在 WSL 中启动:")
        print("   wsl sh -c 'nohup ollama serve > /dev/null 2>&1 &'")
        print("   或: python -m agents check")
        return {"total": 0, "success": 0, "failed": 0}

    # 检查模型
    available = _get_available_models(ollama_url)
    if not any(model in m for m in available):
        print(f"\n⚠️  Ollama 中未找到模型 '{model}'")
        if available:
            print(f"   可用: {', '.join(available[:8])}")
        if "qwen2.5vl:7b" in str(available):
            print("   提示: 使用 --model qwen2.5vl:7b")
        return {"total": 0, "success": 0, "failed": 0}

    # 执行标图
    success = existing
    failed = 0
    start = time.time()

    for i, f in enumerate(files):
        txt_path = f.with_suffix(".txt")
        if txt_path.exists():
            continue  # 跳过已有标注的

        print(f"  [{i+1}/{len(files)}] {f.name}...", end=" ", flush=True)
        try:
            caption = caption_image(model, f, trigger, ollama_url)
            txt_path.write_text(caption + "\n", encoding="utf-8")
            success += 1
            print(f"✅ {caption[:60]}")
        except (URLError, OSError, json.JSONDecodeError) as exc:
            failed += 1
            print(f"❌ {exc}")
            if "timeout" in str(exc).lower():
                print("    超时，跳过后续。")
                break

        if (i + 1) % 10 == 0:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed
            remaining = (len(files) - i - 1) / rate if rate > 0 else 0
            print(f"    进度: {i+1}/{len(files)} | {elapsed:.0f}s | "
                  f"预估剩余: {remaining:.0f}s")

    elapsed = time.time() - start
    print(f"\n标图完成: {success}/{len(files)} 成功, {failed} 失败, {elapsed:.0f}s")
    return {"total": len(files), "success": success, "failed": failed}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Ollama VL 自动标图 — 生成训练数据 .txt 标注",
    )
    parser.add_argument(
        "--dir", required=True,
        help="训练图片目录（会扫描所有 .png .jpg 等）",
    )
    parser.add_argument(
        "--trigger", required=True,
        help="角色触发词（如 Ha Eun、Knives、Caster）",
    )
    parser.add_argument(
        "--model", default="qwen3.5:9b",
        help="Ollama VL 模型名（默认 qwen3.5:9b）",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="预览模式，不实际调用 API",
    )
    args = parser.parse_args()

    result = run_captioning(
        Path(args.dir),
        args.trigger,
        model=args.model,
        dry_run=args.dry_run,
    )

    if result.get("dry_run"):
        print("\n使用 --dry-run 确认后，去掉该选项执行实际标图。")
    elif result["total"] == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
