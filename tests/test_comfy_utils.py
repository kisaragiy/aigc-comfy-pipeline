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
