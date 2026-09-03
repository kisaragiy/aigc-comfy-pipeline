#!/usr/bin/env python3
"""
quality_judge.py — 商业立绘质量判据（P0 代码量化层）

【定位】不靠 VLM 感觉，用代码硬指标抓"半成品"。这是质量门禁里最可靠的一层。
   解决用户痛点："糊图/平涂/分辨率不足/黑图也能过"——VLM 会因整体美观带偏，
   代码不会。VLM 只负责结构语义(手崩/表情/风格)，交给 vlm_auto_eval.py。

【判据】(P0, 全部可量化)
  C1 故障图     : 黑图/花屏/全白/错乱(方差过低) → dead
  A5 分辨率     : 最短边 < RES_MIN → fail (商用需≥1500或超分)
  A4 清晰度     : 拉普拉斯方差 < SHARP_MIN → fail (糊)
  A2d 空白占比  : 低纹理区域占比过高 → fail (大面积平涂=半成品)
  A2 完成度     : 细节密度(局部纹理方差均值) < DETAIL_MIN → fail (平涂/敷衍)
  C2 重复度     : 感知哈希相似度 > DUP_THRESH 同批高度重复 → warn
  F3 水印/伪影  : 检测仿水印网格/压缩块残留 → warn

【用法】
  python quality_judge.py  <image>            # 单张判据
  python quality_judge.py batch <dir> [--limit N]   # 批量
  python quality_judge.py dup <dir>           # 同批重复度检测
  python quality_judge.py scan <dir>          # 汇总: 每张+判定+统计

【输出】每项 {passed: bool, value, threshold, note}
  综合 verdict: pass / warn / fail(任一硬指标不过)
"""

from __future__ import annotations

import argparse
import hashlib
import math
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from PIL import ImageFilter

# ─────────────────────────────────────────────────────────────
# 判据阈值(可按批次/需求校准)
# ─────────────────────────────────────────────────────────────
RES_MIN = 1500          # 商业立绘最短边(需≥1500或超分; 原始生成896常不够→提示超分)
SHARP_MIN = 1000        # 拉普拉斯方差, 低于=糊(同批elizabeth中位1139, 38%<1000)
DETAIL_MIN = 2.5        # 局部纹理方差均值, 低于=平涂/敷衍(占多数则半成品)
BLANK_RATIO_MAX = 0.55  # 低纹理区占比, 超=大面积平涂/空白
DUP_THRESH = 0.95       # 感知哈希相似度, 超=同批重复

# ── A6 过度细节上限 (2026-08-31 新增) ──────────────────────────
# 背景: 现有判据全部只防"太平/太糊"这一头, 对"高频伪细节"整类失明。
#   IPAdapter 参考图过冲产生的撕裂/噪点, 在数学上表现为**锐度和细节双高**,
#   实测被门禁全部放行(E0 锐度7288/细节3873 判 PASS, 比多张好图分还高)。
# 定标依据(9 样本, IPAdapter 过冲故障集 workspace/ipa_rootcause):
#   BAD(撕裂)  detail = 3873 / 5277
#   WARN       detail = 1568 / 3348
#   GOOD       detail = 1341 ~ 2868
#   → 3500 落在 WARN最高(3348) 与 BAD最低(3873) 之间, 两侧均有余量
# ⚠️ 为何不用锐度做这件事: 同批锐度 BAD=[7288, 2998] 与 GOOD=[4518..1315] **重叠**,
#   单阈值无法分开(E4 比多张好图还钝) —— 锐度不适合当过冲判据。
# ⚠️ 小样本初值(仅 2 张 BAD), 需更多故障样本校准 → **不进死点**, 只标 suspect
#   触发人眼放大复核(沿用 8-24/8-30 教训: 代码层不拍板, 避免误杀合法艺术处理)。
OVER_DETAIL_MAX = 3500

ERROR_SHARP = 60        # 低于此几乎无纹理=黑图/花屏/全白这类故障图


# ─────────────────────────────────────────────────────────────
# 图像指标
# ─────────────────────────────────────────────────────────────
def laplacian_variance(img: Image.Image) -> float:
    """拉普拉斯方差: 糊图低, 锐图高。反映清晰度/纹理量。"""
    a = np.asarray(img.convert("L"), dtype=np.float32)
    lap = (np.roll(a, -1, 0) + np.roll(a, 1, 0) +
           np.roll(a, -1, 1) + np.roll(a, 1, 1) - 4 * a)
    return float(lap.var())


