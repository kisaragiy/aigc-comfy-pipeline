# -*- coding: utf-8 -*-
"""成本追踪测试（G8）：record/summarize/坏行容错/CLI"""
import json
import os
import pytest
from pathlib import Path

import workshop.cost_tracker as ct


@pytest.fixture
def tmp_cost(monkeypatch, tmp_path):
    """把成本日志指向临时文件"""
    log = tmp_path / "cost_log.jsonl"
    monkeypatch.setattr(ct, "COST_LOG", log)
    return log


def test_record_creates_jsonl(tmp_cost):
    """record 写入 JSONL 一行"""
    n = ct.record_generation(engine="flux", seed=42, elapsed_sec=12.5,
                             retries=1, score=0.8, vlm_score=7.5, passed=True)
    assert n == 1
    lines = tmp_cost.read_text(encoding="utf-8").strip().split("\n")
    row = json.loads(lines[0])
    assert row["engine"] == "flux"
    assert row["seed"] == 42
    assert row["elapsed_sec"] == 12.5
    assert row["retries"] == 1
    assert row["passed"] is True
    assert "date" in row and "ts" in row


def test_record_appends(tmp_cost):
    """多次 record 追加不覆盖"""
    ct.record_generation(engine="sdxl", elapsed_sec=5.0)
    ct.record_generation(engine="flux", elapsed_sec=8.0)
    lines = tmp_cost.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2


def test_summarize_aggregates(tmp_cost):
    """summarize 汇总统计正确"""
    ct.record_generation(engine="flux", elapsed_sec=10.0, passed=True, score=0.9)
    ct.record_generation(engine="flux", elapsed_sec=20.0, passed=False, score=0.3)
    ct.record_generation(engine="sdxl", elapsed_sec=30.0, passed=True, score=0.7)
    s = ct.summarize()
    assert s["total"] == 3
    assert s["passed"] == 2
    assert s["passed_rate"] == pytest.approx(0.67, abs=0.01)
    assert s["total_sec"] == pytest.approx(60.0)
    assert s["avg_sec"] == pytest.approx(20.0)
    assert s["by_engine"]["flux"]["count"] == 2
    assert s["by_engine"]["sdxl"]["count"] == 1
    assert s["by_engine"]["flux"]["avg_sec"] == pytest.approx(15.0)


def test_summarize_empty(tmp_cost):
    """无记录 → 空统计不崩"""
    s = ct.summarize()
    assert s["total"] == 0
    assert s["by_engine"] == {}


def test_bad_lines_skipped(tmp_cost):
    """坏行跳过不崩（日志不因脏数据崩掉）"""
    tmp_cost.write_text('{"engine": "flux", "passed": true}\nNOT_JSON_LINE\n{"engine": "sdxl", "passed": false}\n',
                        encoding="utf-8")
    s = ct.summarize()
    assert s["total"] == 2


def test_extra_fields(tmp_cost):
    """extra 字段写入（简单类型）"""
    ct.record_generation(engine="video", elapsed_sec=60.0, extra={"frames": 49, "size": "848x480"})
    row = json.loads(tmp_cost.read_text(encoding="utf-8").strip())
    assert row["frames"] == 49
    assert row["size"] == "848x480"


def test_days_filter(tmp_cost):
    """days 过滤（旧记录排除）"""
    ct.record_generation(engine="flux", elapsed_sec=1.0)
    # 手写一行旧日期
    with open(tmp_cost, "a", encoding="utf-8") as f:
        f.write(json.dumps({"engine": "old", "date": "2020-01-01", "passed": False,
                            "elapsed_sec": 999.0}) + "\n")
    s = ct.summarize(days=7)
    assert s["total"] == 1
    all_s = ct.summarize()
    assert all_s["total"] == 2


def test_cli_help(tmp_path, monkeypatch):
    """CLI --json 输出可解析"""
    log = tmp_path / "cost_log.jsonl"
    monkeypatch.setattr(ct, "COST_LOG", log)
    ct.record_generation(engine="flux", elapsed_sec=3.0, passed=True)
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = ct.main(["--json"])
    assert rc == 0
    data = json.loads(buf.getvalue())
    assert data["total"] == 1


def test_format_report_empty(tmp_cost):
    """空账报表提示语"""
    assert "暂无生成成本记录" in ct.format_report(ct.summarize())