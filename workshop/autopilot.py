"""Autopilot — 自动扫参 + 空闲跑批 + 质量数据库。

用法:
  python -m agents workshop autopilot batch.txt --db quality.json
  python -m agents workshop autopilot batch.txt --grid "steps:20,30,40;cfg:5.0,7.0"
  python -m agents workshop autopilot --recommend "银发精灵 森林"  # 查最佳参数
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from agents.go_flux import build_flux_workflow
    from agents.comfy_utils import (
        apply_preset, comfy_post_prompt, comfy_base_url,
        generate_with_quality, wait_images, resolve_comfy_root,
    )
    from workshop.inspect import inspect_image
    from workshop.engine import nls_to_prompt
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


# ── 质量数据库 ────────────────────────────────────────────

class QualityDB:
    """JSON 质量数据库：记录 prompt→参数→分数，越用越准。"""

    def __init__(self, path: str = "quality.json"):
        self.path = Path(path)
        self.data: dict[str, dict[str, Any]] = {}
        if self.path.is_file():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self.data = {}

    def _hash(self, prompt: str) -> str:
        """对 prompt 取 hash 作为键。"""
        import hashlib
        return hashlib.md5(prompt.encode()).hexdigest()[:16]

    def record(self, prompt: str, params: dict[str, Any], score: dict[str, float]) -> None:
        """记录一次生成结果。"""
        key = self._hash(prompt)
        entry = self.data.get(key, {"prompt": prompt, "runs": []})
        entry["runs"].append({
            "params": {k: v for k, v in params.items() if v is not None},
            "score": score,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        # 按综合分排序，最优在前
        def _best(r: dict) -> float:
            s = r.get("score", {})
            return s.get("combined", 0) or s.get("overall", 0)
        entry["runs"].sort(key=_best, reverse=True)
        # 只保留前 20 条
        entry["runs"] = entry["runs"][:20]
        self.data[key] = entry
        self._save()

    def best_params(self, prompt: str) -> dict[str, Any] | None:
        """查询该 prompt 的最优参数。"""
        key = self._hash(prompt)
        entry = self.data.get(key)
        if entry and entry.get("runs"):
            return entry["runs"][0].get("params")
        return None

    def best_score(self, prompt: str) -> float:
        """查询该 prompt 的最高分。"""
        key = self._hash(prompt)
        entry = self.data.get(key)
        if entry and entry.get("runs"):
            s = entry["runs"][0].get("score", {})
            return s.get("combined", 0) or s.get("overall", 0)
        return 0.0

    def best_diverse_params(self, prompt: str, k: int = 3) -> list[dict[str, Any]]:
        """返回 TOP-K 多样化参数组合（steps/cfg 维度差异大）。

        Args:
            prompt: 查询 prompt
            k: 最多返回几组

        Returns:
            [{steps, cfg, preset, score, source}, ...] 按质量降序，但保证参数多样性
        """
        key = self._hash(prompt)
        entry = self.data.get(key)
        if not entry or not entry.get("runs"):
            return []

        runs = entry["runs"]
        # 构建参数→最高分映射
        param_scores: dict[str, dict[str, Any]] = {}
        for r in runs:
            params = r.get("params", {})
            if not params:
                continue
            # 用 steps,cfg 做 key
            pkey = f"{params.get('steps', '?')}_{params.get('cfg', '?')}"
            score = r.get("score", {}).get("combined", 0)
            if pkey not in param_scores or score > param_scores[pkey].get("score", 0):
                param_scores[pkey] = {
                    "steps": params.get("steps", 20),
                    "cfg": params.get("cfg", 7.0),
                    "preset": params.get("preset"),
                    "score": score,
                }

        if not param_scores:
            return []

        params_list = list(param_scores.values())
        # 按分数降序
        params_list.sort(key=lambda x: -x["score"])

        if k >= len(params_list):
            for p in params_list:
                p["source"] = "auto"
            return params_list

        # 贪心选择: 先拿最高分，然后每次选与已选集距离最大的
        selected = [params_list[0]]
        remaining = params_list[1:]

        while len(selected) < k and remaining:
            # 对每个剩余的，找到与已选集的最小距离
            best_dist = -1
            best_idx = 0
            for i, cand in enumerate(remaining):
                min_dist = min(_param_distance(cand, s) for s in selected)
                if min_dist > best_dist:
                    best_dist = min_dist
                    best_idx = i
            selected.append(remaining.pop(best_idx))

        for p in selected:
            p["source"] = "auto"
        return selected

    def find_related_prompts(self, prompt: str, max_results: int = 5) -> list[dict[str, Any]]:
        """查找与当前 prompt 相关的历史最优参数。

        匹配策略:
          1. 精确匹配（同 prompt hash）
          2. 共享角色签名（同角色名或独特特征）
          3. 回退空列表

        Returns:
            [{prompt, steps, cfg, preset, score}, ...]
        """
        # 1. 精确匹配
        exact = self.best_diverse_params(prompt, k=3)
        if exact:
            return exact

        # 2. 角色签名匹配
        sig = extract_character_signature(prompt)
        if sig:
            primary_marker = sig[0]
            related: list[dict[str, Any]] = []
            for key, entry in self.data.items():
                ep = entry.get("prompt", "")
                esig = extract_character_signature(ep)
                if primary_marker in esig:
                    runs = entry.get("runs", [])
                    if runs:
                        # 取该 prompt 的最佳参数
                        best_run = runs[0]
                        params = best_run.get("params", {})
                        score = best_run.get("score", {}).get("combined", 0)
                        related.append({
                            "prompt": ep[:60],
                            "steps": params.get("steps", 20),
                            "cfg": params.get("cfg", 7.0),
                            "preset": params.get("preset"),
                            "score": score,
                            "source": f"related: {ep[:40]}",
                        })
            if related:
                related.sort(key=lambda x: -x["score"])
                return related[:3]

        return []

    def stats(self) -> dict[str, Any]:
        """返回统计信息。"""
        total = len(self.data)
        total_runs = sum(len(e.get("runs", [])) for e in self.data.values())
        return {"prompts": total, "runs": total_runs}

    def _save(self) -> None:
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 角色签名提取 ──────────────────────────────────────────

def extract_character_signature(prompt: str) -> list[str]:
    """从 prompt 中提取角色身份标记（角色名、独特装饰、服装等）。

    用于区分不同角色的最优参数，防止跨角色参数污染。

    Returns:
        角色标记列表（按重要性降序）
    """
    import re
    markers: list[str] = []

    # 1. 引号内的字符名: "Alice" 或 'Bob'
    quoted = re.findall(r'["\u201c\u201d]([^"\u201c\u201d]+)["\u201c\u201d]', prompt)
    markers.extend(quoted)

    # 2. 角色/人物/人设 标签后的名字
    char_after = re.findall(r'(?:角色|人物|人设)[：:]\s*(\S+)', prompt)
    markers.extend(char_after)

    # 3. 常见角色名前缀: 作为|名为|叫 后面跟着的名字
    named = re.findall(r'(?:作为|名为|叫)\s*(\S+?)(?:\s|，|,|。|$)', prompt)
    markers.extend(named)

    # 4. 独有服饰/特征标记: 提取"的"前面2-4字的独特描述
    #    "红色蝴蝶结"、"猫耳发饰"、"眼罩" 等
    unique_items = re.findall(r'([\u4e00-\u9fff]{2,6}(?:蝴蝶结|发饰|发夹|耳环|项链|戒指|手镯|头饰|帽子'
                              r'|眼镜|眼罩|口罩|围巾|披风|斗篷|铠甲|纹身|伤疤|翅膀|尾巴))', prompt)
    markers.extend(unique_items)

    # 5. 颜色+服饰/部位组合
    color_items = re.findall(r'([\u4e00-\u9fff]{1,2}(?:色|)*[\u4e00-\u9fff]{1,4}(?:发|眼|瞳|裙|衣|服|裤|鞋|袜))', prompt)
    markers.extend(color_items)

    return markers


# ── 参数多样性 ────────────────────────────────────────────

DIVERSE_PRESETS: list[dict[str, Any]] = [
    {"name": "quality", "steps": 30, "cfg": 7.0, "preset": "quality"},
    {"name": "balanced", "steps": 20, "cfg": 7.0, "preset": "balanced"},
    {"name": "fast", "steps": 15, "cfg": 5.0, "preset": "fast"},
    {"name": "creative", "steps": 25, "cfg": 9.0, "preset": "balanced"},
]


def _param_distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    """计算两组参数的距离（steps/cfg 维度）。"""
    s1 = a.get("steps", 20) or 20
    s2 = b.get("steps", 20) or 20
    c1 = a.get("cfg", 7.0) or 7.0
    c2 = b.get("cfg", 7.0) or 7.0
    return ((s1 - s2) / 10) ** 2 + ((c1 - c2) / 2.0) ** 2


# ── 参数调度生成 ──────────────────────────────────────────

def build_param_schedule(
    count: int,
    *,
    steps: int = 20,
    cfg: float = 7.0,
    preset: str | None = None,
    auto_diverse: list[dict[str, Any]] | None = None,
    variety: int = 1,
    explore_rate: float = 0.0,
) -> list[dict[str, Any]]:
    """为 count 张候选构建参数调度表（每张候选使用什么参数）。

    Args:
        count: 候选总数
        steps: 默认步数
        cfg: 默认 CFG
        preset: 默认预设
        auto_diverse: 来自 quality DB 的多样化推荐参数（含权重），
                      每个元素: {steps, cfg, preset, weight}
        variety: 多样性模式 >1 时在内置预设间轮换
        explore_rate: 探索率 (0~1, 多少比例的候选用随机附近参数)

    Returns:
        [{steps, cfg, preset, source}, ...] 长度 = count
    """
    import random

    schedule: list[dict[str, Any]] = []

    # 确定候选"池"
    pool: list[dict[str, Any]] = []

    if auto_diverse:
        # 来自 quality DB 的多样化推荐
        pool = list(auto_diverse)
    elif variety > 1:
        # 内置多样性模式
        for v in range(variety):
            vp = DIVERSE_PRESETS[v % len(DIVERSE_PRESETS)].copy()
            vp["source"] = f"variety_{vp['name']}"
            pool.append(vp)
    else:
        pool.append({
            "steps": steps, "cfg": cfg, "preset": preset,
            "source": "default",
        })

    if not pool:
        pool.append({
            "steps": steps, "cfg": cfg, "preset": preset,
            "source": "default",
        })

    # 按权重构建调度
    for i in range(count):
        # 探索模式
        if explore_rate > 0 and random.random() < explore_rate:
            base = random.choice(pool)
            explore_steps = min(80, max(10, (base.get("steps", 20) or 20) + random.choice([-5, 0, 5])))
            explore_cfg = round(min(20.0, max(1.0, (base.get("cfg", 7.0) or 7.0) + random.choice([-0.5, 0, 0.5]))), 1)
            schedule.append({
                "steps": explore_steps,
                "cfg": explore_cfg,
                "preset": base.get("preset"),
                "source": "explore",
            })
        else:
            # 从池中轮换选择
            entry = pool[i % len(pool)]
            schedule.append({
                "steps": entry.get("steps", steps),
                "cfg": entry.get("cfg", cfg),
                "preset": entry.get("preset", preset),
                "source": entry.get("source", "auto"),
            })

    return schedule


# ── 质量 DB 增强 ──────────────────────────────────────────

DEFAULT_GRID = "steps:20,30;cfg:5.0,7.0"
QUALITY_WEIGHTS = {"face": 0.3, "hand": 0.2, "foot": 0.1, "blur": 0.1, "clip": 0.3}


def parse_grid(grid_str: str) -> dict[str, list[Any]]:
    """解析参数网格字符串 → 参数字典。

    "steps:20,30;cfg:5.0,7.0" → {"steps": [20, 30], "cfg": [5.0, 7.0]}
    """
    grid: dict[str, list[Any]] = {}
    for part in grid_str.split(";"):
        part = part.strip()
        if ":" not in part:
            continue
        key, vals_str = part.split(":", 1)
        key = key.strip()
        vals: list[Any] = []
        for v in vals_str.split(","):
            v = v.strip()
            try:
                if "." in v:
                    vals.append(float(v))
                else:
                    vals.append(int(v))
            except ValueError:
                vals.append(v)
        if vals:
            grid[key] = vals
    return grid


def _grid_product(grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """展开参数网格为参数组合列表。"""
    from itertools import product
    keys = list(grid.keys())
    if not keys:
        return [{}]
    combos = []
    for values in product(*[grid[k] for k in keys]):
        combos.append(dict(zip(keys, values)))
    return combos


def _combined_score(inspect_result: dict[str, Any], clip_score: float | None = None) -> dict[str, float]:
    """综合质检结果 + CLIP 分数 → 加权评分。"""
    scores = inspect_result.get("scores", {})
    overall = scores.get("overall", 0)
    face = scores.get("脸", 0)
    hand = scores.get("手", 0)
    foot = scores.get("脚", 0)
    blur = scores.get("模糊", 0)

    combined = (
        face * QUALITY_WEIGHTS["face"] +
        hand * QUALITY_WEIGHTS["hand"] +
        foot * QUALITY_WEIGHTS["foot"] +
        blur * QUALITY_WEIGHTS["blur"]
    )
    if clip_score and clip_score > 0:
        combined = combined * 0.6 + clip_score * 0.4

    return {
        "overall": overall,
        "face": face, "hand": hand, "foot": foot, "blur": blur,
        "clip": clip_score or 0,
        "combined": round(combined, 4),
    }


def param_grid_generate(
    prompt: str,
    grid_str: str = DEFAULT_GRID,
    *,
    ref_path: str | None = None,
    db: QualityDB | None = None,
    verbose: bool = False,
) -> list[dict[str, Any]]:
    """对同一 prompt 跑参数网格扫描，返回所有结果。"""
    grid = parse_grid(grid_str)
    combos = _grid_product(grid)
    results: list[dict[str, Any]] = []

    for i, params in enumerate(combos):
        print(f"\r  [{i+1}/{len(combos)}] 参数: {params}", end="", flush=True)
        try:
            qr = generate_with_quality(
                build_flux_workflow, prompt,
                preset=params.get("preset"),
                min_score=0.0,
                max_retries=1,
                no_validate=True,
                seed=-1,
                ref_image=ref_path,
                ip_weight=0.7,
                ip_balance=0.5,
                steps=params.get("steps", 20),
                cfg=params.get("cfg", 7.0),
            )
            images = qr.get("images", [])
            img_path = images[0] if images else ""
            inspect_result = {}
            clip_val: float | None = qr.get("score")
            if img_path and Path(img_path).is_file():
                inspect_result = inspect_image(img_path, use_mediapipe=False)
            score = _combined_score(inspect_result, clip_val)

            result = {
                "params": params,
                "image": img_path,
                "score": score,
                "seed": qr.get("seed"),
            }
            results.append(result)

            if db:
                db.record(prompt, params, score)
            if verbose:
                print(f"  => 综合 {score['combined']:.4f}")
        except Exception as exc:
            if verbose:
                print(f"  => ❌ {exc}")

    # 按综合分降序
    results.sort(key=lambda r: r["score"]["combined"], reverse=True)
    return results


# ── 空闲检测 ──────────────────────────────────────────────

def wait_until_idle(url: str | None = None, check_interval: float = 5.0, timeout: float = 3600) -> bool:
    """等待 ComfyUI queue 为空。返回是否在超时前空闲。"""
    import requests
    base = comfy_base_url(url)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = requests.get(f"{base}/queue", timeout=10)
            data = r.json()
            running = data.get("queue_running")
            pending = data.get("queue_pending", [])
            if not running and not pending:
                return True
        except Exception:
            pass
        time.sleep(check_interval)
    return False


# ── Autopilot 主函数 ──────────────────────────────────────

def run_autopilot(
    prompts_file: str,
    *,
    grid_str: str = DEFAULT_GRID,
    db_path: str = "quality.json",
    ref_path: str | None = None,
    idle_mode: bool = False,
    verbose: bool = False,
) -> list[dict[str, Any]]:
    """自动扫参跑批。

    Args:
        prompts_file: 批量文件路径（每行一条 prompt）
        grid_str: 参数网格
        db_path: 质量数据库路径
        ref_path: 参考图路径（所有 prompt 共用）
        idle_mode: 空闲模式（每批之间等待 ComfyUI 空闲）
        verbose: 详细信息

    Returns:
        每个 prompt 的最优结果列表
    """
    fp = Path(prompts_file)
    if not fp.is_file():
        print(f"❌ 文件不存在: {prompts_file}")
        return []

    lines = [l.strip() for l in fp.read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.strip().startswith("#")]
    if not lines:
        print("❌ 文件中没有有效 prompt")
        return []

    db = QualityDB(db_path)
    print(f"\n{'='*60}")
    print(f"🤖 Autopilot: {len(lines)} 条 prompt, 网格 {grid_str}")
    print(f"📊 数据库: {db_path} ({db.stats()['runs']} 条记录)")
    print(f"{'='*60}\n")

    all_results = []
    for i, prompt_text in enumerate(lines, 1):
        print(f"\n[{i}/{len(lines)}] 📝 {prompt_text[:60]}")

        # 先查数据库，如果有最优参数则跳过网格扫描
        best = db.best_params(prompt_text)
        if best and not verbose:
            print(f"      📋 已有最优参数: {best} (score={db.best_score(prompt_text):.4f})")
            continue

        results = param_grid_generate(
            prompt_text, grid_str=grid_str,
            ref_path=ref_path, db=db, verbose=verbose)

        if results:
            best_result = results[0]
            print(f"      🏆 最优: {best_result['params']} → 综合 {best_result['score']['combined']:.4f}")
            all_results.append({"prompt": prompt_text, **best_result})

        # 空闲模式：等待 ComfyUI 空闲
        if idle_mode and i < len(lines):
            print(f"      ⏳ 等待 ComfyUI 空闲...")
            if not wait_until_idle(timeout=600):
                print(f"      ⚠️ 超时，跳过等待")

    print(f"\n{'='*60}")
    print(f"📊 Autopilot 完成: {len(all_results)}/{len(lines)} 条有新结果")
    print(f"📊 数据库: {db.stats()['runs']} 条总记录")
    return all_results


# ── 质量报告 ──────────────────────────────────────────────

def generate_report(db_path: str, output_path: str = "quality_report.html") -> str:
    """从质量数据库生成 HTML 报告。

    Args:
        db_path: 质量数据库路径
        output_path: HTML 输出路径

    Returns:
        HTML 文件路径
    """
    db = QualityDB(db_path)
    rows = ""
    best_overall = 0.0
    best_prompt = ""

    for key, entry in sorted(db.data.items(), key=lambda x: x[0]):
        prompt = entry.get("prompt", "?")[:60]
        runs = entry.get("runs", [])
        if not runs:
            continue
        top = runs[0]
        score = top.get("score", {})
        combined = score.get("combined", 0)
        params = top.get("params", {})
        param_str = ", ".join(f"{k}={v}" for k, v in params.items()) if params else "默认"
        run_count = len(runs)
        worst = min(r.get("score", {}).get("combined", 0) for r in runs) if runs else 0

        if combined > best_overall:
            best_overall = combined
            best_prompt = prompt

        rows += f"""<tr>
  <td class="name">{prompt}</td>
  <td>{combined:.4f}</td>
  <td>{param_str}</td>
  <td>{run_count}</td>
  <td class="bar-cell"><div class="bar" style="width:{combined*100:.0f}%"></div></td>
