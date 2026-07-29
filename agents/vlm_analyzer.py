"""
统一 VLM 分析引擎 — 角色特征、画风、caption、通用描述。

优先级:
  1. Ollama qwen3.5:9b (WSL, port 11434) — 原生多模态推理模型（精准）
  2. Ollama qwen3-vl:8b（可用 `OLLAMA_VL_MODEL` 切换）
  3. 返回空结果

注意:
  - qwen2.5vl:7b 已被禁用（不准）
  - Qwen3 系列的 <think> 标签自动剥离 /api/generate + /api/chat 双通道
"""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import requests

# ── 配置 ──────────────────────────────────────────

# Ollama VL 模型 — qwen3.5:9b 是原生多模态推理模型（精准）
# 也可换 qwen3-vl:8b（更轻量，无 reasoning 开销）
OLLAMA_API_BASE = os.environ.get("OLLAMA_API_BASE", "http://172.22.175.253:11434")
OLLAMA_VL_MODEL = os.environ.get("OLLAMA_VL_MODEL", "qwen3.5:9b")

# 注: qwen2.5vl:7b 已被禁用（不准）。


# ── 原生工具函数 ───────────────────────────────────

def _encode_image(image_path: str) -> str:
    """图片 → base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _check_vlm() -> bool:
    """检查 Qwen3.5-9B-VLM 是否可用"""
    try:
        r = requests.get(VLM_API_URL.replace("/v1/chat/completions", "/health"), timeout=3)
        return r.status_code == 200
    except Exception:
        pass
    try:
        r = requests.get(VLM_API_URL.replace("/v1/chat/completions", "/v1/models"), timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def _check_ollama_vl() -> bool:
    """检查 Ollama VL 是否可用"""
    try:
        r = requests.get(OLLAMA_VL_URL.replace("/api/chat", "/api/tags"), timeout=3)
        if r.status_code != 200:
            return False
        models = r.json().get("models", [])
        return any("vl" in m.get("name", "") for m in models)
    except Exception:
        return False


# ── Thinking 标签剥离（Qwen3 推理模型专用）───────

_THINK_PATTERN = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


def _strip_thinking_tags(text: str) -> str:
    """剥离 Qwen3 系列的 <think> 标签。"""
    text = _THINK_PATTERN.sub("", text)
    # 也处理未闭合的 <think>
    if "<think>" in text:
        text = text[: text.index("<think>")]
    return text.strip()


def _check_ollama_model(model: str = "") -> bool:
    """检查 Ollama 指定模型是否可用（通过 WSL 桥接）"""
    check_model = model or OLLAMA_VL_MODEL
    try:
        import subprocess, tempfile, json
        cmd = 'curl -s --max-time 10 http://localhost:11434/api/tags'
        proc = subprocess.run(['wsl', 'bash', '-c', cmd],
                            capture_output=True, text=True, timeout=15)
        if proc.returncode != 0 or not proc.stdout.strip():
            return False
        models = json.loads(proc.stdout.strip()).get("models", [])
        return any(check_model in m.get("name", "") for m in models)
    except Exception:
        return False


# ── Ollama 模型管理 ────────────────────────────────


def unload_vlm(model: str = "") -> None:
    """通知 Ollama 卸载指定模型释放显存。
    不指定模型则卸载当前主力模型。
    """
    model_to_unload = model or OLLAMA_VL_MODEL
    try:
        url = OLLAMA_VL_URL.replace("/api/chat", "/api/generate")
        payload = {"model": model_to_unload, "keep_alive": 0}
        requests.post(url, json=payload, timeout=5)
        print(f"[vlm_analyzer] ✅ Ollama 已卸载模型: {model_to_unload}", file=__import__('sys').stderr)
    except Exception as e:
        print(f"[vlm_analyzer] ⚠️ 卸载模型失败: {e}", file=__import__('sys').stderr)
# ── Ollama 视觉调用 ───────────────────────────────

def _call_ollama_vl(
    prompt: str,
    image_path: str,
    model: str = "",
    max_tokens: int = 1024,
) -> dict[str, Any]:
    """调用 Ollama VL 模型（支持推理/非推理模型）。
    自动剥离 Qwen3 的 <think> 标签。
    先试 /api/generate，若 response 空则试 /api/chat。
    """
    use_model = model or OLLAMA_VL_MODEL
    try:
        # 压缩图片到 768px 内
        from PIL import Image as _PIL
        import io as _io
        img = _PIL.open(image_path)
        w, h = img.size
        scale = 768 / max(w, h)
        if scale < 1:
            img = img.resize((int(w * scale), int(h * scale)), _PIL.LANCZOS)
        buf = _io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode()

        api_base = OLLAMA_API_BASE if "OLLAMA_API_BASE" in dir() or "OLLAMA_API_BASE" in globals() else "http://172.22.175.253:11434"
        if not api_base:
            api_base = "http://172.22.175.253:11434"

        # ── 方案 A: /api/generate via WSL bridge ──
        import tempfile as _tf
        payload = {
            "model": use_model,
            "prompt": prompt,
            "images": [b64],
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0.05},
        }
        pf = _tf.mktemp(suffix='.json')
        with open(pf, 'w') as f:
            json.dump(payload, f)
        wsl_path = '/mnt/c' + pf[2:].replace('\\', '/')
        wsl_cmd = f'cat {wsl_path} | curl -s --max-time 180 -X POST http://localhost:11434/api/generate -d @-'
        proc = subprocess.run(['wsl', 'bash', '-c', wsl_cmd],
                            capture_output=True, text=True, timeout=240)
        resp = ""
        if proc.returncode == 0 and proc.stdout.strip():
            data = json.loads(proc.stdout.strip())
            resp = data.get("response", "").strip()
            # 如果 response 空，检查 thinking 字段
            if not resp:
                resp = data.get("thinking", "").strip()

        # ── 剥离 thinking 标签 ──
        cleaned = _strip_thinking_tags(resp)
        if cleaned:
            resp = cleaned

        # ── 如果有内容直接返回 ──
        if resp:
            return {"available": True, "response": resp, "model": use_model}

        # ── 方案 B: /api/chat（某些推理模型在 chat 端点回复更完整）─
        chat_url = f"{api_base}/api/chat"
        chat_payload = {
            "model": use_model,
            "messages": [
                {"role": "user", "content": prompt, "images": [b64]},
            ],
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0.05},
        }
        try:
            r2 = requests.post(chat_url, json=chat_payload, timeout=180)
            if r2.status_code == 200:
                data2 = r2.json()
                msg = data2.get("message", {})
                chat_resp = msg.get("content", "").strip()
                # 同样剥离 thinking
                cleaned2 = _strip_thinking_tags(chat_resp)
                if cleaned2:
                    chat_resp = cleaned2
                if chat_resp:
                    return {"available": True, "response": chat_resp, "model": use_model, "_via": "chat"}
        except Exception:
            pass

        return {"available": False, "error": f"空响应: {resp[:100] if resp else '无输出'}"}
    except Exception as e:
        return {"available": False, "error": str(e)}


# ── 统一入口 ──────────────────────────────────────

def unified_vlm_analyze(
    image_path: str,
    prompt: str,
    prefer_vlm: bool = True,
    fallback_to_ollama: bool = True,
    max_tokens: int = 1024,
) -> dict[str, Any]:
    """统一 VLM 分析接口。

    优先级:
      1. Ollama qwen3-vl:8b（WSL）— 唯一视觉模型
      2. 返回空结果

    Args:
        image_path: 图片路径
        prompt: 分析的 prompt
        prefer_vlm: 始终 True（保留参数兼容）
        fallback_to_ollama: 保留参数兼容
        max_tokens: 最大输出 token

    Returns:
        {"available": bool, "response": str, "model": str, ...}
    """
    image_path = str(Path(image_path).resolve())
    if not Path(image_path).is_file():
        return {"available": False, "error": f"文件不存在: {image_path}"}

    # qwen3-vl:8b 是唯一可用的视觉模型
    if _check_ollama_model():
        result = _call_ollama_vl(prompt, image_path, max_tokens=max_tokens)
        if result.get("available"):
            return result

    return {"available": False, "error": "qwen3-vl:8b 不可用"}


def _extract_json(text: str) -> dict[str, Any] | None:
    """从 VLM 回复中提取 JSON 对象。"""
    # 尝试直接解析
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 找 { ... }
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return None


# ── 角色特征提取 ──────────────────────────────────

CHARACTER_PROMPT = """Analyze this character image in detail. Output ONLY valid JSON:
{
  "hair_style": "long straight flowing",
  "hair_color": "silver-white",
  "eye_color": "purple-violet",
  "eye_shape": "large almond",
  "skin_tone": "pale fair",
  "face_shape": "oval small",
  "distinctive_features": ["gold hair ornament", "black ribbon"],
  "outfit_top": "navy military jacket gold trim",
  "outfit_bottom": "white skirt",
  "outfit_color": "navy white gold",
  "accessories": ["gold ornament", "ribbon", "boots"],
  "overall_impression": "elegant confident cool-type"
}
Keep descriptions concise (2-5 words each). Include hex color codes if possible."""


def analyze_character(
    image_path: str,
    prefer_vlm: bool = True,
) -> dict[str, Any]:
    """角色特征提取 — 发色/瞳色/服装/饰品等结构化数据。"""
    result = unified_vlm_analyze(image_path, CHARACTER_PROMPT, prefer_vlm=prefer_vlm)
    if not result.get("available"):
        return result

    parsed = _extract_json(result["response"])
    if parsed:
        result.update(parsed)

    return result


# ── 画风分析 ──────────────────────────────────────

STYLE_PROMPT = """Analyze the ART STYLE of this image (NOT the character/scene content).
Output ONLY valid JSON:
{
  "art_style": "anime semi-realistic",
  "shading": "smooth cel shading",
  "line_art": "thin clean lines",
  "color_palette": "warm vibrant",
  "lighting": "soft rim light",
  "brushwork": "smooth detailed",
  "contrast": "medium",
  "mood": "serene dynamic"
}
Focus on HOW it's drawn, not WHAT is drawn."""


