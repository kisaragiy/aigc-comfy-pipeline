"""测试 go_flux.py 的 build_flux_workflow 工作流构建。

无需 ComfyUI 或 GPU — 仅测试 JSON 节点结构。
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agents"))

from go_flux import build_flux_workflow, MODEL_CONFIGS, build_upscale_workflow, build_restore_face_workflow


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
    """测试 Flux.2 Klein 原生视觉参考（ReferenceLatent + RefLatentController）。"""

    def test_ref_image_adds_ref_nodes(self):
        """ref_image 应添加所有视觉参考节点。"""
        ref_path = _create_test_ref()
        try:
            wf, _ = build_flux_workflow("test prompt", ref_image=ref_path)
            node_types = {n["class_type"] for n in wf.values()}
            assert "LoadImage" in node_types
            assert "VAEEncode" in node_types
            assert "ReferenceLatent" in node_types, "应有正通道 ReferenceLatent"
            assert "Flux2KleinRefLatentController" in node_types
            assert "Flux2KleinTextRefBalance" in node_types, "应有 TextRefBalance"
        finally:
            Path(ref_path).unlink(missing_ok=True)

    def test_ref_adds_six_nodes(self):
        """ref_image 应比无 ref 多 6 个节点。"""
        wf_base, _ = build_flux_workflow("test")
        ref_path = _create_test_ref()
        try:
            wf_ref, _ = build_flux_workflow("test", ref_image=ref_path)
            assert len(wf_ref) - len(wf_base) == 6, \
                f"期望 6 节, 实际 {len(wf_ref)-len(wf_base)}"
        finally:
            Path(ref_path).unlink(missing_ok=True)

    def test_ref_has_two_reference_latents(self):
        """应有 2 个 ReferenceLatent 节点（正负通道）。"""
        ref_path = _create_test_ref()
        try:
            wf, _ = build_flux_workflow("test", ref_image=ref_path)
            ref_lat_count = sum(
                1 for n in wf.values() if n["class_type"] == "ReferenceLatent")
            assert ref_lat_count == 2, f"期望 2 个 ReferenceLatent, 实际 {ref_lat_count}"
        finally:
            Path(ref_path).unlink(missing_ok=True)

    def test_ref_balance_passed(self):
        """ip_balance 应传入 TextRefBalance 的 balance 参数。"""
        ref_path = _create_test_ref()
        try:
            wf, _ = build_flux_workflow("test", ref_image=ref_path, ip_balance=0.3)
            for n in wf.values():
                if n["class_type"] == "Flux2KleinTextRefBalance":
                    assert n["inputs"]["balance"] == 0.3
                    break
            else:
                assert False, "未找到 Flux2KleinTextRefBalance"
        finally:
            Path(ref_path).unlink(missing_ok=True)

    def test_ref_skips_missing_file(self):
        """不存在的 ref_image 应跳过且不报错。"""
        wf, _ = build_flux_workflow("test", ref_image="C:/nonexistent/ref.png")
        node_types = {n["class_type"] for n in wf.values()}
        assert "ReferenceLatent" not in node_types
        assert "Flux2KleinRefLatentController" not in node_types
        assert "Flux2KleinTextRefBalance" not in node_types

    def test_ref_missing_node_count_unchanged(self):
        """不存在的 ref → 节点数与基础工作流相同。"""
        wf_base, _ = build_flux_workflow("test")
        wf_skip, _ = build_flux_workflow("test", ref_image="C:/nonexistent/ref.png")
        assert len(wf_skip) == len(wf_base)


def _create_test_ref() -> str:
    """创建临时测试参考图。"""
    import tempfile
    f = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    f.close()
    return f.name


class TestPostProcessWorkflows:
    """测试超分 + 修脸工作流构建。"""

    def test_upscale_workflow_nodes(self):
        wf = build_upscale_workflow("test.png")
        types = {n["class_type"] for n in wf.values()}
        assert "LoadImage" in types
        assert "ImageScaleBy" in types
        assert "SaveImage" in types

    def test_upscale_workflow_count(self):
        wf = build_upscale_workflow("test.png", upscale_factor=4.0)
        assert len(wf) == 3

    def test_upscale_passes_factor(self):
        wf = build_upscale_workflow("test.png", upscale_factor=2.0)
        for n in wf.values():
            if n["class_type"] == "ImageScaleBy":
                assert n["inputs"]["upscale_by"] == 2.0

    def test_restore_face_workflow_nodes(self):
        wf = build_restore_face_workflow("test.png")
        types = {n["class_type"] for n in wf.values()}
        assert "LoadImage" in types
        assert "MTB_LoadFaceEnhanceModel" in types
        assert "MTB_RestoreFace" in types
        assert "SaveImage" in types

    def test_restore_face_workflow_count(self):
        wf = build_restore_face_workflow("test.png")
        assert len(wf) == 4
