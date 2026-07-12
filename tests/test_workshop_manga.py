"""测试 workshop.manga 纯函数 — 无需 ComfyUI / Ollama。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agents"))

from workshop.manga.manga import (
    _layout_size,
    _seed_from_shot,
    _template_storyboard,
    storyboard_to_prompts,
)


# ── _seed_from_shot ──────────────────────────────────────

class TestSeedFromShot:
    def test_S01(self):
        seed = _seed_from_shot("S01")
        assert isinstance(seed, int)
        assert 0 <= seed <= 2 ** 31 - 1

    def test_deterministic(self):
        """同一镜号始终返回相同种子。"""
        assert _seed_from_shot("S01") == _seed_from_shot("S01")

    def test_different_shots_different(self):
        """不同镜号大概率不同。"""
        assert _seed_from_shot("S01") != _seed_from_shot("S02")

    def test_S10(self):
        """两位数镜号。"""
        seed = _seed_from_shot("S10")
        assert isinstance(seed, int)
        assert seed > 0

    def test_no_numbers(self):
        """无数字镜号。"""
        seed = _seed_from_shot("ABC")
        assert isinstance(seed, int)

    def test_with_prefix(self):
        """完整镜号格式。"""
        seed = _seed_from_shot("S01-教室")
        assert seed > 0


# ── _layout_size ─────────────────────────────────────────

class TestLayoutSize:
    def test_close_up(self):
        w, h = _layout_size("特写")
        assert (w, h) == (768, 768)

    def test_big_head(self):
        w, h = _layout_size("大头")
        assert (w, h) == (768, 768)

    def test_full_body(self):
        w, h = _layout_size("全身")
        assert (w, h) == (768, 1152)

    def test_wide_shot(self):
        w, h = _layout_size("远景")
        assert (w, h) == (1152, 768)

    def test_medium_default(self):
        w, h = _layout_size("中景")
        assert (w, h) == (768, 1024)

    def test_unknown_fallback(self):
        """未识别的景别返回半身/中景默认尺寸。"""
        w, h = _layout_size("未知景别")
        assert (w, h) == (768, 1024)

    def test_close_up_variant(self):
        """包含特写关键词的变体。"""
        w, h = _layout_size("面部特写")
        assert (w, h) == (768, 768)


# ── _template_storyboard ─────────────────────────────────

class TestTemplateStoryboard:
    def _default_chars(self, names: list[str]) -> dict:
        return {n: {"服饰": "校服", "发型": "长发", "特征": ""} for n in names}

    def test_1_character(self):
        chars = self._default_chars(["Alice"])
        shots = _template_storyboard("教室对话", chars)
        # 1 角色: 2 基础 + 0(≥2) + 0(≥3) + 0(≥4) + 1 特写 = 3
        assert len(shots) == 3
        assert shots[0]["人物"] == "Alice"
        assert shots[-1]["景别"] == "特写"

    def test_2_characters(self):
        chars = self._default_chars(["Alice", "Bob"])
        shots = _template_storyboard("教室对话", chars)
        # 2 角色: 2 基础 + 1(≥2) + 0(≥3) + 0(≥4) + 1 特写 = 4
        assert len(shots) == 4
        assert shots[0]["人物"] == "Alice"
        assert shots[2]["人物"] == "Bob"
        assert shots[-1]["景别"] == "特写"

    def test_3_characters(self):
        chars = self._default_chars(["Alice", "Bob", "Charlie"])
        shots = _template_storyboard("教室对话", chars)
        # 3 角色: 2 基础 + 1(≥2) + 1(≥3) + 0(≥4) + 1 特写 = 5
        assert len(shots) == 5
        assert shots[-1]["景别"] == "特写"

    def test_4_characters(self):
        chars = self._default_chars(["Alice", "Bob", "Charlie", "Diana"])
        shots = _template_storyboard("教室对话", chars)
        # 4 角色: 2 基础 + 1(≥2) + 1(≥3) + 1(≥4) + 1 特写 = 6
        assert len(shots) == 6
        assert shots[-1]["景别"] == "特写"

    def test_empty_characters(self):
        """无角色时仍生成基础镜。"""
        shots = _template_storyboard("场景", {})
        assert len(shots) == 3  # 2 基础 + 1 特写
        assert shots[0]["人物"] == "角色A"
        assert shots[-1]["人物"] == "角色A"

    def test_all_have_required_keys(self):
        chars = self._default_chars(["Alice"])
        shots = _template_storyboard("教室", chars)
        required = {"镜号", "人物", "场景", "景别", "音频提示", "画面描述", "台词", "备注"}
        for shot in shots:
            assert required.issubset(shot.keys())

    def test_dynamic_shot_numbers(self):
        chars = self._default_chars(["A", "B", "C"])
        shots = _template_storyboard("场景", chars)
        for i, shot in enumerate(shots, 1):
            expected = f"S{i:02d}"
            assert shot["镜号"] == expected, f"镜号应为 {expected}，实际 {shot['镜号']}"


# ── storyboard_to_prompts ────────────────────────────────

class TestStoryboardToPrompts:
    def _sample_storyboard(self, n: int = 2) -> list[dict[str, str]]:
        return [
            {"镜号": f"S{i+1:02d}", "人物": "Alice" if i == 0 else "Bob",
             "场景": "教室", "景别": "中景" if i == 0 else "特写",
             "音频提示": "", "画面描述": f"画面{i+1}", "台词": "", "备注": ""}
            for i in range(n)
        ]

    def _chars(self) -> dict:
        return {
            "Alice": {"服饰": "白校服", "发型": "银发", "特征": "红瞳"},
            "Bob": {"服饰": "黑校服", "发型": "黑发", "特征": ""},
        }

    def test_returns_correct_count(self):
        storyboard = self._sample_storyboard(2)
        panels = storyboard_to_prompts(storyboard, self._chars(), style_hint="anime")
        assert len(panels) == 2

    def test_required_keys(self):
        storyboard = self._sample_storyboard(1)
        panels = storyboard_to_prompts(storyboard, self._chars(), style_hint="anime")
        required = {"shot", "prompt", "negative", "seed", "width", "height",
                    "character", "dialogue", "scene", "camera"}
        assert required.issubset(panels[0].keys())

    def test_seed_deterministic(self):
        storyboard = self._sample_storyboard(2)
        panels1 = storyboard_to_prompts(storyboard, self._chars(), style_hint="anime")
        panels2 = storyboard_to_prompts(storyboard, self._chars(), style_hint="anime")
        for p1, p2 in zip(panels1, panels2):
            assert p1["seed"] == p2["seed"]

    def test_seed_unique_per_shot(self):
        storyboard = self._sample_storyboard(2)
        panels = storyboard_to_prompts(storyboard, self._chars(), style_hint="anime")
        assert panels[0]["seed"] != panels[1]["seed"]

    def test_dimensions_from_camera(self):
        storyboard = [
            {"镜号": "S01", "人物": "Alice", "场景": "教室", "景别": "特写",
             "音频提示": "", "画面描述": "表情", "台词": "", "备注": ""},
            {"镜号": "S02", "人物": "Bob", "场景": "教室", "景别": "全身",
             "音频提示": "", "画面描述": "站立", "台词": "", "备注": ""},
        ]
        panels = storyboard_to_prompts(storyboard, self._chars(), style_hint="anime")
        assert panels[0]["width"] == 768 and panels[0]["height"] == 768  # 特写
        assert panels[1]["width"] == 768 and panels[1]["height"] == 1152  # 全身

    def test_negative_from_style_preset(self):
        storyboard = self._sample_storyboard(1)
        panels = storyboard_to_prompts(storyboard, self._chars(), style_hint="photoreal")
        assert "anime" in panels[0]["negative"].lower() or "illustration" in panels[0]["negative"].lower()

    def test_character_traits_in_prompt(self):
        """角色特征（服饰/发型）被注入 prompt。"""
        storyboard = self._sample_storyboard(1)
        panels = storyboard_to_prompts(storyboard, self._chars(), style_hint="anime")
        # 白校服 来自 Alice 的角色特征
        assert "白校服" in panels[0]["prompt"] or "white" in panels[0]["prompt"].lower()

    def test_character_name_in_prompt(self):
        """角色名出现在 prompt 中。"""
        storyboard = self._sample_storyboard(1)
        panels = storyboard_to_prompts(storyboard, self._chars(), style_hint="anime")
        assert "alice" in panels[0]["prompt"].lower()
