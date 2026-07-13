"""测试 go_flux.py 的 build_flux_workflow 工作流构建。

无需 ComfyUI 或 GPU — 仅测试 JSON 节点结构。
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agents"))

from go_flux import build_flux_workflow, MODEL_CONFIGS


class TestBuildFluxWorkflow:
    """测试 build_flux_workflow 基础结构。"""

    def test_returns_workflow_and_seed(self):
        wf, seed = build_flux_workflow("test prompt")
        assert isinstance(wf, dict)
        assert len(wf) > 0
        assert isinstance(seed, int) and seed > 0

    def test_has_required_nodes(self):
        wf, _ = build_flux_workflow("test prompt")
        node_types = {n["class_type"] for n in wf.values()}
        assert "UNETLoader" in node_types
        assert "CLIPLoader" in node_types
        assert "VAELoader" in node_types
        assert "CFGGuider" in node_types
        assert "SamplerCustomAdvanced" in node_types
        assert "SaveImage" in node_types

    def test_node_count(self):
        """基础工作流应有 13 个节点（不含 IP-Adapter）。"""
        wf, _ = build_flux_workflow("test prompt")
        assert len(wf) == 13

    def test_negative_prompt_adds_node(self):
        wf_default, _ = build_flux_workflow("test")
        wf_neg, _ = build_flux_workflow("test", negative_prompt="blurry")
        assert len(wf_neg) > len(wf_default)

    def test_lora_adds_node(self):
        wf, _ = build_flux_workflow("test", lora_name="test_lora.safetensors")
        node_types = {n["class_type"] for n in wf.values()}
        assert "LoraLoader" in node_types

    def test_model_variant_9b(self):
        wf, _ = build_flux_workflow("test", model_variant="9b")
        for n in wf.values():
            if n["class_type"] == "UNETLoader":
                assert "9b" in n["inputs"]["unet_name"]
                break


class TestIPAdapterWorkflow:
    """测试 IP-Adapter 工作流节点结构。"""

    def test_ref_image_adds_ipa_nodes(self):
        """ref_image 参数应添加 IP-Adapter 节点。"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            ref_path = f.name
            # 写一个最小 PNG
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        try:
            wf, _ = build_flux_workflow("test prompt", ref_image=ref_path)
            node_types = {n["class_type"] for n in wf.values()}
            assert "LoadImage" in node_types, "ref_image 应添加 LoadImage 节点"
            assert "IPAdapterUnifiedLoader" in node_types, "ref_image 应添加 IPAdapterUnifiedLoader"
            assert "IPAdapterAdvanced" in node_types, "ref_image 应添加 IPAdapterAdvanced"
        finally:
            Path(ref_path).unlink(missing_ok=True)

    def test_ipa_adds_more_nodes(self):
        """ref_image 应比无 ref 多 3 个节点。"""
        wf_base, _ = build_flux_workflow("test")
        n_base = len(wf_base)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            ref_path = f.name
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        try:
            wf_ipa, _ = build_flux_workflow("test", ref_image=ref_path)
            assert len(wf_ipa) - n_base == 3, "ref_image 应恰好添加 3 个新节点"
        finally:
            Path(ref_path).unlink(missing_ok=True)

    def test_ipa_model_uses_specified_weight(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            ref_path = f.name
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        try:
            wf, _ = build_flux_workflow("test", ref_image=ref_path, ip_weight=0.5)
            for n in wf.values():
                if n["class_type"] == "IPAdapterAdvanced":
                    assert n["inputs"]["weight"] == 0.5
                    assert n["inputs"]["weight_type"] == "linear"
                    break
            else:
                assert False, "未找到 IPAdapterAdvanced 节点"
        finally:
            Path(ref_path).unlink(missing_ok=True)

    def test_ipa_skips_missing_ref(self):
        """不存在的 ref_image 应跳过 IP-Adapter 且不报错。"""
        wf, _ = build_flux_workflow("test prompt", ref_image="C:/nonexistent/ref.png")
        node_types = {n["class_type"] for n in wf.values()}
        assert "IPAdapterAdvanced" not in node_types

    def test_ipa_node_count_same_as_basic_when_skip(self):
        """不存在的 ref_image → 节点数与基础工作流相同。"""
        wf_base, _ = build_flux_workflow("test")
        wf_skip, _ = build_flux_workflow("test", ref_image="C:/nonexistent/ref.png")
        assert len(wf_skip) == len(wf_base)
