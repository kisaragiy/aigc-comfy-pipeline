# -*- coding: utf-8 -*-
"""E1 逐批续写机制测试（业界对齐 AI Comic Factory predictNextPanels）"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workshop.manga.manga import _ollama_generate_storyboard_batch, _parse_storyboard_lines

CHARS = {"Alice": {"服饰": "白裙", "发型": "金发", "特征": "蓝瞳"}, "Bob": {"服饰": "黑西装", "发型": "黑发", "特征": "眼镜"}}


def test_parse_storyboard_lines_basic():
    """CSV-like 解析基础"""
    text = """镜号|人物|场景|景别|音频提示|画面描述|台词|备注
S01|Alice|教室|全景|脚步声|Alice 走进教室||"""
    shots = _parse_storyboard_lines(text)
    assert len(shots) == 1
    assert shots[0]["镜号"] == "S01"
    assert shots[0]["人物"] == "Alice"
    assert shots[0]["景别"] == "全景"


def test_parse_storyboard_lines_ignores_header():
    """表头行应被跳过"""
    text = "镜号|人物|场景|景别|音频提示|画面描述|台词|备注\nS01|Alice|教室|全景||Alice 走进教室||\nS02|Bob|教室|中景||Bob 回头||"
    shots = _parse_storyboard_lines(text)
    assert len(shots) == 2
    assert shots[0]["镜号"] == "S01"
    assert shots[1]["镜号"] == "S02"


def test_parse_storyboard_lines_invalid_skipped():
    """无效行（<6 列）应跳过"""
    text = "垃圾行\nS01|Alice|教室|全景||Alice||"
    shots = _parse_storyboard_lines(text)
    assert len(shots) == 1


def test_batch_continuation_renumbers(monkeypatch):
    """逐批续写应重编号（LLM 输出 S1-S2，第二轮应接 S3）"""
    calls = []

    def fake_ollama(prompt, **kw):
        calls.append(prompt)
        if len(calls) == 1:
            # 第一轮：输出 2 格
            return "S01|Alice|教室|全景||Alice 走进教室||\nS02|Bob|教室|中景||Bob 回头||"
        # 第二轮：LLM 可能会输出乱序/错号，但我们要重编号
        return "S99|Alice|走廊|特写||Alice 微笑||\nS05|Bob|走廊|近景||Bob 跟上||"

    monkeypatch.setattr("agents.comfy_utils.ollama_generate", fake_ollama)
    shots = _ollama_generate_storyboard_batch(
        "校园故事", CHARS, batch_size=2, max_shots=4
    )
    assert len(shots) == 4
    nums = [s["镜号"] for s in shots]
    assert nums == ["S01", "S02", "S03", "S04"], f"重编号失败: {nums}"


def test_batch_continuation_feeds_existing(monkeypatch):
    """第二轮 prompt 应包含已有分镜 JSON（业界核心：喂回已有面板）"""
    prompts = []

    def fake_ollama(prompt, **kw):
        prompts.append(prompt)
        if len(prompts) == 1:
            return "S01|Alice|教室|全景||Alice 走进教室||\nS02|Bob|教室|中景||Bob 回头||"
        return "S03|Alice|走廊|特写||Alice 微笑||"

    monkeypatch.setattr("agents.comfy_utils.ollama_generate", fake_ollama)
    _ollama_generate_storyboard_batch("校园故事", CHARS, batch_size=2, max_shots=3)
    assert len(prompts) == 2
    # 第二轮 prompt 应包含"已有分镜"和 Alice 的信息
    assert "已有分镜" in prompts[1]
    assert "Alice" in prompts[1]
    assert "S02" in prompts[1]  # 已有分镜 JSON 被喂回


def test_batch_stops_when_llm_ends(monkeypatch):
    """LLM 提前结束（输出 < batch）时应停止"""
    calls = []

    def fake_ollama(prompt, **kw):
        calls.append(prompt)
        return "S01|Alice|教室|全景||Alice 走进教室||"

    monkeypatch.setattr("agents.comfy_utils.ollama_generate", fake_ollama)
    shots = _ollama_generate_storyboard_batch("短故事", CHARS, batch_size=2, max_shots=8)
    assert len(shots) == 1
    assert len(calls) == 1  # 只调了一次


def test_batch_unparseable_falls_back(monkeypatch):
    """首轮输出不可解析应降级模板（不崩）"""
    def fake_ollama(prompt, **kw):
        return "完全不是分镜格式的输出!!!"

    monkeypatch.setattr("agents.comfy_utils.ollama_generate", fake_ollama)
    shots = _ollama_generate_storyboard_batch("故事", CHARS, batch_size=2, max_shots=4)
    # 降级模板应仍返回分镜
    assert len(shots) >= 2
    assert shots[0]["镜号"].startswith("S")
