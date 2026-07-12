"""测试 workshop.engine.engine 纯函数 — 无需 ComfyUI / Ollama。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agents"))

from workshop.engine.engine import (
    _clean_subject,
    _detect_composition,
    _detect_lighting,
    _detect_negative,
    _detect_style,
    _extract_keywords,
    _template_fallback,
    list_presets,
)


# ── _detect_style ────────────────────────────────────────

class TestDetectStyle:
    def test_anime(self):
        assert _detect_style("二次元少女") == "anime"
        assert _detect_style("动漫风格角色") == "anime"
        assert _detect_style("动画渲染") == "anime"
        assert _detect_style("日系画风") == "anime"

    def test_photoreal(self):
        assert _detect_style("写实人物") == "photoreal"
        assert _detect_style("真人照片") == "photoreal"

    def test_photography(self):
        assert _detect_style("摄影作品") == "photography"
        assert _detect_style("照片风格") == "photography"
        assert _detect_style("写真") == "photography"

    def test_cosplay(self):
        assert _detect_style("cos服装") == "cosplay"
        assert _detect_style("c服角色") == "cosplay"

    def test_cg(self):
        assert _detect_style("cg渲染") == "cg"
        assert _detect_style("3d建模") == "cg"
        assert _detect_style("渲染图") == "cg"

    def test_cinematic(self):
        assert _detect_style("电影感") == "cinematic"
        assert _detect_style("镜头语言") == "cinematic"

    def test_oil(self):
        assert _detect_style("油画风格") == "oil"

    def test_sketch(self):
        assert _detect_style("素描") == "sketch"
        assert _detect_style("草图") == "sketch"
        assert _detect_style("线稿") == "sketch"

    def test_watercolor(self):
        assert _detect_style("水彩画") == "watercolor"

    def test_pixel(self):
        assert _detect_style("像素风格") == "pixel"

    def test_ink(self):
        assert _detect_style("水墨画") == "ink"

    def test_default_anime(self):
        """无匹配关键词时默认 anime。"""
        assert _detect_style("一个少女站在窗前") == "anime"

    def test_empty_string(self):
        assert _detect_style("") == "anime"

    def test_hint_overrides(self):
        """style_hint 参数优先。"""
        assert _detect_style("油画少女", hint="photoreal") == "photoreal"

    def test_hint_only_recognized(self):
        """不认识的 hint 忽略。"""
        assert _detect_style("少女", hint="unknown_style") == "anime"

    def test_mixed_signals(self):
        """多个风格信号，第一个匹配优先。"""
        # 按 style_map 顺序 "二次元" 在 "油画" 前面
        assert _detect_style("二次元少女油画质感") == "anime"

    def test_style_map_order(self):
        """确认 '摄影' 在 '照片' 前匹配。"""
        # 如果有 "摄影" 和 "写真"，摄影先匹配
        assert _detect_style("摄影作品") == "photography"


# ── _detect_composition ──────────────────────────────────

class TestDetectComposition:
    def test_full_body(self):
        assert "full body" in _detect_composition("全身照")
        assert "full body" in _detect_composition("全身")

    def test_upper_body(self):
        assert "upper body" in _detect_composition("半身像")

    def test_close_up(self):
        assert "close-up" in _detect_composition("特写镜头")

    def test_headshot(self):
        assert "headshot" in _detect_composition("大头照")

    def test_medium_shot(self):
        assert "medium shot" in _detect_composition("中景构图")

    def test_wide_shot(self):
        assert "wide shot" in _detect_composition("远景")

    def test_high_angle(self):
        assert "high angle" in _detect_composition("俯视角度")

    def test_low_angle(self):
        assert "low angle" in _detect_composition("仰视")

    def test_over_shoulder(self):
        assert "over the shoulder" in _detect_composition("过肩镜头")

    def test_side_profile(self):
        assert "side profile" in _detect_composition("侧面")

    def test_from_behind(self):
        assert "from behind" in _detect_composition("背面")

    def test_default_return(self):
        assert "medium shot" in _detect_composition("一个少女")
        assert "balanced" in _detect_composition("")

    def test_no_false_match(self):
        """不包含关键词时返回默认。"""
        assert "medium shot" in _detect_composition("随机文字")


# ── _detect_lighting ────────────────────────────────────

class TestDetectLighting:
    def test_natural(self):
        assert "natural" in _detect_lighting("自然光拍摄")

    def test_backlight(self):
        assert "backlight" in _detect_lighting("逆光")
        assert "rim light" in _detect_lighting("逆光")

    def test_side_light(self):
        assert "side lighting" in _detect_lighting("侧光")

    def test_top_light(self):
        assert "overhead light" in _detect_lighting("顶光")

    def test_soft_light(self):
        assert "soft lighting" in _detect_lighting("柔光")

    def test_neon(self):
        assert "neon" in _detect_lighting("霓虹灯光")

    def test_candle(self):
        assert "candle light" in _detect_lighting("烛光")

    def test_stage(self):
        assert "stage lighting" in _detect_lighting("舞台光")

    def test_morning(self):
        assert "morning light" in _detect_lighting("晨光")

    def test_sunset(self):
        assert "sunset" in _detect_lighting("黄昏")
        assert "golden backlight" in _detect_lighting("黄昏")

    def test_moonlight(self):
        assert "moonlight" in _detect_lighting("月光")

    def test_volumetric(self):
        assert "volumetric" in _detect_lighting("体积光")

    def test_default(self):
        assert "soft natural" in _detect_lighting("少女")
        assert "diffused" in _detect_lighting("")


# ── _extract_keywords ────────────────────────────────────

class TestExtractKeywords:
    def test_cyberpunk(self):
        kws = _extract_keywords("赛博朋克少女")
        assert any("cyberpunk" in kw for kw in kws)

    def test_vaporwave(self):
        kws = _extract_keywords("蒸汽波风格")
        assert any("vaporwave" in kw for kw in kws)

    def test_fantasy(self):
        kws = _extract_keywords("奇幻森林")
        assert any("fantasy" in kw for kw in kws)

    def test_gufeng(self):
        kws = _extract_keywords("古风少女")
        assert any("gufeng" in kw for kw in kws)

    def test_no_keywords(self):
        assert _extract_keywords("一个少女站在窗前") == []

    def test_multiple_keywords(self):
        kws = _extract_keywords("赛博朋克都市夜景")
        assert len(kws) >= 2  # 赛博朋克 + 都市

    def test_empty(self):
        assert _extract_keywords("") == []


# ── _clean_subject ───────────────────────────────────────

class TestCleanSubject:
    def test_removes_known_keywords(self):
        cleaned = _clean_subject("一个少女站在窗前，逆光，半身")
        assert "逆光" not in cleaned
        assert "半身" not in cleaned

    def test_preserves_core_subject(self):
        cleaned = _clean_subject("银发少女校服教室窗边逆光")
        # "逆光" 被移除，但核心描述保留
        assert "银发" in cleaned
        assert "校服" in cleaned or "教室" in cleaned or "窗边" in cleaned

    def test_fallback_to_original(self):
        """当清理后为空，返回原文。"""
        orig = "全身"
        cleaned = _clean_subject(orig)
        assert cleaned == orig

    def test_empty_string(self):
        assert _clean_subject("") == ""

    def test_full_clean(self):
        """只有关键词的场景。"""
        cleaned = _clean_subject("逆光侧面半身仰视")
        assert cleaned  # 应保留非关键词字符（如果有）
        # 全是关键词时，清理后可能是空格，fallback 回原文
        assert "逆光" not in cleaned or cleaned  # 至少不为空


# ── _template_fallback ───────────────────────────────────

class TestTemplateFallback:
    def test_returns_non_empty_prompt(self):
        result = _template_fallback("银发少女校服教室窗边逆光")
        assert isinstance(result, str)
        assert len(result) > 20

    def test_includes_quality_tag(self):
        result = _template_fallback("银发少女")
        assert "masterpiece" in result or "best quality" in result

    def test_respects_style_hint(self):
        result = _template_fallback("银发少女", style_hint="photoreal")
        assert "photorealistic" in result

    def test_empty_input(self):
        """空输入仍产生模板 prompt。"""
        result = _template_fallback("")
        assert isinstance(result, str)
        assert len(result) > 10

    def test_cyberpunk_keywords(self):
        result = _template_fallback("赛博朋克少女霓虹街景")
        assert "cyberpunk" in result or "neon" in result

    def test_no_duplicate_terms(self):
        """确保不重复相同的 quality/style tag。"""
        result = _template_fallback("动漫少女")
        # 去重后同一 tag 只出现一次
        assert result.count("masterpiece") <= 1


# ── list_presets ─────────────────────────────────────────

class TestListPresets:
    def test_returns_dict_with_keys(self):
        presets = list_presets()
        assert "styles" in presets
        assert "compositions" in presets
        assert "lighting" in presets
        assert "style_keywords" in presets

    def test_styles_include_major_types(self):
        styles = list_presets()["styles"]
        assert "anime" in styles
        assert "photoreal" in styles
        assert "cinematic" in styles
        assert "oil" in styles

    def test_compositions_are_strings(self):
        comps = list_presets()["compositions"]
        assert all(isinstance(c, str) for c in comps)

    def test_lighting_count(self):
        lightings = list_presets()["lighting"]
        assert len(lightings) >= 10  # 至少有 10+ 种光照类型


# ── _detect_negative ─────────────────────────────────────

class TestDetectNegative:
    def test_no_negative(self):
        assert _detect_negative("银发少女站在窗前") == ""

    def test_empty(self):
        assert _detect_negative("") == ""
        assert _detect_negative("  ") == ""

    def test_blurry_direct(self):
        result = _detect_negative("模糊背景少女")
        assert "blurry" in result

    def test_不要_pattern(self):
        result = _detect_negative("不要模糊背景")
        assert "blurry" in result

    def test_别_pattern(self):
        result = _detect_negative("别崩手")
        assert "bad hands" in result

    def test_没有_pattern(self):
        result = _detect_negative("没有水印")
        assert "watermark" in result

    def test_不能有_pattern(self):
        result = _detect_negative("不能有文字")
        assert "text" in result

    def test_排除_pattern(self):
        result = _detect_negative("排除噪点")
        assert "noise" in result

    def test_bad_hands(self):
        result = _detect_negative("崩手")
        assert "bad hands" in result

    def test_bad_face(self):
        result = _detect_negative("崩脸")
        assert "bad face" in result

    def test_watermark(self):
        result = _detect_negative("不要水印不要签名")
        assert "watermark" in result
        assert "signature" in result  # both map to same tag
        # 去重，只出现一次
        assert result.count("watermark") == 1

    def test_text(self):
        result = _detect_negative("没有文字")
        assert "text" in result

    def test_too_dark(self):
        result = _detect_negative("太暗了")
        assert "dark" in result
        assert "underexposed" in result

    def test_too_bright(self):
        result = _detect_negative("太亮了")
        assert "overexposed" in result

    def test_chromatic_aberration(self):
        result = _detect_negative("紫边严重")
        assert "chromatic" in result

    def test_ghosting(self):
        result = _detect_negative("鬼影")
        assert "ghosting" in result

    def test_multiple_negatives(self):
        result = _detect_negative("不要模糊背景，别崩手，排除水印")
        assert "blurry" in result
        assert "bad hands" in result
        assert "watermark" in result

    def test_no_double_count(self):
        """同一关键词在句式和直匹配中只出现一次。"""
        result = _detect_negative("不要模糊背景，模糊")
        assert result.count("blurry") == 1

    def test_pattern_and_standalone(self):
        result = _detect_negative("不要崩手")
        assert result.count("bad hands") == 1

    def test_keyword_within_no_pattern(self):
        """直接在文本中的关键词（无句式）也被检测。"""
        result = _detect_negative("这张图太模糊了")
        assert "blurry" in result
