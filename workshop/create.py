"""
端到端创作管线 — "一句话出高质量图，自动质检，自动挑最好的"。

流程:
  NL 描述 → Prompt 引擎 → generate_with_quality × N → 逐张质检 → 排序选最优

用法 (CLI):
  python -m agents workshop create "银发少女校服教室窗边逆光" --count 6 --inspect
  python -m agents workshop create "prompt" --style anime --ref ref.png --count 4

返回:
  {
    "prompt": "优化后的提示词",
    "best": {"image": "路径", "score": 0.95, "inspect": {...}},
    "candidates": [{"image": "path", "inspect": {...}}, ...],
    "summary": "[脸:ok] [手:ok] [模糊:正常]",
  }
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from agents.comfy_utils import (
    generate_with_quality,
    resolve_comfy_root,
)
from workshop.engine import nls_to_prompt, ref_analyze_to_prompt


def create_from_nl(
    nl_text: str,
    *,
    count: int = 4,
    style_hint: str | None = None,
    ref_path: str | None = None,
    preset: str | None = None,
    min_score: float = 0.0,
    retry: int = 0,
    no_validate: bool = False,
    inspect: bool = True,
    seed: int = -1,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict[str, Any]:
    """自然语言描述 → 生成多张候选 → 质检排序 → 返回最优。

    Args:
        nl_text: 用户自然语言描述
        count: 生成候选数
        style_hint: 画风提示（anime/photoreal/cg/...）
        ref_path: 参考图路径（启用角色特征分析）
        preset: 质量预设
        min_score: 最低 CLIP 分（低于此值触发重试）
        retry: 最大重试次数
        no_validate: 跳过 CLIP 验证
        inspect: 是否执行逐部位质检
        seed: 起始种子（自动递增）
        dry_run: 预览模式
        verbose: 详细信息

    Returns:
        {
            "prompt": "最终使用的提示词",
            "best": {"image": "path", "score": N, "seed": N, "inspect": {...}},
            "candidates": [各张结果],
            "inspection_summary": "...",
        }
    """
    # 1. 生成专业提示词
    if ref_path and Path(ref_path).is_file():
        analysis = ref_analyze_to_prompt(ref_path, nl_text, ollama_available=False)
        final_prompt = analysis["prompt"]
        if verbose:
            print(f"📎 参考图分析: {analysis['character_desc'][:60]}...")
    else:
        final_prompt = nls_to_prompt(nl_text, style_hint=style_hint, ollama_available=False)

    if verbose:
        print(f"📝 Prompt: {final_prompt[:120]}...")

    if dry_run:
        candidate_list = []
        for i in range(count):
            s = seed + i if seed > 0 else seed
            candidate_list.append({"seed": s, "image": "", "dry_run": True})
        return {
            "prompt": final_prompt,
            "best": candidate_list[0] if candidate_list else {},
            "candidates": candidate_list,
            "dry_run": True,
        }

    # 2. 生成多张候选
    from agents.go_flux import build_flux_workflow

    candidates: list[dict[str, Any]] = []
    comfy_root = resolve_comfy_root()

    for i in range(count):
        s = seed + i if seed > 0 else -1
        if verbose:
            print(f"\n[{i+1}/{count}] seed={s}...")

        qr = generate_with_quality(
            build_flux_workflow, final_prompt,
            preset=preset,
            min_score=min_score,
            max_retries=retry,
            no_validate=no_validate,
            seed=s,
            filename_prefix=f"create_{i:02d}",
        )

        # 提取图片路径
        image_path = ""
        for sub, name in qr.get("images", []):
            p = comfy_root / "output" / sub / name
            if p.is_file():
                image_path = str(p.resolve())
                break

        candidate = {
            "seed": qr.get("seed", 0),
            "image": image_path,
            "score": qr.get("score", -1),
            "retries": qr.get("retries", 0),
        }
        candidates.append(candidate)

        if verbose:
            print(f"   score={candidate['score']} | {image_path}")

    # 3. 逐张质检
    if inspect and candidates:
        if verbose:
            print(f"\n🔍 质检 {len(candidates)} 张...")
        for c in candidates:
            if c["image"] and Path(c["image"]).is_file():
                from workshop.inspect import inspect_image
                ir = inspect_image(c["image"], prompt=final_prompt, use_mediapipe=False)
                c["inspect"] = ir
            else:
                c["inspect"] = {"status": "error", "error": "无图片"}

    # 4. 排序选最优
    def _rank_key(c: dict[str, Any]) -> tuple:
        """排序键: (无inspect放最后, score降序, inspect分数降序)。"""
        ins = c.get("inspect", {})
        no_inspect = 1 if ins.get("status") == "error" else 0
        insp_score = ins.get("scores", {}).get("overall", 0.5) if ins else 0.5
        clip = c.get("score", 0)
        # 综合: inspect score(50%) + CLIP score(50%)
        if clip < 0:
            clip = 0
        combined = insp_score * 0.5 + clip * 0.5
        return (no_inspect, -combined)

    candidates.sort(key=_rank_key)

    best = candidates[0] if candidates else {}
    summary = best.get("inspect", {}).get("summary", "")

    return {
        "prompt": final_prompt,
        "best": best,
        "candidates": candidates,
        "inspection_summary": summary,
    }
