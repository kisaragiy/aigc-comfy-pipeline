# -*- coding: utf-8 -*-
"""One-shot: copy agents + workflows + resize sample images into docs/samples/."""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_AGENTS = Path(r"C:\DrawingLive\agents")
SRC_WF = Path(r"C:\DrawingLive\ComfyUI\user\default\workflows")
SRC_OUT = Path(r"C:\DrawingLive\ComfyUI\output")
DST_AGENTS = ROOT / "agents"
DST_WF = ROOT / "workflows"
DST_SAMPLES = ROOT / "docs" / "samples"

AGENT_FILES = [
    "comfy_utils.py",
    "run.py",
    "go_knives_lora.py",
    "go_knives_ipadapter.py",
    "go_multi_char_lora.py",
    "go_caster_lora.py",
    "run_knives_lora_batch.py",
    "workflow.json",
    "workflow_knives_lora_sdxl.json",
    "workflow_knives_lora_sdxl_ipadapter.json",
    "workflow_multi_char_lora_sdxl.json",
    "workflow_caster_lora_sdxl.json",
]

WORKFLOW_FILES = [
    "workflow_knives_lora_sdxl_ipadapter.json",
    "galgame_heroine_knives_lora_sdxl.json",
    "galgame_heroine_gacha_sdxl.json",
    "workflow_knives_lora_sdxl.json",
]

# (source filename in ComfyUI/output, dest name, caption)
SAMPLES = [
    ("knives_lora_sdxl_00027_.png", "01_sdxl_lora_txt2img.jpg", "SDXL 角色 LoRA 文生图"),
    ("caster_lora_sdxl_00086_.png", "02_sdxl_caster_lora.jpg", "第二角色 LoRA"),
    ("knives_ipa_sdxl_00100_.png", "03_ipadapter_face_lock.jpg", "IPAdapter 参考图锁脸"),
    ("multi_char_lora_sdxl_00001_.png", "04_multi_character.jpg", "双 LoRA 多角色同框"),
    ("gal_heroine_knives_00040_.png", "05_galgame_heroine.jpg", "Galgame 向角色立绘"),
    ("knives_lora_sdxl_batch_01_00001_.png", "06_batch_pipeline.jpg", "批处理出图"),
    ("gal_heroine_knives_00035_.png", "07_pose_variation.jpg", "同角色多姿势"),
    ("caster_lora_sdxl_00085_.png", "08_style_consistency.jpg", "风格一致性"),
    ("knives_ipa_sdxl_00093_.png", "09_ipadapter_series.jpg", "IPAdapter 系列"),
]


def copy_agents():
    DST_AGENTS.mkdir(parents=True, exist_ok=True)
    for name in AGENT_FILES:
        src = SRC_AGENTS / name
        if not src.is_file():
            print(f"skip missing agent file: {name}")
            continue
        shutil.copy2(src, DST_AGENTS / name)
        print(f"agents/{name}")


def copy_workflows():
    DST_WF.mkdir(parents=True, exist_ok=True)
    for name in WORKFLOW_FILES:
        src = SRC_WF / name
        if not src.is_file():
            alt = SRC_AGENTS / name
            src = alt if alt.is_file() else src
        if not src.is_file():
            print(f"skip missing workflow: {name}")
            continue
        shutil.copy2(src, DST_WF / name)
        print(f"workflows/{name}")


def resize_samples():
    try:
        from PIL import Image
    except ImportError:
        print("PIL not found, copying PNG without resize")
        Image = None  # type: ignore

    DST_SAMPLES.mkdir(parents=True, exist_ok=True)
    captions_path = DST_SAMPLES / "captions.txt"
    lines = []

    for src_name, dst_name, caption in SAMPLES:
        src = SRC_OUT / src_name
        if not src.is_file():
            print(f"skip missing sample: {src_name}")
            continue
        dst = DST_SAMPLES / dst_name
        if Image:
            im = Image.open(src).convert("RGB")
            im.thumbnail((960, 1200), Image.Resampling.LANCZOS)
            im.save(dst, format="JPEG", quality=88, optimize=True)
        else:
            shutil.copy2(src, dst.with_suffix(".png"))
        lines.append(f"{dst_name}\t{caption}")
        print(f"docs/samples/{dst_name}")

    captions_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # 3x3 contact sheet for README
    if Image and lines:
        paths = [DST_SAMPLES / ln.split("\t")[0] for ln in lines if (DST_SAMPLES / ln.split("\t")[0]).is_file()]
        if len(paths) >= 9:
            thumbs = [Image.open(p).convert("RGB") for p in paths[:9]]
            w, h = thumbs[0].size
            grid = Image.new("RGB", (w * 3, h * 3), (32, 32, 32))
            for i, t in enumerate(thumbs):
                t = t.resize((w, h), Image.Resampling.LANCZOS)
                grid.paste(t, ((i % 3) * w, (i // 3) * h))
            grid.thumbnail((1400, 1800), Image.Resampling.LANCZOS)
            grid.save(DST_SAMPLES / "00_gallery_grid.jpg", format="JPEG", quality=90, optimize=True)
            print("docs/samples/00_gallery_grid.jpg")


def main():
    if not SRC_AGENTS.is_dir():
        raise SystemExit(f"agents dir not found: {SRC_AGENTS}")
    copy_agents()
    copy_workflows()
    if SRC_OUT.is_dir():
        resize_samples()
    else:
        print(f"warn: ComfyUI output missing: {SRC_OUT}")
    print("done.")


if __name__ == "__main__":
    main()
