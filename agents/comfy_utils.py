"""ComfyUI / Ollama 共用工具（agents 目录内脚本复用）。"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

AGENTS_DIR = Path(__file__).resolve().parent
DEFAULT_COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188/prompt")
DEFAULT_OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
DEFAULT_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:14b")


def bootstrap_agents_path() -> Path:
    """保证从任意工作目录运行脚本时都能 import 同目录模块。"""
    root = str(AGENTS_DIR)
    if root not in sys.path:
        sys.path.insert(0, root)
    return AGENTS_DIR


def comfy_base_url(prompt_url: str | None = None) -> str:
    u = prompt_url or DEFAULT_COMFY_URL
    p = urlparse(u)
    return f"{p.scheme}://{p.netloc}"


def resolve_comfy_root() -> Path:
    if os.environ.get("COMFY_ROOT"):
        return Path(os.environ["COMFY_ROOT"]).resolve()
    for candidate in (
        Path(r"C:\DrawingLive\comfyUI"),
        Path(r"C:\DrawingLive\ComfyUI"),
    ):
        if candidate.is_dir():
            return candidate.resolve()
    return Path(r"C:\DrawingLive\comfyUI")


def ollama_generate(
    prompt: str,
    *,
    url: str | None = None,
    model: str | None = None,
    timeout: float = 120,
) -> str:
    ollama_url = url or DEFAULT_OLLAMA_URL
    ollama_model = model or DEFAULT_OLLAMA_MODEL
    try:
        r = requests.post(
            ollama_url,
            json={"model": ollama_model, "prompt": prompt, "stream": False},
            timeout=timeout,
        )
        r.raise_for_status()
        data = r.json()
        text = data.get("response", "").strip()
        if not text:
            raise RuntimeError(f"Ollama 返回为空: {data!r}")
        return text
    except requests.RequestException as exc:
        raise RuntimeError(
            f"无法连接 Ollama（{ollama_url}，模型 {ollama_model}）: {exc}\n"
            "处理：1) 启动本机 Ollama 或修正环境变量 OLLAMA_URL / OLLAMA_MODEL\n"
            "      2) 使用 --raw 跳过 Ollama，直接写英文 tag"
        ) from exc


def comfy_post_prompt(
    workflow: dict,
    *,
    prompt_url: str | None = None,
    timeout: float = 60,
) -> dict:
    url = prompt_url or DEFAULT_COMFY_URL
    try:
        r = requests.post(
            url,
            json={"prompt": workflow, "client_id": os.urandom(8).hex()},
            timeout=timeout,
        )
        print("ComfyUI 原始响应：", r.text)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as exc:
        base = comfy_base_url(url)
        raise RuntimeError(
            f"无法连接 ComfyUI（{url}）: {exc}\n"
            f"请确认 ComfyUI 已启动，浏览器可打开 {base}"
        ) from exc


def extract_images_from_history(data: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if not isinstance(data, dict):
        return out
    for job in data.values():
        if not isinstance(job, dict):
            continue
        for node_out in (job.get("outputs") or {}).values():
            if not isinstance(node_out, dict):
                continue
            for img in node_out.get("images") or []:
                if isinstance(img, dict) and img.get("filename"):
                    out.append((str(img.get("subfolder") or ""), str(img["filename"])))
    return out


def wait_images(
    prompt_id: str,
    base: str,
    timeout_s: float = 900.0,
) -> list[tuple[str, str]]:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            r = requests.get(f"{base}/history/{prompt_id}", timeout=30)
        except requests.RequestException as exc:
            raise RuntimeError(f"无法读取 ComfyUI 历史（{base}）: {exc}") from exc
        if r.status_code != 200:
            time.sleep(1.5)
            continue
        data = r.json()
        imgs = extract_images_from_history(data)
        if imgs:
            return imgs
        if isinstance(data, dict) and data:
            first = next(iter(data.values()), None)
            if isinstance(first, dict):
                st = (first.get("status") or {}).get("status_str")
                if st == "error":
                    msgs = (first.get("status") or {}).get("messages") or []
                    raise RuntimeError(f"ComfyUI 任务错误: {msgs}")
        time.sleep(1.5)
    raise TimeoutError(f"等待 ComfyUI 出图超时 prompt_id={prompt_id}")
