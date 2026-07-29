"""人工审核系统 — 扫描、标注、管理生成结果。"""

from __future__ import annotations

import json
import shutil
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

# ── 数据模型 ────────────────────────────────────────────

REVIEW_FILE = "review.json"
TRASH_DIR = "_trash"

# 审核判决
VERDICT_KEEP = "keep"       # 保留（默认）
VERDICT_DELETE = "delete"   # 删除（移至 _trash）
VERDICT_FAVORITE = "favorite"  # 精选（面试样张候选）
VERDICT_RETRY = "retry"     # 需重试
VERDICTS = [VERDICT_KEEP, VERDICT_DELETE, VERDICT_FAVORITE, VERDICT_RETRY]

# 预设标签
PRESET_TAGS = [
    "崩脸", "崩手", "崩脚",
    "表情好", "表情差",
    "构图佳", "构图差",
    "色彩好", "色彩糊",
    "姿势自然", "姿势僵硬",
    "光影好",
]

# ── 核心函数 ────────────────────────────────────────────


def scan_output(output_dir: str) -> list[dict[str, Any]]:
    """扫描 demo 输出目录，返回待审图片列表。

    返回结构:
        [{
            "path": "portrait/gallery/candidate_00.png",   # 相对路径
            "abs_path": "C:\\...\\demo\\portrait\\gallery\\candidate_00.png",
            "scene": "近景肖像",
            "scene_id": "portrait",
            "seed": 123456789,
            "auto_score": -1.0,
            "inspect": {"face": 1.0, "hand": 1.0, "foot": 1.0, "blur": 1.0, "summary": "..."},
            "is_best": False,
            "index": 0,  # candidate 序号
        }, ...]
    """
    out = Path(output_dir)
    if not out.is_dir():
        raise NotADirectoryError(f"输出目录不存在: {output_dir}")

    # 尝试从 demo_report.md 或一致性报告推断场景列表
    scenes = _detect_scenes(out)
    images: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    for scene_id, scene_title in scenes:
        scene_dir = out / scene_id
        meta_path = scene_dir / "metadata.json"

        if not meta_path.is_file():
            continue

        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue

        candidates = meta.get("candidates", [])
        gallery_dir = scene_dir / "gallery"

        for idx, cand in enumerate(candidates):
            # 确定图片路径
            img_rel = f"{scene_id}/gallery/candidate_{idx:02d}.png"
            img_abs = out / img_rel

            # 兜底：尝试 .jpg
            if not img_abs.is_file():
                img_rel = f"{scene_id}/gallery/candidate_{idx:02d}.jpg"
                img_abs = out / img_rel
                if not img_abs.is_file():
                    continue

            # 去重
            abs_str = str(img_abs.resolve())
            if abs_str in seen_paths:
                continue
            seen_paths.add(abs_str)

            # 解析 inspect 摘要
            summary = cand.get("inspect_summary", "")
            inspection = _parse_inspect_summary(summary)
            # 补充 inspect_overall
            overall = cand.get("inspect_overall")
            if overall is not None:
                inspection["overall"] = overall
            inspection["summary"] = summary

            images.append({
                "path": img_rel.replace("\\", "/"),
                "abs_path": abs_str,
                "scene": scene_title,
                "scene_id": scene_id,
                "seed": cand.get("seed", 0),
                "auto_score": cand.get("score", -1.0),
                "inspect": inspection,
                "is_best": False,
                "index": idx,
            })

        # 检查 best.png
        for best_name in ["best.png", "best.jpg", "best.jpeg"]:
            best_path = scene_dir / best_name
            if best_path.is_file():
                best_rel = f"{scene_id}/{best_name}"
                abs_str = str(best_path.resolve())
                if abs_str not in seen_paths:
                    seen_paths.add(abs_str)
                    # 取第一个 candidate 的种子作为 best 的种子
                    best_seed = candidates[0].get("seed", 0) if candidates else 0
                    images.append({
                        "path": best_rel.replace("\\", "/"),
                        "abs_path": abs_str,
                        "scene": scene_title,
                        "scene_id": scene_id,
                        "seed": best_seed,
                        "auto_score": -1.0,
                        "inspect": {"overall": -1, "summary": ""},
                        "is_best": True,
                        "index": -1,
                    })
                break

    return images


