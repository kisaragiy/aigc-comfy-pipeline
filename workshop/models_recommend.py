"""workshop models recommend — 按风格推荐最佳模型组合。

用法:
  python -m workshop.models_recommend anime_character
  python -m workshop.models_recommend photoreal
  python -m workshop.models_recommend --list            # 列出所有风格
  python -m workshop.models_recommend --all             # 显示全部模型评分
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REGISTRY_PATH = Path(__file__).resolve().parent.parent / "workshop" / "models" / "registry.json"


def load_registry() -> dict:
    with open(REGISTRY_PATH) as f:
        return json.load(f)


# 风格标签的中文说明
STYLE_LABELS = {
    "anime_character": "动漫角色（原创/同人）",
    "anime_portrait": "动漫头像/半身",
    "anime_fullbody": "动漫全身/站立",
    "photoreal": "写实/照片级",
    "fast_generation": "快速出图",
    "low_vram": "低显存友好",
}


def recommend(style: str, top_k: int = 3) -> list[dict]:
    """按风格推荐模型，返回排序后的列表。"""
    reg = load_registry()
    scored = []
    for name, m in reg.get("models", {}).items():
        scores = m.get("recommended_for", {})
        if not scores:
            continue
        score = scores.get(style, 0)
        if score > 0:
            scored.append({
                "name": name,
                "score": score,
                "base": m.get("base", "?"),
                "size_gb": m.get("size_gb", "?"),
                "notes": m.get("notes", "")[:80],
                "face_detailer": m.get("face_detailer", False),
            })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def list_styles() -> list[str]:
    """列出 registry 中所有有评分记录的风格标签。"""
    reg = load_registry()
    styles: set[str] = set()
    for m in reg.get("models", {}).values():
        styles.update(m.get("recommended_for", {}).keys())
    return sorted(styles)


def show_all() -> list[dict]:
    """显示所有模型在所有风格上的评分。"""
    reg = load_registry()
    rows = []
    for name, m in reg.get("models", {}).items():
        scores = m.get("recommended_for", {})
        if not scores:
            continue
        rows.append({
            "name": name,
            "scores": scores,
            "size_gb": m.get("size_gb", "?"),
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="模型推荐工具")
    parser.add_argument("style", nargs="?", default="", help="风格标签")
    parser.add_argument("--top", type=int, default=3, help="返回前N个推荐")
    parser.add_argument("--list", action="store_true", help="列出所有可用风格")
    parser.add_argument("--all", action="store_true", help="显示全部模型评分")
    args = parser.parse_args()

    if args.list:
        print("可用风格标签:")
        for s in list_styles():
            label = STYLE_LABELS.get(s, s)
            print(f"  {s:25s}  {label}")
        return

    if args.all:
        rows = show_all()
        if not rows:
            print("没有模型评分数据")
            return
        for r in rows:
            scores_str = "  ".join(f"{k}={v}" for k, v in sorted(r["scores"].items()))
            print(f"{r['name']:35s} {r['size_gb']}GB  {scores_str}")
        return

    style = args.style
    if not style:
        parser.print_help()
        return

    results = recommend(style, top_k=args.top)
    if not results:
        print(f"没有找到风格「{style}」的推荐。可用: 使用 --list 查看")
        return

    label = STYLE_LABELS.get(style, style)
    print(f"\n{'=' * 50}")
    print(f"风格: {label}  Top {args.top}")
    print(f"{'=' * 50}")
    for i, r in enumerate(results, 1):
        fd = " ✅FD" if r["face_detailer"] else ""
        print(f"\n  #{i}  {r['name']}")
        print(f"      评分: {r['score']}/10{fd}")
        print(f"      底模: {r['base']}  {r['size_gb']}GB")
        print(f"      说明: {r['notes']}")


if __name__ == "__main__":
    main()
