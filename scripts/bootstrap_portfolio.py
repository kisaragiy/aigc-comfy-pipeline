# -*- coding: utf-8 -*-
"""Copy agents + workflows; build SFW portfolio samples (workflow screenshots)."""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_AGENTS = Path(r"C:\DrawingLive\agents")
SRC_WF = Path(r"C:\DrawingLive\ComfyUI\user\default\workflows")
SRC_EXAMPLE = ROOT / "示例"
DST_AGENTS = ROOT / "agents"
DST_WF = ROOT / "workflows"
DST_SAMPLES = ROOT / "docs" / "samples"
DST_ASSETS = ROOT / "docs" / "assets"

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

# 公开展示：仅使用 ComfyUI 节点/workflow 界面截图（不含成图）
SAMPLE_SOURCES = [
    ("workflow_demo_01.jpg", "01_flux_klein_workflow.jpg", "Flux.2 + Klein 身份一致性工作流"),
    ("workflow_demo_02.jpg", "02_multi_node_pipeline.jpg", "多节点 AIGC 管线总览"),
    ("workflow_demo_03.jpg", "03_identity_guidance.jpg", "身份引导 / 单图工作流"),
    ("workflow_demo_04.jpg", "04_img2img_swap.jpg", "图生图 / 局部重绘流程"),
    ("workflow_demo_05.jpg", "05_ipadapter_blend.jpg", "IPAdapter 参考图融合"),
    ("workflow_demo_06.jpg", "06_lora_txt2img_setup.jpg", "SDXL LoRA 文生图节点配置"),
    ("workflow_demo_07.jpg", "07_lora_img2img_setup.jpg", "LoRA + 图生图编排"),
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


def build_assets_from_examples():
    """Compress 示例/*.png into docs/assets (workflow UI screenshots)."""
    try:
        from PIL import Image
    except ImportError:
        return

    if not SRC_EXAMPLE.is_dir():
        return

    DST_ASSETS.mkdir(parents=True, exist_ok=True)
    mapping = []
    for i, src in enumerate(sorted(SRC_EXAMPLE.glob("*.png")), start=1):
        if src.stat().st_size < 5000:
            continue
        dst = DST_ASSETS / f"workflow_demo_{i:02d}.jpg"
        im = Image.open(src).convert("RGB")
        im.thumbnail((1280, 960), Image.Resampling.LANCZOS)
        im.save(dst, format="JPEG", quality=85, optimize=True)
        mapping.append(f"{dst.name}\t{src.name}")
        print(f"docs/assets/{dst.name}")

    if mapping:
        (DST_ASSETS / "sources.txt").write_text("\n".join(mapping) + "\n", encoding="utf-8")


def build_sfw_samples():
    """Portfolio thumbnails = workflow screenshots only."""
    try:
        from PIL import Image
    except ImportError:
        raise SystemExit("Pillow required: pip install pillow")

    build_assets_from_examples()
    DST_SAMPLES.mkdir(parents=True, exist_ok=True)

    # remove old character render samples
    for old in DST_SAMPLES.glob("*.jpg"):
        old.unlink()

    lines = []
    for src_name, dst_name, caption in SAMPLE_SOURCES:
        src = DST_ASSETS / src_name
        if not src.is_file():
            print(f"skip missing asset: {src_name}")
            continue
        dst = DST_SAMPLES / dst_name
        shutil.copy2(src, dst)
        lines.append(f"{dst_name}\t{caption}")
        print(f"docs/samples/{dst_name}")

    (DST_SAMPLES / "captions.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (DST_SAMPLES / "README.txt").write_text(
        "公开展示样张均为 ComfyUI 工作流/节点界面截图，不含成图内容。\n",
        encoding="utf-8",
    )

    paths = [DST_SAMPLES / ln.split("\t")[0] for ln in lines]
    paths = [p for p in paths if p.is_file()]
    if len(paths) >= 4:
        thumbs = [Image.open(p).convert("RGB") for p in paths[:9]]
        n = len(thumbs)
        cols = 3
        rows = (n + cols - 1) // cols
        w, h = thumbs[0].size
        grid = Image.new("RGB", (w * cols, h * rows), (32, 32, 32))
        for i, t in enumerate(thumbs):
            t = t.resize((w, h), Image.Resampling.LANCZOS)
            grid.paste(t, ((i % cols) * w, (i // cols) * h))
        grid.thumbnail((1400, 1200), Image.Resampling.LANCZOS)
        grid.save(DST_SAMPLES / "00_gallery_grid.jpg", format="JPEG", quality=90, optimize=True)
        print("docs/samples/00_gallery_grid.jpg")


def main():
    if not SRC_AGENTS.is_dir():
        raise SystemExit(f"agents dir not found: {SRC_AGENTS}")
    copy_agents()
    copy_workflows()
    build_sfw_samples()
    print("done (SFW workflow-only samples).")


if __name__ == "__main__":
    main()
