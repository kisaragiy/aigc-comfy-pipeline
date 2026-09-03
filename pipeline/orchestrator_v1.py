#!/usr/bin/env python3
"""编排器 v1.5 · P1 修复链（失败类型分类 + 多级修复路由）

管线：S1 出图 → S10 门禁 → 修复链 → S10 终检 → 交付

修复链（按代价递增，P0 教训：E4 结构性撕裂 S5 修不好，必须升级）：
  MANUAL_REVIEW (A6_over_detail) → S5 tile（表层）→ 终检
     仍 MANUAL_REVIEW/FAIL → S6 lineart（中度）→ 终检
         仍 MANUAL_REVIEW/FAIL → S7 openpose（重度，≈重画）→ 终检
             仍 MANUAL_REVIEW → 人工复核（管线如实报告，不谎报）

用法：
  python pipeline/orchestrator_v1.py --prompt "..." [--style v4] [--seed N]
  python pipeline/orchestrator_v1.py --input <img> --skip-gen
  python pipeline/orchestrator_v1.py --input <img> --max-fix 0   # 只诊断
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))

from common import new_job, write_manifest  # noqa: E402

STAGES = ROOT / "pipeline" / "stages"
OUTDIR = ROOT / "outputs"


def run_stage(script: str, args: list[str], timeout: int = 600) -> tuple[int, str]:
    cmd = [sys.executable, str(STAGES / script), "--outdir", str(OUTDIR)] + args
    env = dict(os.environ)
    env["PYTHONPATH"] = ""
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    return p.returncode, (p.stdout + p.stderr)


def extract_job_id(output: str) -> str | None:
    for line in output.splitlines():
        if "JOB_ID=" in line:
            return line.split("JOB_ID=", 1)[1].strip()
    return None


def extract_verdict(output: str) -> str | None:
    for line in output.splitlines():
        if "verdict=" in line:
            return line.split("verdict=")[1].strip()
    return None


def extract_suspect(output: str) -> str:
    for line in output.splitlines():
        if "suspect=" in line:
            return line.split("suspect=")[1].strip()
    return ""


def gate(img: str, outdir: Path) -> tuple[str, str]:
    """跑门禁，返回 (verdict, suspect)。"""
    rc, out = run_stage("s10_gate.py", ["--input", img, "--code"])
    print(out)
    return extract_verdict(out) or "UNKNOWN", extract_suspect(out)


def fix(img: str, stage: str, outdir: Path) -> str:
    """跑修复工位，返回新图路径。"""
    print(f"\n── {stage} 修复 ──")
    rc, out = run_stage(stage, ["--input", img])
    print(out)
    if rc != 0:
        raise RuntimeError(f"{stage} 失败")
    jid = extract_job_id(out)
    return str(outdir / f"{jid}.png") if jid else img


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", default="")
    ap.add_argument("--input", default="")
    ap.add_argument("--style", choices=["v3", "v4"], default="v4")
    ap.add_argument("--seed", type=int, default=20260901)
    ap.add_argument("--max-fix", type=int, default=3,
                    help="最大修复轮数（0=只诊断；1=S5；2=S5+S6；3=S5+S6+S7）")
    args = ap.parse_args()
    OUTDIR.mkdir(parents=True, exist_ok=True)

    job = new_job("PIPE")
    print(f"═══ 编排器 v1.5 {job}  max_fix={args.max_fix} ═══")

    # ── S1 ──
    cur_img = args.input
    history: list[str] = []
    if cur_img:
        print("[S1] 跳过（--input）")
        history.append("S1(skip)")
    else:
        if not args.prompt:
            print("❌ 需要 --prompt 或 --input")
            return 1
        rc, out = run_stage("s1_txt2img.py", ["--prompt", args.prompt,
                                              "--style", args.style,
                                              "--seed", str(args.seed)])
        print(out)
        if rc != 0:
            print("❌ S1 失败，管线中止")
            return 1
        jid = extract_job_id(out)
        if not jid:
            print("❌ S1 无法解析 JOB_ID")
            return 1
        cur_img = str(OUTDIR / f"{jid}.png")
        history.append("S1")

    # ── 首次门禁 ──
    print("\n── S10 门禁 ──")
    verdict, suspect = gate(cur_img, OUTDIR)
    history.append("S10")
    print(f"   verdict={verdict} suspect={suspect}")

    if verdict == "PASS":
        print(f"\n✅ PASS → 直接交付: {cur_img}")
        write_manifest(job, "PIPE", cur_img, args.prompt,
                       {"gate_verdict": "PASS", "fixed": False},
                       gate={"verdict": "PASS"}, history=history, status="pass")
        print(f"   manifest: {ROOT}/manifests/{job}.json")
        return 0
    if verdict == "FAIL":
        print("\n❌ C1 故障图 → 丢弃")
        write_manifest(job, "PIPE", cur_img, args.prompt,
                       {"gate_verdict": "FAIL", "fixed": False},
                       gate={"verdict": "FAIL"}, history=history, status="fail")
        return 0

    # ── MANUAL_REVIEW → 修复链 ──
    fix_chain = ["s5_tile.py", "s6_lineart.py", "s7_openpose.py"]
    if args.max_fix <= 0:
        print(f"\n⚠️ MANUAL_REVIEW + --max-fix 0 → 停在人工复核")
        write_manifest(job, "PIPE", cur_img, args.prompt,
                       {"gate_verdict": "MANUAL_REVIEW", "fixed": False,
                        "suspect": suspect},
                       gate={"verdict": "MANUAL_REVIEW", "suspect": suspect},
                       history=history, status="manual_review")
        return 0

    fixed = False
    for i, fix_stage in enumerate(fix_chain[: args.max_fix], 1):
        print(f"\n── 修复链 第{i}级: {fix_stage} ──")
        cur_img = fix(cur_img, fix_stage, OUTDIR)
        history.append(f"S{fix_stage[1]}")
        verdict2, suspect2 = gate(cur_img, OUTDIR)
        history.append("S10")
        if verdict2 == "PASS":
            print(f"\n✅ 第{i}级修复后 PASS → 交付: {cur_img}")
            fixed = True
            write_manifest(job, "PIPE", cur_img, args.prompt,
                           {"gate_verdict": "MANUAL_REVIEW", "fixed": True,
                            "fix_level": i, "final_verdict": "PASS"},
                           gate={"verdict": "PASS", "suspect": suspect2},
                           history=history, status="pass")
            print(f"   manifest: {ROOT}/manifests/{job}.json")
            return 0
        print(f"   第{i}级后仍 {verdict2} → 升级")
        if verdict2 == "FAIL":
            print("   FAIL（新故障？）→ 停止修复，标记人工")
            break

    print(f"\n⚠️ 修复链耗尽（{args.max_fix} 级）仍 MANUAL_REVIEW → 人工复核: {cur_img}")
    write_manifest(job, "PIPE", cur_img, args.prompt,
                   {"gate_verdict": "MANUAL_REVIEW", "fixed": fixed,
                    "fix_level": args.max_fix, "final_verdict": "MANUAL_REVIEW",
                    "suspect": suspect},
                   gate={"verdict": "MANUAL_REVIEW", "suspect": suspect},
                   history=history, status="manual_review")
    print(f"   manifest: {ROOT}/manifests/{job}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
