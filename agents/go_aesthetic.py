#!/usr/bin/env python3
"""
VLM 审美评估引擎 — Agent 工程化的审美判断

目标: 达到人类审美标准的视觉评估

核心设计 (Agent 循环):
  1. INITIAL SCAN: 快速整体评估 (VLM 快评)
  2. DETAILED ANALYSIS: 分维度深度评估 (构图/色彩/角色/服装/背景/技术)
  3. SCORING: 各项打分 + 综合分
  4. FEEDBACK: 发现缺陷 → 生成改进建议
  5. COMPARISON: A/B 对比评估
  6. ITERATION: 生成 → 评估 → 建议 → 重新生成 (循环)

两个 VLM 通道:
  - Ollama: qwen3-vl:8b (主力, 实测8s/图合并6维度评分, 2025年5月发布)
  - Dedicated: Qwen3.5-9B-VLM GGUF on port 8083 (备用, 有专用上下文)

"视觉模型也需要做好agent工程才能有极高的符合人类审美标准的审美能力"
============================================================ """

from __future__ import annotations

import base64
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

import requests

# ── 配置 ──

OLLAMA_API = os.environ.get("OLLAMA_API", "http://127.0.0.1:11434")
OLLAMA_VL_MODEL = os.environ.get("OLLAMA_VL_MODEL", "qwen3-vl:8b")  # qwen3-vl:8b 是最新 Qwen 视觉模型(2025.5), 10s/图; 备选 qwen2.5vl:7b(旧)
OLLAMA_VL_FALLBACK = os.environ.get("OLLAMA_VL_FALLBACK", "qwen2.5vl:7b")
DEDICATED_VLM_API = os.environ.get("DEDICATED_VLM_API", "http://127.0.0.1:8083/v1/chat/completions")
DEDICATED_VLM_MODEL = os.environ.get("DEDICATED_VLM_MODEL", "Qwen3.5-9B-VLM")

# ════════════════════════════════════════════════════════════
# 数据模型
# ════════════════════════════════════════════════════════════

@dataclass
class AestheticDimension:
    """一个审美维度的评分"""
    name: str                # 维度名
    score: float             # 0-10
    feedback: str            # 文字反馈
    issues: list[str] = field(default_factory=list)  # 发现的缺陷
    suggestions: list[str] = field(default_factory=list)  # 改进建议


@dataclass
class AestheticResult:
    """完整审美评估结果"""
    image_path: str = ""
    dimensions: dict[str, AestheticDimension] = field(default_factory=dict)
    overall_score: float = 0.0
    overall_feedback: str = ""
    is_pass: bool = False          # 是否通过 (≥7.0/10)
    pass_threshold: float = 7.0
    vlm_model_used: str = ""
    evaluation_time_ms: int = 0
    
    def summary(self) -> str:
        lines = [f"📊 审美评分: {self.overall_score:.1f}/10 {'✅' if self.is_pass else '❌'}",
                 f"   模型: {self.vlm_model_used}"]
        for name, dim in sorted(self.dimensions.items(), key=lambda x: x[1].score):
            bar = "█" * int(dim.score) + "░" * (10 - int(dim.score))
            lines.append(f"   {name:10s} | {bar} | {dim.score:.1f}")
        if not self.is_pass and self.dimensions:
            worst = min(self.dimensions.values(), key=lambda d: d.score)
            if worst.issues:
                lines.append(f"\n   🔧 主要问题 ({worst.name}):")
                for issue in worst.issues[:3]:
                    lines.append(f"     - {issue}")
                if worst.suggestions:
                    lines.append(f"   💡 建议:")
                    for s in worst.suggestions[:2]:
                        lines.append(f"     - {s}")
        return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# VLM 通信
# ════════════════════════════════════════════════════════════

def image_to_base64(path: str, max_dim: int = 768) -> str:
    """图片文件 → base64 (自动缩放到 max_dim, 减少 VLM 传输开销)"""
    from PIL import Image
    import io
    try:
        img = Image.open(path)
        if max(img.size) > max_dim:
            ratio = max_dim / max(img.size)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except ImportError:
        # PIL 不可用时降级为原始文件读取
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")


