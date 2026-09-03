"""
Agent 质量闭环 — 超越"换种子重试"的智能 Agent 迭代。

流程:
  生成 → VLM 评分 → 分析缺陷 → 针对性修改 prompt →
  重新生成 → VLM 验证 → 循环直至达标或达上限

用法:
  from agents.go_agent_loop import agent_quality_loop
  result = agent_quality_loop("银发少女校服教室窗边逆光")
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# ── 前置依赖 ──
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.aesthetic_scorer import AestheticScorer

# ── 默认配置 ──
AGENT_MAX_ITERATIONS = 3          # 最大 Agent 迭代次数
AGENT_MIN_SCORE = 6.5             # Agent 评分最低达标线
VERBOSE = True


# ═══════════════════════════════════════════════════
# 第1步: VLM 分析图片缺陷
# ═══════════════════════════════════════════════════

DEFECT_ANALYSIS_PROMPT = """You are a professional art director analyzing an image.
Look at this image carefully and identify its specific flaws and weaknesses.

Return ONLY valid JSON with these fields:
{
  "defects": [
    {
      "aspect": "<face|hands|composition|color|lighting|anatomy|detail|style|other>",
      "severity": <1-10>,
      "description": "<specific issue>",
      "how_to_fix": "<how to fix this in the prompt>"
    }
  ],
  "prompt_issues": "<what in the prompt caused these defects>",
  "prompt_fixes": "<specific wording changes to fix it>",
  "overall_assessment": "<brief 1-sentence assessment>"
}"""


def analyze_defects(image_path: str) -> dict[str, Any]:
    """VLM 分析图片缺陷，返回结构化缺陷报告。"""
    scorer = AestheticScorer(backend="ollama")
    try:
        with open(image_path, "rb") as f:
            import base64
            img_b64 = base64.b64encode(f.read()).decode("utf-8")

        # 2026-08-20 修复：/api/generate + num_predict=2048（而非 /api/chat + max_tokens=1024）
        payload = {
            "model": "qwen3-vl:8b",
            "prompt": DEFECT_ANALYSIS_PROMPT,
            "images": [img_b64],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 2048},
        }

        import requests
        r = requests.post("http://127.0.0.1:11434/api/generate", json=payload, timeout=90)
        r.raise_for_status()
        data = r.json()
        content = data.get("response", "").strip()

        # 清理 think 标签（备用）
        if " response" in content:
            content = re.sub(r' thinking.*? response\s*', '', content, flags=re.DOTALL).strip()
        elif " thinking" in content:
            idx = content.index(" thinking")
            end = content.find(" response", idx)
            content = content[:idx] + (content[end + 8:] if end > 0 else "")

        # 提取 JSON
        if "```" in content:
            for part in content.split("```"):
                c = part.strip().removeprefix("json").strip()
                if c.startswith("{") and c.endswith("}"):
                    content = c
                    break

        analysis = json.loads(content)
        analysis["available"] = True
        return analysis

    except Exception as e:
        return {
            "available": False,
            "error": str(e),
            "defects": [],
            "prompt_issues": "",
            "prompt_fixes": "",
        }


# ═══════════════════════════════════════════════════
# 第2步: Agent 改进 prompt
# ═══════════════════════════════════════════════════

PROMPT_IMPROVER_PROMPT = """You are a master prompt engineer for AI image generation.
Your task: improve the given prompt to fix the specific defects detected.

Current prompt: {original_prompt}

Defect analysis:
{defect_report}

Requirements:
1. Keep the original subject and style intact
2. Add/rewrite prompt elements to fix the specific defects mentioned
3. Use the specific wording suggestions from the defect analysis
4. Keep it concise - quality over length
5. Output ONLY the improved prompt text, nothing else.

