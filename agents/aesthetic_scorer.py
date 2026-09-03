"""
VLM 审美评分引擎 — 统一接口

主力: Ollama qwen3-vl:8b（合并评分, 8s/图, 6维度）
备选: 专用 llama-server Qwen3.5-9B-VLM (port 8083)

用法:
    from agents.aesthetic_scorer import AestheticScorer
    scorer = AestheticScorer()
    result = scorer.score("output.png")
    # → {"face_score": 8, "composition_score": 7, "color_score": 9,
    #     "overall_score": 8.0, "feedback": "...", "available": True}
"""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

import requests

# ── Ollama 配置（主力） ──
def _detect_ollama_api() -> str:
    env = os.environ.get("OLLAMA_API", "").strip()
    if env:
        return env.rstrip("/")
    try:
        r = subprocess.run(
            ["wsl", "-e", "bash", "-c", "hostname -I | awk '{print $1}'"],
            capture_output=True, text=True, timeout=8)
        ip = r.stdout.strip().split()[0] if r.stdout.strip() else ""
        if ip:
            return f"http://{ip}:11434"
    except Exception:
        pass
    return "http://127.0.0.1:11434"

OLLAMA_API = _detect_ollama_api()
OLLAMA_VL_MODEL = os.environ.get("OLLAMA_VL_MODEL", "qwen3-vl:8b")

# ── 专用 VLM 配置（备选） ──
VLM_HOST = os.environ.get("VLM_HOST", "127.0.0.1")
VLM_PORT = int(os.environ.get("VLM_PORT", "8083"))
VLM_MODEL = os.environ.get("VLM_MODEL", "Qwen3.5-9B-VLM")
LLAMA_DIR = Path(os.environ.get("LLAMA_DIR", r"C:\llama\llama.cpp"))
LLAMA_SERVER = LLAMA_DIR / "llama-server.exe"
MODEL_PATH = LLAMA_DIR / "models" / "Qwen3.5-9B-Q4_K_M.gguf"
MMPROJ_PATH = LLAMA_DIR / "models" / "Qwen3.5-9B-mmproj-F16.gguf"

# ── 合并评估 Prompt（6维度+符合度, 1次调用） ──
COMBINED_EVAL_PROMPT = """Analyze this image aesthetically. Return ONLY valid JSON (no markdown, no extra text):
{
  "composition": <0-10>,
  "color": <0-10>,
  "lighting": <0-10>,
  "character": <0-10>,
  "emotional": <0-10>,
  "overall": <0-10>,
  "has_subject": <true/false>,
  "subject_match": "<does the image contain the main subject described in the request? be honest, empty image or wrong subject = false>",
  "strength": "<main advantage of this image>",
  "weakness": "<main flaw if any, e.g. missing subject, deformed hands, wrong clothing>",
  "summary": "<1 sentence overall assessment>"
}"""