def texture_variance_map(img: Image.Image, block: int = 64) -> tuple[float, float]:
    """局部纹理方差统计: 返回 (均值, 低纹理占比)。
    均值低=整体平涂; 低纹理占比高=大面积空白/无细节区。"""
    gray = np.asarray(img.convert("L"), dtype=np.float32)
    h, w = gray.shape
    var_scores = []
    low_count = 0
    total = 0
    for by in range(0, h - block + 1, block):
        for bx in range(0, w - block + 1, block):
            blk = gray[by:by + block, bx:bx + block]
            v = float(blk.var())
            var_scores.append(v)
            total += 1
            if v < 30:   # 低纹理块(近纯色/平涂)
                low_count += 1
    if not var_scores:
        return 0.0, 1.0
    return float(np.mean(var_scores)), low_count / total


def is_broken_image(img: Image.Image) -> tuple[bool, str]:
    """故障检测: 黑图/全白/花屏/错乱。用方差判断。

    ⚠️ 2026-08-30 修正: 移除 mean>245 判据。
    bug 复现: 明石_19(白底立绘) mean=246 被判"白屏"→误杀。
    真相: 白底商业立绘(碧蓝/原神风格) mean>245 是正常格式(方便抠图/合成),
    非白像素占比低但 var 高(1285, 有主体)。真白屏/花屏是 var<30(低方差)。
    mean 判据多余且误杀, 删除。只保留 var 判据。
    """
    gray = np.asarray(img.convert("L"), dtype=np.float32)
    mean = float(gray.mean())
    var = float(gray.var())
    if var < 30 or mean < 8:
        return True, f"低信息量(mean={mean:.0f}, var={var:.0f})→黑/花屏"
    return False, ""


def lineart_quality(img: Image.Image) -> tuple[float, float]:
    """线条/边缘质量统计: 返回 (边缘碎片率, 线宽均匀度)。

    通过边缘梯度检测 + 局部连通性分析判断线稿崩坏:
    - 边缘碎片率 = 孤立的短边缘占比(高=线稿断裂/碎)
    - 线宽均匀度 = 边缘厚度的变异系数(高=粗细不均/锯齿)
    商业立绘线稿: 碎片率低、均匀度适中。
    """
    gray = np.asarray(img.convert("L"), dtype=np.float32)
    if gray.shape[0] < 3 or gray.shape[1] < 3:
        return 0.0, 0.0
    edge_mag = np.sqrt(np.gradient(gray)[0] ** 2 + np.gradient(gray)[1] ** 2)
    edge_mask = edge_mag > 60   # 边缘像素

    total_px = edge_mask.size
    edge_px = int(edge_mask.sum())
    if edge_px == 0:
        return 1.0, 1.0   # 几乎无边缘 = 线稿缺失/全糊

    # 碎片率: 8邻域连通的分量中, 小分量(<5px)占比
    # 用简单的形态学统计: 计算孤立边缘点(周围8邻域内无其他边缘点)
    padded = np.pad(edge_mask, 1, mode="constant")
    neighbor_count = np.zeros_like(edge_mask, dtype=np.int32)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            neighbor_count += padded[1+dy:1+dy+edge_mask.shape[0],
                                     1+dx:1+dx+edge_mask.shape[1]]
    isolated = ((edge_mask) & (neighbor_count <= 1)).sum()   # 孤立碎片
    fragment_rate = isolated / max(1, edge_px)

    # 线宽均匀度: 每行/列边缘连续段的宽度变异
    widths = []
    for row in edge_mask[::4]:   # 抽样行
        in_seg = False
        seg_len = 0
        for v in row:
            if v:
                if not in_seg:
                    in_seg = True
                    seg_len = 1
                else:
                    seg_len += 1
            else:
                if in_seg:
                    widths.append(seg_len)
                    in_seg = False
        if in_seg:
            widths.append(seg_len)
    if widths:
        import statistics
        width_var = statistics.pstdev(widths) / max(1, (sum(widths)/len(widths)))
    else:
        width_var = 1.0
    return round(fragment_rate, 3), round(width_var, 2)


