"""测试 workshop.create — _maybe_save_output, _generate_gallery_html 等纯函数。"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agents"))

from workshop.create import _maybe_save_output, _generate_gallery_html, _summarize_inspect


# ── _summarize_inspect ──────────────────────────────────

class TestSummarizeInspect:
    def test_empty(self):
        assert _summarize_inspect({}) == {}

    def test_full(self):
        ins = {
            "status": "ok",
            "summary": "face ok",
            "scores": {"overall": 0.85, "face": 0.9},
            "parts": {"脸": {"status": "ok"}},
        }
        s = _summarize_inspect(ins)
        assert s["status"] == "ok"
        assert s["summary"] == "face ok"
        assert s["overall"] == 0.85
        # 不应包含原始嵌套数据
        assert "parts" not in s
        assert "scores" not in s


# ── _maybe_save_output ──────────────────────────────────

class TestMaybeSaveOutput:
    def _sample_result(self) -> dict:
        return {
            "prompt": "a girl in classroom",
            "negative_prompt": "blurry",
            "best": {
                "seed": 42,
                "score": 0.85,
                "image": "",
                "inspect": {"status": "ok", "summary": "all good", "scores": {"overall": 0.9}},
            },
            "candidates": [
                {
                    "seed": 42,
                    "score": 0.85,
                    "retries": 0,
                    "inspect": {"status": "ok", "summary": "face ok", "scores": {"overall": 0.88}},
                },
                {
                    "seed": 43,
                    "score": 0.72,
                    "retries": 1,
                    "inspect": {"status": "issues_found", "summary": "blurry", "scores": {"overall": 0.45}},
                },
                {
                    "seed": 44,
                    "score": -1,
                    "retries": 0,
                    "error": "ComfyUI timeout",
                    "inspect": {"status": "error", "error": "ComfyUI timeout"},
                },
            ],
        }

    def test_saves_metadata_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._sample_result()
            _maybe_save_output(result, tmp)

            meta_path = Path(tmp) / "metadata.json"
            assert meta_path.is_file()

            meta = json.loads(meta_path.read_text(encoding="utf-8"))

        # 顶层字段
        assert meta["prompt"] == "a girl in classroom"
        assert meta["negative_prompt"] == "blurry"
        assert meta["candidates_count"] == 3
        assert "version" in meta
        assert "created_at" in meta

    def test_best_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._sample_result()
            _maybe_save_output(result, tmp)
            meta = json.loads((Path(tmp) / "metadata.json").read_text(encoding="utf-8"))

        best = meta["best"]
        assert best["seed"] == 42
        assert best["score"] == 0.85
        assert best["image_relative"] == ""  # 无图片时不复制
        assert best["inspect"]["status"] == "ok"

    def test_candidates_per_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._sample_result()
            _maybe_save_output(result, tmp)
            meta = json.loads((Path(tmp) / "metadata.json").read_text(encoding="utf-8"))

        cands = meta["candidates"]
        assert len(cands) == 3

        # 第一个候选
        assert cands[0]["seed"] == 42
        assert cands[0]["score"] == 0.85
        assert cands[0]["retries"] == 0
        assert cands[0]["inspect_overall"] > 0.8
        assert cands[0]["inspect_status"] == "ok"

        # 第三个候选（失败）
        assert cands[2]["error"] == "ComfyUI timeout"
        assert cands[2]["inspect_status"] == "error"

    def test_extra_meta(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._sample_result()
            extra = {"engine_detection": {"style": "anime", "composition": "close-up"}}
            _maybe_save_output(result, tmp, extra_meta=extra)
            meta = json.loads((Path(tmp) / "metadata.json").read_text(encoding="utf-8"))

        assert "engine_detection" in meta
        assert meta["engine_detection"]["style"] == "anime"

    def test_no_output_dir(self):
        """output_dir 为 None 时静默跳过。"""
        _maybe_save_output({}, None)  # 不应抛出异常

    def test_empty_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            _maybe_save_output({"prompt": "x", "best": {}, "candidates": []}, tmp)
            meta = json.loads((Path(tmp) / "metadata.json").read_text(encoding="utf-8"))
        assert meta["candidates_count"] == 0
        assert meta["candidates"] == []


# ── _generate_gallery_html ──────────────────────────────

class TestGenerateGalleryHtml:
    def _sample_result(self) -> dict:
        return {
            "prompt": "a girl in classroom",
            "negative_prompt": "blurry, bad hands",
            "best": {
                "seed": 42,
                "score": 0.85,
                "image": "",
                "inspect": {"status": "ok", "summary": "all good", "scores": {"overall": 0.9}},
            },
            "candidates": [
                {
                    "seed": 42,
                    "score": 0.85,
                    "retries": 0,
                    "image": "",
                    "inspect": {"status": "ok", "summary": "face ok", "scores": {"overall": 0.88}},
                },
                {
                    "seed": 43,
                    "score": 0.72,
                    "retries": 1,
                    "image": "",
                    "inspect": {"status": "ok", "summary": "fine", "scores": {"overall": 0.65}},
                },
            ],
        }

    def test_generates_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._sample_result()
            path = _generate_gallery_html(result, tmp)
            assert Path(path).is_file()
            html = Path(path).read_text(encoding="utf-8")

        # 基础结构
        assert "<!DOCTYPE html>" in html
        assert "创作工坊 · Gallery" in html
        assert "a girl in classroom" in html
        assert "</html>" in html

    def test_negative_prompt_in_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._sample_result()
            path = _generate_gallery_html(result, tmp)
            html = Path(path).read_text(encoding="utf-8")

        assert "blurry, bad hands" in html
        assert "负向" in html

    def test_engine_detection_optional(self):
        """引擎推测信息非必需，未提供时不报错。"""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._sample_result()
            path = _generate_gallery_html(result, tmp)
            html = Path(path).read_text(encoding="utf-8")
        # 无 engine_detection 时 engine_html 为空，不显示引擎区块
        # CSS 中 .engine 类存在但不影响显示，检查内容中不含"风格:"（引擎区特有）
        assert "风格:" not in html

    def test_engine_detection_shown(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._sample_result()
            result["engine_detection"] = {
                "style": "anime",
                "composition": "close-up shot",
                "lighting": "soft",
                "auto_negative": "",
            }
            path = _generate_gallery_html(result, tmp)
            html = Path(path).read_text(encoding="utf-8")

        assert "风格:" in html
        assert "anime" in html
        assert "close-up" in html  # 前 30 字
        assert "soft" in html

    def test_sort_note_in_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._sample_result()
            path = _generate_gallery_html(result, tmp)
            html = Path(path).read_text(encoding="utf-8")

        assert "已排序" in html

    def test_per_candidate_rank(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._sample_result()
            path = _generate_gallery_html(result, tmp)
            html = Path(path).read_text(encoding="utf-8")

        # 候选应有 #1, #2 排名（即使图片不存在，错误占位也显示排名）
        assert "#1" in html and "#2" in html

    def test_best_badge(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._sample_result()
            result["best"]["image"] = result["candidates"][0]["image"]  # 让第一个候选成为最优
            path = _generate_gallery_html(result, tmp)
            html = Path(path).read_text(encoding="utf-8")

        assert "最优" in html

    def test_no_negative_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._sample_result()
            result["negative_prompt"] = ""
            path = _generate_gallery_html(result, tmp)
            html = Path(path).read_text(encoding="utf-8")

        assert "负向" not in html  # 无负向时不显示区块
        assert "a girl in classroom" in html  # prompt 仍显示

    def test_parts_displayed(self):
        """质检逐部位分数应在 gallery 中显示。"""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._sample_result()
            # 创建真实候选图让 gallery 渲染卡片而非错误占位
            for i, c in enumerate(result["candidates"]):
                img_path = Path(tmp) / f"candidate_{i}.png"
                img_path.write_text("fake-png")
                c["image"] = str(img_path)
                # 添加逐部位分
                c["inspect"]["scores"]["脸"] = 1.0
                c["inspect"]["scores"]["手"] = 0.2
            result["candidates"][1]["inspect"]["scores"]["模糊"] = 1.0
            result["candidates"][1]["inspect"]["scores"]["左眼"] = 0.5
            # 让最优指向一个真实的图
            result["best"]["image"] = result["candidates"][0]["image"]

            path = _generate_gallery_html(result, tmp)
            html = Path(path).read_text(encoding="utf-8")

        assert "Face" in html
        assert "Hand" in html
        assert "Blur" in html
        # 分数字符出现
        assert "1.0" in html
        assert "0.2" in html

    def test_gallery_keyboard_nav_js_array(self):
        """Gallery HTML 包含键盘导航所需的 JS images 数组。"""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._sample_result()
            for i, c in enumerate(result["candidates"]):
                img_path = Path(tmp) / f"candidate_{i}.png"
                img_path.write_text("fake-png")
                c["image"] = str(img_path)
            result["best"]["image"] = result["candidates"][0]["image"]
            path = _generate_gallery_html(result, tmp)
            html = Path(path).read_text(encoding="utf-8")
        assert "var images = [" in html
        assert "candidate_00.png" in html
        assert "candidate_01.png" in html

    def test_gallery_openmodal_uses_index(self):
        """卡片 onclick 使用 openModal(N) 而非 openModal(this.src)。"""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._sample_result()
            for i, c in enumerate(result["candidates"]):
                img_path = Path(tmp) / f"candidate_{i}.png"
                img_path.write_text("fake-png")
                c["image"] = str(img_path)
            result["best"]["image"] = result["candidates"][0]["image"]
            path = _generate_gallery_html(result, tmp)
            html = Path(path).read_text(encoding="utf-8")
        assert "openModal(0)" in html or "openModal(1)" in html
        assert "openModal(this.src)" not in html

    def test_gallery_keyboard_handlers(self):
        """Gallery 包含键盘事件处理代码。"""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._sample_result()
            for i, c in enumerate(result["candidates"]):
                img_path = Path(tmp) / f"candidate_{i}.png"
                img_path.write_text("fake-png")
                c["image"] = str(img_path)
            result["best"]["image"] = result["candidates"][0]["image"]
            path = _generate_gallery_html(result, tmp)
            html = Path(path).read_text(encoding="utf-8")
        assert "ArrowLeft" in html
        assert "ArrowRight" in html
        assert "Escape" in html
        assert "keydown" in html
        assert "modal-counter" in html
        assert "currentIdx" in html

    def test_gallery_download_button(self):
        """Gallery Lightbox 包含下载按钮。"""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._sample_result()
            for i, c in enumerate(result["candidates"]):
                img_path = Path(tmp) / f"candidate_{i}.png"
                img_path.write_text("fake-png")
                c["image"] = str(img_path)
            result["best"]["image"] = result["candidates"][0]["image"]
            path = _generate_gallery_html(result, tmp)
            html = Path(path).read_text(encoding="utf-8")
        assert "#modal-dl" in html
        assert "updateDownload" in html
        assert "download" in html
        assert "⬇" in html

    def test_gallery_close_all_click(self):
        """点击 modal 背景（非图片区域）关闭 Lightbox。"""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._sample_result()
            for i, c in enumerate(result["candidates"]):
                img_path = Path(tmp) / f"candidate_{i}.png"
                img_path.write_text("fake-png")
                c["image"] = str(img_path)
            result["best"]["image"] = result["candidates"][0]["image"]
            path = _generate_gallery_html(result, tmp)
            html = Path(path).read_text(encoding="utf-8")
        assert "closeModal" in html
        assert "function closeModal" in html


# ── create_from_nl --clean ───────────────────────────

class TestCreateClean:
    """测试 create_from_nl 的 --clean 参数。"""

    def test_clean_parameter_accepted(self):
        """create_from_nl 接受 clean 参数（非 integration 验证）。"""
        from workshop.create import create_from_nl
        import inspect
        sig = inspect.signature(create_from_nl)
        assert "clean" in sig.parameters
        assert sig.parameters["clean"].default is False

    def test_clean_removes_files(self):
        """clean=True 时删除输出目录中的旧文件。"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            # 创建旧文件
            (Path(tmp) / "old.png").write_text("old")
            (Path(tmp) / "old.json").write_text('{"old": true}')
            (Path(tmp) / "old.html").write_text("<html/>")
            (Path(tmp) / "keep.txt").write_text("keep")  # 不受影响
            # 清理至少调用了目录删除逻辑（dry_run 模式会走 cleanup 但后续失败）
            # 直接测试清理逻辑本身
            from workshop.create import create_from_nl
            # dry_run=True 跳过了 ComfyUI 检查，但 cleanup 在 prompt 生成前执行
            result = create_from_nl(
                "test",
                clean=True,
                output_dir=tmp,
                dry_run=True,
            )
            # cleanup 删除了旧文件，dry_run 模式不生成新文件
            assert not (Path(tmp) / "old.png").is_file()
            assert not (Path(tmp) / "old.json").is_file()
            assert not (Path(tmp) / "old.html").is_file()
            assert (Path(tmp) / "keep.txt").is_file()  # 不受影响

    def test_clean_removes_gallery_subdir(self):
        """clean=True 时删除 gallery 子目录。"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            gal = Path(tmp) / "gallery"
            gal.mkdir()
            (gal / "index.html").write_text("gallery")
            (gal / "candidate_00.png").write_text("img")

            from workshop.create import create_from_nl
            create_from_nl(
                "test",
                clean=True,
                output_dir=tmp,
                dry_run=True,
            )
            assert not gal.is_dir()