def _detect_scenes(out: Path) -> list[tuple[str, str]]:
    """从输出目录推断场景列表 (scene_id, scene_title)。"""
    # 尝试读 demo_report.md
    report = out / "demo_report.md"
    scenes: list[tuple[str, str]] = []

    if report.is_file():
        try:
            text = report.read_text(encoding="utf-8")
            in_table = False
            for line in text.splitlines():
                if line.startswith("| 序号 |"):
                    in_table = True
                    continue
                if in_table and line.startswith("|"):
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) >= 3:
                        sid = parts[1]
                        title = parts[2]
                        if sid and title and sid != "序号":
                            scenes.append((sid, title))
                elif in_table and not line.startswith("|"):
                    break
        except OSError:
            pass

    if not scenes:
        # 兜底：扫描子目录
        for d in sorted(out.iterdir()):
            if d.is_dir() and not d.name.startswith("_") and d.name != "gallery":
                scenes.append((d.name, d.name))

    return scenes


def _parse_inspect_summary(summary: str) -> dict[str, float]:
    """解析 inspect 摘要字符串为结构化评分。

    "[脸:ok] [左眼:ok] [右眼:ok] [手:ok] [脚:ok] [模糊:正常]"
    → {"face": 1.0, "left_eye": 1.0, "right_eye": 1.0, "hand": 1.0, "foot": 1.0, "blur": 1.0}
    """
    mapping: dict[str, float] = {}
    if not summary:
        return mapping

    import re
    for match in re.finditer(r"\[([^:]+):([^\]]+)\]", summary):
        key = match.group(1).strip()
        val = match.group(2).strip()
        # "ok" / "正常" → 1.0, 其他 → 0.0
        mapping[key] = 1.0 if val.lower() in ("ok", "正常", "pass") else 0.0

    # 兼容旧格式
    if "脸" in mapping and "face" not in mapping:
        mapping["face"] = mapping.pop("脸")
    if "手" in mapping and "hand" not in mapping:
        mapping["hand"] = mapping.pop("手")
    if "脚" in mapping and "foot" not in mapping:
        mapping["foot"] = mapping.pop("脚")
    if "模糊" in mapping and "blur" not in mapping:
        mapping["blur"] = mapping.pop("模糊")

    return mapping


# ── 审核 CRUD ───────────────────────────────────────────


def load_review(output_dir: str) -> dict[str, Any]:
    """加载 review.json，不存在则返回空结构。"""
    path = Path(output_dir) / REVIEW_FILE
    if path.is_file():
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return {"version": "1.0", "output_dir": output_dir, "images": []}


