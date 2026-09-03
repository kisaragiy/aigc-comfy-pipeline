#!/usr/bin/env python3
"""Koren 小说《幻想着加入北山实验中学学生会》场景出图

从原文提取 6 个高画面感场景，用管线 S1 工位出图（偏好 V4 干净二次元）。
目标：给作者看，激发灵感。

场景来源（全部来自原文，可追溯）：
  S1 学生会初遇望月（第一话）——丁达尔效应/黑长发/白色衬衫/阳光办公室
  S2 空地铁梦境（第四话）——无限车厢/诡异小女孩/及腰长发/束腰连衣裙
  S3 木棉树下睡着的女孩（第五话）——夏末夜晚/蜷缩/高马尾/功能饮料
  S4 天台黄昏（第一话）——班主任抽烟/楼顶围栏/夕阳
  S5 夏末月色校园夜行（第六话）——月光走廊/学生会办公室灯光
  S6 望月人设（多话）——半扎黑长发/校服/庄严少女/学生会

用法:
  python scripts/koren_scenes.py --dry-run
  python scripts/koren_scenes.py [--start 1] [--count 6]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTDIR = ROOT / "outputs" / "koren"
sys.path.insert(0, str(ROOT / "pipeline"))

SCENES = [
    {
        "id": "S1_first_meet",
        "title": "学生会初遇望月",
        "prompt": ("1girl, beautiful serious student council president, long flowing "
                   "black hair, neat white school shirt, sitting at a desk reviewing "
                   "documents with a red pen, dust particles floating in sunlight, "
                   "sunbeam through window, dusty old office room, morning light, "
                   "upper body, dignified expression"),
    },
    {
        "id": "S2_empty_subway",
        "title": "空地铁梦境",
        "prompt": ("1girl, mysterious little girl, waist-length flowing hair, puffy "
                   "waist dress, sitting calmly alone in an empty subway car, "
                   "endless identical train cars stretching into darkness, "
                   "reflection in window glass, surreal dream atmosphere, "
                   "eerie blue light, no other passengers"),
    },
    {
        "id": "S3_tree_girl",
        "title": "木棉树下的女孩",
        "prompt": ("1girl, high ponytail, sleeping curled up under a spiky cottonwood "
                   "tree at night, school uniform, knees hugged, spread hair on lawn, "
                   "an unopened energy drink beside her, dim campus night light, "
                   "single ponytail spread across grass, quiet mysterious atmosphere, "
                   "full body"),
    },
    {
        "id": "S4_rooftop_sunset",
        "title": "天台黄昏",
        "prompt": ("1boy, high school student with tired sharp eyes, leaning on "
                   "rooftop railing at sunset, middle-aged teacher smoking beside him, "
                   "offering a cigarette, golden evening sun low on horizon, "
                   "wind blowing, school rooftop, warm orange sky, dynamic composition"),
    },
    {
        "id": "S5_moonlight_school",
        "title": "夏末月色校园",
        "prompt": ("1girl, beautiful student council president, half-tied long black "
                   "hair, school uniform immaculate, walking across a moonlit school "
                   "courtyard at night, full moon, silver moonlight reflecting on "
                   "corridor railing, late summer atmosphere, quiet and beautiful, "
                   "distant school building lights, full body"),
    },
    {
        "id": "S6_wangyue_portrait",
        "title": "望月人设",
        "prompt": ("1girl, character design sheet style, beautiful aloof student "
                   "council president, half-tied long black hair, neat white school "
                   "shirt, immaculate uniform, cold dignified expression, "
                   "studio background, front view upper body, official character art"),
    },
]


def run_s1(prompt: str, style: str, seed: int, outdir: Path) -> str:
    """调 S1 工位出图，返回输出路径。"""
    cmd = [sys.executable, str(ROOT / "pipeline" / "stages" / "s1_txt2img.py"),
           "--prompt", prompt, "--style", style, "--seed", str(seed),
           "--size", "1024x1024", "--outdir", str(outdir)]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                       env={"PYTHONPATH": "", **__import__("os").environ})
    out = p.stdout + p.stderr
    for line in out.splitlines():
        if "✅ S1 完成" in line and "->" in line:
            return line.split("->")[-1].strip()
    print(f"⚠️ 出图失败: {out[-500:]}")
    return ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--count", type=int, default=6)
    args = ap.parse_args()
    OUTDIR.mkdir(parents=True, exist_ok=True)

    sel = SCENES[args.start - 1: args.start - 1 + args.count]
    if args.dry_run:
        for s in sel:
            print(f"  {s['id']}  {s['title']}  ({len(s['prompt'])} chars)")
        print(f"[dry-run] {len(sel)} 场景 -> {OUTDIR}")
        return

    for i, s in enumerate(sel, args.start):
        print(f"\n═══ [{i}/{len(SCENES)}] {s['id']} {s['title']} ═══")
        dst = run_s1(s["prompt"], "v4", 20260901 + i * 7, OUTDIR)
        if dst:
            print(f"  ✅ -> {dst}")
        else:
            print(f"  ❌ 失败")


if __name__ == "__main__":
    main()
