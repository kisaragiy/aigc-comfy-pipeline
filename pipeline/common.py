#!/usr/bin/env python3
"""管线工位化 · 基类与 manifest 契约

每个工位 = 一个可独立运行的脚本，输入图+参数 → 输出图+manifest.json。
manifest 是工位间接力的唯一契约（缺失时编排器无法做路由决策）。

manifest.json 标准（v1）:
{
  "job_id": "20260901-<stage>-<ts>",
  "stage": "S1",
  "input": "绝对路径或null",
  "output": "输出图绝对路径",
  "prompt": "生成/修复用 prompt（S10 门禁为 null）",
  "params": {工位专属参数},
  "gate": {门禁结果（S10 填充）},
  "history": ["S1", "S5", "S10"],   # 工位执行轨迹
  "status": "ok|fail|pass|manual_review",
  "ts": "ISO时间"
}
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path


def new_job(stage: str) -> str:
    return f"{stage}-{time.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"


def write_manifest(job_id: str, stage: str, output: str | None,
                   prompt: str | None, params: dict, gate: dict | None,
                   history: list[str], status: str) -> Path:
    """写 manifest 到 <outdir>/manifests/<job_id>.json，返回路径。"""
    m = {
        "job_id": job_id,
        "stage": stage,
        "input": None,
        "output": output,
        "prompt": prompt,
        "params": params,
        "gate": gate,
        "history": history,
        "status": status,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    # 找 manifest 目录：output 的父级/manifests
    outdir = Path(output).parent.parent if output else Path.cwd()
    mdir = outdir / "manifests"
    mdir.mkdir(parents=True, exist_ok=True)
    mpath = mdir / f"{job_id}.json"
    mpath.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    return mpath


def load_manifest(job_id: str) -> dict | None:
    """按 job_id 读回 manifest。"""
    for mdir in [Path("manifests"), Path("../manifests")]:
        p = mdir / f"{job_id}.json"
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    return None
