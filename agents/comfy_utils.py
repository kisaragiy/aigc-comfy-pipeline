"""ComfyUI / Ollama 共用工具（agents 目录内脚本复用）。"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any
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


def _fallback_prompt(user_input: str) -> str:
    """Ollama 不可用时的模板兜底。关键词匹配 → 英文 tag 模板。"""
    quality = "masterpiece, best quality, ultra detailed, 8k"
    base_style = "anime style, anime coloring, anime artwork"
    camera = "cowboy shot, upper body, looking at viewer"
    lighting = "soft lighting, natural light"
    bg = "detailed background"

    # 关键词 → 参数覆盖
    keywords = {
        "风景": {"camera": "wide shot, landscape, scenery, cityscape"},
        "山水": {"camera": "wide shot, landscape, scenery, mountains"},
        "城市": {"camera": "wide shot, cityscape, urban",
                "lighting": "neon lighting, street lights"},
        "夜景": {"lighting": "moonlight, night lighting, dark atmosphere",
                "camera": "night scene, wide shot"},
        "赛博朋克": {"style": "cyberpunk, futuristic, neon",
                  "lighting": "neon lighting, holographic, colorful lights"},
        "全身": {"camera": "full body, standing, dynamic pose"},
        "半身": {"camera": "upper body, cowboy shot, waist up"},
        "特写": {"camera": "close-up, face focus, extreme close-up, detailed face"},
        "战斗": {"style": "action scene, dynamic action, battle",
                "camera": "dynamic angle, action pose, mid-air"},
        "海边": {"bg": "beach, ocean, seaside, waves, sand, sunset"},
        "教室": {"bg": "classroom, desk, blackboard, school interior"},
        "校服": {"style": "school uniform, casual, student"},
        "战斗": {"style": "action, dynamic pose, battle ready"},
        "微笑": {"camera": "smiling, gentle smile, happy expression"},
        "少女": {"style": "bishoujo, cute girl, anime girl"},
    }

    for kw, overrides in keywords.items():
        if kw in user_input:
            if "camera" in overrides:
                camera = overrides["camera"]
            if "lighting" in overrides:
                lighting = overrides["lighting"]
            if "bg" in overrides:
                bg = overrides["bg"]
            if "style" in overrides:
                base_style = overrides["style"]

    return f"{quality}, {base_style}, {user_input}, {camera}, {bg}, {lighting}"


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
        print(f"[warn] Ollama 不可用，使用模板兜底: {exc}", file=sys.stderr)
        return _fallback_prompt(user_input)


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


# ============================================================
# 质量预设 + 自动门禁
# ============================================================

QUALITY_PRESETS: dict[str, dict[str, Any]] = {
    "quality": {"steps": 40, "cfg": 7.0, "sampler": "dpmpp_3m_sde", "scheduler": "karras"},
    "balanced": {"steps": 28, "cfg": 6.5, "sampler": "dpmpp_2m", "scheduler": "karras"},
    "fast": {"steps": 15, "cfg": 5.0, "sampler": "euler", "scheduler": "normal"},
    "portrait": {"width": 896, "height": 1152, "cfg": 7.5,
                 "sampler": "dpmpp_2m", "scheduler": "karras"},
}

VIDEO_PRESETS: dict[str, dict[str, Any]] = {
    "quality": {"frames": 81, "fps": 25, "width": 1024, "height": 1024,
                "steps": 40, "cfg": 7.0},
    "balanced": {"frames": 49, "fps": 20, "width": 848, "height": 480,
                 "steps": 30, "cfg": 7.0},
    "fast": {"frames": 25, "fps": 15, "width": 512, "height": 288,
             "steps": 20, "cfg": 5.0},
    "cinematic": {"frames": 81, "fps": 24, "width": 1280, "height": 720,
                  "steps": 40, "cfg": 8.0},
}


def _load_custom_presets() -> dict[str, dict[str, Any]]:
    """从项目根目录 presets.json 加载自定义预设。"""
    path = AGENTS_DIR.parent / "presets.json"
    if not path.is_file():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[warn] 自定义预设加载失败: {exc}", file=sys.stderr)
        return {}


# 合并自定义预设到内置预设表中
_CUSTOM_PRESETS = _load_custom_presets()
QUALITY_PRESETS.update(_CUSTOM_PRESETS.get("QUALITY_PRESETS", {}))
VIDEO_PRESETS.update(_CUSTOM_PRESETS.get("VIDEO_PRESETS", {}))


def apply_preset(params: dict[str, Any], preset: str | None = None,
                 presets: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """应用预设到参数。用户显式指定的参数优先。

    Args:
        params: 用户参数（显式值覆盖预设）
        preset: 预设名称；None 使用 AIGC_PRESET 环境变量
        presets: 预设表；None 使用 QUALITY_PRESETS

    Returns:
        合并后的参数字典
    """
    table = presets if presets is not None else QUALITY_PRESETS
    env_key = "AIGC_VIDEO_PRESET" if presets is not None else "AIGC_PRESET"
    fallback = "balanced" if "balanced" in table else next(iter(table))
    name = preset or os.environ.get(env_key, fallback)
    if name not in table:
        fallback_name = next(iter(table))
        print(f"[warn] 未知预设 '{name}'，使用 {fallback_name}", file=sys.stderr)
        name = fallback_name

    result = dict(table[name])
    for k, v in params.items():
        if v is not None and k not in ("preset", "min_score", "retry", "no_validate"):
            result[k] = v

    preset_example = ", ".join(
        f"{k}={v}" for k, v in result.items() if k in next(iter(table.values()), {}))
    print(f"[info] 预设 {name} → {preset_example}" if preset_example
          else f"[info] 预设 {name}")
    return result


def generate_with_quality(
    build_fn: callable,
    prompt: str,
    *,
    min_score: float = 0.0,
    max_retries: int = 0,
    preset: str | None = None,
    no_validate: bool = False,
    wait_timeout: float = 900.0,
    **kwargs: Any,
) -> dict[str, Any]:
    """生成 + 质量验证 + 自动重试。

    Args:
        build_fn: 工作流构建函数（如 build_flux_workflow）
        prompt: 提示词
        min_score: CLIP 评分阈值（≤0 跳过验证）
        max_retries: 最大重试次数
        preset: 质量预设名
        no_validate: 强制跳过验证
        wait_timeout: 等待出图超时秒数（视频需要更长）
        kwargs: 传给 build_fn 的参数

    Returns:
        {"workflow": wf, "seed": seed, "images": [...], "score": score, "retries": n}
    """
    import random

    params = apply_preset(kwargs, preset)
    for skip_key in ("preset", "no_validate", "min_score", "retry"):
        params.pop(skip_key, None)

    do_validate = not no_validate and min_score > 0

    best_score = -1.0
    best_result: dict[str, Any] | None = None

    for attempt in range(max_retries + 1):
        # seed 由 generate_with_quality 管理，不在 params 中传递
        params.pop("seed", None)
        seed = kwargs.get("seed", -1)
        if isinstance(seed, (int, float)) and (seed == -1 or attempt > 0):
            seed = random.randint(1, 2**48 - 1)

        wf, actual_seed = build_fn(prompt, seed=int(seed), **params)
        r = comfy_post_prompt(wf)
        pid = r.get("prompt_id", "")

        if pid == "dry-run":
            return {"workflow": wf, "seed": actual_seed, "images": [], "score": None, "retries": 0}

        base = comfy_base_url()
        try:
            images = wait_images(pid, base, timeout_s=wait_timeout)
        except (TimeoutError, RuntimeError) as exc:
            print(f"  [warn] 等待出图失败: {exc}", file=sys.stderr)
            continue

        comfy_root = resolve_comfy_root()
        image_paths: list[str] = []
        for sub, name in images:
            path = (comfy_root / "output" / sub / name).resolve()
            if path.is_file():
                image_paths.append(str(path))

        score: float | None = None
        if do_validate and image_paths:
            try:
                from go_validate import validate_image
                v = validate_image(image_paths[0], prompt)
                clip = v.get("clip_score", {})
                if clip.get("available") and clip.get("score") is not None:
                    score = clip["score"]
            except Exception as exc:
                print(f"  [warn] 验证失败: {exc}", file=sys.stderr)

        current = {"workflow": wf, "seed": actual_seed, "images": image_paths,
                   "score": score, "retries": attempt}

        if score is not None and score > best_score:
            best_score = score
            best_result = current

        if score is not None and score >= min_score:
            print(f"  ✅ score={score:.3f} ≥ {min_score}")
            return current

        if attempt < max_retries:
            s = f"{score:.3f}" if score is not None else "N/A"
            print(f"  ⚠️ score={s} < {min_score}，重试 ({attempt+1}/{max_retries})")

    if best_result:
        return best_result

    return {"workflow": wf, "seed": actual_seed, "images": image_paths,
            "score": score, "retries": attempt}
