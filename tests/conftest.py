"""pytest 共享夹具。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def sample_workflow_api() -> dict[str, Any]:
    """一个简单的 API 格式 workflow 样本。"""
    return {
        "3": {"class_type": "KSampler", "inputs": {
            "seed": 42, "steps": 20, "cfg": 7.0,
            "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
            "model": ["12", 0], "positive": ["6", 0],
            "negative": ["7", 0], "latent_image": ["5", 0]}},
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {
            "ckpt_name": "sd_xl_base.safetensors"}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {
            "width": 1024, "height": 1024, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {
            "text": "a cat", "clip": ["12", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {
            "text": "blurry", "clip": ["12", 1]}},
        "8": {"class_type": "VAEDecode", "inputs": {
            "samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {
            "images": ["8", 0], "filename_prefix": "test"}},
        "12": {"class_type": "LoraLoader", "inputs": {
            "model": ["4", 0], "clip": ["4", 1],
            "lora_name": "my_lora.safetensors",
            "strength_model": 0.8, "strength_clip": 0.8}},
    }


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """临时产出目录。"""
    return tmp_path / "outputs"