</tr>"""

    score_dist = ""
    scores = [r.get("score", {}).get("combined", 0)
              for e in db.data.values() for r in e.get("runs", [])]
    if scores:
        avg = sum(scores) / len(scores)
        score_dist = f"平均分: {avg:.4f} | 最高: {max(scores):.4f} | 最低: {min(scores):.4f}"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>质量报告 · Autopilot</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#1a1a2e;color:#eee;font-family:system-ui,sans-serif;padding:20px}}
h1{{font-size:1.4rem;margin-bottom:4px;color:#e8a87c}}
.summary{{color:#aaa;font-size:.85rem;margin-bottom:16px}}
table{{width:100%;border-collapse:collapse;font-size:.85rem}}
th,td{{padding:8px 10px;text-align:left;border-bottom:1px solid #333}}
th{{color:#7ec8e3;font-weight:600}}
.name{{max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.bar-cell{{width:150px}}
.bar{{height:16px;background:#4ade80;border-radius:3px;min-width:4px;transition:width .3s}}
.best{{color:#e8a87c;font-weight:600}}
</style></head>
<body>
<h1>📊 质量报告</h1>
<div class="summary">
  共 {db.stats()['prompts']} 个 prompt · {db.stats()['runs']} 次生成 · {score_dist}
</div>
<table>
<tr><th>Prompt</th><th>最佳分</th><th>最优参数</th><th>尝试</th><th>趋势</th></tr>
{rows}
</table>
</body></html>"""
    Path(output_path).write_text(html, encoding="utf-8")
    print(f"  🖼️  质量报告: {output_path}")
    return output_path