def call_ollama_vlm(model: str, prompt: str, image_path: str, timeout: int = 60) -> dict:
    """
    调用 Ollama VLM 模型分析图片。
    返回 {"response": "...", "success": True/False, "error": "..."}
    """
    try:
        encoded = image_to_base64(image_path)
        # 先尝试 /api/chat API (qwen3.5 系列)
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt, "images": [encoded]}
            ],
            "stream": False,
            "options": {"temperature": 0.1}
        }
        r = requests.post(f"{OLLAMA_API}/api/chat", json=payload, timeout=timeout)
        if r.ok:
            data = r.json()
            content = data.get("message", {}).get("content", "")
            return {"response": content, "success": True}
        
        # fallback: 尝试 /api/generate API
        payload2 = {
            "model": model,
            "prompt": prompt,
            "images": [encoded],
            "stream": False,
            "options": {"temperature": 0.1}
        }
        r2 = requests.post(f"{OLLAMA_API}/api/generate", json=payload2, timeout=timeout)
        if r2.ok:
            data2 = r2.json()
            return {"response": data2.get("response", ""), "success": True}
        
        return {"response": "", "success": False, "error": f"Ollama API error: {r.status_code}"}
    
    except requests.exceptions.ConnectionError:
        return {"response": "", "success": False, "error": "Ollama 未运行"}
    except Exception as e:
        return {"response": "", "success": False, "error": str(e)}


def call_dedicated_vlm(prompt: str, image_path: str, timeout: int = 60) -> dict:
    """调用专用 VLM 服务 (llama-server)"""
    try:
        encoded = image_to_base64(image_path)
        data_url = f"data:image/png;base64,{encoded}"
        
        payload = {
            "model": DEDICATED_VLM_MODEL,
            "messages": [
                {"role": "system", "content": "You are a professional image aesthetic evaluator."},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": prompt}
                ]}
            ],
            "temperature": 0.1,
            "max_tokens": 1024
        }
        r = requests.post(DEDICATED_VLM_API, json=payload, timeout=timeout)
        if r.ok:
            data = r.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"response": content, "success": True}
        return {"response": "", "success": False, "error": f"Dedicated VLM error: {r.status_code}"}
    
    except requests.exceptions.ConnectionError:
        return {"response": "", "success": False, "error": "Dedicated VLM 未运行 (127.0.0.1:8083)"}
    except Exception as e:
        return {"response": "", "success": False, "error": str(e)}


def call_vlm(image_path: str, prompt: str, prefer: str = "ollama") -> dict:
    """
    智能调用 VLM:
      - prefer="ollama": 先用 Ollama, 失败则尝试专用
      - prefer="dedicated": 先用专用, 失败则尝试 Ollama
    """
    result = {"response": "", "model": "", "success": False}
    
    if prefer == "ollama":
        r = call_ollama_vlm(OLLAMA_VL_MODEL, prompt, image_path)
        if r["success"]:
            result["response"] = r["response"]
            result["model"] = f"ollama:{OLLAMA_VL_MODEL}"
            result["success"] = True
            return result
        # fallback
        r2 = call_dedicated_vlm(prompt, image_path)
        if r2["success"]:
            result["response"] = r2["response"]
            result["model"] = f"dedicated:{DEDICATED_VLM_MODEL}"
            result["success"] = True
    else:
        r = call_dedicated_vlm(prompt, image_path)
        if r["success"]:
            result["response"] = r["response"]
            result["model"] = f"dedicated:{DEDICATED_VLM_MODEL}"
            result["success"] = True
            return result
        r2 = call_ollama_vlm(OLLAMA_VL_MODEL, prompt, image_path)
        if r2["success"]:
            result["response"] = r2["response"]
            result["model"] = f"ollama:{OLLAMA_VL_MODEL}"
            result["success"] = True
    
    return result


# ════════════════════════════════════════════════════════════
# 多维度审美 Prompt 工程
# ════════════════════════════════════════════════════════════

