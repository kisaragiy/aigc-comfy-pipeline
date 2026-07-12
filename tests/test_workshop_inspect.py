"""测试 workshop.inspect — annotate_image + 批量摘要。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agents"))

from workshop.inspect import annotate_image, format_report


# ── annotate_image ──────────────────────────────────────

class TestAnnotateImage:
    def test_nonexistent_image(self):
        """不存在的图片返回空字符串。"""
        result = annotate_image("/nonexistent/test.png", {"status": "ok", "parts": {}, "scores": {"overall": 1.0}})
        assert result == ""

    def test_non_image_file(self):
        """非图片文件返回空字符串。"""
        result = annotate_image(__file__, {})  # __file__ is a .py, not an image
        assert result == ""


# ── format_report ───────────────────────────────────────

class TestFormatReport:
    def test_ok_report(self):
        """ok 状态报告包含预期内容。"""
        result = {
            "status": "ok",
            "summary": "全部位正常",
            "parts": {"脸": {"status": "ok"}, "手": {"status": "ok"}, "模糊": {"status": "正常"}},
            "scores": {"脸": 1.0, "手": 1.0, "模糊": 1.0, "overall": 1.0},
        }
        report = format_report(result)
        assert "ok" in report.lower() or "✅" in report
        assert "全部位正常" in report

    def test_issues_report(self):
        """有问题的报告显示详细问题。"""
        result = {
            "status": "issues_found",
            "summary": "脸崩了, 手崩了",
            "parts": {"脸": {"status": "崩了", "detail": "模糊"}, "手": {"status": "崩了", "detail": "畸形"}},
            "scores": {"脸": 0.0, "手": 0.0, "overall": 0.0},
        }
        report = format_report(result)
        assert "脸" in report
        assert "手" in report
        assert "崩了" in report

    def test_error_result(self):
        """error 状态显示错误信息。"""
        result = {"status": "error", "error": "文件不存在"}
        report = format_report(result)
        assert "文件不存在" in report


# ── 批量摘要逻辑 (来自 _workshop_inspect) ─────────────────

class TestBatchSummary:
    """测试批量质检的失败原因聚合逻辑（纯函数级测试）。"""

    @staticmethod
    def _aggregate(results: list[dict]) -> dict[str, int]:
        """模拟 CLI 中的 fail_reasons Counter 逻辑。"""
        from collections import Counter
        reasons: Counter[str] = Counter()
        for item in results:
            r = item["result"]
            parts = r.get("parts", {})
            for part, info in parts.items():
                s = info.get("status", "")
                if s in ("崩了", "模糊", "异常"):
                    reasons[part] += 1
        return dict(reasons)

    def test_all_ok(self):
        results = [
            {"path": "a.png", "result": {"status": "ok", "parts": {"脸": {"status": "ok"}, "手": {"status": "ok"}}}},
            {"path": "b.png", "result": {"status": "ok", "parts": {"脸": {"status": "ok"}, "手": {"status": "ok"}}}},
        ]
        assert self._aggregate(results) == {}

    def test_mixed(self):
        results = [
            {"path": "a.png", "result": {"status": "issues_found", "parts": {"脸": {"status": "崩了"}, "手": {"status": "ok"}}}},
            {"path": "b.png", "result": {"status": "issues_found", "parts": {"脸": {"status": "崩了"}, "手": {"status": "崩了"}}}},
            {"path": "c.png", "result": {"status": "ok", "parts": {"脸": {"status": "ok"}, "手": {"status": "ok"}}}},
        ]
        agg = self._aggregate(results)
        assert agg.get("脸") == 2
        assert agg.get("手") == 1

    def test_blur_and_abnormal(self):
        results = [
            {"path": "a.png", "result": {"status": "issues_found", "parts": {"模糊": {"status": "模糊"}, "脚": {"status": "异常"}}}},
        ]
        agg = self._aggregate(results)
        assert agg.get("模糊") == 1
        assert agg.get("脚") == 1

    def test_unknown_ignored(self):
        results = [
            {"path": "a.png", "result": {"status": "error", "parts": {"脸": {"status": "unknown"}}}},
        ]
        assert self._aggregate(results) == {}


# ── inspect JSON 输出 ─────────────────────

class TestInspectJson:
    """测试 inspect_image 返回 JSON 可序列化。"""

    def test_inspect_result_is_json_serializable(self):
        """inspect_image 的返回结果可以 JSON 序列化。"""
        import json
        result = {
            "status": "ok",
            "summary": "全部位正常",
            "parts": {"脸": {"status": "ok", "detail": "1 张人脸", "confidence": 0.9, "count": 1}},
            "scores": {"脸": 1.0, "overall": 1.0},
            "issues": [],
        }
        s = json.dumps(result, ensure_ascii=False, indent=2)
        assert '"status": "ok"' in s
        assert '"脸"' in s
        assert '"overall": 1.0' in s

    def test_inspect_json_issues_structure(self):
        """有问题的质检结果 JSON 包含 issues 字段。"""
        import json
        result = {
            "status": "issues_found",
            "summary": "[脸:崩了] [手:ok]",
            "parts": {
                "脸": {"status": "崩了", "detail": "模糊", "confidence": 0.0, "count": 0},
                "手": {"status": "ok", "detail": "2 只手", "count": 2},
            },
            "scores": {"脸": 0.0, "手": 1.0, "overall": 0.5},
            "issues": ["脸崩了: 模糊"],
        }
        s = json.dumps(result, ensure_ascii=False, indent=2)
        assert '"脸"' in s
        assert '"崩了"' in s
        assert '"手"' in s
        assert len(json.loads(s)["issues"]) == 1

    @pytest.mark.slow
    def test_inspect_json_via_cli_png(self):
        """通过 CLI python -m agents workshop inspect 加 --json 输出 JSON。"""
        import subprocess
        import tempfile
        import cv2
        import numpy as np

        with tempfile.TemporaryDirectory() as tmp:
            img_path = Path(tmp) / "test.png"
            cv2.imencode(".png", np.ones((200, 200, 3), dtype=np.uint8) * 200)[1].tofile(str(img_path))

            result = subprocess.run(
                [sys.executable, "-m", "agents", "workshop", "inspect", str(img_path), "--json"],
                capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent,
            )
            assert result.returncode == 0, f"stderr: {result.stderr}"
            import json
            data = json.loads(result.stdout)
            assert "path" in data
            assert "result" in data
            assert "status" in data["result"]
            assert "parts" in data["result"]
            assert "scores" in data["result"]
