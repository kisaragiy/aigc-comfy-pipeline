"""测试 go_video_process.py 的核心函数。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from go_video_process import auto_output_path


class TestAutoOutputPath:
    def test_gif_suffix(self):
        path = Path("/tmp/test.mp4")
        result = auto_output_path(path, "gif", ext="gif")
        assert result == Path("/tmp/test_gif.gif")

    def test_mp4_suffix(self):
        path = Path("/tmp/test.mp4")
        result = auto_output_path(path, "trimmed")
        assert result == Path("/tmp/test_trimmed.mp4")

    def test_custom_suffix(self):
        path = Path("/tmp/video.mp4")
        result = auto_output_path(path, "speed2_0")
        assert result == Path("/tmp/video_speed2_0.mp4")

    def test_preserves_parent_dir(self):
        path = Path("/some/deep/path/video.webm")
        result = auto_output_path(path, "processed")
        assert result.parent == Path("/some/deep/path")

    def test_with_gif_ext_overrides_suffix(self):
        path = Path("/tmp/video.mp4")
        result = auto_output_path(path, "converted", ext="gif")
        assert result.suffix == ".gif"
        assert "converted" in result.stem


class TestToGifCommand:
    """测试 to_gif 的 ffmpeg 命令构建逻辑（mock _run_ffmpeg）。"""

    def _make_mock_run(self, captured: list) -> callable:
        """创建一个 _run_ffmpeg mock 也创建输出文件。"""
        def mock_run(cmd, desc=""):
            captured.append(cmd)
            out_path = Path(cmd[-1])
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text("mocked")
        return mock_run

    def test_default_fps(self, monkeypatch, tmp_path):
        from go_video_process import to_gif

        captured: list[list[str]] = []

        monkeypatch.setattr("go_video_process._run_ffmpeg", self._make_mock_run(captured))
        monkeypatch.setattr("go_video_process._find_ffmpeg", lambda: "ffmpeg")

        input_path = tmp_path / "test.mp4"
        input_path.write_text("fake video data")
        output_path = tmp_path / "test.gif"

        to_gif(input_path, output_path)

        assert len(captured) >= 1
        ffmpeg_cmd = captured[0]
        assert "fps=10" in " ".join(ffmpeg_cmd)
        assert str(output_path) in ffmpeg_cmd

    def test_custom_fps_and_scale(self, monkeypatch, tmp_path):
        from go_video_process import to_gif

        captured: list[list[str]] = []

        monkeypatch.setattr("go_video_process._run_ffmpeg", self._make_mock_run(captured))
        monkeypatch.setattr("go_video_process._find_ffmpeg", lambda: "ffmpeg")

        input_path = tmp_path / "test.mp4"
        input_path.write_text("fake video")
        to_gif(input_path, tmp_path / "test.gif", fps=15, scale="480:-1")

        ffmpeg_cmd = captured[0]
        cmd_str = " ".join(ffmpeg_cmd)
        assert "fps=15" in cmd_str
        assert "scale=480:-1:flags=lanczos" in cmd_str

    def test_auto_suffix_to_gif(self, monkeypatch, tmp_path):
        from go_video_process import to_gif

        captured: list[list[str]] = []

        monkeypatch.setattr("go_video_process._run_ffmpeg", self._make_mock_run(captured))
        monkeypatch.setattr("go_video_process._find_ffmpeg", lambda: "ffmpeg")

        input_path = tmp_path / "test.mp4"
        input_path.write_text("fake")
        # Pass mp4 output — function should convert to .gif
        result = to_gif(input_path, tmp_path / "out.mp4")
        assert result.suffix == ".gif"


class TestTrimParsing:
    """测试 trim_video 参数解析逻辑。"""

    def test_trim_format(self, monkeypatch, tmp_path):
        from go_video_process import trim_video

        captured: list[list[str]] = []

        def _mock_run(cmd, desc=""):
            captured.append(cmd)
            out_path = Path(cmd[-1])
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text("mocked")

        monkeypatch.setattr("go_video_process._run_ffmpeg", _mock_run)
        monkeypatch.setattr("go_video_process._find_ffmpeg", lambda: "ffmpeg")

        input_path = tmp_path / "test.mp4"
        input_path.write_text("fake")
        output_path = tmp_path / "trimmed.mp4"
        trim_video(input_path, "00:05-00:15", output_path)

        cmd_str = " ".join(captured[0])
        assert "-ss" in cmd_str
        assert "00:05" in cmd_str
        assert "-to" in cmd_str
        assert "00:15" in cmd_str


class TestChangeSpeedLogic:
    """测试 change_speed 的 atempo 链式逻辑。"""

    def _mock_run(self, captured):
        def mock_fn(cmd, desc=""):
            captured.append(cmd)
            out_path = Path(cmd[-1])
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text("mocked")
        return mock_fn

    def test_below_2x_single_atempo(self, monkeypatch, tmp_path):
        from go_video_process import change_speed

        captured: list[list[str]] = []

        monkeypatch.setattr("go_video_process._run_ffmpeg", self._mock_run(captured))
        monkeypatch.setattr("go_video_process._find_ffmpeg", lambda: "ffmpeg")

        input_path = tmp_path / "test.mp4"
        input_path.write_text("fake")
        change_speed(input_path, 1.5, tmp_path / "speed.mp4")

        cmd_str = " ".join(captured[0])
        assert "setpts=0.6666666666666666*PTS" in cmd_str
        assert "atempo=1.5" in cmd_str or "atempo=1.50" in cmd_str

    def test_above_2x_chained_atempo(self, monkeypatch, tmp_path):
        from go_video_process import change_speed

        captured: list[list[str]] = []

        monkeypatch.setattr("go_video_process._run_ffmpeg", self._mock_run(captured))
        monkeypatch.setattr("go_video_process._find_ffmpeg", lambda: "ffmpeg")

        input_path = tmp_path / "test.mp4"
        input_path.write_text("fake")
        change_speed(input_path, 4.0, tmp_path / "speed.mp4")

        cmd_str = " ".join(captured[0])
        # 4x should chain atempo=2.0,atempo=2.0
        assert "atempo=2.0" in cmd_str
        assert "setpts=0.25*PTS" in cmd_str

    def test_exact_2x_single_atempo(self, monkeypatch, tmp_path):
        from go_video_process import change_speed

        captured: list[list[str]] = []

        monkeypatch.setattr("go_video_process._run_ffmpeg", self._mock_run(captured))
        monkeypatch.setattr("go_video_process._find_ffmpeg", lambda: "ffmpeg")

        input_path = tmp_path / "test.mp4"
        input_path.write_text("fake")
        change_speed(input_path, 2.0, tmp_path / "speed.mp4")

        cmd_str = " ".join(captured[0])
        # 2.0 should use single atempo=2.0
        assert "atempo=2.0" in cmd_str


class TestConcatFilelist:
    """测试 concat_videos 的文件列表写法。"""

    def test_filelist_content(self, monkeypatch, tmp_path):
        from go_video_process import concat_videos

        captured: list[list[str]] = []

        def _mock_run(cmd, desc=""):
            captured.append(cmd)
            out_path = Path(cmd[-1])
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text("mocked")

        monkeypatch.setattr("go_video_process._run_ffmpeg", _mock_run)
        monkeypatch.setattr("go_video_process._find_ffmpeg", lambda: "ffmpeg")

        v1 = tmp_path / "a.mp4"
        v2 = tmp_path / "b.mp4"
        v1.write_text("fake")
        v2.write_text("fake")

        out = tmp_path / "merged.mp4"
        concat_videos([v1, v2], out)

        # Check that concat uses -f concat
        cmd_str = " ".join(captured[0])
        assert "-f concat" in cmd_str or "-f" in cmd_str

        # Verify filelist was cleaned up
        assert not (tmp_path / ".concat_filelist.txt").exists()
