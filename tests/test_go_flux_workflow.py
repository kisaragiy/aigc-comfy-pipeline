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
    """测试 IP-Adapter 工作流节点结构（当前已禁用）。"""

    def test_ref_image_does_not_add_ipa_nodes(self):
        """IP-Adapter 节点已被移除，ref_image 参数不影响工作流。"""
        ref_path = _create_test_ref()
        try:
            wf, _ = build_flux_workflow("test prompt", ref_image=ref_path)
            node_types = {n["class_type"] for n in wf.values()}
            assert "IPAdapterModelLoader" not in node_types
            assert "CLIPVisionLoader" not in node_types
            assert "IPAdapterAdvanced" not in node_types
        finally:
            Path(ref_path).unlink(missing_ok=True)

    def test_ref_image_node_count_same_as_basic(self):
        """ref_image 参数不改变节点数（IP-Adapter 已禁用）。"""
        wf_base, _ = build_flux_workflow("test")
        ref_path = _create_test_ref()
        try:
            wf_ref, _ = build_flux_workflow("test", ref_image=ref_path)
            assert len(wf_ref) == len(wf_base)
        finally:
            Path(ref_path).unlink(missing_ok=True)

    def test_ref_image_params_still_accepted(self):
        """ref_image 和 ip_weight 参数仍可传入（不影响工作流）。"""
        ref_path = _create_test_ref()
        try:
            wf, seed = build_flux_workflow("test", ref_image=ref_path, ip_weight=0.5)
            assert isinstance(wf, dict) and len(wf) > 0
            assert isinstance(seed, int) and seed > 0
        finally:
            Path(ref_path).unlink(missing_ok=True)


def _create_test_ref() -> str:
    """创建临时测试参考图。"""
    import tempfile
    f = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    f.close()
    return f.name
