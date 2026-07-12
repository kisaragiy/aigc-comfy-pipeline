"""测试 workflow_manager.py 的核心函数。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from workflow_manager import extract_schema, show_graph
from workflow_manager import _CONTROLLABLE_KEYWORDS


class TestExtractSchema:
    def test_has_prompt(self, sample_workflow_api):
        schema = extract_schema(sample_workflow_api)
        assert schema["has_prompt"] is True
        assert schema["has_seed"] is True
        assert schema["has_steps"] is True
        assert schema["has_cfg"] is True
        assert schema["has_lora"] is True
        assert schema["has_checkpoint"] is True
        assert schema["parameter_count"] >= 10
        assert schema["node_count"] == 8

    def test_class_types(self, sample_workflow_api):
        schema = extract_schema(sample_workflow_api)
        assert "KSampler" in schema["class_types"]
        assert "CheckpointLoaderSimple" in schema["class_types"]
        assert "LoraLoader" in schema["class_types"]

    def test_empty_workflow(self):
        schema = extract_schema({})
        assert schema["parameter_count"] == 0
        assert schema["has_prompt"] is False
        assert schema["node_count"] == 0


class TestShowGraph:
    def test_shows_connections(self, sample_workflow_api):
        graph = show_graph(sample_workflow_api)
        assert "[12] LoraLoader" in graph
        assert "model" in graph  # references another node

    def test_empty(self):
        assert show_graph({}) == ""


class TestControllableKeywords:
    def test_all_keywords_mapped(self):
        assert "text" in _CONTROLLABLE_KEYWORDS
        assert "seed" in _CONTROLLABLE_KEYWORDS
        assert "steps" in _CONTROLLABLE_KEYWORDS
        assert "cfg" in _CONTROLLABLE_KEYWORDS
        assert "ckpt_name" in _CONTROLLABLE_KEYWORDS
        assert "lora_name" in _CONTROLLABLE_KEYWORDS
