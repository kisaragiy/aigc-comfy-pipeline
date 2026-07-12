"""测试 run.py — 参数映射 + 模式路由。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---- 辅助: 构造 args ----

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "agents"))


def _make_args(**overrides: dict) -> argparse.Namespace:
    """构造标准 args，覆盖默认值。"""
    defaults = dict(
        prompt="test",
        raw=False,
        video=False,
        ref=None,
        model="9b",
        lora=None,
        lora_strength=1.0,
        prefix="flux_klein",
        negative=None,
        seed=-1,
        steps=None,
        cfg=None,
        width=None,
        height=None,
        sampler=None,
        scheduler=None,
        preset=None,
        timeout=None,
        frames=None,
        fps=None,
        denoise=None,
        min_score=0.0,
        retry=0,
        no_validate=False,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class TestBuildImageKwargs:
    """_build_image_kwargs 参数映射测试。"""

    def _import(self):
        from run import _build_image_kwargs
        return _build_image_kwargs

    def test_basic_params(self):
        """steps/cfg/width/height/sampler/scheduler 透传。"""
        args = _make_args(steps=28, cfg=6.5, width=896, height=1152,
                          sampler="euler", scheduler="normal")
        kw = self._import()(args)
        assert kw["steps"] == 28
        assert kw["cfg"] == 6.5
        assert kw["width"] == 896
        assert kw["height"] == 1152
        assert kw["sampler"] == "euler"
        assert kw["scheduler"] == "normal"

    def test_negative_mapped(self):
        """negative → negative_prompt。"""
        args = _make_args(negative="bad quality")
        kw = self._import()(args)
        assert kw["negative_prompt"] == "bad quality"

    def test_negative_default_empty(self):
        """negative 未设时为空字符串。"""
        args = _make_args()
        kw = self._import()(args)
        assert kw["negative_prompt"] == ""

    def test_lora_mapped(self):
        """lora → lora_name。"""
        args = _make_args(lora="my_lora.safetensors")
        kw = self._import()(args)
        assert kw["lora_name"] == "my_lora.safetensors"

    def test_model_mapped(self):
        """model → model_variant。"""
        args = _make_args(model="4b")
        kw = self._import()(args)
        assert kw["model_variant"] == "4b"

    def test_prefix_mapped(self):
        """prefix → filename_prefix。"""
        args = _make_args(prefix="custom_prefix")
        kw = self._import()(args)
        assert kw["filename_prefix"] == "custom_prefix"

    def test_lora_strength(self):
        """lora_strength 透传。"""
        args = _make_args(lora="test.safetensors", lora_strength=0.85)
        kw = self._import()(args)
        assert kw["lora_strength"] == 0.85

    def test_empty_args_core_keys(self):
        """基础 key 集合。"""
        args = _make_args()
        kw = self._import()(args)
        assert "negative_prompt" in kw
        assert "lora_strength" in kw
        # model="9b" 默认 → model_variant 出现
        assert "model_variant" in kw
        assert kw["model_variant"] == "9b"
        # prefix="flux_klein" 默认 → filename_prefix 出现
        assert "filename_prefix" in kw
        assert kw["filename_prefix"] == "flux_klein"

    def test_lora_adds_lora_name_key(self):
        """设 lora 时多出 lora_name。"""
        args = _make_args(lora="x.safetensors")
        kw = self._import()(args)
        assert "lora_name" in kw

    def test_prefix_adds_filename_prefix_key(self):
        """设 prefix 时多出 filename_prefix。"""
        args = _make_args(prefix="pre")
        kw = self._import()(args)
        assert "filename_prefix" in kw

    def test_model_adds_model_variant_key(self):
        """设 model 时多出 model_variant。"""
        args = _make_args(model="4b")
        kw = self._import()(args)
        assert "model_variant" in kw


class TestBuildVideoKwargs:
    """_build_video_kwargs 参数映射测试。"""

    def _import(self):
        from run import _build_video_kwargs
        return _build_video_kwargs

    def test_basic_params(self):
        """steps/cfg/width/height/seed/sampler/scheduler/frames/fps/denoise 透传。"""
        args = _make_args(steps=30, cfg=6.0, width=640, height=480,
                          seed=42, sampler="dpmpp_2m", scheduler="karras",
                          frames=49, fps=15, denoise=0.85)
        kw = self._import()(args)
        assert kw["steps"] == 30
        assert kw["cfg"] == 6.0
        assert kw["width"] == 640
        assert kw["height"] == 480
        assert kw["seed"] == 42
        assert kw["sampler"] == "dpmpp_2m"
        assert kw["scheduler"] == "karras"
        assert kw["frames"] == 49
        assert kw["fps"] == 15
        assert kw["denoise"] == 0.85

    def test_negative_mapped(self):
        """negative → negative（视频保持原名）。"""
        args = _make_args(negative="bad")
        kw = self._import()(args)
        assert kw["negative"] == "bad"

    def test_ref_mapped(self):
        """ref → ref_image。"""
        args = _make_args(ref="start.png")
        kw = self._import()(args)
        assert kw["ref_image"] == "start.png"

    def test_ref_sets_default_denoise(self):
        """设 ref 时默认 denoise = 0.85（若未显式指定）。"""
        args = _make_args(ref="start.png")
        kw = self._import()(args)
        assert kw["denoise"] == 0.85

    def test_ref_respects_explicit_denoise(self):
        """设 ref 时 denoise 可显式覆盖。"""
        args = _make_args(ref="start.png", denoise=0.9)
        kw = self._import()(args)
        assert kw["denoise"] == 0.9

    def test_timeout_mapped(self):
        """timeout → wait_timeout。"""
        args = _make_args(timeout=600)
        kw = self._import()(args)
        assert kw["wait_timeout"] == 600

    def test_timeout_default(self):
        """未设 timeout 时 wait_timeout = 1800。"""
        args = _make_args()
        kw = self._import()(args)
        assert kw["wait_timeout"] == 1800

    def test_no_validate_present(self):
        """always has no_validate=True。"""
        args = _make_args()
        kw = self._import()(args)
        assert kw["no_validate"] is True

    def test_preset_present(self):
        """always has preset from args。"""
        args = _make_args(preset="cinematic")
        kw = self._import()(args)
        assert kw["preset"] == "cinematic"

    def test_empty_args_core_keys(self):
        """仅必选 key。"""
        args = _make_args()
        kw = self._import()(args)
        assert "no_validate" in kw
        assert "preset" in kw
        assert "wait_timeout" in kw


class TestRunImageMode:
    """_run_image_mode 路由测试。"""

    @patch("run.generate_with_quality")
    @patch("run.optimize_prompt")
    def test_calls_generate_with_quality(self, mock_opt, mock_gwq):
        """调用 generate_with_quality。"""
        mock_opt.return_value = "optimized prompt"
        mock_gwq.return_value = {"prompt_id": "dry-run", "seed": 42, "images": []}

        from run import _run_image_mode
        args = _make_args()
        _run_image_mode("test", args)

        mock_gwq.assert_called_once()
        call_kwargs = mock_gwq.call_args
        # positional: build_flux_workflow, prompt
        assert call_kwargs[0][0].__name__ == "build_flux_workflow"
        assert call_kwargs[0][1] == "optimized prompt"

    @patch("run.optimize_prompt")
    def test_raw_prompt_no_optimize(self, mock_opt):
        """--raw 时跳过 optimize_prompt。"""
        mock_opt.return_value = "should not be used"
        with patch("run.generate_with_quality") as mock_gwq:
            mock_gwq.return_value = {"prompt_id": "dry-run", "seed": 0, "images": []}

            from run import _run_image_mode
            args = _make_args(raw=True)
            _run_image_mode("raw prompt text", args)

            # generate_with_quality 应被传 raw prompt
            assert mock_gwq.call_args[0][1] == "raw prompt text"
            mock_opt.assert_not_called()

    @patch("run.generate_with_quality")
    @patch("run.optimize_prompt")
    def test_negative_forwarded(self, mock_opt, mock_gwq):
        """negative 传给 generate_with_quality。"""
        mock_opt.return_value = "test"
        mock_gwq.return_value = {"prompt_id": "dry-run", "seed": 0, "images": []}

        from run import _run_image_mode
        args = _make_args(negative="bad", raw=True)
        _run_image_mode("test", args)

        _, kwargs = mock_gwq.call_args
        assert kwargs.get("negative_prompt")  # via _build_image_kwargs or passed explicitly

    @patch("run.generate_with_quality")
    @patch("run.optimize_prompt")
    def test_preset_forwarded(self, mock_opt, mock_gwq):
        """preset 传给 generate_with_quality。"""
        mock_opt.return_value = "test"
        mock_gwq.return_value = {"prompt_id": "dry-run", "seed": 0, "images": []}

        from run import _run_image_mode
        args = _make_args(preset="anime", raw=True)
        _run_image_mode("test", args)

        _, kwargs = mock_gwq.call_args
        assert kwargs.get("preset") == "anime"


class TestRunVideoMode:
    """_run_video_mode 路由测试。"""

    @patch("run.generate_with_quality")
    @patch("run.optimize_prompt")
    def test_calls_generate_with_quality(self, mock_opt, mock_gwq):
        """调用 generate_with_quality 并传入 build_video_workflow。"""
        mock_opt.return_value = "optimized prompt"
        mock_gwq.return_value = {"prompt_id": "dry-run", "seed": 42, "images": []}

        from run import _run_video_mode
        args = _make_args()
        _run_video_mode("test", args)

        mock_gwq.assert_called_once()
        call_args = mock_gwq.call_args
        # positional: build_video_workflow, prompt
        assert call_args[0][0].__name__ == "build_video_workflow"
        assert call_args[0][1] == "optimized prompt"

    @patch("run.optimize_prompt")
    def test_ref_forwarded(self, mock_opt):
        """ref 通过 _build_video_kwargs 传下去。"""
        mock_opt.return_value = "test"
        with patch("run.generate_with_quality") as mock_gwq:
            mock_gwq.return_value = {"prompt_id": "dry-run", "seed": 0, "images": []}

            from run import _run_video_mode
            args = _make_args(ref="start.png", raw=True)
            _run_video_mode("test", args)

            _, kwargs = mock_gwq.call_args
            # generate_with_quality 收到 ref 在 **kw 中
            # 检查 _build_video_kwargs 产物中有 ref_image
            assert any(
                k in kwargs for k in ("ref_image", "ref")
            )


@patch("run._run_video_mode")
@patch("run._run_image_mode")
class TestMain:
    """main() 路由测试。"""

    def test_default_routes_to_image(self, mock_image, mock_video):
        """无 --video 时走图片模式。"""
        import run

        with patch.object(run.sys, "argv", ["run", "test_prompt"]):
            run.main()
        mock_image.assert_called_once()
        mock_video.assert_not_called()

    def test_video_flag_routes_to_video(self, mock_image, mock_video):
        """--video 时走视频模式。"""
        import run

        with patch.object(run.sys, "argv", ["run", "--video", "test_prompt"]):
            run.main()
        mock_video.assert_called_once()
        mock_image.assert_not_called()

    def test_ref_flag_routes_to_video(self, mock_image, mock_video):
        """--ref 时走视频模式。"""
        import run

        with patch.object(run.sys, "argv", ["run", "--ref", "img.png", "test_prompt"]):
            run.main()
        mock_video.assert_called_once()
        mock_image.assert_not_called()
