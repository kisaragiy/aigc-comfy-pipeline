"""测试人工审核系统核心逻辑。"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from workshop.review import (
    VERDICT_KEEP,
    VERDICT_DELETE,
    VERDICT_FAVORITE,
    VERDICT_RETRY,
    _parse_inspect_summary,
    apply_verdict,
    generate_report,
    load_review,
    save_review,
    scan_output,
)


# ── Fixtures ────────────────────────────────────────────


@pytest.fixture
def demo_dir(tmp_path: Path) -> Path:
    """创建模拟 demo 输出目录。"""
    scenes = {
        "portrait": "近景肖像",
        "halfbody": "半身动作",
    }

    candidates_data = [
        {"seed": 100, "score": 0.85, "inspect_overall": 0.9,
         "inspect_summary": "[脸:ok] [手:ok] [脚:ok] [模糊:正常]"},
        {"seed": 101, "score": 0.65, "inspect_overall": 0.7,
         "inspect_summary": "[脸:ok] [手:崩了] [脚:ok] [模糊:正常]"},
    ]

    for scene_id, scene_title in scenes.items():
        scene_dir = tmp_path / scene_id
        scene_dir.mkdir(parents=True)
        gallery_dir = scene_dir / "gallery"
        gallery_dir.mkdir()

        # metadata.json
        meta = {
            "scene_id": scene_id,
            "scene_title": scene_title,
            "candidates": candidates_data,
        }
        with open(scene_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        # gallery images
        for idx in range(len(candidates_data)):
            (gallery_dir / f"candidate_{idx:02d}.png").write_text(f"fake_image_{scene_id}_{idx}")

        # best.png
        (scene_dir / "best.png").write_text(f"fake_best_{scene_id}")

    return tmp_path


# ── Tests ────────────────────────────────────────────────


class TestParseInspectSummary:
    def test_ok_all(self):
        result = _parse_inspect_summary("[脸:ok] [手:ok] [脚:ok] [模糊:正常]")
        assert result["face"] == 1.0
        assert result["hand"] == 1.0
        assert result["foot"] == 1.0
        assert result["blur"] == 1.0

    def test_partial_fail(self):
        result = _parse_inspect_summary("[脸:ok] [手:崩了] [脚:异常] [模糊:正常]")
        assert result["face"] == 1.0
        assert result["hand"] == 0.0
        assert result["foot"] == 0.0
        assert result["blur"] == 1.0

    def test_empty(self):
        assert _parse_inspect_summary("") == {}

    def test_mixed_keys(self):
        """兼容中文和英文键名。"""
        result = _parse_inspect_summary("[脸:ok] [左眼:ok] [右眼:ok] [手:ok] [脚:ok] [模糊:正常]")
        assert "face" in result
        assert "hand" in result
        assert "foot" in result
        assert "blur" in result


class TestScanOutput:
    def test_scans_all_images(self, demo_dir: Path):
        images = scan_output(str(demo_dir))
        # 2 scenes × 2 candidates + 2 best = 6 images
        assert len(images) == 6

    def test_image_metadata(self, demo_dir: Path):
        images = scan_output(str(demo_dir))
        # Filter by scene + candidate_00
        portrait_0 = [i for i in images if i["scene_id"] == "portrait" and "candidate_00" in i["path"]]
        assert len(portrait_0) == 1
        img = portrait_0[0]
        assert img["scene_id"] == "portrait"
        assert img["seed"] == 100
        assert img["auto_score"] == 0.85

    def test_best_detected(self, demo_dir: Path):
        images = scan_output(str(demo_dir))
        bests = [i for i in images if i["is_best"]]
        assert len(bests) == 2  # one per scene

    def test_not_a_directory(self):
        with pytest.raises(NotADirectoryError):
            scan_output("/nonexistent")


class TestReviewCRUD:
    def test_save_and_load(self, demo_dir: Path):
        data = {"version": "1.0", "output_dir": str(demo_dir), "images": []}
        save_review(str(demo_dir), data)
        loaded = load_review(str(demo_dir))
        assert loaded["version"] == "1.0"
        assert loaded["images"] == []

    def test_load_empty(self, tmp_path: Path):
        loaded = load_review(str(tmp_path))
        assert loaded["version"] == "1.0"
        assert loaded["images"] == []

    def test_apply_and_persist(self, demo_dir: Path):
        apply_verdict(
            str(demo_dir),
            "portrait/gallery/candidate_00.png",
            VERDICT_FAVORITE,
            tags=["表情好"],
            comment="面试候选",
        )

        # Verify in saved review.json
        review = load_review(str(demo_dir))
        assert len(review["images"]) == 1
        entry = review["images"][0]
        assert entry["path"] == "portrait/gallery/candidate_00.png"
        assert entry["verdict"] == VERDICT_FAVORITE
        assert entry["tags"] == ["表情好"]
        assert entry["comment"] == "面试候选"
        assert "reviewed_at" in entry

    def test_delete_moves_to_trash(self, demo_dir: Path):
        candidate_path = "portrait/gallery/candidate_00.png"
        abs_path = demo_dir / candidate_path
        assert abs_path.is_file()

        apply_verdict(str(demo_dir), candidate_path, VERDICT_DELETE)

        # Original gone
        assert not abs_path.is_file()
        # Moved to trash
        trash = demo_dir / "_trash"
        assert trash.is_dir()
        trash_files = list(trash.iterdir())
        assert len(trash_files) == 1

    def test_invalid_verdict(self, demo_dir: Path):
        with pytest.raises(ValueError, match="无效判决"):
            apply_verdict(str(demo_dir), "test.png", "invalid")


class TestReport:
    def test_empty_report(self, demo_dir: Path):
        report = generate_report(str(demo_dir))
        assert report["total"] == 6
        assert report["reviewed"] == 0
        assert report["pending"] == 6
        assert report["trashed"] == 0

    def test_report_with_reviews(self, demo_dir: Path):
        # Apply some verdicts
        apply_verdict(str(demo_dir), "portrait/gallery/candidate_00.png", VERDICT_FAVORITE)
        apply_verdict(str(demo_dir), "portrait/gallery/candidate_01.png", VERDICT_DELETE)
        apply_verdict(str(demo_dir), "halfbody/gallery/candidate_00.png", VERDICT_KEEP)

        report = generate_report(str(demo_dir))
        # total includes the deleted file (counted from review.json)
        assert report["total"] == 6
        assert report["reviewed"] == 3
        assert report["pending"] == 3
        assert report["trashed"] == 1  # delete moved to trash
        assert report["verdicts"].get(VERDICT_FAVORITE) == 1
        assert report["verdicts"].get(VERDICT_DELETE) == 1
        assert report["verdicts"].get(VERDICT_KEEP) == 1