def analyze_style(
    image_path: str,
    prefer_vlm: bool = True,
) -> dict[str, Any]:
    """画风分析 — 笔触/配色/光源等风格特征。"""
    result = unified_vlm_analyze(image_path, STYLE_PROMPT, prefer_vlm=prefer_vlm)
    if not result.get("available"):
        return result

    parsed = _extract_json(result["response"])
    if parsed:
        result.update(parsed)

    return result


# ── Caption 生成 ──────────────────────────────────

def generate_caption(
    image_path: str,
    trigger_word: str,
    format: str = "tags",
    prefer_vlm: bool = True,
) -> dict[str, Any]:
    """训练数据标图 — 生成 Danbooru-style caption。"""
    examples = {
        "tags": "shm_character, 1girl, silver_hair, long_hair, purple_eyes, white_dress, standing, looking_at_viewer, outdoors, garden, sunset",
        "natural": "shm_character is a young woman with long silver hair and purple eyes wearing a white dress, standing in a garden at sunset.",
        "hybrid": "shm_character, silver_hair, long_hair, purple_eyes, white_dress, standing in a garden at sunset, soft lighting",
    }
    fmt_example = examples.get(format, examples["tags"])

    prompt = f"""Generate a detailed image caption for training a LoRA model.
The trigger word is "{trigger_word}".
Use {format} format like this example:
{fmt_example}

Describe: hair style+color, eye color+shape, skin tone, outfit colors+style,
accessories, expression, pose, background.
Start the caption with "{trigger_word}".

Caption:"""

    result = unified_vlm_analyze(image_path, prompt, prefer_vlm=prefer_vlm)
    if result.get("available"):
        result["format"] = format
        result["trigger_word"] = trigger_word
    return result


