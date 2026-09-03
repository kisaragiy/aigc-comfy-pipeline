#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/cost_tracker.py — 生成成本追踪（G8·业界最佳：每张图成本/耗时核算）
============================================================
轻量 JSONL 成本账：每次生成追加一行 → 任意时刻可汇总。

业界对标：专业管线有成本核算（GPU 分钟 × 单价 + API 费用 + 重试损耗），
单人本地管线最值钱的是「时间账」—— 每张图耗时/重试/达标率，用于：
  - 引擎对比（Flux vs SDXL 谁快谁慢）
  - 批量任务估时（下一批要跑多久）
  - 面试可讲（可复现的工程化度量）

用法:
  python -m agents workshop cost [--days N] [--json]
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

PROJECT = Path(__file__).resolve().parent.parent
COST_LOG = PROJECT / "cost_log.jsonl"


def record_generation(
    *,
    engine: str = "flux",
    seed: int = -1,
    elapsed_sec: float = 0.0,
    retries: int = 0,
    score: float | None = None,
    vlm_score: float | None = None,
    passed: bool = True,
    prompt_hint: str = "",
    extra: dict[str, Any] | None = None,
) -> str:
    """追加一行生成成本记录到 cost_log.jsonl。

    Args:
        engine: 生成引擎（flux/sdxl/video/...）
        seed: 使用的种子
        elapsed_sec: 总耗时（秒，含重试）
        retries: 重试次数
        score: CLIP/质检分（可选）
        vlm_score: VLM 审美分（可选）
        passed: 是否达标
        prompt_hint: prompt 摘要（前 40 字，不存全文防脏数据）
        extra: 额外字段（如视频帧数/尺寸）

    Returns:
        行号（append 后的总行数）
    """
    now = datetime.now()
    row = {
        "ts": now.strftime("%Y-%m-%d %H:%M:%S"),
        "date": now.strftime("%Y-%m-%d"),
        "engine": engine,
        "seed": int(seed),
        "elapsed_sec": round(float(elapsed_sec), 1),
        "retries": int(retries),
        "score": round(float(score), 3) if score is not None else None,
        "vlm_score": round(float(vlm_score), 2) if vlm_score is not None else None,
        "passed": bool(passed),
        "prompt_hint": str(prompt_hint)[:40],
    }
    if extra:
        # 只保留可 JSON 序列化的简单值
        for k, v in extra.items():
            if isinstance(v, (str, int, float, bool)) or v is None:
                row[k] = v
    COST_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(COST_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return _line_count()


def _iter_rows():
    """逐行读 cost_log.jsonl，容忍坏行（跳过不崩）。"""
    if not COST_LOG.exists():
        return
    with open(COST_LOG, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                yield json.loads(ln)
            except json.JSONDecodeError:
                continue  # 坏行跳过（日志不应让统计崩掉）


def _line_count() -> int:
    if not COST_LOG.exists():
        return 0
    return sum(1 for _ in open(COST_LOG, encoding="utf-8"))


def summarize(days: int | None = None) -> dict[str, Any]:
    """汇总成本账。

    Args:
        days: 只看最近 N 天（None=全部）

    Returns:
        {
          "total": 生成总次数,
          "passed": 达标数, "passed_rate": 达标率,
          "total_sec": 总耗时(秒), "avg_sec": 平均耗时,
          "by_engine": {引擎: {count, avg_sec}},
          "by_date": {日期: count},
        }
    """
    rows = list(_iter_rows())
    if days is not None and days > 0:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = [r for r in rows if r.get("date", "") >= cutoff]

    total = len(rows)
    if total == 0:
        return {"total": 0, "by_engine": {}}

    passed = sum(1 for r in rows if r.get("passed", False))
    secs = [r.get("elapsed_sec", 0.0) for r in rows if isinstance(r.get("elapsed_sec"), (int, float))]
    total_sec = sum(secs)
    avg_sec = total_sec / len(secs) if secs else 0.0

    by_engine: dict[str, dict] = {}
    by_date: dict[str, int] = {}
    for r in rows:
        eng = r.get("engine", "unknown")
        e = by_engine.setdefault(eng, {"count": 0, "secs": []})
        e["count"] += 1
        if isinstance(r.get("elapsed_sec"), (int, float)):
            e["secs"].append(r["elapsed_sec"])
        date = r.get("date", "?")
        by_date[date] = by_date.get(date, 0) + 1

    for e in by_engine.values():
        e["avg_sec"] = (sum(e["secs"]) / len(e["secs"])) if e["secs"] else 0.0
        e.pop("secs", None)

    return {
        "total": total,
        "passed": passed,
        "passed_rate": round(passed / total, 2) if total else 0.0,
        "total_sec": round(total_sec, 1),
        "avg_sec": round(avg_sec, 1),
        "by_engine": by_engine,
        "by_date": by_date,
    }


def format_report(stats: dict[str, Any], days: int | None = None) -> str:
    """汇总 → 可读报表。"""
    if stats["total"] == 0:
        return "📊 暂无生成成本记录（跑一次 workshop create 后会自动记账）"
    lines = []
    title = f"最近 {days} 天" if days else "累计"
    lines.append(f"📊 生成成本账（{title}）")
    lines.append(f"  生成次数: {stats['total']}  达标: {stats['passed']} ({stats['passed_rate']*100:.0f}%)")
    lines.append(f"  总耗时: {stats['total_sec']:.0f}s ≈ {stats['total_sec']/60:.1f}min  平均: {stats['avg_sec']:.1f}s/张")
    if stats.get("by_engine"):
        lines.append("  按引擎:")
        for eng, e in sorted(stats["by_engine"].items(), key=lambda kv: -kv[1]["count"]):
            lines.append(f"    {eng:<10} {e['count']} 张  avg {e['avg_sec']:.1f}s")
    if stats.get("by_date"):
        lines.append("  按日期:")
        for d, cnt in sorted(stats["by_date"].items()):
            lines.append(f"    {d}  {cnt} 张")
    return "\n".join(lines)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="workshop cost", description="生成成本账（JSONL 累计）")
    ap.add_argument("--days", type=int, default=None, help="只看最近 N 天")
    ap.add_argument("--json", action="store_true", help="输出 JSON（程序可读）")
    args = ap.parse_args(argv)

    stats = summarize(args.days)
    if args.json:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    else:
        print(format_report(stats, args.days))
    return 0


if __name__ == "__main__":
    sys.exit(main())