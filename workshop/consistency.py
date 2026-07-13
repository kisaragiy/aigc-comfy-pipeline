"""一致性验证 — 比较同一角色多张画中各个部位的质量稳定性。"""

from __future__ import annotations
from typing import Any

PART_KEYS = {
    "面部": ("face", "脸", "face_score"),
    "手部": ("hand", "手", "hand_score"),
    "脚部": ("foot", "脚", "foot_score"),
    "模糊度": ("blur", "模糊", "blur_score"),
}


def _extract_part_score(candidate: dict[str, Any], part: str) -> float | None:
    """从 candidate 中提取指定部位得分（多种字段名兼容）。"""
    ins = candidate.get("inspect", {})
    if isinstance(ins, dict):
        scores = ins.get("scores") or ins
        for key in PART_KEYS.get(part, ()):
            val = scores.get(key)
            if val is not None:
                return float(val)
    # 与旧格式兼容
    for key in PART_KEYS.get(part, ()):
        val = candidate.get(key) or candidate.get(f"{key}_score")
        if val is not None:
            return float(val)
    return None


def verify_consistency(
    candidates: list[dict[str, Any]],
    *,
    character_name: str | None = None,
    threshold_std: float = 0.15,
) -> dict[str, Any]:
    """验证同一角色跨图片的质量一致性。

    Args:
        candidates: 候选列表（含 inspect 结果）
        character_name: 角色名（可选，用于报告）
        threshold_std: 标准差阈值，超此值标记为波动

    Returns:
        {
            "character": str | None,
            "total": int,
            "passed": int,
            "failed": int,
            "parts": {
                part_name: {
                    "mean": float,
                    "std": float,
                    "min": float,
                    "min_idx": int,
                    "stable": bool,
                },
                ...
            },
            "flags": [
                {"idx": int, "part": str, "score": float, "avg": float, "suggestion": str},
                ...
            ],
            "summary": str,
            "html": str,        # 可直接渲染的 HTML
        }
    """
    valid = [c for c in candidates if c.get("error") is None and c.get("image")]
    if not valid:
        return {"character": character_name, "total": 0, "parts": {}, "flags": [], "summary": "无有效候选"}

    # 收集各部位得分
    part_scores: dict[str, list[tuple[int, float]]] = {}  # part → [(idx, score)]
    for part in PART_KEYS:
        scores = []
        for i, c in enumerate(valid):
            s = _extract_part_score(c, part)
            if s is not None:
                scores.append((i, s))
        if scores:
            part_scores[part] = scores

    import statistics

    parts_report: dict[str, Any] = {}
    flags: list[dict[str, Any]] = []

    for part, scores in part_scores.items():
        vals = [s[1] for s in scores]
        mean = statistics.mean(vals)
        std = statistics.stdev(vals) if len(vals) > 1 else 0.0
        min_val = min(vals)
        min_idx = scores[vals.index(min_val)][0]
        stable = std <= threshold_std

        parts_report[part] = {
            "mean": round(mean, 4),
            "std": round(std, 4),
            "min": round(min_val, 4),
            "min_idx": min_idx,
            "stable": stable,
        }

        if not stable and len(vals) > 1:
            # 标记低于 mean-std 的图片
            for idx, val in scores:
                if val < mean - std:
                    flags.append({
                        "idx": idx,
                        "part": part,
                        "score": round(val, 4),
                        "avg": round(mean, 4),
                        "suggestion": f"候选 #{idx+1} 的{part}得分 {val:.3f} 低于平均 {mean:.3f}，建议重试 (seed={valid[idx].get('seed','?')})",
                    })

    passed = sum(1 for p in parts_report.values() if p["stable"])
    failed = len(parts_report) - passed

    # 构造摘要
    summary_parts = []
    for part, rp in parts_report.items():
        icon = "✅" if rp["stable"] else "⚠️"
        summary_parts.append(f"  {icon} {part}: {rp['mean']:.3f}±{rp['std']:.3f}")
    summary = "\n".join(summary_parts)

    # 构造 HTML 报告
    html_parts = []
    for part, rp in parts_report.items():
        icon = "🟢" if rp["stable"] else "🟡" if rp["std"] <= threshold_std * 2 else "🔴"
        html_parts.append(
            f"<div class='part'><span class='icon'>{icon}</span>"
            f"<strong>{part}</strong> "
            f"<span class='val'>均值</span> <code>{rp['mean']:.3f}</code> "
            f"<span class='val'>σ</span> <code>{rp['std']:.4f}</code> "
            f"<span class='val'>最低</span> <code>{rp['min']:.3f}</code> "
            f"{'✅' if rp['stable'] else '⚠️ 波动'}</div>"
        )

    flag_lines = []
    for fl in flags:
        flag_lines.append(
            f"<div class='flag'><span class='warn'>⚠️</span> "
            f"{fl['suggestion']}</div>"
        )

    char_tag = f"<h2>{character_name}</h2>" if character_name else ""
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>一致性报告</title>
<style>
body {{ font-family: system-ui; max-width: 720px; margin: 2em auto; padding: 0 1em; }}
h1 {{ color: #333; }}
h2 {{ color: #666; }}
.part {{ padding: 0.5em 1em; margin: 0.3em 0; background: #f5f5f5; border-radius: 6px; display: flex; gap: 0.5em; align-items: center; }}
.icon {{ font-size: 1.2em; }}
.val {{ color: #888; font-size: 0.85em; }}
code {{ background: #e8e8e8; padding: 0.1em 0.4em; border-radius: 3px; }}
.flag {{ padding: 0.5em 1em; margin: 0.3em 0; background: #fff3cd; border-radius: 6px; }}
.warn {{ font-size: 1.1em; }}
.summary {{ margin: 1em 0; padding: 1em; background: #e8f5e9; border-radius: 8px; }}
.total {{ color: #666; font-size: 0.9em; margin-bottom: 1em; }}
</style>
</head><body>
<h1>📊 一致性验证报告</h1>
<div class='total'>共 {len(candidates)} 张 | {passed}/{len(parts_report)} 项稳定</div>
{char_tag}
{chr(10).join(html_parts)}
{chr(10).join(flag_lines) if flag_lines else "<p>✅ 所有部位质量一致，无需重试</p>"}
<h3>摘要</h3>
<pre>{summary}</pre>
</body></html>"""

    return {
        "character": character_name,
        "total": len(valid),
        "passed": passed,
        "failed": failed,
        "parts": parts_report,
        "flags": flags,
        "summary": summary,
        "html": html,
    }


def print_verify_report(report: dict[str, Any]) -> None:
    """在终端输出一致性报告。"""
    char_tag = f" —— {report['character']}" if report.get("character") else ""
    print(f"\n{'='*50}")
    print(f"📊 一致性验证报告{char_tag}")
    print(f"{'='*50}")
    print(f"  共 {report['total']} 张")
    print()

    for part, rp in report.get("parts", {}).items():
        icon = "✅" if rp["stable"] else "⚠️"
        print(f"  {icon} {part}: 均值 {rp['mean']:.3f}  σ={rp['std']:.4f}  最低 {rp['min']:.3f}")

    flags = report.get("flags", [])
    if flags:
        print()
        for fl in flags:
            print(f"  ⚠️ {fl['suggestion']}")
    else:
        print(f"\n  ✅ 所有部位质量一致，无需重试")

    print(f"{'='*50}\n")