def save_review(output_dir: str, data: dict[str, Any]) -> None:
    """保存 review.json。"""
    data["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    path = Path(output_dir) / REVIEW_FILE
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[review] 已保存审核记录: {path}")


def get_review_index(images: list[dict[str, Any]], output_dir: str) -> dict[str, dict[str, Any]]:
    """构建 path → 审核记录 的查找表。"""
    review = load_review(output_dir)
    index: dict[str, dict[str, Any]] = {}
    for entry in review.get("images", []):
        p = entry.get("path", "")
        if p:
            index[p] = entry
    return index


def apply_verdict(
    output_dir: str,
    image_path: str,
    verdict: str,
    tags: list[str] | None = None,
    comment: str = "",
) -> dict[str, Any]:
    """对某张图片设置审核判决。

    Args:
        output_dir: 输出目录
        image_path: 图片相对路径（如 "portrait/gallery/candidate_00.png"）
        verdict: 判决（keep/delete/favorite/retry）
        tags: 标签列表
        comment: 备注

    Returns:
        更新后的审核记录条目
    """
    if verdict not in VERDICTS:
        raise ValueError(f"无效判决: {verdict}, 可选: {VERDICTS}")

    review = load_review(output_dir)
    img_list = review.setdefault("images", [])

    # 查找或创建
    entry = None
    for e in img_list:
        if e.get("path") == image_path:
            entry = e
            break

    if entry is None:
        entry = {"path": image_path}
        img_list.append(entry)

    entry["verdict"] = verdict
    entry["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    if tags:
        entry["tags"] = tags
    if comment:
        entry["comment"] = comment

    # 如果是删除，物理移动文件到 _trash/
    if verdict == VERDICT_DELETE:
        _move_to_trash(output_dir, image_path)

    save_review(output_dir, review)
    return entry


def _move_to_trash(output_dir: str, image_path: str) -> bool:
    """将图片移动到 _trash/ 目录。"""
    src = Path(output_dir) / image_path
    if not src.is_file():
        return False

    trash = Path(output_dir) / TRASH_DIR
    trash.mkdir(parents=True, exist_ok=True)

    # 保持目录结构，避免重名
    safe_name = image_path.replace("/", "_").replace("\\", "_")
    dst = trash / safe_name

    # 如果已存在，加时间戳
    if dst.exists():
        stamp = datetime.now().strftime("%H%M%S")
        dst = trash / f"{stamp}_{safe_name}"

    shutil.move(str(src), str(dst))
    print(f"[review] 已移至 trash: {image_path} → {dst.name}")
    return True


# ── 审核报告 ────────────────────────────────────────────


def generate_report(output_dir: str) -> dict[str, Any]:
    """生成审核统计报告。"""
    images = scan_output(output_dir)
    review = load_review(output_dir)
    review_index = {e["path"]: e for e in review.get("images", [])}

    total = len(images)
    reviewed = 0
    verdicts: dict[str, int] = {}
    tags: dict[str, int] = {}

    for img in images:
        entry = review_index.get(img["path"])
        if entry and entry.get("verdict"):
            reviewed += 1
            v = entry["verdict"]
            verdicts[v] = verdicts.get(v, 0) + 1
            for t in entry.get("tags", []):
                tags[t] = tags.get(t, 0) + 1

    # 也统计已物理删除但 review.json 还有记录的图片
    scanned_paths = {img["path"] for img in images}
    deleted_from_review = 0
    for entry in review.get("images", []):
        if entry.get("verdict") == VERDICT_DELETE and entry.get("path") not in scanned_paths:
            reviewed += 1
            deleted_from_review += 1
            verdicts[VERDICT_DELETE] = verdicts.get(VERDICT_DELETE, 0) + 1
            for t in entry.get("tags", []):
                tags[t] = tags.get(t, 0) + 1

    trashed = len(list((Path(output_dir) / TRASH_DIR).glob("*"))) if (Path(output_dir) / TRASH_DIR).is_dir() else 0

    return {
        "total": total + deleted_from_review,
        "reviewed": reviewed,
        "pending": total + deleted_from_review - reviewed,
        "trashed": trashed,
        "verdicts": verdicts,
        "tags": tags,
    }

def print_report(report: dict[str, Any]) -> None:
    """打印审核报告到控制台。"""
    print(f"\n📋 审核报告")
    print(f"{'='*40}")
    print(f"  总张数: {report['total']}")
    print(f"  已审核: {report['reviewed']}/{report['total']}")
    print(f"  待审核: {report['pending']}")
    print(f"  已删除: {report['trashed']} (移至 _trash/)")
    if report["verdicts"]:
        print(f"\n  判决分布:")
        for v, c in sorted(report["verdicts"].items()):
            icon = {"keep": "✅", "delete": "❌", "favorite": "⭐", "retry": "🔄"}.get(v, "❓")
            print(f"    {icon} {v}: {c}")
    if report["tags"]:
        print(f"\n  标签统计:")
        for t, c in sorted(report["tags"].items(), key=lambda x: -x[1]):
            print(f"    #{t}: {c}")
    print(f"{'='*40}")
