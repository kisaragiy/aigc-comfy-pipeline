"""测试 comfy_utils.py 的核心函数。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from comfy_utils import (
    comfy_base_url,
    extract_images_from_history,
    wait_images,
    DRY_RUN,
)


class TestComfyBaseUrl:
    def test_strips_prompt(self):
        assert comfy_base_url("http://127.0.0.1:8188/prompt") == "http://127.0.0.1:8188"

    def test_strips_prompt_https(self):
        assert comfy_base_url(
            "https://cloud.comfy.org/prompt"
        ) == "https://cloud.comfy.org"

    def test_default(self):
        url = comfy_base_url()
        assert url.startswith("http")


class TestExtractImagesFromHistory:
    def test_typical_history(self):
        data = {
            "abc": {
                "outputs": {
                    "9": {
                        "images": [
                            {"filename": "out.png", "subfolder": "",
                             "type": "output"},
                        ],
                    },
                },
            },
        }
        imgs = extract_images_from_history(data)
        assert len(imgs) == 1
        assert imgs[0] == ("", "out.png")

    def test_empty_inputs(self):
        assert extract_images_from_history({}) == []
        assert extract_images_from_history(None) == []
        assert extract_images_from_history("not a dict") == []

    def test_missing_outputs(self):
        assert extract_images_from_history({"abc": {}}) == []

    def test_multiple_images(self):
        data = {
            "job1": {
                "outputs": {
                    "9": {"images": [
                        {"filename": "a.png", "subfolder": "", "type": "output"},
                        {"filename": "b.png", "subfolder": "", "type": "output"},
                    ]},
                },
            },
        }
        assert len(extract_images_from_history(data)) == 2


class TestDryRunMode:
    def test_dry_run_variable_exists(self):
        assert DRY_RUN is not None

    def test_wait_images_dry_run(self):
        result = wait_images("dry-run", "http://test")
        assert result == []


class TestCustomPresets:
    """测试自定义预设解析。"""

    def test_parse_preset_definitions(self):
        from comfy_utils import parse_preset_definitions
        result = parse_preset_definitions("my_preset:steps=30,cfg=7.5")
        assert "my_preset" in result
        assert result["my_preset"]["steps"] == 30
        assert result["my_preset"]["cfg"] == 7.5

    def test_parse_multiple_presets(self):
        from comfy_utils import parse_preset_definitions
        result = parse_preset_definitions("a:steps=20;b:steps=40,cfg=8.0")
        assert "a" in result and "b" in result
        assert result["a"]["steps"] == 20
        assert result["b"]["steps"] == 40
        assert result["b"]["cfg"] == 8.0

    def test_parse_string_value(self):
        from comfy_utils import parse_preset_definitions
        result = parse_preset_definitions("p:sampler=euler,scheduler=karras")
        assert result["p"]["sampler"] == "euler"
        assert result["p"]["scheduler"] == "karras"

    def test_parse_empty_skipped(self):
        from comfy_utils import parse_preset_definitions
        result = parse_preset_definitions("a:steps=20;;;b:steps=30")
        assert len(result) == 2

    def test_parse_no_name_skipped(self):
        from comfy_utils import parse_preset_definitions
        result = parse_preset_definitions(":steps=20")
        assert len(result) == 0

    def test_load_preset_file_nonexistent(self):
        from comfy_utils import load_preset_file
        result = load_preset_file("/nonexistent/presets.json")
        assert result == {}
