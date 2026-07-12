"""测试 go_video.py 预览模式和构建函数。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from go_video import (
    DEFAULT_CFG,
    DEFAULT_FRAMES,
    DEFAULT_FPS,
    DEFAULT_HEIGHT,
    DEFAULT_STEPS,
    DEFAULT_WIDTH,
    PREVIEW_CFG,
    PREVIEW_FRAMES,
    PREVIEW_HEIGHT,
    PREVIEW_STEPS,
    PREVIEW_WIDTH,
    build_video_workflow,
)


class TestPreviewConstants:
    """预览模式常量应正确设置。"""

    def test_preview_frames_lower_than_default(self):
        assert PREVIEW_FRAMES < DEFAULT_FRAMES

    def test_preview_resolution_lower_than_default(self):
        assert PREVIEW_WIDTH < DEFAULT_WIDTH
        assert PREVIEW_HEIGHT < DEFAULT_HEIGHT

    def test_preview_steps_lower_than_default(self):
        assert PREVIEW_STEPS < DEFAULT_STEPS

    def test_preview_cfg_lower_than_default(self):
        assert PREVIEW_CFG < DEFAULT_CFG

    def test_preview_frames_value(self):
        assert PREVIEW_FRAMES == 25

    def test_preview_width_value(self):
        assert PREVIEW_WIDTH == 480

    def test_preview_height_value(self):
        assert PREVIEW_HEIGHT == 270

    def test_preview_steps_value(self):
        assert PREVIEW_STEPS == 15

    def test_preview_cfg_value(self):
        assert PREVIEW_CFG == 5.0

    def test_default_fps_value(self):
        assert DEFAULT_FPS == 15


class TestBuildVideoWorkflow:
    """测试视频工作流构建函数。"""

    def test_returns_tuple(self):
        wf, seed = build_video_workflow("a cat walking", seed=42)
        assert isinstance(wf, dict)
        assert isinstance(seed, int)

    def test_seed_auto_generates(self):
        wf, seed = build_video_workflow("test", seed=-1)
        assert isinstance(seed, int)
        assert seed > 0  # random seed

    def test_seed_passed_through(self):
        wf, seed = build_video_workflow("test", seed=12345)
        assert seed == 12345

    def test_workflow_contains_required_nodes(self):
        wf, _ = build_video_workflow("a cat walking")
        required = {"1", "2", "3a", "3b", "4", "5", "6", "8"}
        for node_id in required:
            assert node_id in wf, f"缺少节点 {node_id}"

    def test_workflow_uses_wan_models(self):
        wf, _ = build_video_workflow("test")
        assert "wan2.2_ti2v_5B_fp16.safetensors" in str(wf)

    def test_i2v_mode_uses_load_image(self):
        wf, _ = build_video_workflow("test", ref_image="start.png")
        assert "load_ref" in wf
        assert wf["load_ref"]["class_type"] == "LoadImage"

    def test_t2v_mode_uses_empty_latent(self):
        wf, _ = build_video_workflow("test")
        assert "7" in wf
        assert wf["7"]["class_type"] == "EmptyLatentVideo"

    def test_i2v_mode_no_empty_latent(self):
        wf, _ = build_video_workflow("test", ref_image="ref.png")
        assert "7" not in wf  # no EmptyLatentVideo in I2V

    def test_ksampler_params(self):
        wf, seed = build_video_workflow("test", seed=42, steps=25, cfg=5.0)
        ks = wf["5"]
        assert ks["inputs"]["seed"] == 42
        assert ks["inputs"]["steps"] == 25
        assert ks["inputs"]["cfg"] == 5.0

    def test_sampler_scheduler_passed(self):
        wf, _ = build_video_workflow("test", sampler="dpmpp_2m", scheduler="karras")
        ks = wf["5"]
        assert ks["inputs"]["sampler_name"] == "dpmpp_2m"
        assert ks["inputs"]["scheduler"] == "karras"

    def test_video_combine_has_fps(self):
        wf, _ = build_video_workflow("test", fps=15)
        vc = wf["8"]
        assert vc["inputs"]["frame_rate"] == 15

    def test_prefix_custom(self):
        wf, _ = build_video_workflow("test", prefix="my_video")
        vc = wf["8"]
        assert vc["inputs"]["filename_prefix"] == "my_video"

    def test_denoise_t2v_is_1(self):
        """T2V 模式下 denoise=1.0 固定。"""
        wf, _ = build_video_workflow("test", denoise=0.85)
        ks = wf["5"]
        # 在 T2V 模式下，denoise 传 1.0，但 build 函数不修改
        # 实际调用在 main 中强制 1.0 — 这里仅验证 build 传参正确
        assert ks["inputs"]["denoise"] == 0.85

    def test_negative_prompt(self):
        wf, _ = build_video_workflow("test", negative="blurry")
        assert "blurry" in str(wf["3b"])
