# -*- coding: utf-8 -*-
"""DFS 细节测试：微信表情规范 / 证件照美颜三色 / 封面批量"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_wx_specs_sizes():
    """微信表情上架规格尺寸"""
    from workshop.emotes import WX_SPECS
    assert WX_SPECS["main"] == (240, 240)
    assert WX_SPECS["thumb"] == (120, 120)
    assert WX_SPECS["banner"] == (750, 400)
    assert WX_SPECS["cover"] == (240, 240)
    assert WX_SPECS["artist"] == (750, 750)
    assert WX_SPECS["title"] == (750, 560)


def test_wx_export_produces_files(tmp_path):
    """微信规格导出生成全部 6 类文件"""
    from workshop.emotes import _export_wx_specs
    from PIL import Image
    # 造 2 个表情图
    d = tmp_path / "emotes"
    d.mkdir()
    for name in ("高兴", "生气"):
        img = Image.new("RGBA", (512, 512), (255, 0, 0, 255))
        img.save(d / f"{name}.png")
    emote_images = {"高兴": str(d / "高兴.png"), "生气": str(d / "生气.png")}
    exported = _export_wx_specs(emote_images, tmp_path)
    # 主图 2 + 缩略图 2 + banner + cover + artist + title = 8
    assert len(exported) == 8
    # 验证主图尺寸
    from PIL import Image as I
    main_img = I.open(exported["main_01"])
    assert main_img.size == (240, 240)


def test_idphoto_beauty_flag():
    """idphoto 支持 beauty 和 all_colors"""
    from workshop.idphoto import idphoto
    import inspect
    params = inspect.signature(idphoto).parameters
    assert "beauty" in params
    assert "all_colors" in params


def test_cover_series_flag():
    """cover 支持 series 批量"""
    from workshop.cover import generate_cover
    import inspect
    assert "series" in inspect.signature(generate_cover).parameters


def test_cover_series_returns_list():
    """series=1 也返回 list"""
    # 不实际调 ComfyUI，只验证签名行为（mock 掉内部）
    from workshop import cover
    import unittest.mock as mock
    with mock.patch.object(cover, "_submit", return_value=["f1.png"]), \
         mock.patch.object(cover, "_add_title_zone", return_value="x.png"), \
         mock.patch("os.path.exists", return_value=True), \
         mock.patch("builtins.open", mock.mock_open()):
        r = cover.generate_cover("test", series=1, output="C:/tmp/out.png")
        assert isinstance(r, list)