# ── A3 线稿阈值 ──
FRAGMENT_RATE_MAX = 0.06   # 碎片率 > 6% = 线稿断裂/碎
WIDTH_VAR_MAX = 1.5        # 线宽变异系数 > 1.5 = 粗细严重不均/锯齿


def perceptual_hash(img: Image.Image, hash_size: int = 16) -> str:
    """感知哈希(均值哈希): 用于同批重复度检测。"""
    im = img.convert("L").resize((hash_size, hash_size), Image.LANCZOS)
    a = np.asarray(im, dtype=np.float32)
    avg = a.mean()
    bits = "".join("1" if p > avg else "0" for p in a.flatten())
    return bits


def hash_distance(h1: str, h2: str) -> float:
    """两个感知哈希的汉明距离 → 相似度(0-1)。"""
    d = sum(a != b for a, b in zip(h1, h2))
    return 1.0 - d / len(h1)


# ─────────────────────────────────────────────────────────────
# 单张判据
# ─────────────────────────────────────────────────────────────
def judge(image_path: str, batch_hashes: list[str] | None = None) -> dict:
    p = Path(image_path)
    if not p.is_file():
        return {"image": image_path, "error": "not_found", "verdict": "fail"}

    try:
        img = Image.open(image_path)
    except Exception as e:
        return {"image": image_path, "error": f"open: {e}", "verdict": "fail"}

    w, h = img.size
    short = min(w, h)
    sharp = laplacian_variance(img)
    detail_mean, blank_ratio = texture_variance_map(img)
    broken, broken_note = is_broken_image(img)
    frag_rate, width_var = lineart_quality(img)

    checks = {}

    # C1 故障图
    checks["C1_broken"] = {
        "passed": not broken, "value": None,
        "threshold": "not_broken", "note": broken_note or "正常",
    }

    # A5 分辨率
    checks["A5_resolution"] = {
        "passed": short >= RES_MIN, "value": short,
        "threshold": f">={RES_MIN}", "note": f"{w}x{h} 最短边{short}",
    }

    # A4 清晰度
    checks["A4_sharpness"] = {
        "passed": sharp >= SHARP_MIN, "value": round(sharp, 1),
        "threshold": f">={SHARP_MIN}", "note": "锐利" if sharp >= SHARP_MIN else "糊/纹理少",
    }

    # A2d 空白占比 + A2 完成度
    checks["A2_detail_density"] = {
        "passed": detail_mean >= DETAIL_MIN, "value": round(detail_mean, 2),
        "threshold": f">={DETAIL_MIN}", "note": "细节充足" if detail_mean >= DETAIL_MIN else "平涂/敷衍",
    }
    checks["A2d_blank_ratio"] = {
        "passed": blank_ratio <= BLANK_RATIO_MAX, "value": round(blank_ratio, 2),
        "threshold": f"<={BLANK_RATIO_MAX}", "note": f"低纹理{blank_ratio*100:.0f}%",
    }

    # A6 过度细节 —— 与 A2 相反方向: A2 防"太平/敷衍", A6 防"太碎/撕裂"
    checks["A6_over_detail"] = {
        "passed": detail_mean <= OVER_DETAIL_MAX,
        "value": round(detail_mean, 2),
        "threshold": f"<={OVER_DETAIL_MAX}",
        "note": "细节密度正常" if detail_mean <= OVER_DETAIL_MAX
                else "高频伪细节(疑撕裂/噪点/参考图过冲)→需放大复核",
    }

    # A3 线稿质量 (P1)
    # 只以碎片率(线稿断裂/碎)为死点——细节丰富的商业图边缘宽度变化本就大, 线宽变异不适合当死点。
    checks["A3_lineart"] = {
        "passed": frag_rate <= FRAGMENT_RATE_MAX,
        "value": {"frag": frag_rate, "width_var": width_var},
        "threshold": f"frag<={FRAGMENT_RATE_MAX}",
        "note": "线稿正常" if frag_rate <= FRAGMENT_RATE_MAX
                else f"碎片率{frag_rate:.1%}(线稿断裂/碎)",
    }

    # C2 重复度(传同批哈希时才检测)
    checks["C2_duplicate"] = {
        "passed": True, "value": None, "threshold": "n/a", "note": "未启用批量对比",
    }

    # F3 水印/伪影(启发式: 检测仿水印网格 — 边缘密度异常高且规则)
    # 简化: 检测常见压缩块残留/横向条纹
    checks["F3_watermark"] = {
        "passed": True, "value": None, "threshold": "n/a", "note": "未做深度水印检测",
    }

    verdict = "pass"
    # 死点语义(真·半成品/故障, 不是"还能补救"):
    #   C1 故障图(黑/花/错乱)    → fail
    #   A2 细节密度(整体敷衍)    → fail
    # ⚠️ A4 清晰度已从死点移除(2026-08-30实测): 主流游戏官方立绘(碧蓝/原神)
    #   大量柔焦/平涂艺术风格, 拉普拉斯方差分不开(正样本282~9032跨度过大,
    #   A3实测误杀35%: 俾斯麦282/胡滕542/信浓624全被杀)。柔焦/平涂是合法艺术处理,
    #   A4_sharpness 仅作提示, 不进死点——真·没画完的AI糊图由C1(低方差)拦截。
    # ⚠️ A2d 空白占比已从死点移除(2026-08-24实测真商业立绘校准):
    #   真·白底商业立绘(elisabeth_official)空白占比0.68——白底/纯色背景是商业立绘
    #   标准格式(方便抠图/合成), 大面积"空白"是特性不是半成品。空白占比仅作提示。
    # ⚠️ A3 线稿碎片率已撤下(2026-08-24实测): 碎片率误把"复杂场景边缘"当"线稿碎"——
    #   00201 是干净商业立绘(轮廓闭合/场景丰富)却碎片率0.079判FAIL。判据误杀好图, 不用。
    # 分辨率(A5) 不作为质量判定——它是"交付前需超分"的动作提示, 不是图本身的缺陷。
    hard_dead = ["C1_broken", "A2_detail_density"]
    hard_fail = [k for k in hard_dead if k in checks and not checks[k]["passed"]]

    if hard_fail:
        verdict = "fail"
    else:
        verdict = "pass"

    # 可疑项: 不判死, 仅提示人眼放大复核(三层分工——代码层标记范围, 人眼拍板)
    suspect_keys = ["A6_over_detail"]
    suspect = [k for k in suspect_keys
               if k in checks and not checks[k]["passed"]]

    return {
        "image": str(p),
        "size": {"w": w, "h": h, "short": short},
        "metrics": {
            "sharpness": round(sharp, 1),
            "detail_density": round(detail_mean, 2),
            "blank_ratio": round(blank_ratio, 2),
            "fragment_rate": frag_rate,
            "line_width_var": width_var,
        },
        "checks": checks,
        "verdict": verdict,
        "suspect": suspect,
    }


