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
    """测试 Flux.2 Klein 原生视觉参考（ReferenceLatent + RefLatentController）。"""

    def test_ref_image_adds_ref_nodes(self):
        """ref_image 应添加 ReferenceLatent 相关节点。"""
        ref_path = _create_test_ref()
        try:
            wf, _ = build_flux_workflow("test prompt", ref_image=ref_path)
            node_types = {n["class_type"] for n in wf.values()}
            assert "LoadImage" in node_types, "ref_image 需 LoadImage 加载参考图"
            assert "VAEEncode" in node_types, "参考图需 VAEEncode 编码为 latent"
            assert "ReferenceLatent" in node_types, "需 ReferenceLatent 注入 conditioning"
            assert "Flux2KleinRefLatentController" in node_types, "需控制器调节注意力"
        finally:
            Path(ref_path).unlink(missing_ok=True)

    def test_ref_adds_four_nodes(self):
        """ref_image 应比无 ref 多 4 个节点。"""
        wf_base, _ = build_flux_workflow("test")
        ref_path = _create_test_ref()
        try:
            wf_ref, _ = build_flux_workflow("test", ref_image=ref_path)
            assert len(wf_ref) - len(wf_base) == 4, \
                "ref 应添加 4 节点: LoadImage + VAEEncode + ReferenceLatent + RefLatentController"
        finally:
            Path(ref_path).unlink(missing_ok=True)

    def test_ref_skips_missing_file(self):
        """不存在的 ref_image 应跳过且不报错。"""
        wf, _ = build_flux_workflow("test", ref_image="C:/nonexistent/ref.png")
        node_types = {n["class_type"] for n in wf.values()}
        assert "ReferenceLatent" not in node_types

    def test_ref_missing_node_count_unchanged(self):
        """不存在的 ref → 节点数与基础工作流相同。"""
        wf_base, _ = build_flux_workflow("test")
        wf_skip, _ = build_flux_workflow("test", ref_image="C:/nonexistent/ref.png")
        assert len(wf_skip) == len(wf_base)

    def test_ref_strength_passed_to_controller(self):
        """ip_weight 应传入 RefLatentController 的 strength 参数。"""
        ref_path = _create_test_ref()
        try:
            wf, _ = build_flux_workflow("test", ref_image=ref_path, ip_weight=0.3)
            for n in wf.values():
                if n["class_type"] == "Flux2KleinRefLatentController":
                    assert n["inputs"]["strength"] == 0.3, "ip_weight 应传递到 strength"
                    break
            else:
                assert False, "未找到 Flux2KleinRefLatentController"
        finally:
            Path(ref_path).unlink(missing_ok=True)

    def test_ref_connections(self):
        """验证关键节点连接的正确性。"""
        ref_path = _create_test_ref()
        try:
            wf, _ = build_flux_workflow("test", ref_image=ref_path)
            # 找到 node IDs
            ref_lat_id = None
            ref_ctrl_id = None
            for nid, n in wf.items():
                if n["class_type"] == "ReferenceLatent":
                    ref_lat_id = nid
                if n["class_type"] == "Flux2KleinRefLatentController":
                    ref_ctrl_id = nid

            assert ref_lat_id is not None, "缺少 ReferenceLatent"
            assert ref_ctrl_id is not None, "缺少 RefLatentController"

            # ReferenceLatent 引用 CLIPTextEncode 的输出
            lat_node = wf[ref_lat_id]
            assert lat_node["inputs"]["latent"][0] is not None

            # Controller 引用 ReferenceLatent 的输出
            ctrl_node = wf[ref_ctrl_id]
            assert ctrl_node["inputs"]["conditioning"][0] == ref_lat_id
        finally:
            Path(ref_path).unlink(missing_ok=True)


def _create_test_ref() -> str:
    """创建临时测试参考图。"""
    import tempfile
    f = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    f.close()
    return f.name
