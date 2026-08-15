# -*- coding: utf-8 -*-
"""商业图细节第三轮：OG/名片/VI/简历头像/促销模板"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_biz_topics_extended():
    """新增 og/card 主题"""
    from workshop.biz import BIZ_TOPICS
    assert "og" in BIZ_TOPICS
    assert "card" in BIZ_TOPICS
    assert BIZ_TOPICS["og"]["size"] == (1200, 630)


def test_vi_function():
    """品牌 VI 全套函数存在"""
    from workshop.biz import brand_vi
    import inspect
    params = inspect.signature(brand_vi).parameters
    assert "brand_desc" in params and "style" in params


def test_resume_flag():
    """简历头像模式"""
    from workshop.biz import main
    import inspect
    assert "resume" in inspect.getsource(main)


def test_biztext_templates():
    """文字模板 default/sale/event"""
    from workshop.biztext import TEMPLATES
    for t in ("default", "sale", "event"):
        assert t in TEMPLATES


def test_biztext_sale_template(tmp_path):
    """促销模板实际输出（价格条）"""
    from workshop.biztext import add_text
    from PIL import Image
    img = Image.new("RGB", (600, 400), (60, 40, 80))
    src = tmp_path / "s.png"
    img.save(src)
    out = tmp_path / "o.png"
    add_text(str(src), "夏季大促", sub="全场五折起", template="sale",
             price_text="¥199", date_text="8月18日-31日", output=str(out))
    assert os.path.exists(out)
    r = Image.open(out)
    assert r.size == (600, 400)


def test_biztext_invalid_template(tmp_path):
    """非法模板报错"""
    from workshop.biztext import add_text
    from PIL import Image
    img = Image.new("RGB", (50, 50))
    src = tmp_path / "s.png"
    img.save(src)
    with pytest.raises(ValueError):
        add_text(str(src), "标题", template="nope")


def test_biztext_event_center(tmp_path):
    """event 模板居中"""
    from workshop.biztext import add_text
    from PIL import Image
    img = Image.new("RGB", (400, 400), (30, 30, 30))
    src = tmp_path / "s.png"
    img.save(src)
    out = tmp_path / "o.png"
    add_text(str(src), "开发者大会", sub="2026 秋季", template="event",
             output=str(out))
    assert os.path.exists(out)