class AestheticScorer:
    def __init__(self, backend: str = "ollama", auto_start: bool = False, verbose: bool = False):
        self.backend = backend
        self.verbose = verbose
        self._server_proc: subprocess.Popen | None = None
        if backend == "dedicated":
            self.api_url = f"http://{VLM_HOST}:{VLM_PORT}"
            if auto_start and not self._check_dedicated():
                self._start_server()
        else:
            self.api_url = OLLAMA_API

    def _check_ollama(self) -> bool:
        try:
            r = requests.get(f"{OLLAMA_API}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def _check_dedicated(self, timeout: float = 3) -> bool:
        try:
            r = requests.get(f"{self.api_url}/health", timeout=timeout)
            return r.status_code == 200
        except Exception:
            pass
        try:
            r = requests.get(f"{self.api_url}/v1/models", timeout=timeout)
            return r.status_code == 200
        except Exception:
            return False

    # ── 评分 ──

    def score(self, image_path: str, timeout: float = 60) -> dict[str, Any]:
        if not Path(image_path).is_file():
            return {"available": False, "error": f"Image not found: {image_path}", "overall_score": -1}
        if self.backend == "dedicated":
            return self._score_dedicated(image_path, timeout)
        return self._score_ollama(image_path, timeout)

    def _score_ollama(self, image_path: str, timeout: float = 60) -> dict[str, Any]:
        """Ollama 合并评分，使用 /api/generate 解决 thinking 吞 response 问题。"""
        if not self._check_ollama():
            return {"available": False, "error": "Ollama not running", "overall_score": -1}

        try:
            from PIL import Image
            import io
            img = Image.open(image_path)
            img.thumbnail((512, 512), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

            # 2026-08-20 修复：/api/generate + num_predict=2048
            # 根因：qwen3-vl thinking 模式吃 token，1024 不够，2048 才够 thinking+response
            payload = {
                "model": OLLAMA_VL_MODEL,
                "prompt": COMBINED_EVAL_PROMPT,
                "images": [img_b64],
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 2048},
            }

            r = requests.post(f"{OLLAMA_API}/api/generate", json=payload, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            content = data.get("response", "").strip()

            # 提取 JSON
            if "```" in content:
                parts = content.split("```")
                for part in parts:
                    candidate = part.strip().removeprefix("json").strip()
                    if candidate.startswith("{") and candidate.endswith("}"):
                        content = candidate
                        break

            raw = json.loads(content)

            # 字段转换
            result = {"available": True, "error": None}
            field_map = {
                "composition": "composition_score",
                "color": "color_score",
                "lighting": "lighting_score",
                "character": "face_score",
                "emotional": "emotional_score",
                "overall": "overall_score",
            }
            feedback_parts = []
            for k, v in raw.items():
                if k in field_map:
                    result[field_map[k]] = float(v) if v is not None else -1
                elif k == "summary":
                    result["feedback"] = v
                    feedback_parts.append(v)
                elif k == "strength":
                    feedback_parts.append(f"优点: {v}")
                elif k == "weakness":
                    feedback_parts.append(f"不足: {v}")

            if not result.get("feedback"):
                result["feedback"] = "; ".join(feedback_parts)

            for key in ["face_score", "composition_score", "color_score",
                         "lighting_score", "emotional_score", "overall_score"]:
                if key not in result:
                    result[key] = -1

            return result

        except Exception as e:
            return {"available": False, "error": f"Ollama VLM error: {e}", "overall_score": -1}

    def _score_dedicated(self, image_path: str, timeout: float = 60) -> dict[str, Any]:
        """专用 VLM 服务器评分（原逻辑，保持兼容）。"""
        if not self._check_dedicated():
            return {"available": False, "error": "VLM server not running", "overall_score": -1}

        try:
            with open(image_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")

            system_prompt = """You are a professional image aesthetic evaluator.
Analyze the image and rate each aspect from 0 (worst) to 10 (best).
Return ONLY valid JSON with these fields:
{"face_score": <0-10>, "face_feedback": "...", "composition_score": <0-10>,
 "composition_feedback": "...", "color_score": <0-10>, "color_feedback": "...",
 "overall_score": <0-10>, "overall_feedback": "..."}"""

            prompt = f"""<|im_start|>system
{system_prompt}<|im_end|>
<|im_start|>user
<image>Evaluate this image aesthetically. Output ONLY valid JSON.<|im_end|>
<|im_start|>assistant
"""

            payload = {
                "prompt": prompt,
                "image_data": [{"data": img_b64, "id": 0}],
                "n_predict": 512,
                "temperature": 0.1,
            }

            r = requests.post(
                f"http://{VLM_HOST}:{VLM_PORT}/completion",
                json=payload, timeout=timeout,
            )
            r.raise_for_status()
            d = r.json()
            content = d.get("content", "").strip()

            if " response" in content:
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            elif " think" in content:
                content = content[:content.index(" think")].strip()

            if "```" in content:
                parts = content.split("```")
                for part in parts:
                    c = part.strip()
                    if c.startswith("json"):
                        c = c[4:].strip()
                    if c.startswith("{") and c.endswith("}"):
                        content = c
                        break

            result = json.loads(content)
            result["available"] = True
            result["error"] = None

            for key in ["face_score", "composition_score", "color_score", "overall_score"]:
                if key not in result:
                    result[key] = -1

            return result
        except Exception as e:
            return {"available": False, "error": f"VLM API error: {e}", "overall_score": -1}

    # ── 自定义分析 ──

    def score_from_prompt(self, image_path: str, custom_prompt: str, timeout: float = 60) -> dict[str, Any]:
        if self.backend == "dedicated":
            return self._analyze_dedicated([image_path], custom_prompt, timeout)
        return self._analyze_ollama(image_path, custom_prompt, timeout)

    def _analyze_ollama(self, image_path: str, prompt: str, timeout: float = 60) -> dict[str, Any]:
        """Ollama 自定义分析，使用 /api/generate。"""
        try:
            with open(image_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")

            # 2026-08-20 修复：/api/generate + num_predict=2048
            payload = {
                "model": OLLAMA_VL_MODEL,
                "prompt": prompt,
                "images": [img_b64],
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 2048},
            }

            r = requests.post(f"{OLLAMA_API}/api/generate", json=payload, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            content = data.get("response", "").strip()

            return {"available": True, "response": content, "error": None}
        except Exception as e:
            return {"available": False, "error": str(e)}

    def _analyze_dedicated(self, images: list[str], prompt: str, timeout: float) -> dict[str, Any]:
        try:
            b64s = []
            for img in images:
                with open(img, "rb") as f:
                    b64s.append(base64.b64encode(f.read()).decode("utf-8"))

            image_tags = "".join(f"<image{i + 1}>" for i in range(len(images)))
            full_prompt = (
                f"<|im_start|>system\nYou are an expert image analyst.\n<|im_end|>\n"
                f"<|im_start|>user\n{image_tags}{prompt}<|im_end|>\n"
                f"<|im_start|>assistant\n"
            )

            payload = {
                "prompt": full_prompt,
                "image_data": [{"data": b, "id": i} for i, b in enumerate(b64s)],
                "n_predict": 1024,
                "temperature": 0.2,
            }

            r = requests.post(
                f"http://{VLM_HOST}:{VLM_PORT}/completion",
                json=payload, timeout=timeout,
            )
            r.raise_for_status()
            return {"available": True, "response": r.json().get("content", ""), "error": None}
        except Exception as e:
            return {"available": False, "error": str(e)}

    # ── 图片对比 ──

    def compare_images(self, path1: str, path2: str, prompt: str = "", timeout: float = 90) -> dict[str, Any]:
        if not prompt:
            prompt = "Compare these two images. Are they the same character? Rate consistency 0-10."
        if self.backend == "dedicated":
            return self._compare_images_dedicated(path1, path2, prompt, timeout)
        # Ollama: describe each then compare via text
        try:
            r1 = self._analyze_ollama(path1, "Describe this image in detail.", timeout)
            r2 = self._analyze_ollama(path2, "Describe this image in detail.", timeout)
            if not r1.get("available") or not r2.get("available"):
                return {"available": False, "error": "Failed to analyze images"}
            compare_p = (
                f"Image A: {r1.get('response', '')}\n\n"
                f"Image B: {r2.get('response', '')}\n\n"
                f"Question: {prompt}\n\n"
                "Return ONLY JSON: {\"consistency_score\": 0-10, \"analysis\": \"...\", \"differences\": [...]}"
            )
            r3 = self._analyze_ollama(path1, compare_p, timeout)
            if r3.get("available"):
                c = r3.get("response", "")
                if "```" in c:
                    for part in c.split("```"):
                        cand = part.strip().removeprefix("json").strip()
                        if cand.startswith("{") and cand.endswith("}"):
                            result = json.loads(cand)
                            result["available"] = True
                            return result
                return {"available": True, "response": c, "consistency_score": -1}
            return r3
        except Exception as e:
            return {"available": False, "error": str(e)}

    def _compare_images_dedicated(self, img1: str, img2: str, prompt: str, timeout: float) -> dict[str, Any]:
        try:
            with open(img1, "rb") as f:
                b64_1 = base64.b64encode(f.read()).decode("utf-8")
            with open(img2, "rb") as f:
                b64_2 = base64.b64encode(f.read()).decode("utf-8")
            full = f"<|im_start|>system\nExpert image comparator.\n<|im_end|>\n<|im_start|>user\n<image1><image2>{prompt}<|im_end|>\n<|im_start|>assistant\n"
            payload = {
                "prompt": full,
                "image_data": [{"data": b64_1, "id": 0}, {"data": b64_2, "id": 1}],
                "n_predict": 1024, "temperature": 0.2,
            }
            r = requests.post(f"http://{VLM_HOST}:{VLM_PORT}/completion", json=payload, timeout=timeout)
            r.raise_for_status()
            return {"available": True, "response": r.json().get("content", ""), "error": None}
        except Exception as e:
            return {"available": False, "error": str(e)}

    # ── 服务管理（dedicated 模式） ──

    def _start_server(self) -> bool:
        if not all(p.is_file() for p in [LLAMA_SERVER, MODEL_PATH, MMPROJ_PATH]):
            return False
        cmd = [str(LLAMA_SERVER), "-m", str(MODEL_PATH), "--mmproj", str(MMPROJ_PATH),
               "--port", str(VLM_PORT), "-ngl", "99", "--no-mmap", "--ctx-size", "8192",
               "--cache-type-k", "q8_0", "--cache-type-v", "q8_0", "-t", "6", "--flash-attn", "on"]
        try:
            self._server_proc = subprocess.Popen(cmd, cwd=str(LLAMA_DIR),
                                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(30):
                time.sleep(2)
                if self._check_dedicated():
                    return True
            return False
        except Exception:
            return False

    def stop(self) -> None:
        if self._server_proc:
            self._server_proc.terminate()
            self._server_proc = None