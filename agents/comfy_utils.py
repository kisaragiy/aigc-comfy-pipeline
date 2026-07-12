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

# Dry-run 标志：设为 True 时 comfy_post_prompt / wait_images 跳过真正提交
DRY_RUN = False


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


def check_comfy_health(prompt_url: str | None = None) -> bool:
    """Check if ComfyUI is reachable and ready. Returns True if healthy."""
    base = comfy_base_url(prompt_url)
    try:
        r = requests.get(f"{base}/queue", timeout=5)
        return r.status_code == 200
    except requests.RequestException:
        return False


def check_ollama_health(url: str | None = None) -> bool:
    """Check if Ollama is reachable. Returns True if healthy."""
    ollama_url = url or DEFAULT_OLLAMA_URL
    base = ollama_url.rstrip("/api/generate").rstrip("/")
    try:
        r = requests.get(f"{base}/api/tags", timeout=5)
        return r.status_code == 200
    except requests.RequestException:
        return False


def ollama_generate_or_fallback(
    prompt: str,
    *,
    url: str | None = None,
    model: str | None = None,
    timeout: float = 120,
    fallback: str | None = None,
) -> str:
    """尝试 Ollama 生成，不可用时 warn + 返回 fallback/原始 prompt。"""
    try:
        return ollama_generate(prompt, url=url, model=model, timeout=timeout)
    except (RuntimeError, requests.RequestException) as exc:
        print(f"[warn] Ollama 不可用，使用原始输入。{exc}", file=sys.stderr)
        return fallback if fallback is not None else prompt


SIX_DIMENSION_TEMPLATE = """\
你是一个 SDXL / Flux 提示词工程师。按六维度构图法将用户描述转为英文 danbooru 标签。
输出格式：一段逗号分隔的英文标签，不要编号、不要解释、不要引号。

六维架构：
[画风定位] 画风、渲染风格
[主体细节] 角色名、外貌、服装、表情、姿势、神态
[环境氛围] 背景、天气、季节、时间、微粒
[光影魔法] 光源方向、体积光、反射、色彩
[镜头语言] 景别、焦距、机位、角度
[质量修饰] masterpiece, best quality, ultra detailed, 8k, cinematic lighting

用户描述：{user_input}

处理规则：
- 如果用户提到角色名（knives/caster），自动追加对应触发词和发色瞳色标签
- 每个维度至少 2-3 个标签
- 角色优先使用动漫/anime 画风
- 颜色要具体（如"深红"而非"红色"）
- 材质要明确（如"丝绸质地"而非"漂亮衣服"）
- 光线必须标注方向
"""


def optimize_prompt(
    user_input: str,
    *,
    url: str | None = None,
    model: str | None = None,
    timeout: float = 120,
) -> str:
    """六维度构图法优化提示词。

    使用 Ollama 将用户自然语言描述转为结构化英文 danbooru 标签。
    若 Ollama 不可用，返回模板化的基础提示词。

    Args:
        user_input: 中文自然语言描述
        url: Ollama URL
        model: Ollama 模型名
        timeout: 超时秒数

    Returns:
        优化后的英文提示词标签串
    """
    prompt = SIX_DIMENSION_TEMPLATE.format(user_input=user_input)
    try:
        return ollama_generate(prompt, url=url, model=model, timeout=timeout)
    except (RuntimeError, requests.RequestException) as exc:
        print(f"[warn] optimize_prompt Ollama 不可用: {exc}", file=sys.stderr)
        # 基础降级：将用户输入作为 raw prompt
        return user_input


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
    # Dry-run 模式：跳过真实提交
    if DRY_RUN:
        print("[dry-run] 跳过 ComfyUI 提交（参数已就绪）")
        return {"prompt_id": "dry-run"}
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
    if prompt_id == "dry-run":
        if __debug__:
            print("[dry-run] 跳过等待出图")
        return []
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