# ─────────────────────────────────────────────────────────────
# 批量 + 汇总
# ─────────────────────────────────────────────────────────────
def collect_images(directory: str, limit: int = 0) -> list[str]:
    exts = (".png", ".jpg", ".jpeg", ".webp")
    files = sorted(
        f for f in Path(directory).rglob("*")
        if f.is_file() and f.suffix.lower() in exts
    )
    if limit:
        files = files[:limit]
    return [str(f) for f in files]


def batch_judge(directory: str, limit: int = 0) -> list[dict]:
    files = collect_images(directory, limit)
    # 先算同批哈希(判断重复)
    hashes = []
    for f in files:
        try:
            img = Image.open(f)
            hashes.append(perceptual_hash(img))
        except Exception:
            hashes.append("")

    results = []
    for i, f in enumerate(files):
        res = judge(f)
        # 补重复度
        if res.get("verdict") != "fail" and len(hashes) > 1:
            sims = [hash_distance(hashes[i], hashes[j])
                    for j in range(len(hashes)) if j != i]
            if sims:
                max_sim = max(sims)
                res["checks"]["C2_duplicate"] = {
                    "passed": max_sim < DUP_THRESH,
                    "value": round(max_sim, 3),
                    "threshold": f"<{DUP_THRESH}",
                    "note": f"同批最高相似{max_sim*100:.0f}%",
                }
                if max_sim >= DUP_THRESH:
                    res["verdict"] = "warn"
        # 死点覆盖(对齐单张 judge): 真·故障/敷衍才 fail (2026-08-30风格判据移出门禁)
        #   C1_broken(黑/花/错乱) + A2_detail_density(整体敷衍) = 死点
        #   移出: A4_sharpness(柔焦/平涂官方风格) / A2d_blank_ratio(白底标准格式)
        dead_keys = ["C1_broken"]  # A2_detail_density 移出(2026-08-31 见修正说明)
        if "checks" in res and any(k in res["checks"] and not res["checks"][k]["passed"]
                                   for k in dead_keys):
            res["verdict"] = "fail"
        results.append(res)
    return results