# ── 通用图片描述 ──────────────────────────────────

DESCRIBE_PROMPT = """Describe this image in detail, suitable for use as an AI image generation prompt.
Focus on: subject appearance, clothing colors and style, pose, facial expression,
background/environment, lighting, atmosphere, composition.
Keep it concise (1-2 sentences). Start with the most important visual elements first."""


def describe_image(
    image_path: str,
    prefer_vlm: bool = True,
) -> str:
    """通用图片描述 — 返回适合作为 prompt 的自然语言描述。"""
    result = unified_vlm_analyze(image_path, DESCRIBE_PROMPT, prefer_vlm=prefer_vlm)
    if result.get("available"):
        return result["response"]
    return ""


# ── 图片描述 → 结构化特征（给 Hermes 用）──────────

def image_to_features(image_path: str) -> dict[str, Any]:
    """一键提取图片所有特征 — 给 Hermes 的通用接口。"""
    char = analyze_character(image_path)
    style = analyze_style(image_path)
    desc = describe_image(image_path)
    return {
        "available": char.get("available") or style.get("available"),
        "description": desc,
        "character": {
            k: char.get(k) for k in [
                "hair_style", "hair_color", "eye_color", "eye_shape",
                "skin_tone", "face_shape", "distinctive_features",
                "outfit_top", "outfit_bottom", "outfit_color", "accessories",
            ] if char.get(k)
        },
        "style": {
            k: style.get(k) for k in [
                "art_style", "shading", "line_art", "color_palette",
                "lighting", "brushwork", "contrast", "mood",
            ] if style.get(k)
        },
    }


# ── CLI ───────────────────────────────────────────

def main():
    import sys
    args = sys.argv[1:]

    if not args:
        print("用法: python vlm_analyzer.py <图片路径> [--char|--style|--caption TRIGGER|--describe]")
        return

    image_path = args[0]
    mode = args[1] if len(args) > 1 else "--describe"

    if mode == "--char":
        result = analyze_character(image_path)
        print(json.dumps(result.get("character", result), ensure_ascii=False, indent=2))
    elif mode == "--style":
        result = analyze_style(image_path)
        print(json.dumps(result.get("style", result), ensure_ascii=False, indent=2))
    elif mode == "--caption" and len(args) > 2:
        result = generate_caption(image_path, args[2])
        print(result.get("response", str(result)))
    else:
        result = describe_image(image_path)
        print(result)


if __name__ == "__main__":
    main()