AESTHETIC_DIMENSIONS = {
    "composition": {
        "name": "构图",
        "prompt": """Evaluate the COMPOSITION of this image (0-10):
- Rule of thirds / golden ratio adherence
- Balance and visual weight distribution 
- Framing and cropping quality
- Depth and layering (foreground/midground/background)
- Leading lines and gaze direction
Output format: score=X/10, feedback=你的评价, issues=发现的缺陷(逗号分隔), suggestions=改进建议(逗号分隔)"""
    },
    "color": {
        "name": "色彩",
        "prompt": """Evaluate the COLOR HARMONY of this image (0-10):
- Color palette consistency and harmony
- Saturation and value balance
- Color temperature (warm/cool) appropriateness for mood
- Skin tone naturalness 
- Overall color grading quality
Output format: score=X/10, feedback=你的评价, issues=发现的缺陷(逗号分隔), suggestions=改进建议(逗号分隔)"""
    },
    "character": {
        "name": "角色",
        "prompt": """Evaluate the CHARACTER QUALITY of this image (0-10):
- Facial features correctness (eyes, nose, mouth symmetry)
- Expression naturalness and emotional conveyance
- Hair quality (flow, texture, naturalness)
- Body proportions and pose naturalness
- Skin/texture quality
Output format: score=X/10, feedback=你的评价, issues=发现的缺陷(逗号分隔), suggestions=改进建议(逗号分隔)"""
    },
    "clothing": {
        "name": "服装",
        "prompt": """Evaluate the CLOTHING/FASHION detail quality (0-10):
- Garment texture and fabric rendering
- Folding, draping and physics realism
- Detail accuracy (buttons, zippers, seams, patterns)
- Color and pattern matching
- Overall fashion aesthetic appeal
- 特别注意: 服装纹理是否真实, 褶皱是否自然, 材质是否有区分度
Output format: score=X/10, feedback=你的评价, issues=发现的缺陷(逗号分隔), suggestions=改进建议(逗号分隔)"""
    },
    "background": {
        "name": "背景",
        "prompt": """Evaluate the BACKGROUND of this image (0-10):
- Integration with foreground (depth of field, lighting consistency)
- Detail level and visual interest
- Color coherence with overall palette
- Whether it complements or distracts from the subject
- Atmospheric effects (lighting, fog, particles)
Output format: score=X/10, feedback=你的评价, issues=发现的缺陷(逗号分隔), suggestions=改进建议(逗号分隔)"""
    },
    "technique": {
        "name": "技法",
        "prompt": """Evaluate the TECHNICAL QUALITY of this image (0-10):
- Sharpness and focus rendering
- Artifact presence (blurriness, noise, compression artifacts)
- Lighting and shadow realism
- Edge quality and anti-aliasing
- Resolution appropriateness for content
Output format: score=X/10, feedback=你的评价, issues=发现的缺陷(逗号分隔), suggestions=改进建议(逗号分隔)"""
    },
}



# ════════════════════════════════════════════════════════════
# 合并评分 Prompt (6维度单次调用, qwen3-vl:8b 支持)
# ════════════════════════════════════════════════════════════

COMBINED_EVAL_PROMPT = """You are an aesthetic evaluator for anime/cg art. Analyze this image and rate each dimension 0-10.
Return ONLY a valid JSON object with no other text:
{
  "composition": <0-10 rule of thirds / balance / framing / depth / leading lines>,
  "color": <0-10 harmony / contrast / palette richness / lighting>,
  "character": <0-10 anatomy / expression / pose / appeal>,
  "clothing": <0-10 texture / draping / detail accuracy / fashion>,
  "background": <0-10 integration / detail / coherence / atmosphere>,
  "technique": <0-10 sharpness / rendering / shading / effects>,
  "overall_score": <weighted average of above>,
  "strength": "<single best dimension name>",
  "weakness": "<single worst dimension name>",
  "summary": "<one sentence review>"
}"""


# ════════════════════════════════════════════════════════════
# 审美 Agent
# ════════════════════════════════════════════════════════════