Improved prompt:"""


def improve_prompt(
    original_prompt: str,
    defect_report: dict[str, Any],
) -> str:
    """用 LLM 改进 prompt 以修复检测到的缺陷。"""
    defect_text = json.dumps(defect_report, indent=2, ensure_ascii=False)
    user_prompt = PROMPT_IMPROVER_PROMPT.format(
        original_prompt=original_prompt,
        defect_report=defect_text,
    )

    payload = {
        "model": "qwen3:14b",
        "messages": [{"role": "user", "content": user_prompt}],
        "options": {"temperature": 0.3, "max_tokens": 512},
        "stream": False,
    }

    try:
        import requests
        r = requests.post("http://127.0.0.1:11434/api/chat", json=payload, timeout=30)
        r.raise_for_status()
        improved = r.json().get("message", {}).get("content", "").strip()
        return improved if improved else original_prompt
    except Exception:
        return original_prompt


# ═══════════════════════════════════════════════════
# 第3步: 主循环
# ═══════════════════════════════════════════════════

def agent_quality_loop(
    nl_text: str,
    *,
    max_iterations: int = AGENT_MAX_ITERATIONS,
    min_score: float = AGENT_MIN_SCORE,
    verbose: bool = VERBOSE,
    **create_kwargs: Any,
) -> dict[str, Any]:
    """Agent 质量闭环 — 生成→评分→分析→改进→再生→验证。

    Args:
        nl_text: 自然语言描述
        max_iterations: 最大 Agent 迭代次数
        min_score: VLM 最低达标线 (0-10)
        verbose: 打印详情
        **create_kwargs: 传递给 create_from_nl 的额外参数

    Returns:
        {
            "prompt": "最终使用的prompt",
            "best_image": "最佳图片路径",
            "best_score": 最佳评分,
            "iteration_history": [...],
            "success": True/False,
        }
    """
    from workshop.create import create_from_nl

    current_prompt = nl_text
    scorer = AestheticScorer(backend="ollama")
    history = []
    best_image = None
    best_score = -1
    final_prompt = nl_text

    for iteration in range(1, max_iterations + 1):
        if verbose:
            print(f"\n{'='*60}")
            print(f"  🎯 Agent 迭代 {iteration}/{max_iterations}")
            print(f"  Prompt: {current_prompt[:120]}...")
            print(f"{'='*60}")

        # ═══ 生成 ═══
        t0 = time.time()
        result = create_from_nl(
            current_prompt if iteration > 1 else nl_text,
            count=2,
            inspect=True,
            aesthetic_min_score=0.0,
            prompt_ready=(iteration > 1),
            use_vlm=False,
            no_validate=False,
            **create_kwargs,
        )
        gen_time = time.time() - t0

        # 取最佳图片
        candidates = result.get("candidates", [])
        if not candidates:
            if verbose:
                print("  ❌ 生成失败，无候选图片")
            continue

        best_candidate = result.get("best", {})
        best_img = best_candidate.get("image", "")
        if not best_img and candidates:
            best_img = candidates[0].get("file", "")
            if best_img:
                best_img = str(Path(result.get("output_dir", "")) / best_img)

        if not best_img or not Path(best_img).is_file():
            if verbose:
                print("  ❌ 最佳图片不存在")
            continue

        # ═══ VLM 评分 ═══
        t1 = time.time()
        score_result = scorer.score(best_img)
        score_time = time.time() - t1
        overall = score_result.get("overall_score", -1)

        if verbose:
            print(f"  📊 VLM 评分: {overall:.1f}/10 (耗时 {score_time:.1f}s)")
            for key in ["composition_score", "color_score", "face_score", "lighting_score", "emotional_score"]:
                val = score_result.get(key)
                if val and val > 0:
                    print(f"       {key}: {val:.1f}")
            fb = score_result.get("feedback", "")
            if fb:
                print(f"       💬 {fb}")

        # 记录
        iteration_record = {
            "iteration": iteration,
            "prompt": current_prompt,
            "image": str(best_img),
            "score": overall,
            "score_detail": score_result,
            "gen_time": gen_time,
            "score_time": score_time,
        }
        history.append(iteration_record)

        # 更新最优
        if overall > best_score:
            best_score = overall
            best_image = str(best_img)
            final_prompt = current_prompt

        # ═══ 达标判断 ═══
        if overall >= min_score:
            if verbose:
                print(f"\n  ✅ 达标！(评分 {overall:.1f} ≥ {min_score})")
            break

        # ═══ 分析 → 改进 prompt（最后一次不改进） ═══
        if iteration < max_iterations:
            if verbose:
                print(f"\n  🔍 评分不足，开始分析缺陷...")

            t2 = time.time()
            analysis = analyze_defects(best_img)
            analysis_time = time.time() - t2

            if verbose:
                defects = analysis.get("defects", [])
                print(f"  📋 缺陷分析 ({analysis_time:.1f}s): {len(defects)} 个问题")
                for d in defects[:3]:
                    print(f"     - [{d.get('aspect','?')}/{d.get('severity',0)}] {d.get('description','')[:80]}")
                pi = analysis.get("prompt_issues", "")
                if pi:
                    print(f"  📝 Prompt 问题: {pi[:100]}")

            t3 = time.time()
            improved = improve_prompt(current_prompt, analysis)
            improve_time = time.time() - t3

            if improved and improved != current_prompt:
                if verbose:
                    print(f"  ✏️ Prompt 改进完成 ({improve_time:.1f}s)")
                    print(f"     改进前: {current_prompt[:100]}...")
                    print(f"     改进后: {improved[:100]}...")
                current_prompt = improved
            else:
                if verbose:
                    print("  ⚠️  Prompt 未改进，换用策略")
                current_prompt = current_prompt + " (masterpiece, best quality, extremely detailed)"

    return {
        "prompt": final_prompt,
        "best_image": best_image,
        "best_score": best_score,
        "iteration_history": history,
        "success": best_score >= min_score,
        "iterations_completed": len(history),
    }


def main() -> None:
    """CLI 入口：分析图片缺陷 或 运行完整 Agent 质量闭环。"""
    import argparse, sys, json

    parser = argparse.ArgumentParser(description="Agent 质量闭环工具")
    parser.add_argument("mode", choices=["analyze", "loop"], help="analyze=分析图片缺陷, loop=完整闭环")
    parser.add_argument("target", help="analyze: 图片路径 / loop: 自然语言描述")
    parser.add_argument("--iterations", type=int, default=3, help="最大迭代次数 (loop模式)")
    parser.add_argument("--min-score", type=float, default=6.5, help="最低达标分 (loop模式)")
    parser.add_argument("--verbose", action="store_true", default=True, help="详细输出")

    parsed = parser.parse_args(sys.argv[1:])

    if parsed.mode == "analyze":
        result = analyze_defects(parsed.target)
        if result.get("available"):
            print(f"缺陷分析: {parsed.target}")
            for d in result.get("defects", []):
                print(f"  [{d.get('aspect','?')}/{d.get('severity',0)}] {d.get('description','')}")
            print(f"\nPrompt问题: {result.get('prompt_issues','')}")
            print(f"修复建议: {result.get('prompt_fixes','')}")
        else:
            print(f"分析失败: {result.get('error','')}")
    elif parsed.mode == "loop":
        print(f"Agent 质量闭环启动 (目标: {parsed.target})")
        print(f"注意: 需要 ComfyUI 运行中")
        result = agent_quality_loop(
            parsed.target,
            max_iterations=parsed.iterations,
            min_score=parsed.min_score,
            verbose=parsed.verbose,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))