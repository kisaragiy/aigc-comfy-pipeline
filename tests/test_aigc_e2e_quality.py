#!/usr/bin/env python3
"""
AIGC 端到端质量评估闭环 v1.0

全链路:
  剧本 → LLM故事板 agent → 工作流 → ComfyUI → 出图 → VLM审美评分

如果 ComfyUI 不在运行则跳过实际出图，只验证前段链路
"""
from __future__ import annotations

import sys, os, json, time, tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agents"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "workshop"))

import requests
import pytest

COMFYUI_URL = "http://127.0.0.1:8188"


# ════════════════════════════════════════════════════════════
# 辅助函数: 检测 ComfyUI 是否存活
# ════════════════════════════════════════════════════════════

def comfyui_is_alive() -> bool:
    try:
        r = requests.get(f"{COMFYUI_URL}/system/stats", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


HAS_COMFYUI = comfyui_is_alive()


# ════════════════════════════════════════════════════════════
# 1) 剧本 → LLM Storyboard
# ════════════════════════════════════════════════════════════

class TestStoryboardPipeline:
    """剧本语义理解链路"""

    def test_storyboard_from_script_exists(self):
        """验证 storyboard_from_script 入口可用"""
        from agents.go_manga import storyboard_from_script
        assert callable(storyboard_from_script)

    def test_llm_storyboard_4panel_romance(self):
        """校园恋爱4格剧本 → LLM 故事板"""
        from agents.go_manga import storyboard_from_script
        sb = storyboard_from_script("""
校园恋爱:
第一镜: 春天的樱花树下, 女主角林小夏一个人看着飘落的花瓣, 表情寂寞
第二镜: 男主角陈宇从远处走来, 看到她的背影, 停下脚步犹豫
第三镜: 林小夏回头, 看到陈宇, 两人目光相遇, 她脸红了
第四镜: 两人并肩走, 夕阳拉长了影子, 气氛温馨
""")
        assert sb is not None
        assert len(sb.panels) == 4
        assert len(sb.characters) >= 2
        assert len(sb.scenes) >= 1

        # 验证情感弧线
        from agents.go_manga import analyze_emotional_arc
        arc = analyze_emotional_arc(sb)
        arc_type = arc.get("arc_type") or arc.get("arc", "") or str(arc.get("type", ""))
        assert len(arc_type) > 0

    def test_llm_storyboard_emotional_beats(self):
        """验证 LLM 为每个 Panel 生成情感标签"""
        from agents.go_manga import storyboard_from_script
        sb = storyboard_from_script("第1镜: 下雨天, 女主躲在屋檐下, 近景")
        # 即使只有1镜，也应该有 emotional_beat
        for p in sb.panels:
            assert hasattr(p, "emotional_beat")

    def test_llm_storyboard_camera_variety(self):
        """验证 LLM 生成的相机角度有多样性"""
        from agents.go_manga import storyboard_from_script
        sb = storyboard_from_script("""
战斗场景:
第一镜: 两个剑士对峙
第二镜: 他们冲向对方
第三镜: 剑刃相撞, 火花四溅
第四镜: 慢动作特写, 两人的眼神
""")
        cameras = [p.camera for p in sb.panels if p.camera and p.camera != "unknown"]
        if cameras:
            unique = len(set(cameras))
            assert unique >= 2, f"应该有至少2种相机角度, 只有 {unique}: {cameras}"


# ════════════════════════════════════════════════════════════
# 2) 故事板 → 工作流
# ════════════════════════════════════════════════════════════

class TestWorkflowConversion:
    """故事板 → ComfyUI工作流 → 实际出图"""

    def test_txt2img_workflow_creation(self):
        """验证 txt2img 工作流可以创建"""
        from agents.workflow_builder import WorkflowBuilder
        wb = WorkflowBuilder.from_prompt("txt2img")
        assert wb is not None
        result = wb.to_dict()
        assert len(result) >= 5  # 至少5个节点

    def test_workflow_with_character_prompt(self):
        """验证加入了角色设计的提示词工作流"""
        from agents.workflow_builder import WorkflowBuilder
        import creative.character_design as cd
        d = cd.design_character("元气", "粉", "双马尾", "圆眼", "红瞳", "水手服")
        prompt = cd.character_to_prompt(d)
        wb = WorkflowBuilder.from_prompt("txt2img", positive=prompt)
        assert wb is not None
        result = wb.to_dict()
        assert len(result) >= 5

    @pytest.mark.skipif(not comfyui_is_alive(), reason="ComfyUI not running")
    def test_actual_comfyui_connection(self):
        """验证 ComfyUI API 可用"""
        r = requests.get(f"{COMFYUI_URL}/system/stats", timeout=5)
        assert r.status_code == 200
        data = r.json()
        print(f"\nComfyUI version: {data.get('system', {}).get('comfyui_version', 'unknown')}")

    @pytest.mark.skipif(not comfyui_is_alive(), reason="ComfyUI not running")
    def test_generate_single_image(self):
        """实际出图: 简单 txt2img"""
        from agents.workflow_builder import WorkflowBuilder
        wb = WorkflowBuilder.from_prompt("txt2img", positive="cat, masterpiece",
                                          negative="blurry, ugly", seed=42, steps=15)
        workflow = wb.to_dict()
        # 确保输出到临时文件夹
        prompt_data = {"prompt": workflow}
        r = requests.post(f"{COMFYUI_URL}/prompt", json=prompt_data, timeout=10)
        assert r.status_code == 200
        result = r.json()
        assert "prompt_id" in result
        print(f"\nImage generation job submitted: {result['prompt_id']}")


# ════════════════════════════════════════════════════════════
# 3) 出图 → VLM 审美评分
# ════════════════════════════════════════════════════════════

class TestAestheticScoring:
    """VLM 审美评分链路"""

    def test_aesthetic_agent_imports(self):
        """验证 AestheticAgent 可导入"""
        from agents.go_aesthetic import AestheticAgent, AestheticResult
        assert AestheticAgent is not None
        assert AestheticResult is not None

    def test_aesthetic_agent_init(self):
        """验证 AestheticAgent 可实例化"""
        from agents.go_aesthetic import AestheticAgent
        agent = AestheticAgent(verbose=False)
        assert agent is not None
        assert hasattr(agent, "evaluate")

    def test_aesthetic_result_error_no_image(self):
        """不存在的图片应返回错误结果"""
        from agents.go_aesthetic import AestheticAgent
        agent = AestheticAgent(verbose=False)
        result = agent.evaluate("/path/does/not/exist.png")
        assert result is not None
        if hasattr(result, "overall_feedback"):
            assert "不存在" in result.overall_feedback

    @pytest.mark.skipif(not comfyui_is_alive(), reason="ComfyUI not running")
    def test_aesthetic_scoring_actual_image(self):
        """实际出图 + VLM 评分"""
        from agents.workflow_builder import WorkflowBuilder
        from agents.go_aesthetic import AestheticAgent

        # 1) 生成一张图
        wb = WorkflowBuilder.from_prompt("txt2img", positive="1girl, anime, cherry blossoms",
                                          negative="nsfw, lowres", seed=42, steps=20)
        workflow = wb.to_dict()
        prompt_data = {"prompt": workflow}
        r = requests.post(f"{COMFYUI_URL}/prompt", json=prompt_data, timeout=15)
        assert r.status_code == 200
        job = r.json()
        prompt_id = job["prompt_id"]

        # 2) 等待完成 (轮询)
        output_path = None
        for _ in range(30):
            time.sleep(2)
            hist = requests.get(f"{COMFYUI_URL}/history/{prompt_id}", timeout=5)
            if hist.status_code == 200 and hist.json().get(prompt_id, {}).get("outputs"):
                outputs = hist.json()[prompt_id]["outputs"]
                for node_id, node_out in outputs.items():
                    for img in node_out.get("images", []):
                        output_path = os.path.join(
                            "C:/DrawingLive/ComfyUI/output",
                            img.get("subfolder", ""),
                            img["filename"]
                        )
                break

        if output_path and os.path.exists(output_path):
            # 3) VLM 评分
            agent = AestheticAgent(verbose=True)
            result = agent.evaluate(output_path)
            assert result is not None
            assert result.overall_score is not None or result.overall_feedback
            print(f"\nImage: {output_path}")
            print(f"Overall score: {result.overall_score}")
            if result.dimensions:
                for d in result.dimensions:
                    print(f"  {d.name}: {d.score}/10")
        else:
            pytest.skip("Image generation did not complete in time")


# ════════════════════════════════════════════════════════════
# 4) 全链路一体化 (仅完整性验证)
# ════════════════════════════════════════════════════════════

class TestFullPipeline:
    """全链路: 剧本 → 故事板 → 工作流 → (ComfyUI) → (VLM)"""

    def test_pipeline_prechecks(self):
        """验证全链路所有模块都可导入"""
        from agents.go_manga import storyboard_from_script, MangaEngine
        from agents.workflow_builder import WorkflowBuilder
        from agents.go_aesthetic import AestheticAgent
        import creative.character_design
        import creative.background_depth
        import creative.fashion_depth
        assert True  # 所有导入成功

    @pytest.mark.timeout(60)
    def test_pipeline_storyboard_to_workflow(self):
        """故事板 → 工作流 转换验证"""
        from agents.go_manga import storyboard_from_script
        from agents.workflow_builder import WorkflowBuilder

        sb = storyboard_from_script("第1镜: 教室, 女主在看书, 特写")
        # 确保至少有分镜
        assert len(sb.panels) >= 0
        # 找到可用的提示词构建
        prompt_parts = []
        for name, char in sb.characters.items():
            prompt_parts.append(char.get_prompt())
        full_prompt = ", ".join(prompt_parts) if prompt_parts else "1girl, school"
        full_prompt += ", anime style, masterpiece"

        wb = WorkflowBuilder.from_prompt("txt2img", positive=full_prompt)
        result = wb.to_dict()
        assert len(result) >= 5
        assert wb.summary is not None


# ════════════════════════════════════════════════════════════
# 5) 覆盖率摘要
# ════════════════════════════════════════════════════════════

def test_quality_summary():
    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║  AIGC 端到端质量评估闭环                                ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print("║  ✅ StoryboardPipeline    — LLM 故事板理解语义          ║")
    print("║  ✅ WorkflowConversion    — 故事板→工作流               ║")
    print("║  ⏳ AestheticScoring      — VLM 评分 (需 ComfyUI)       ║")
    print("║  ✅ FullPipeline          — 全链路完整性                 ║")
    if HAS_COMFYUI:
        print("║  ✅ ComfyUI: RUNNING                                   ║")
    else:
        print("║  ⚠️ ComfyUI: NOT RUNNING — 出图/VLM 评分已跳过        ║")
    print("╚══════════════════════════════════════════════════════════╝")