class AestheticAgent:
    """
    审美评估 Agent — Agent 工程化的审美判断
    
    工作流:
      1. call(image) → 全部 6 维度评估
      2. score() → 综合打分 
      3. feedback() → 改进建议
      4. compare(a, b) → A/B 对比
      5. review(image, round=N) → 多轮评审迭代
    """
    
    def __init__(self, prefer: str = "ollama", verbose: bool = False):
        self.prefer = prefer
        self.verbose = verbose
    
    def _parse_dimension_output(self, text: str) -> AestheticDimension:
        """解析 VLM 输出为结构化数据"""
        score = 5.0
        feedback = text.strip()
        issues = []
        suggestions = []
        
        # 提取 score=X/10
        score_match = re.search(r'score\s*[=:]\s*(\d+(?:\.\d+)?)\s*/?\s*10', text, re.IGNORECASE)
        if score_match:
            score = min(10.0, max(0.0, float(score_match.group(1))))
        
        # 提取 issues
        issues_match = re.search(r'issues\s*[=:]\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        if issues_match:
            issues = [i.strip() for i in issues_match.group(1).split(",") if i.strip()]
        
        # 提取 suggestions
        sugg_match = re.search(r'suggestions\s*[=:]\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        if sugg_match:
            suggestions = [s.strip() for s in sugg_match.group(1).split(",") if s.strip()]
        
        # 提取 feedback (去掉 score/issues/suggestions 行后剩余)
        clean = re.sub(r'(?:score|issues|suggestions)\s*[=:]\s*.+?(?:\n|$)', '', text, flags=re.IGNORECASE).strip()
        if clean:
            feedback = clean
        
        return AestheticDimension(
            name="",
            score=score,
            feedback=feedback,
            issues=issues,
            suggestions=suggestions
        )
    
    def evaluate_dimension(self, image_path: str, dim_key: str) -> Optional[AestheticDimension]:
        """评估单个维度"""
        dim_info = AESTHETIC_DIMENSIONS.get(dim_key)
        if not dim_info:
            return None
        
        result = call_vlm(image_path, dim_info["prompt"], prefer=self.prefer)
        if not result["success"]:
            return None
        
        dim = self._parse_dimension_output(result["response"])
        dim.name = dim_info["name"]
        
        if self.verbose:
            print(f"  [{dim.name}] score={dim.score}/10 | issues={len(dim.issues)} | model={result['model']}")
        
        return dim

    def evaluate_combined(self, image_path: str) -> tuple[Optional[float], Optional[dict], Optional[str]]:
        """合并评分: 1次VLM调用评估全部6维度 (qwen3-vl:8b 优化模式)
        
        Returns:
            (overall_score: float|None, dimensions: dict|None, summary: str|None)
        """
        result = call_vlm(image_path, COMBINED_EVAL_PROMPT, prefer=self.prefer)
        if not result["success"] or not result["response"].strip():
            return None, None, None

        try:
            import json
            import re
            # 提取 JSON (可能有多余文字)
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', result["response"], re.DOTALL)
            if not json_match:
                return None, None, None
            data = json.loads(json_match.group())

            # 解析维度
            dims = {}
            dim_names_zh = {"composition": "构图", "color": "色彩", "character": "角色",
                           "clothing": "服装", "background": "背景", "technique": "技法"}
            for eng_key, zh_name in dim_names_zh.items():
                score = data.get(eng_key)
                if score is not None and isinstance(score, (int, float)):
                    dims[eng_key] = AestheticDimension(
                        name=zh_name,
                        score=min(10.0, max(0.0, float(score))),
                        feedback=f"{zh_name}: {score}/10",
                        issues=[],
                        suggestions=[]
                    )

            overall = data.get("overall_score")
            if overall is not None:
                overall = min(10.0, max(0.0, float(overall)))
            summary = data.get("summary", "")

            if self.verbose:
                print(f"  📊 合并评分: {sum([d.score for d in dims.values()])/len(dims):.1f}/10 | model={result['model']}")
                for d in dims.values():
                    print(f"    {d.name}: {d.score}/10")
                strength = data.get("strength", "")
                weakness = data.get("weakness", "")
                if strength:
                    print(f"    💪 最强: {strength}  |  ⚠️ 最弱: {weakness}")

            return overall, dims, summary
        except Exception as e:
            if self.verbose:
                print(f"  ⚠️ 合并评分解析失败: {e}, 降级为逐维度评分")
            return None, None, None
    
    
    def evaluate(self, image_path: str, dimensions: Optional[list[str]] = None) -> AestheticResult:
        """
        对图片进行全维度审美评估
        
        Args:
            image_path: 图片路径
            dimensions: 要评估的维度列表, 默认全部
        
        Returns:
            AestheticResult
        """
        start = time.time()
        
        if not os.path.exists(image_path):
            return AestheticResult(image_path=image_path,
                                 overall_feedback=f"图片不存在: {image_path}")
        
        if dimensions is None:
            dimensions = list(AESTHETIC_DIMENSIONS.keys())
        
        result = AestheticResult(image_path=image_path)
        
        if self.verbose:
            print(f"\n🔍 审美评估: {os.path.basename(image_path)}")
            print(f"   维度: {', '.join(AESTHETIC_DIMENSIONS[d]['name'] for d in dimensions if d in AESTHETIC_DIMENSIONS)}")
        
        # 优先尝试合并评分 (1次VLM调用评估全部6维度, qwen3-vl:8b优化模式)
        combined_score, combined_dims, combined_summary = self.evaluate_combined(image_path)
        
        if combined_dims and len(combined_dims) >= 4:
            # 合并评分成功
            result.dimensions = combined_dims
            result.overall_score = combined_score
            result.overall_feedback = combined_summary or ""
            if self.verbose:
                print(f"  ✅ 使用合并评分模式 (1次调用)")
        else:
            # 降级: 逐维度评估
            if self.verbose and combined_dims is None:
                print(f"  ⚠️ 合并评分不可用, 降级为逐维度评估 ({len(dimensions)}次调用)")
            for dim_key in dimensions:
                dim = self.evaluate_dimension(image_path, dim_key)
                if dim:
                    result.dimensions[dim_key] = dim
        
        # 计算综合分 (加权平均)
        weights = {
            "composition": 0.20,
            "color": 0.15,
            "character": 0.25,
            "clothing": 0.15,
            "background": 0.10,
            "technique": 0.15,
        }
        total_weight = 0
        weighted_sum = 0
        for dim_key, dim in result.dimensions.items():
            w = weights.get(dim_key, 0.15)
            weighted_sum += dim.score * w
            total_weight += w
        
        result.overall_score = weighted_sum / total_weight if total_weight > 0 else 0
        result.overall_score = min(10.0, max(0.0, result.overall_score))
        result.is_pass = result.overall_score >= result.pass_threshold
        result.evaluation_time_ms = int((time.time() - start) * 1000)
        
        # 生成综合反馈
        if result.dimensions:
            worst = min(result.dimensions.values(), key=lambda d: d.score)
            best = max(result.dimensions.values(), key=lambda d: d.score)
            result.overall_feedback = (
                f"综合评分 {result.overall_score:.1f}/10. "
                f"最强: {best.name}({best.score:.1f}). "
                f"最弱: {worst.name}({worst.score:.1f}). "
                f"{'通过 ✅' if result.is_pass else '未通过 ❌, 需要改进'}"
            )
        
        if self.verbose:
            print(result.summary())
            print(f"   耗时: {result.evaluation_time_ms}ms")
        
        return result
    
    def compare(self, image_a: str, image_b: str) -> dict:
        """
        A/B 对比评估
        返回谁更好 + 各维度差异
        """
        result_a = self.evaluate(image_a, verbose=False)
        result_b = self.evaluate(image_b, verbose=False)
        
        comparison = {
            "image_a": {"path": image_a, "overall": result_a.overall_score, "pass": result_a.is_pass},
            "image_b": {"path": image_b, "overall": result_b.overall_score, "pass": result_b.is_pass},
            "winner": "A" if result_a.overall_score > result_b.overall_score else "B",
            "margin": abs(result_a.overall_score - result_b.overall_score),
            "dimension_comparison": {}
        }
        
        all_dims = set(result_a.dimensions.keys()) | set(result_b.dimensions.keys())
        for dim_key in all_dims:
            a_score = result_a.dimensions[dim_key].score if dim_key in result_a.dimensions else 0
            b_score = result_b.dimensions[dim_key].score if dim_key in result_b.dimensions else 0
            dim_name = AESTHETIC_DIMENSIONS.get(dim_key, {}).get("name", dim_key)
            comparison["dimension_comparison"][dim_name] = {
                "A": a_score, "B": b_score,
                "diff": a_score - b_score,
                "better": "A" if a_score > b_score else "B" if b_score > a_score else "平"
            }
        
        return comparison
    
    def review_with_feedback(self, image_path: str, rounds: int = 1) -> list[AestheticResult]:
        """
        多轮评审迭代:
          第1轮: 全面评估 → 发现缺陷
          第2轮: 聚焦最弱维度再次评估
          第3轮: 检查改进效果
        """
        results = []
        for r in range(1, rounds + 1):
            if self.verbose:
                print(f"\n{'='*50}")
                print(f"  第 {r} 轮评审")
                print(f"{'='*50}")
            
            if r == 1:
                result = self.evaluate(image_path)
            else:
                # 后续轮次: 聚焦前一轮最弱维度
                prev = results[-1]
                if prev.dimensions:
                    weakest = min(prev.dimensions.values(), key=lambda d: d.score)
                    weak_key = [k for k, v in prev.dimensions.items() if v is weakest][0]
                    result = self.evaluate(image_path, dimensions=[weak_key])
                else:
                    result = self.evaluate(image_path)
            
            results.append(result)
        
        return results


# ════════════════════════════════════════════════════════════
# 时尚细节识别 — 用 VLM 深度分析服装
# ════════════════════════════════════════════════════════════

FASHION_ANALYSIS_PROMPT = """Analyze this image in extreme detail for FASHION ITEMS. 
Identify EVERY piece of clothing, accessory, and footwear visible:

For each item, describe:
1. Type (e.g., "crew neck t-shirt", "A-line miniskirt", "thigh-high stockings 15D")
2. Color (exact shade)
3. Material/fabric (if identifiable: cotton, denim, silk, velvet, lace, nylon...)
4. Key design features (neckline, sleeve type, closure, pattern, texture)
5. Fit (tight/loose/oversized)

Also describe:
- Hairstyle and hair color
- Makeup style
- Pose and body language

Output as structured text. Be specific. If unsure about material, state "appears to be..."."""


def fashion_detail_analysis(image_path: str) -> dict:
    """用 VLM 对图片中的服装进行深度分析"""
    agent = AestheticAgent(verbose=False)
    result = call_vlm(image_path, FASHION_ANALYSIS_PROMPT, prefer=agent.prefer)
    return {
        "success": result["success"],
        "analysis": result["response"],
        "model": result["model"],
        "error": result.get("error", ""),
    }


# ════════════════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════╗")
    print("║     VLM 审美评估 Agent v1.0                         ║")
    print("╚══════════════════════════════════════════════════════╝")
    
    print(f"\n🔌 VLM 通道:")
    print(f"  Ollama: {OLLAMA_API}/{OLLAMA_VL_MODEL}")
    print(f"  专用:   {DEDICATED_VLM_API} ({DEDICATED_VLM_MODEL})")
    
    # 测试 Ollama 连通性
    print("\n📡 测试 VLM 连接...")
    try:
        r = requests.get(f"{OLLAMA_API}/api/tags", timeout=3)
        if r.ok:
            models = [m["name"] for m in r.json().get("models", [])]
            print(f"  ✅ Ollama 在线, 模型: {models}")
        else:
            print(f"  ❌ Ollama 错误: {r.status_code}")
    except Exception as e:
        print(f"  ❌ Ollama 不可达: {e}")
    
    try:
        r = requests.get(DEDICATED_VLM_API.replace("/v1/chat/completions", "/health"), timeout=2)
        if r.ok:
            print(f"  ✅ 专用 VLM 在线")
        else:
            print(f"  ❌ 专用 VLM 不可达 ({r.status_code})")
    except:
        print(f"  ❌ 专用 VLM 不可达 (127.0.0.1:8083)")
    
    print(f"""
📋 用法:
    from agents.go_aesthetic import AestheticAgent
    
    agent = AestheticAgent(verbose=True)
    
    # 单图评估
    result = agent.evaluate("output.png")
    print(result.summary())
    
    # A/B 对比
    cmp = agent.compare("img_a.png", "img_b.png")
    print(f"胜者: {cmp['winner']}, 差距: {cmp['margin']:.1f}")
    
    # 多轮评审
    results = agent.review_with_feedback("output.png", rounds=2)
    
    # 时尚细节分析
    fashion = fashion_detail_analysis("output.png")
    print(fashion['analysis'])

评估维度权重:
   角色(面部/表情/体态) = 25%
   构图               = 20%
   色彩               = 15%
   服装细节           = 15%
   技法(清晰度/噪点)    = 15%
   背景               = 10%
""")
