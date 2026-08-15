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
    """自动探测 Ollama 地址：环境变量 → WSL IP → 127.0.0.1"""
    env = os.environ.get("OLLAMA_API", "").strip()
    if env:
        return env.rstrip("/")
    # 尝试通过 wsl 获取 IP（Windows 侧 127.0.0.1 转发经常失效）
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
    """VLM 审美评分器。默认使用 Ollama qwen3-vl:8b（合并评分）。
    
    Args:
        backend: "ollama"（默认）或 "dedicated"（port 8083 专用VLM服务器）
        auto_start: 对 ollama 无意义；对 dedicated 自动启动 llama-server
        verbose: 打印详细信息
    """

    def __init__(
        self,
        backend: str = "ollama",
        auto_start: bool = False,
        verbose: bool = False,
    ):
        self.backend = backend
        self.verbose = verbose
        self._server_proc: subprocess.Popen | None = None

        if backend == "dedicated":
            self.api_url = f"http://{VLM_HOST}:{VLM_PORT}"
            if auto_start and not self._check_dedicated():
                self._start_server()
        else:
            self.api_url = OLLAMA_API

    # ── 服务管理 ──

    def _check_ollama(self) -> bool:
        """检查 Ollama 是否可用。"""
        try:
            r = requests.get(f"{OLLAMA_API}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def _check_dedicated(self, timeout: float = 3) -> bool:
        """检查专用 VLM 服务是否运行。"""
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

    def _start_server(self) -> bool:
        """启动专用 llama-server 进程（仅 backend='dedicated' 时）。"""
        if not LLAMA_SERVER.is_file():
            if self.verbose:
                print(f"[Aesthetic] ❌ llama-server not found: {LLAMA_SERVER}")
            return False
        if not MODEL_PATH.is_file():
            if self.verbose:
                print(f"[Aesthetic] ❌ Model not found: {MODEL_PATH}")
            return False
        if not MMPROJ_PATH.is_file():
            if self.verbose:
                print(f"[Aesthetic] ❌ mmproj not found: {MMPROJ_PATH}")
            return False

        cmd = [
            str(LLAMA_SERVER), "-m", str(MODEL_PATH),
            "--mmproj", str(MMPROJ_PATH), "--port", str(VLM_PORT),
            "-ngl", "99", "--no-mmap", "--ctx-size", "8192",
            "--cache-type-k", "q8_0", "--cache-type-v", "q8_0",
            "-t", "6", "--flash-attn", "on",
        ]
        if self.verbose:
            print(f"[Aesthetic] 🚀 Starting VLM server on port {VLM_PORT}...")
        try:
            self._server_proc = subprocess.Popen(
                cmd, cwd=str(LLAMA_DIR),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            for _ in range(30):
                time.sleep(2)
                if self._check_dedicated():
                    if self.verbose:
                        print(f"[Aesthetic] ✅ VLM server ready on port {VLM_PORT}")
                    return True
            return False
        except Exception as e:
            if self.verbose:
                print(f"[Aesthetic] ❌ Failed to start server: {e}")
            return False

    def stop(self) -> None:
        """停止专用 VLM 服务（仅 dedicated 模式）。"""
        if self._server_proc:
            self._server_proc.terminate()
            self._server_proc = None
            if self.verbose:
                print("[Aesthetic] 🛑 VLM server stopped")

    # ── 图片编码 ──

    @staticmethod
    def _encode_image(image_path: str) -> str:
        with open(image_path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        ext = Path(image_path).suffix.lower()
        mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(
            ext.lstrip("."), "png"
        )
        return f"data:image/{mime};base64,{data}"

    # ── 审美评分 ──

    def score(
        self, image_path: str, timeout: float = 60
    ) -> dict[str, Any]:
        """对图片进行审美评分。
        
        Returns:
            {"face_score": ..., "composition_score": ..., "color_score": ...,
             "overall_score": ..., "feedback": ..., "available": True/False,
             "error": "..." (if failed)}
        """
        if not Path(image_path).is_file():
            return {"available": False, "error": f"Image not found: {image_path}", "overall_score": -1}

        if self.backend == "dedicated":
            return self._score_dedicated(image_path, timeout)
        return self._score_ollama(image_path, timeout)

    def _score_ollama(self, image_path: str, timeout: float = 60) -> dict[str, Any]:
        """Ollama 合并评分（qwen3-vl:8b, 6维度, 1次调用）。"""
        if not self._check_ollama():
            return {"available": False, "error": "Ollama not running", "overall_score": -1}

        try:
            # 压缩图片再评分：原始图常 1-2MB，base64 后 2-3MB 会撑爆 WSL 桥接 + VLM 处理慢
            # 512px 内足够 VLM 看构图/光影/崩坏，速度快 10 倍
            from PIL import Image
            import io
            img = Image.open(image_path)
            img.thumbnail((512, 512), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

            payload = {
                "model": OLLAMA_VL_MODEL,
                "messages": [
                    {"role": "user", "content": COMBINED_EVAL_PROMPT,
                     "images": [img_b64]},
                ],
                "options": {"temperature": 0.1, "max_tokens": 1024},
                "stream": False,
            }

            r = requests.post(f"{OLLAMA_API}/api/chat", json=payload, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            content = data.get("message", {}).get("content", "").strip()

            # 去掉 think 标签
            if "</think>" in content:
                content = re.sub(r'<think>.*?</think>\s*', '', content, flags=re.DOTALL).strip()
            elif "<think>" in content:
                idx = content.index("<think>")
                end = content.find("</think>", idx)
                if end > 0:
                    content = content[:idx] + content[end + 8:]
                else:
                    content = content[:idx].strip()

            # 提取 JSON
            if "```" in content:
                parts = content.split("```")
                for part in parts:
                    candidate = part.strip().removeprefix("json").strip()
                    if candidate.startswith("{") and candidate.endswith("}"):
                        content = candidate
                        break

            raw = json.loads(content)

            # 转换字段: composition→composition_score, overall→overall_score, ...
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

            # 填充缺失字段
            for key in ["face_score", "composition_score", "color_score",
                         "lighting_score", "emotional_score", "overall_score"]:
                if key not in result:
                    result[key] = -1

            return result

        except Exception as e:
            return {"available": False, "error": f"Ollama VLM error: {e}",
                    "overall_score": -1}

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
            data = r.json()
            content = data.get("content", "").strip()

            if "</think>" in content:
                content = re.sub(r'<think>.*?</think>\s*', '', content, flags=re.DOTALL).strip()
            elif "<think>" in content:
                content = content[:content.index("<think>")].strip()

            if "```" in content:
                parts = content.split("```")
                for part in parts:
                    candidate = part.strip()
                    if candidate.startswith("json"):
                        candidate = candidate[4:].strip()
                    if candidate.startswith("{") and candidate.endswith("}"):
                        content = candidate
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

    def score_from_prompt(
        self, image_path: str, custom_prompt: str, timeout: float = 60
    ) -> dict[str, Any]:
        """用自定义 prompt 分析图片。"""
        if self.backend == "dedicated":
            return self._analyze_dedicated([image_path], custom_prompt, timeout)
        return self._analyze_ollama(image_path, custom_prompt, timeout)

    def _analyze_ollama(self, image_path: str, prompt: str, timeout: float = 60) -> dict[str, Any]:
        """Ollama 自定义分析。"""
        try:
            with open(image_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")

            payload = {
                "model": OLLAMA_VL_MODEL,
                "messages": [
                    {"role": "user", "content": prompt, "images": [img_b64]},
                ],
                "options": {"temperature": 0.3, "max_tokens": 1024},
                "stream": False,
            }

            r = requests.post(f"{OLLAMA_API}/api/chat", json=payload, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            content = data.get("message", {}).get("content", "").strip()

            return {"available": True, "response": content, "error": None}
        except Exception as e:
            return {"available": False, "error": str(e)}

    def compare_images(
        self, image_path1: str, image_path2: str, prompt: str = "", timeout: float = 90
    ) -> dict[str, Any]:
        """对比两张图（角色一致性判断）。"""
        if not prompt:
            prompt = (
                "Compare these two images. Are they the same character/person? "
                "Rate consistency 0-10. Explain similarities and differences."
            )

        if self.backend == "dedicated":
            return self._compare_images_dedicated(image_path1, image_path2, prompt, timeout)

        # Ollama 模式：先分析图1，再分析图2，最后对比
        try:
            r1 = self._analyze_ollama(image_path1, "Describe this image in detail.", timeout)
            r2 = self._analyze_ollama(image_path2, "Describe this image in detail.", timeout)
            if not r1.get("available") or not r2.get("available"):
                return {"available": False, "error": "Failed to analyze images",
                        "response": "", "consistency_score": -1}

            compare_prompt = f"""Image 1 description: {r1.get('response', '')}

Image 2 description: {r2.get('response', '')}

Question: {prompt}

Return ONLY valid JSON with fields: "consistency_score" (0-10), "analysis" (string), "differences" (list of strings)"""

            r3 = self._analyze_ollama(image_path1, compare_prompt, timeout)
            if r3.get("available"):
                content = r3.get("response", "")
                if "```" in content:
                    parts = content.split("```")
                    for part in parts:
                        candidate = part.strip().removeprefix("json").strip()
                        if candidate.startswith("{") and candidate.endswith("}"):
                            result = json.loads(candidate)
                            result["available"] = True
                            return result
                return {"available": True, "response": content, "consistency_score": -1}
            return r3
        except Exception as e:
            return {"available": False, "error": str(e)}

    def _compare_images_dedicated(self, img1: str, img2: str, prompt: str, timeout: float) -> dict[str, Any]:
        """专用 VLM 对比（原逻辑）。"""
        try:
            with open(img1, "rb") as f:
                b64_1 = base64.b64encode(f.read()).decode("utf-8")
            with open(img2, "rb") as f:
                b64_2 = base64.b64encode(f.read()).decode("utf-8")

            full_prompt = (
                f"<|im_start|>system\nYou are an expert at comparing images. "
                f"Analyze carefully and provide detailed comparison.\n<|im_end|>\n"
                f"<|im_start|>user\n<image1><image2>{prompt}<|im_end|>\n"
                f"<|im_start|>assistant\n"
            )

            payload = {
                "prompt": full_prompt,
                "image_data": [
                    {"data": b64_1, "id": 0},
                    {"data": b64_2, "id": 1},
                ],
                "n_predict": 1024,
                "temperature": 0.2,
            }

            r = requests.post(
                f"http://{VLM_HOST}:{VLM_PORT}/completion",
                json=payload, timeout=timeout,
            )
            r.raise_for_status()
            data = r.json()
            return {"available": True, "response": data.get("content", ""), "error": None}
        except Exception as e:
            return {"available": False, "error": str(e)}