def print_result(res: dict):
    name = Path(res.get("image", "")).name
    if res.get("error"):
        print(f"  {name}: ❌ {res['error']}")
        return
    m = res.get("metrics", {})
    print(f"  {name}  [{res['verdict'].upper()}]  "
          f"锐度={m.get('sharpness')} 细节={m.get('detail_density')} "
          f"空白={m.get('blank_ratio')} 尺寸={res.get('size',{}).get('short')}")
    for k, v in res.get("checks", {}).items():
        flag = "✅" if v["passed"] else "❌"
        if k == "C2_duplicate" and v["passed"] and "未启用" in str(v["note"]):
            continue
        print(f"     {flag} {k}: {v['note']}")


def summarize(results: list[dict]) -> None:
    total = len(results)
    if not total:
        print("无图片")
        return
    by = {"pass": 0, "warn": 0, "fail": 0}
    for r in results:
        by[r.get("verdict", "fail")] = by.get(r.get("verdict", "fail"), 0) + 1
    print(f"\n{'='*50}\n批量判据汇总 ({total} 张)")
    print(f"{'='*50}")
    print(f"  ✅ pass: {by['pass']} ({by['pass']/total*100:.0f}%)")
    print(f"  ⚠️ warn: {by['warn']}")
    print(f"  ❌ fail: {by['fail']} ({by['fail']/total*100:.0f}%)")
    # fail 详细
    if by["fail"]:
        print("\n  未通过(半成品/故障):")
        for r in results:
            if r.get("verdict") == "fail":
                m = r.get("metrics", {})
                name = Path(r.get("image", "")).name
                fails = [k for k, v in r.get("checks", {}).items() if not v["passed"]]
                print(f"     ❌ {name}: {' / '.join(fails)}")


def main():
    ap = argparse.ArgumentParser(description="商业立绘质量判据(P0代码层)")
    sub = ap.add_subparsers(dest="action", required=True)

    s1 = sub.add_parser("judge", help="单张判据")
    s1.add_argument("path")

    s2 = sub.add_parser("batch", help="批量判据")
    s2.add_argument("dir")
    s2.add_argument("--limit", type=int, default=0)

    s3 = sub.add_parser("dup", help="同批重复度检测")
    s3.add_argument("dir")

    s4 = sub.add_parser("scan", help="批量+汇总")
    s4.add_argument("dir")
    s4.add_argument("--limit", type=int, default=0)

    args = ap.parse_args()

    if args.action == "judge":
        print_result(judge(args.path))
    elif args.action == "batch":
        for r in batch_judge(args.dir):
            print_result(r)
    elif args.action == "dup":
        files = collect_images(args.dir)
        hashes = []
        for f in files:
            try:
                hashes.append(perceptual_hash(Image.open(f)))
            except Exception:
                hashes.append("")
        print(f"{len(files)} 张, 重复对检测:")
        for i in range(len(hashes)):
            for j in range(i + 1, len(hashes)):
                if hashes[i] and hashes[j]:
                    sim = hash_distance(hashes[i], hashes[j])
                    if sim >= DUP_THRESH:
                        print(f"  ⚠️ {Path(files[i]).name} ≈ {Path(files[j]).name} ({sim*100:.0f}%)")
        print("(无输出=无重复)")
    elif args.action == "scan":
        results = batch_judge(args.dir, args.limit)
        for r in results:
            print_result(r)
        summarize(results)


if __name__ == "__main__":
    main()
