"""测试 go_sweep 的核心函数。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from go_sweep import expand_grid, build_sweep_label


class TestExpandGrid:
    def test_single_key(self):
        grid = {"steps": [20, 30]}
        result = expand_grid(grid)
        assert len(result) == 2
        assert result == [{"steps": 20}, {"steps": 30}]

    def test_multi_key(self):
        grid = {"steps": [20, 30], "cfg": [1.0, 2.0]}
        result = expand_grid(grid)
        assert len(result) == 4
        assert {"steps": 20, "cfg": 1.0} in result
        assert {"steps": 30, "cfg": 2.0} in result

    def test_empty(self):
        assert expand_grid({}) == [{}]

    def test_single_value_lists(self):
        grid = {"steps": [20], "cfg": [1.0]}
        assert len(expand_grid(grid)) == 1

    def test_three_params(self):
        grid = {"a": [1, 2], "b": [3, 4], "c": [5]}
        assert len(expand_grid(grid)) == 4  # 2*2*1


class TestBuildSweepLabel:
    def test_single_param(self):
        assert build_sweep_label({"steps": 20}) == "steps20"

    def test_multi_param(self):
        label = build_sweep_label({"steps": 20, "cfg": 1.0})
        assert "steps20" in label
        assert "cfg1.0" in label

    def test_int_and_float(self):
        label = build_sweep_label({"seed": 42, "cfg": 1.5})
        assert "seed42" in label
        assert "cfg1.5" in label
