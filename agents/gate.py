#!/usr/bin/env python3
"""
gate.py — 商业立绘统一质量门禁（P0 整合：代码量化层 + VLM 定位层 + 放大复核）

【分层分工】
  ① 代码量化层 (quality_judge)  : 抓"糊/平涂/黑图/分辨率"——硬指标, 不被氛围带偏
  ② VLM 定位层 (vlm_auto_eval)  : 抓"手崩/结构错乱/画错东西"——指出具体区域和问题
  ③ 放大复核 (crop + vision)     : 对 VLM 报的 high 区域裁切放大, 人眼实锤排除幻觉

【用法】
  python gate.py  <image>              # 完整门禁: 两层+需放大区域
  python gate.py --code <image>        # 仅代码层(最快,不调VLM)
  python gate.py --deep <image>        # 加VLM定位层(结构语义)
  python gate.py batch <dir> [--limit N] [--deep]
  python gate.py link <image>          # 打印需放大复核的裁剪命令

【输出】verdict: PASS / FAIL / MANUAL_REVIEW(需放大确认)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from quality_judge import judge as code_judge
from quality_judge import collect_images


def load_vlm():
    """加载 vlm_auto_eval 的 scan(若脚本在 Hermes scripts 目录)。"""
    vlm_script = os.path.expanduser(
        "~/AppData/Local/hermes/scripts/vlm_auto_eval.py")
    if not Path(vlm_script).is_file():
        return None
    import importlib.util
    spec = importlib.util.spec_from_file_location("vlm_gate", vlm_script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_gate(image: str, deep: bool = False, verbose: bool = True,
             check_compliance: bool = False) -> dict:
    code = code_judge(image)
    if code.get("error"):
        return {"image": image, "error": code["error"], "verdict": "FAIL"}

    # 代码层死点: 仅真·故障 → FAIL (2026-08-30对齐业界: 风格判据移出门禁)
    #   C1_broken(黑/花/错乱) = 真故障 → 死点
    #   A2_detail_density(整体敷衍) = 提示性死点 (不误杀官方立绘, 拦"大面积平涂")
    #   以下均移出死点(合法艺术处理, 实测误杀, 参照8-24/8-30教训):
    #     A4_sharpness(柔焦/平涂=主流官方立绘风格, 实测误杀35%)
    #     A2d_blank_ratio(白底/纯色背景=官方立绘标准格式)
    #     A3_lineart(碎片率误杀复杂场景)
    dead_hits = [k for k, v in code["checks"].items()
                 if k in ("C1_broken",) and not v["passed"]]
    verdict = "FAIL" if dead_hits else "PASS"

    # A6 过度细节(高频伪细节: 撕裂/噪点/参考图过冲) — 2026-08-31 新增
    #   不判死(小样本阈值, 且怕误杀高细节合法风格), 直接标 MANUAL_REVIEW 要人眼放大。
    #   来由: 实测 IPAdapter 过冲故障图锐度/细节双高, 被旧门禁 100% 放行。
    code_suspect = code.get("suspect", [])
    if code_suspect and verdict == "PASS":
        verdict = "MANUAL_REVIEW"

    regions = []
    vlm = None
    compliance = None

    # B1 提示词符合度(可选): 读元数据prompt + VLM对比图 → 画错东西=F1死点
    if check_compliance:
        try:
            sys.path.insert(0, str(HERE))
            from compliance import compliance_check
            compliance = compliance_check(image)
            if compliance.get("verdict") == "fail":
                verdict = "FAIL"   # 画错东西(关键属性不符) → 死点
        except Exception as e:
            if verbose:
                print(f"  ⚠️ 符合度检查失败(跳过): {str(e)[:100]}")

    # VLM 定位层(可选): 结构语义(手崩/画错)
    if deep:
        vlm = load_vlm()
        if vlm:
            try:
                report = vlm.scan(image, use_local=False)
                regions = report.get("suspicious_regions", [])
                # VLM 报 high 需放大 → 即使代码层 pass 也标记 MANUAL_REVIEW
                if regions and any(
                        r.get("needs_zoom") or r.get("severity") == "high"
                        for r in regions) and verdict != "FAIL":
                    verdict = "MANUAL_REVIEW"
            except Exception as e:
                if verbose:
                    print(f"  ⚠️ VLM 定位失败(跳过): {str(e)[:100]}")

    return {
        "image": image,
        "verdict": verdict,
        "code_dead_hits": dead_hits,
        "code_suspect": code_suspect,
        "code_metrics": code.get("metrics", {}),
        "code_checks": code.get("checks", {}),
        "vlm_regions": regions,
        "compliance": compliance,
        "needs_zoom": any(r.get("needs_zoom") or r.get("severity") == "high"
                          for r in regions),
    }


def _adapt_code_result(code_res: dict) -> dict:
    """把 quality_judge 原生结果适配成 run_gate 的输出格式。

    2026-08-31 修 bug: batch 模式原先把 batch_judge 的原生结构直接喂给 print_gate,
    但两者字段名不一致(metrics vs code_metrics)、verdict 大小写不一致(pass vs PASS)
    → 批量审图时锐度/细节/空白全部打印成 None, 等于白跑。
    本适配器统一结构, 同时保留 batch 独有的 C2 同批重复度检测结果。
    """
    if code_res.get("error"):
        return {"image": code_res.get("image"), "error": code_res["error"],
                "verdict": "FAIL"}
    checks = code_res.get("checks", {})
    dead_hits = [k for k, v in checks.items()
                 if k in ("C1_broken", "A2_detail_density") and not v.get("passed")]
    suspect = code_res.get("suspect", [])
    dup_warn = not checks.get("C2_duplicate", {}).get("passed", True)
    if dead_hits:
        verdict = "FAIL"
    elif suspect or dup_warn:
        verdict = "MANUAL_REVIEW"      # A6 过度细节 / 同批重复 → 人眼复核
    else:
        verdict = "PASS"
    return {
        "image": code_res.get("image"),
        "verdict": verdict,
        "code_dead_hits": dead_hits,
        "code_suspect": suspect,
        "code_metrics": code_res.get("metrics", {}),
        "code_checks": checks,
        "vlm_regions": [],
        "compliance": None,
        "needs_zoom": False,
    }


def print_gate(res: dict):
    name = Path(res.get("image", "")).name
    if res.get("error"):
        print(f"  {name}: ❌ {res['error']}")
        return
    v = res["verdict"]
    icon = {"PASS": "✅", "FAIL": "❌", "MANUAL_REVIEW": "🔍"}.get(v, "?")
    m = res.get("code_metrics", {})
    print(f"\n{icon} {name}  [{v}]  "
          f"锐度={m.get('sharpness')} 细节={m.get('detail_density')} "
          f"空白={m.get('blank_ratio')}")

    # 代码层
    dead = res.get("code_dead_hits", [])
    if dead:
        print(f"    ❌ 代码死点: {' / '.join(dead)}")
    for k, c in res.get("code_checks", {}).items():
        if k in ("C1_broken", "A5_resolution") and not c["passed"]:
            if k == "A5_resolution":
                print(f"    ⓘ 分辨率: {c.get('note','')} (交付前需超分)")
            else:
                print(f"    ⓘ 故障: {c.get('note','')}")

    # VLM 层
    for r in res.get("vlm_regions", []):
        zoom = "🔍" if r.get("needs_zoom") else "  "
        print(f"    {zoom} [{r.get('severity','?')}] {r.get('region')} "
              f"({r.get('position','?')}): {r.get('issue','')}")

    # B1 符合度层
    comp = res.get("compliance")
    if comp:
        cicon = {"pass": "✅", "fail": "❌", "warn": "⚠️"}.get(comp.get("verdict"), "?")
        found = "有" if comp.get("prompt_found") else "无元数据"
        print(f"    {cicon} 符合度({found}): {comp.get('detail','')}")

    if res.get("verdict") == "MANUAL_REVIEW":
        print(f"    → 需 vision_analyze 放大复核; 裁剪命令见 gate.py link")


def main():
    ap = argparse.ArgumentParser(description="商业立绘统一质量门禁 (代码层+VLM定位+符合度)")
    ap.add_argument("mode", nargs="?", choices=["gate", "batch", "link"],
                    default="gate", help="gate=单图, batch=批量, link=打印放大命令")
    ap.add_argument("target", nargs="?", help="图片路径 或 目录(batch)")
    ap.add_argument("--code", action="store_true", help="仅代码层(不调VLM)")
    ap.add_argument("--deep", action="store_true", help="加VLM定位层")
    ap.add_argument("--compliance", action="store_true", help="加提示词符合度检查")
    ap.add_argument("--limit", type=int, default=0, help="batch 限制张数")
    args = ap.parse_args()

    if args.mode == "gate":
        if not args.target:
            ap.print_help(); return
        res = run_gate(args.target,
                       deep=args.deep and not args.code,
                       check_compliance=args.compliance)
        print_gate(res)
    elif args.mode == "batch":
        if not args.target:
            ap.print_help(); return
        # 用 quality_judge.batch_judge: 已含 C2 同批重复度检测 + 循环判据
        imgs = collect_images(args.target, args.limit)
        print(f"门禁批量: {len(imgs)} 张 "
              f"{'(VLM深度)' if args.deep else ''}{'(符合度)' if args.compliance else ''}")
        from quality_judge import batch_judge
        results = batch_judge(args.target, args.limit)
        # 重复度标注到每张
        for raw in results:
            # 2026-08-31: 必须经适配器转成 run_gate 结构, 否则 print_gate 读不到指标
            res = _adapt_code_result(raw)
            if args.deep or args.compliance:
                extra = run_gate(res["image"], deep=args.deep,
                                 check_compliance=args.compliance)
                res["vlm_regions"] = extra.get("vlm_regions", [])
                res["compliance"] = extra.get("compliance", None)
                res["needs_zoom"] = extra.get("needs_zoom", False)
                if extra["verdict"] != "PASS":
                    res["verdict"] = extra["verdict"]
            print_gate(res)
    elif args.mode == "link":
        if not args.target:
            ap.print_help(); return
        res = run_gate(args.target, deep=True)
        zooms = [r for r in res.get("vlm_regions", [])
                 if r.get("needs_zoom") or r.get("severity") == "high"]
        print(f"需放大复核 {len(zooms)} 处:")
        for i, r in enumerate(zooms):
            print(f"  [{i}] {r.get('region')} ({r.get('position','')}): {r.get('issue','')}")
        print("\n裁剪命令(crop, 相对坐标按图比例):")
        for r in zooms:
            print(f"  python ~/AppData/Local/hermes/scripts/vlm_auto_eval.py crop \"{args.target}\" 0.3 0.1 0.7 0.5")


if __name__ == "__main__":
    main()
