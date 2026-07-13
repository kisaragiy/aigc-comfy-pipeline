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

    def stats(self) -> dict[str, Any]:
        """返回统计信息。"""
        total = len(self.data)
        total_runs = sum(len(e.get("runs", [])) for e in self.data.values())
        return {"prompts": total, "runs": total_runs}

    def _save(self) -> None:
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 参数网格扫描 ──────────────────────────────────────────

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
