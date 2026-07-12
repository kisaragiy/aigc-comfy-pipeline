"""测试 model_manager.py 的核心函数。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from model_manager import _extract_model_refs, CATEGORY_DIR_MAP


class TestExtractModelRefs:
    def test_basic_refs(self, sample_workflow_api):
        refs = _extract_model_refs(sample_workflow_api)
        names = [r["value"] for r in refs]
        assert "sd_xl_base.safetensors" in names
        assert "my_lora.safetensors" in names

    def test_empty_workflow(self):
        assert _extract_model_refs({}) == []

    def test_category_mapping(self):
        refs = _extract_model_refs({
            "1": {"class_type": "CLIPLoader", "inputs": {
                "clip_name": "clip.safetensors"}},
        })
        assert len(refs) == 1
        assert refs[0]["category"] == "clip"

    def test_multiple_model_refs(self):
        refs = _extract_model_refs({
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {
                "ckpt_name": "model.safetensors"}},
            "2": {"class_type": "LoraLoader", "inputs": {
                "lora_name": "lora.safetensors",
                "model": ["1", 0], "clip": ["1", 1]}},
            "3": {"class_type": "VAELoader", "inputs": {
                "vae_name": "vae.safetensors"}},
        })
        categories = [r["category"] for r in refs]
        assert "checkpoint" in categories
        assert "lora" in categories
        assert "vae" in categories


class TestCategoryDirMap:
    def test_common_categories(self):
        assert CATEGORY_DIR_MAP["checkpoints"] == "checkpoint"
        assert CATEGORY_DIR_MAP["loras"] == "lora"
        assert CATEGORY_DIR_MAP["vae"] == "vae"
        assert CATEGORY_DIR_MAP["clip"] == "clip"
        assert CATEGORY_DIR_MAP["controlnet"] == "controlnet"
        assert CATEGORY_DIR_MAP["diffusion_models"] == "checkpoint"
