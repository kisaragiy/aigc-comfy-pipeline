"""测试 go_sweep.py 的视频路由和对比页面生成。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from go_sweep import _get_build_fn, build_sweep_label, expand_grid


class TestGetBuildFn:
    """测试 _get_build_fn 路由逻辑。"""

    def test_video_type_returns_callable(self):
        fn = _get_build_fn("video")
        assert callable(fn)

    def test_image_type_returns_callable(self):
        fn = _get_build_fn("image")
        assert callable(fn)

    def test_video_fn_is_build_video_workflow(self):
        fn = _get_build_fn("video")
        import go_video
        assert fn is go_video.build_video_workflow

    def test_image_fn_is_build_flux_workflow(self):
        fn = _get_build_fn("image")
        import go_flux
        assert fn is go_flux.build_flux_workflow

    def test_cached_after_first_call(self):
        # Clear cache first
        from go_sweep import _BUILD_FUNCTIONS
        _BUILD_FUNCTIONS.clear()

        fn1 = _get_build_fn("video")
        fn2 = _get_build_fn("video")
        assert fn1 is fn2  # same object from cache


class TestExpandGridForVideo:
    """扩展 expand_grid 测试，验证参数展开正确。"""

    def test_video_params(self):
        grid = {"frames": [25, 49], "fps": [8, 15]}
        result = expand_grid(grid)
        assert len(result) == 4
        assert {"frames": 25, "fps": 8} in result
        assert {"frames": 49, "fps": 15} in result

    def test_mixed_image_video_params(self):
        grid = {"steps": [20, 30], "frames": [49]}
        result = expand_grid(grid)
        assert len(result) == 2
        for combo in result:
            assert "steps" in combo
            assert "frames" in combo


class TestBuildSweepLabelVideo:
    """测试视频参数生成的标签。"""

    def test_video_specific_params(self):
        label = build_sweep_label({"frames": 49, "fps": 15, "steps": 30})
        assert "frames49" in label
        assert "fps15" in label
        assert "steps30" in label

    def test_denoise_in_label(self):
        label = build_sweep_label({"denoise": 0.85, "sampler": "euler"})
        assert "denoise0.85" in label
        assert "samplereuler" in label
