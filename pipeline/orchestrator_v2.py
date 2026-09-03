#!/usr/bin/env python3
"""编排器 v2 · P2 候选池 + 交付前自动超分

在 v1.5 修复链基础上增加：
  1. 候选池：S1 批量出 N 张 → 门禁择优 → 只对选中的送修（省 token 省显存）
  2. 交付前 S9 超分（商业图最短边需≥1500）

用法：
  python pipeline/orchestrator_v2.py --prompt "..." --count 4 [--style v4] [--seed 起点]
  python pipeline/orchestrator_v2.py --prompt "..." --count 4 --upscale 2048
  python pipeline/orchestrator_v2.py --input <img> --skip-gen --max-fix 2
"""
from __future__ import annotations

import argparse
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


def gate(img: str) -> tuple[str, str]:
    rc, out = run_stage("s10_gate.py", ["--input", img, "--code"])
    return extract_verdict(out) or "UNKNOWN", extract_suspect(out)


def fix(img: str, stage: str) -> str:
    rc, out = run_stage(stage, ["--input", img])
    if rc != 0:
        raise RuntimeError(f"{stage} 失败")
    jid = extract_job_id(out)
    return str(OUTDIR / f"{jid}.png") if jid else img


def upscale(img: str, target_width: int) -> str:
    rc, out = run_stage("s9_upscale.py", ["--input", img,
                                          "--target-width", str(target_width)])
    if rc != 0:
        return img
    jid = extract_job_id(out)
    return str(OUTDIR / f"{jid}.png") if jid else img


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", default="")
    ap.add_argument("--input", default="")
    ap.add_argument("--style", choices=["v3", "v4"], default="v4")
    ap.add_argument("--seed", type=int, default=20260901)
    ap.add_argument("--count", type=int, default=1, help="候选池数量（S1 批量）")
    ap.add_argument("--max-fix", type=int, default=3)
    ap.add_argument("--upscale", type=int, default=0, help="交付前超分目标宽度（0=不超分）")
    ap.add_argument("--keep-all", action="store_true",
                    help="候选池不择优，全部走管线（诊断用）")
    args = ap.parse_args()
    OUTDIR.mkdir(parents=True, exist_ok=True)

    job = new_job("PIPE")
    print(f"═══ 编排器 v2 {job}  count={args.count} max_fix={args.max_fix} "
          f"upscale={args.upscale} ═══")

    # ── 候选池 ──
    candidates: list[tuple[str, str]] = []  # (path, verdict)
    history: list[str] = []
    if args.input:
        print("[S1] 跳过（--input）")
        candidates.append((args.input, ""))
        history.append("S1(skip)")
    else:
        if not args.prompt:
            print("❌ 需要 --prompt 或 --input")
            return 1
        for i in range(args.count):
            seed = args.seed + i
            rc, out = run_stage("s1_txt2img.py", ["--prompt", args.prompt,
                                                  "--style", args.style,
                                                  "--seed", str(seed)])
            print(out)
            if rc != 0:
                print(f"⚠️ S1 第{i+1}张失败，跳过")
                continue
            jid = extract_job_id(out)
            if jid:
                candidates.append((str(OUTDIR / f"{jid}.png"), ""))
        history.append(f"S1x{len(candidates)}")
        if not candidates:
            print("❌ 候选池为空")
            return 1

    # ── 候选池门禁 + VLM 美学评分择优 ──
    print(f"\n── 候选池门禁+评分（{len(candidates)} 张）──")
    for idx, (path, _) in enumerate(candidates):
        verdict, suspect = gate(path)
        candidates[idx] = (path, verdict)
        print(f"  [{idx}] {Path(path).name} → {verdict}  suspect={suspect}")

    if not args.keep_all:
        # 择优 v2.1：先按 PASS > MANUAL > FAIL 分层，层内再用 VLM 美学评分选最高分
        rank = {"PASS": 0, "MANUAL_REVIEW": 1, "UNKNOWN": 2, "FAIL": 3}
        candidates.sort(key=lambda c: rank.get(c[1], 4))
        top = candidates[0]
        if top[1] != "PASS":
            print("\n── 候选池有非 PASS 项，VLM 评分择优 ──")
            pool_pass = [c for c in candidates if c[1] == "PASS"]
            scored = []
            for path, v in (pool_pass or candidates[:3]):
                rc, out = run_stage("s11_vlm_score.py", ["--input", path])
                print(out[-400:])
                total = None
                for line in out.splitlines():
                    if "TOTAL=" in line:
                        total = float(line.split("TOTAL=")[1].strip())
                        break
                if total is not None:
                    scored.append((path, v, total))
            if scored:
                scored.sort(key=lambda x: x[2], reverse=True)
                top = scored[0]
                print(f"  🏆 最优: {Path(top[0]).name}  VLM={top[2]}")

        if top[1] == "PASS":
            cur = top[0]
            final = upscale(cur, args.upscale) if args.upscale else cur
            # 超分后终检（超分可能引入伪影）
            final_verdict = "PASS"
            if final != cur:
                rc, out = run_stage("s10_gate.py", ["--input", final, "--code"])
                print(out)
                final_verdict = extract_verdict(out) or "UNKNOWN"
                history.append("S10(final)")
            print(f"\n{'✅' if final_verdict != 'FAIL' else '⚠️'} 候选池 PASS → 交付: {final}  "
                  f"(超分后门禁 {final_verdict})")
            write_manifest(job, "PIPE", final, args.prompt,
                           {"pool": [Path(p).name for p, _ in candidates],
                            "gate_verdict": "PASS", "fixed": False,
                            "upscaled": final != cur,
                            "final_verdict": final_verdict,
                            "vlm_total": top[2] if len(top) > 2 else None},
                           gate={"verdict": final_verdict}, history=history,
                           status=final_verdict.lower())
            print(f"   manifest: {ROOT}/manifests/{job}.json")
            return 0
        best = top[0]
    else:
        best = candidates[0][0]

    # ── 修复链 ──
    print(f"\n── 最优候选: {Path(best).name} → 修复链 ──")
    verdict, suspect = gate(best)
    history.append("S10")
    if verdict == "FAIL":
        print("❌ C1 故障图 → 丢弃")
        write_manifest(job, "PIPE", best, args.prompt,
                       {"pool": [Path(p).name for p, _ in candidates],
                        "gate_verdict": "FAIL", "fixed": False},
                       gate={"verdict": "FAIL"}, history=history, status="fail")
        return 0

    fix_chain = ["s5_tile.py", "s6_lineart.py", "s7_openpose.py"]
    cur = best
    fixed = False
    for i, fix_stage in enumerate(fix_chain[: args.max_fix], 1):
        print(f"\n── 修复链 第{i}级: {fix_stage} ──")
        cur = fix(cur, fix_stage)
        history.append(f"S{fix_stage[1]}")
        verdict2, suspect2 = gate(cur)
        history.append("S10")
        if verdict2 == "PASS":
            fixed = True
            print(f"✅ 第{i}级后 PASS")
            break
        print(f"   仍 {verdict2} → 升级")

    # ── 交付前超分 + 终检 ──
    final = cur
    if args.upscale:
        print(f"\n── S9 超分 ({args.upscale}px) ──")
        final = upscale(final, args.upscale)
        history.append("S9")
        # 超分后终检（超分可能引入伪影）
        rc, out = run_stage("s10_gate.py", ["--input", final, "--code"])
        print(out)
        verdict2, _ = extract_verdict(out) or "UNKNOWN", ""
        history.append("S10(final)")
        print(f"   超分后门禁: {verdict2}")
    else:
        history.append("S9(skip)")

    status = "pass" if fixed or (not fixed and verdict2 == "PASS") else "manual_review"
    print(f"\n{'✅' if status == 'pass' else '⚠️'} 交付: {final}")
    write_manifest(job, "PIPE", final, args.prompt,
                   {"pool": [Path(p).name for p, _ in candidates],
                    "gate_verdict": "MANUAL_REVIEW", "fixed": fixed,
                    "final_verdict": verdict2 if "verdict2" in locals() else "PASS"},
                   gate={"verdict": verdict2 if "verdict2" in locals() else "PASS",
                         "suspect": suspect},
                   history=history, status=status)
    print(f"   manifest: {ROOT}/manifests/{job}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
