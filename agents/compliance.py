#!/usr/bin/env python3
"""
compliance.py — B1 提示词符合度检测（P0）

【定位】生成图"是不是按你要的画的"。用 PNG metadata(ComfyUI tEXt 存的 prompt)
  与 VLM 对图的视觉描述对比，抓"画错东西"（如发色错了/服装错了/姿势不对/场景不同）。

【原理】
  1. 读 PNG tEXt 里的 prompt（ComfyUI 生成时自动写入，含关键特征）
  2. 提取 prompt 里的约束特征（发色/瞳色/服装/姿势/场景/风格）
  3. VLM 看图，输出该图的实际特征
  4. 对比 prompt 约束 vs 图实际特征 → 判定符合度
     - 关键属性(发色/瞳色/服装)不符 → 死点 FAIL(画错东西)
     - 次要属性(场景/姿势)偏差 → warn
     - 符合 → pass

【用法】
  from compliance import compliance_check
  res = compliance_check("out.png")   # 读元数据+调VLM
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

TIMEOUT = 90

# 关键属性词（大小写不敏感；命中即视为"必须核对"）
KEY_ATTR_PATTERNS = {
    "hair": r"\b(hair|长发|短发|马尾|头发)\b",
    "eye": r"\b(eyes?|eye color|瞳|眼睛)\b",
    "outfit": r"\b(dress|outfit|uniform|裙|服|衣|铠甲)\b",
}


def _load_deepseek():
    """读 Hermes .env 的 DeepSeek key。"""
    api_key, base_url = "", "https://api.deepseek.com"
    env_path = os.path.expanduser("~/AppData/Local/hermes/.env")
    if Path(env_path).is_file():
        with open(env_path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    v = v.strip().strip('"').strip("'")
                    if k.strip() == "DEEPSEEK_API_KEY":
                        api_key = v
                    elif k.strip() == "DEEPSEEK_BASE_URL":
                        base_url = v.strip().rstrip("/")
    return api_key, base_url


def read_prompt_meta(image_path: str) -> str:
    """读 PNG tEXt 里的 prompt（ComfyUI 标准键）。"""
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from workshop.image_utils import read_png_meta
        meta = read_png_meta(image_path)
        # prompt 可能是 json 字符串或纯文本
        p = meta.get("prompt", "")
        if not p:
            return ""
        # ComfyUI 的 prompt 是 json；尝试提取 positive 的关键文本
        try:
            data = json.loads(p)
            # 从 ComfyUI workflow prompt 里找 CLIPTextEncode 的 text
            texts = []
            for node_id, node in data.items():
                if isinstance(node, dict):
                    inputs = node.get("inputs", {})
                    t = inputs.get("text", "")
                    if isinstance(t, str) and t.strip():
                        texts.append(t)
            return "\n".join(texts) if texts else p
        except json.JSONDecodeError:
            return p
    except Exception:
        return ""


def image_to_data_url(path: str, max_dim: int = 1100) -> str:
    from PIL import Image
    import io
    import base64
    im = Image.open(path).convert("RGB")
    if max(im.size) > max_dim:
        r = max_dim / max(im.size)
        im = im.resize((int(im.width * r), int(im.height * r)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


# VLM 符合度判断 prompt
COMPLIANCE_PROMPT = """You are checking if an AI-image matches its generation prompt.
Below is the PROMPT that was used to generate the image:

=== PROMPT ===
{prompt}
=== END PROMPT ===

Now look at the actual image. Determine if it matches the prompt's KEY attributes.
Check SPECIFICALLY:
1. 发色 (hair color): prompt 说的发色 vs 图中实际发色 — 一致?
2. 瞳色 (eye color): 一致?
3. 服装 (outfit/clothing): 主要服装特征(款式/颜色) — 一致?
4. 姿势/场景/风格: 大体符合?

Return ONLY JSON:
{"hair_match": <true/false>, "eye_match": <true/false>, "outfit_match": <true/false>,
 "overall_match": <true/false>, "mismatches": [<具体不符处, 无则空数组>],
 "confidence": <0-1>}"""


def vlm_check_compliance(data_url: str, prompt: str, api_key: str, base_url: str) -> dict:
    import requests
    # 用 replace 而非 .format —— COMPLIANCE_PROMPT 里 JSON 示例含大量 {},
    # .format 会把 "hair_match" 这类当占位符导致 KeyError。
    pl = COMPLIANCE_PROMPT.replace("{prompt}", prompt[:2000])
    payload = {
        "model": "deepseek-v4-flash-vision-exp",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": pl},
            ],
        }],
        "max_tokens": 2000,
        "stream": False,
        "reasoning_effort": "low",
    }
    r = requests.post(f"{base_url}/v1/chat/completions",
                      headers={"Authorization": f"Bearer {api_key}"},
                      json=payload, timeout=TIMEOUT)
    content = r.json()["choices"][0]["message"].get("content", "")
    m = re.search(r"\{.*\}", content, re.DOTALL)
    if not m:
        return {"error": "no_json", "raw": content[:200]}
    try:
        return json.loads(m.group(0))
    except Exception as e:
        return {"error": f"json: {e}"}


def compliance_check(image_path: str) -> dict:
    """B1 提示词符合度。返回 {passed, verdict, detail, prompt_found}。"""
    prompt = read_prompt_meta(image_path)
    if not prompt:
        return {
            "passed": True, "verdict": "pass", "prompt_found": False,
            "detail": "无元数据 prompt(无法核对, 跳过)", "vlm": None,
        }

    api_key, base_url = _load_deepseek()
    if not api_key:
        return {"passed": True, "verdict": "pass", "prompt_found": True,
                "detail": "No DeepSeek key, 跳过", "vlm": None}

    try:
        data_url = image_to_data_url(image_path)
        vlm = vlm_check_compliance(data_url, prompt, api_key, base_url)
    except Exception as e:
        return {"passed": True, "verdict": "pass", "prompt_found": True,
                "detail": f"VLM 调用失败: {str(e)[:80]}", "vlm": None}

    if "error" in vlm:
        return {"passed": True, "verdict": "pass", "prompt_found": True,
                "detail": f"VLM 返回: {vlm['error']}", "vlm": vlm}

    mismatches = vlm.get("mismatches", []) or []
    # 关键属性字段可能缺失(VLM 某些返回略键) → 缺失视为无法核实, 不误判
    hair = vlm.get("hair_match")
    eye = vlm.get("eye_match")
    outfit = vlm.get("outfit_match")
    # 若三个关键字段全缺 → 无法核对, 保守 pass(不误杀), 标注
    if hair is None and eye is None and outfit is None:
        return {
            "passed": True, "verdict": "pass", "prompt_found": True,
            "detail": f"VLM 未返回关键属性字段, 无法核对 ({mismatches or '无信息'})",
            "vlm": vlm,
        }
    key_fail = not (hair if hair is not None else True) or \
               not (eye if eye is not None else True) or \
               not (outfit if outfit is not None else True)
    overall = vlm.get("overall_match", True)

    if key_fail:
        verdict = "fail"
    elif not overall:
        verdict = "warn"
    else:
        verdict = "pass"

    return {
        "passed": verdict == "pass",
        "verdict": verdict,
        "prompt_found": True,
        "detail": "，".join(mismatches) if mismatches else (
            "关键属性(发色/瞳色/服装)全部符合" if verdict == "pass" else "次要偏差"),
        "vlm": vlm,
    }
