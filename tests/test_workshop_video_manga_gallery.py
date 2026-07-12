"""测试 workshop.video（预览模式）+ workshop.manga gallery。"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agents"))

from workshop.manga import generate_manga_gallery


# ── generate_manga_gallery ──────────────────────────────

class TestGenerateMangaGallery:
    def test_basic_gallery(self):
        """最基本的画廊生成（1 面板 + 无拼页 + 无角色）。"""
        with tempfile.TemporaryDirectory() as tmp:
            # 创建占位面板图
            panel_png = Path(tmp) / "panel_00.png"
            panel_png.write_text("fake-png")
            meta = {
                "脚本": "test script",
                "角色": {},
                "风格": "anime",
                "layout": "auto",
                "逐格图": {"S01": str(panel_png)},
            }
            result = generate_manga_gallery(
                output_dir=tmp,
                meta=meta,
                panel_paths={"S01": str(panel_png)},
                assembled_path=None,
            )
            assert result.endswith("gallery.html")
            html = Path(result).read_text(encoding="utf-8")
            assert "漫画画廊" in html
            assert "test script" in html
            assert "panel_00.png" in html
            assert "S01" in html
            assert "anime" in html

    def test_with_assembled(self):
        """包含拼页图。"""
        with tempfile.TemporaryDirectory() as tmp:
            panel = Path(tmp) / "p.png"
            panel.write_text("fake")
            assembled = Path(tmp) / "manga_page.png"
            assembled.write_text("fake-assembled")
            meta = {"脚本": "x", "角色": {}, "风格": "anime", "layout": "auto", "逐格图": {"S01": str(panel)}}
            result = generate_manga_gallery(
                output_dir=tmp, meta=meta,
                panel_paths={"S01": str(panel)},
                assembled_path=str(assembled),
            )
            html = Path(result).read_text(encoding="utf-8")
            assert "manga_page.png" in html
            assert "拼页" in html

    def test_with_characters(self):
        """包含角色信息。"""
        with tempfile.TemporaryDirectory() as tmp:
            panel = Path(tmp) / "p.png"
            panel.write_text("fake")
            meta = {
                "脚本": "x",
                "角色": {"Alice": {"服饰": "红裙", "发型": "长发", "特征": "蓝瞳"}},
                "风格": "anime",
                "layout": "auto",
                "逐格图": {"S01": str(panel)},
            }
            result = generate_manga_gallery(
                output_dir=tmp, meta=meta,
                panel_paths={"S01": str(panel)},
            )
            html = Path(result).read_text(encoding="utf-8")
            assert "Alice" in html
            assert "红裙" in html
            assert "长发" in html
            assert "蓝瞳" in html

    def test_multi_panel(self):
        """多个面板。"""
        with tempfile.TemporaryDirectory() as tmp:
            meta = {"脚本": "x", "角色": {}, "风格": "anime", "layout": "auto", "逐格图": {}}
            panel_paths = {}
            for i in range(3):
                p = Path(tmp) / f"p_{i}.png"
                p.write_text("fake")
                panel_paths[f"S0{i+1}"] = str(p)
            result = generate_manga_gallery(
                output_dir=tmp, meta=meta, panel_paths=panel_paths,
            )
            html = Path(result).read_text(encoding="utf-8")
            assert "共 3 格" in html

    def test_special_chars_script(self):
        """剧本含特殊字符不破坏 HTML。"""
        with tempfile.TemporaryDirectory() as tmp:
            panel = Path(tmp) / "p.png"
            panel.write_text("fake")
            meta = {"脚本": "Alice & Bob > 100", "角色": {}, "风格": "anime", "layout": "auto", "逐格图": {"S01": str(panel)}}
            result = generate_manga_gallery(
                output_dir=tmp, meta=meta, panel_paths={"S01": str(panel)},
            )
            html = Path(result).read_text(encoding="utf-8")
            assert "Alice & Bob" in html  # should not break HTML


# ── workshop video --preview ────────────────────────────

class TestWorkshopVideoPreview:
    """验证 _workshop_video() 的 --preview 模式（通过 --dry-run 模拟预览逻辑）。"""

    def test_preview_output(self):
        """预览模式应打印参数不生成。"""
        from workshop.video import generate_video
        result = generate_video(
            "test prompt", dry_run=True,
            frames=49, fps=15, width=848, height=480,
            steps=30, cfg=7.0, seed=42,
        )
        assert result.get("dry_run") is True
        assert result.get("error") is None

    def test_video_compose_empty(self):
        """空视频列表不应崩溃。"""
        from workshop.video import video_compose
        result = video_compose([], output_path=tempfile.mktemp(suffix=".mp4"))
        assert result == ""  # 无视频文件时返回空字符串
