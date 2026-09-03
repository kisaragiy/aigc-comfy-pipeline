#!/usr/bin/env python3
"""工位 S10 · 质量门禁（gate.py 封装为工位接口）

统一接口：pipeline/stages/s10_gate.py --input <img> [--code] [--deep]
输出：stdout 打印 verdict + 写 manifest（gate 字段）

返回码：0=PASS  2=FAIL  3=MANUAL_REVIEW  1=错误
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "agents"))
sys.path.insert(0, str(ROOT / "pipeline"))

from gate import run_gate  # noqa: E402
from common import new_job, write_manifest  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="图片路径")
    ap.add_argument("--code", action="store_true", help="仅代码层(默认)")
    ap.add_argument("--deep", action="store_true", help="加VLM定位层")
    ap.add_argument("--compliance", action="store_true")
    ap.add_argument("--outdir", default=str(ROOT / "outputs"))
    args = ap.parse_args()

    img = Path(args.input)
    if not img.is_file():
        print(f"❌ S10 输入不存在: {img}")
        return 1

    job = new_job("S10")
    deep = args.deep and not args.code
    res = run_gate(str(img), deep=deep, verbose=True,
                   check_compliance=args.compliance)
    if res.get("error"):
        print(f"❌ S10 错误: {res['error']}")
        return 1

    verdict = res["verdict"]
    gate_info = {
        "verdict": verdict,
        "dead_hits": res.get("code_dead_hits", []),
        "suspect": res.get("code_suspect", []),
        "metrics": res.get("code_metrics", {}),
        "needs_zoom": res.get("needs_zoom", False),
    }
    write_manifest(
        job, "S10", str(img), None, {"mode": "deep" if deep else "code"},
        gate=gate_info, history=["S10"], status=verdict.lower())

    print(f"[S10] {img.name} verdict={verdict}")
    m = res.get("code_metrics", {})
    print(f"  锐度={m.get('sharpness')} 细节={m.get('detail_density')} "
          f"空白={m.get('blank_ratio')}")
    print(f"  suspect={res.get('code_suspect')}  dead={res.get('code_dead_hits')}")
    rc = {2: "FAIL", 3: "MANUAL_REVIEW", 0: "PASS"}.get(
        2 if verdict == "FAIL" else 3 if verdict == "MANUAL_REVIEW" else 0, 0)
    return rc


if __name__ == "__main__":
    sys.exit(main())
