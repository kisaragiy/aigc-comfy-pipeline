"""测试 output_manager.py 的核心函数。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))


class TestSaveAndList:
    def test_save_run(self, temp_output_dir, monkeypatch):
        monkeypatch.setenv("AIGC_OUTPUT_DIR", str(temp_output_dir))
        from output_manager import save_run, list_runs

        img_file = temp_output_dir / "images" / "test.png"
        img_file.parent.mkdir(parents=True)
        img_file.write_text("fake png")

        run_id = save_run("test", [str(img_file)], {"prompt": "hello", "seed": 42})
        assert run_id is not None
        assert "test" in run_id

        runs = list_runs()
        assert len(runs) == 1
        assert runs[0]["command"] == "test"
        assert runs[0]["params"]["prompt"] == "hello"
        assert runs[0]["params"]["seed"] == 42

    def test_clean_runs(self, temp_output_dir, monkeypatch):
        monkeypatch.setenv("AIGC_OUTPUT_DIR", str(temp_output_dir))
        from output_manager import clean_runs, save_run

        img_file = temp_output_dir / "images" / "t.png"
        img_file.parent.mkdir(parents=True)
        img_file.write_text("x")

        save_run("test", [str(img_file)], {})

        n = clean_runs(days=0)
        assert isinstance(n, int)

    def test_list_empty(self, temp_output_dir, monkeypatch):
        monkeypatch.setenv("AIGC_OUTPUT_DIR", str(temp_output_dir))
        from output_manager import list_runs

        assert list_runs() == []


class TestSaveWorkflowOutputs:
    def test_dry_run_returns_none(self, monkeypatch):
        from output_manager import save_workflow_outputs

        result = save_workflow_outputs("dry-run", "http://test", "test")
        assert result is None
