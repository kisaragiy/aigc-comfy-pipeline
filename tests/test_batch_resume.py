# -*- coding: utf-8 -*-
"""断点续跑（G7）测试：create_batch --resume 跳过已成功条目。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import pytest
from unittest.mock import patch


def _write_batch_file(tmp_path, prompts):
    f = tmp_path / "prompts.txt"
    f.write_text("\n".join(prompts), encoding="utf-8")
    return f


def _write_prev_meta(batch_root, done_texts):
    """模拟上次运行的 batch_metadata.json（部分成功）"""
    prompts = []
    for i, t in enumerate(done_texts, start=1):
        prompts.append({
            "text": t,
            "output_dir": str(batch_root / f"{i:03d}_ok"),
            "best_seed": 42,
            "best_score": 0.8,
            "error": None,
        })
    meta = {"total": len(done_texts), "success": len(done_texts), "fail": 0, "prompts": prompts}
    (batch_root / "batch_metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return prompts


@pytest.fixture
def mock_create_from_nl():
    """mock create_from_nl：记录调用，返回成功结果"""
    calls = []
    def _fake(prompt_text, **kw):
        calls.append(prompt_text)
        return {"best": {"seed": 1, "score": 0.9}, "candidates": [{"seed": 1}], "error": None}
    with patch("workshop.create.create_from_nl", side_effect=_fake) as m:
        m.calls = calls
        yield m, calls


class TestResume:
    def test_resume_skips_done(self, tmp_path, mock_create_from_nl):
        from workshop.create import create_batch
        mock, calls = mock_create_from_nl
        prompts = ["alpha girl", "beta boy", "gamma cat"]
        pf = _write_batch_file(tmp_path, prompts)
        batch_root = tmp_path / "out"
        batch_root.mkdir()
        _write_prev_meta(batch_root, ["alpha girl", "gamma cat"])  # alpha/gamma 已成功

        results = create_batch(str(pf), output_dir=str(batch_root), resume=True)

        # 只应跑 beta boy
        assert calls == ["beta boy"]
        assert len(results) == 1
        assert results[0]["prompt_text"] == "beta boy"

    def test_resume_all_done_no_run(self, tmp_path, mock_create_from_nl):
        from workshop.create import create_batch
        mock, calls = mock_create_from_nl
        prompts = ["alpha girl"]
        pf = _write_batch_file(tmp_path, prompts)
        batch_root = tmp_path / "out"
        batch_root.mkdir()
        _write_prev_meta(batch_root, ["alpha girl"])

        results = create_batch(str(pf), output_dir=str(batch_root), resume=True)

        assert calls == []
        assert results == []

    def test_resume_no_meta_runs_all(self, tmp_path, mock_create_from_nl):
        from workshop.create import create_batch
        mock, calls = mock_create_from_nl
        prompts = ["alpha girl", "beta boy"]
        pf = _write_batch_file(tmp_path, prompts)
        batch_root = tmp_path / "out"
        batch_root.mkdir()

        results = create_batch(str(pf), output_dir=str(batch_root), resume=True)

        assert calls == ["alpha girl", "beta boy"]
        assert len(results) == 2

    def test_resume_merges_metadata(self, tmp_path, mock_create_from_nl):
        from workshop.create import create_batch
        mock, calls = mock_create_from_nl
        prompts = ["alpha girl", "beta boy"]
        pf = _write_batch_file(tmp_path, prompts)
        batch_root = tmp_path / "out"
        batch_root.mkdir()
        _write_prev_meta(batch_root, ["alpha girl"])

        create_batch(str(pf), output_dir=str(batch_root), resume=True)

        # 合并后 metadata 应含 alpha(上次) + beta(本次) = 2 条成功
        meta = json.loads((batch_root / "batch_metadata.json").read_text(encoding="utf-8"))
        assert meta["success"] == 2
        texts = [p["text"] for p in meta["prompts"]]
        assert "alpha girl" in texts
        assert "beta boy" in texts

    def test_no_resume_runs_all(self, tmp_path, mock_create_from_nl):
        from workshop.create import create_batch
        mock, calls = mock_create_from_nl
        prompts = ["alpha girl", "beta boy"]
        pf = _write_batch_file(tmp_path, prompts)
        batch_root = tmp_path / "out"
        batch_root.mkdir()
        _write_prev_meta(batch_root, ["alpha girl"])

        create_batch(str(pf), output_dir=str(batch_root), resume=False)

        # 不带 --resume 照常全跑
        assert calls == ["alpha girl", "beta boy"]
