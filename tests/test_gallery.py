"""测试 go_gallery.py 的海报提取和视频标签生成。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from go_gallery import _get_poster_path, _has_image, _has_video


class TestHasVideo:
    """测试视频检测逻辑。"""

    def test_mp4_detected(self):
        run = {"images": ["output.mp4", "something.png"]}
        assert _has_video(run)

    def test_webm_detected(self):
        run = {"images": ["clip.webm"]}
        assert _has_video(run)

    def test_mov_detected(self):
        run = {"images": ["movie.mov"]}
        assert _has_video(run)

    def test_no_video(self):
        run = {"images": ["img1.png", "img2.jpg"]}
        assert not _has_video(run)

    def test_empty_images(self):
        run = {"images": []}
        assert not _has_video(run)


class TestHasImage:
    """测试图片检测逻辑。"""

    def test_png_image(self):
        run = {"images": ["photo.png"]}
        assert _has_image(run)

    def test_mixed_returns_true(self):
        run = {"images": ["video.mp4", "photo.png"]}
        assert _has_image(run)

    def test_video_only_returns_false(self):
        run = {"images": ["video.mp4"]}
        assert not _has_image(run)


class TestGetPosterPath:
    """测试海报路径生成。"""

    def test_poster_path_mp4(self):
        video = Path("/outputs/run1/images/video.mp4")
        poster = _get_poster_path(video)
        assert poster == Path("/outputs/run1/images/video_poster.jpg")

    def test_poster_path_webm(self):
        video = Path("/outputs/run1/images/clip.webm")
        poster = _get_poster_path(video)
        assert poster.name == "clip_poster.jpg"

    def test_poster_path_mov(self):
        video = Path("/outputs/run1/images/movie.mov")
        poster = _get_poster_path(video)
        assert poster.name == "movie_poster.jpg"
        assert poster.suffix == ".jpg"
