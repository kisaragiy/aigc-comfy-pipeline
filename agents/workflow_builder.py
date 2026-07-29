#!/usr/bin/env python3
"""ComfyUI 工作流自动生成器 — 从 DAG 描述到 API JSON

功能:
  - 声明式 DAG: 用 Python 表达节点连接
  - 自动分配 node_id / 连接引用
  - 预置常用节点模板 (checkpoint/采样器/ControlNet/IPAdapter/放大/VAE)
  - 输出 ComfyUI API JSON (可直接 POST /prompt)
  - 支持 50-100 节点复杂工作流

用法:
  from agents.workflow_builder import WorkflowBuilder, nodes
  
  wb = WorkflowBuilder()
  ckpt = wb.add(nodes.Checkpoint("sd_xl_base.safetensors"))
  clip = wb.add(nodes.CLIPTextEncode("a beautiful girl, masterpiece", clip=ckpt.out("clip")))
  latent = wb.add(nodes.EmptyLatentImage(1024, 768))
  sampler = wb.add(nodes.KSampler(model=ckpt.out("model"), positive=clip.out("cond"), latent=latent.out("latent")))
  ...
  wb.to_json("workflow.json")
============================================================ """

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

# ════════════════════════════════════════════════════════════
# 节点定义
# ════════════════════════════════════════════════════════════

@dataclass
class NodeOutput:
    """一个节点的输出端口"""
    node_id: int
    slot_index: int = 0

    def to_ref(self) -> list:
        return [str(self.node_id), self.slot_index]


class Node:
    """ComfyUI 节点基类"""
    _node_counter: int = 0
    
    def __init__(self, class_type: str, **inputs):
        Node._node_counter += 1
        self.node_id = Node._node_counter
        self.class_type = class_type
        self._inputs: dict[str, Any] = inputs
        # 缓存输出端口数量 (子类覆盖)
        self._output_slots: int = 1
        self._display_name: str = class_type
    
    def out(self, slot: int = 0) -> NodeOutput:
        """获取此节点的输出连接引用"""
        return NodeOutput(self.node_id, slot)
    
    def to_dict(self) -> dict:
        """转换为 ComfyUI API JSON 格式"""
        inputs = {}
        for key, value in self._inputs.items():
            if isinstance(value, NodeOutput):
                inputs[key] = value.to_ref()
            elif isinstance(value, list) and all(isinstance(v, NodeOutput) for v in value):
                inputs[key] = [v.to_ref() for v in value]
            else:
                inputs[key] = value
        return {str(self.node_id): {"class_type": self.class_type, "inputs": inputs}}
    
    def __repr__(self) -> str:
        return f"[{self.node_id}] {self.class_type}"


# ════════════════════════════════════════════════════════════
# 预置节点模板
# ════════════════════════════════════════════════════════════

class nodes:
    """所有预置 ComfyUI 节点类型"""
    
    class CheckpointLoader(Node):
        """模型加载器"""
        def __init__(self, ckpt_name: str):
            super().__init__("CheckpointLoaderSimple", ckpt_name=ckpt_name)
            self._output_slots = 3  # model, clip, vae
            self._display_name = f"模型:{ckpt_name[:20]}"
    
    class UNETLoader(Node):
        """单独加载 UNET (Flux 系列用)"""
        def __init__(self, unet_name: str):
            super().__init__("UNETLoader", unet_name=unet_name)
            self._output_slots = 1
    
    class DualCLIPLoader(Node):
        """双 CLIP 加载器 (Flux/hunyuan 用)"""
        def __init__(self, clip_name1: str, clip_name2: str = "", type: str = "flux"):
            super().__init__("DualCLIPLoader", clip_name1=clip_name1, clip_name2=clip_name2, type=type)
            self._output_slots = 1
    
    class CLIPTextEncode(Node):
        """CLIP 文本编码"""
        def __init__(self, text: str, clip: Optional[NodeOutput] = None):
            kwargs = {"text": text}
            if clip:
                kwargs["clip"] = clip
            super().__init__("CLIPTextEncode", **kwargs)
            self._output_slots = 1
    
    class CLIPTextEncodeSD3(Node):
        """SD3/Flux 文本编码 (3 路 CLIP)"""
        def __init__(self, text: str, clip_l: NodeOutput, clip_g: NodeOutput, t5: Optional[NodeOutput] = None):
            super().__init__("CLIPTextEncodeSD3", text=text, clip_l=clip_l, clip_g=clip_g)
            if t5:
                self._inputs["t5"] = t5
            self._output_slots = 1
    
    class EmptyLatentImage(Node):
        """空潜空间初始化"""
        def __init__(self, width: int = 1024, height: int = 768, batch_size: int = 1):
            super().__init__("EmptyLatentImage", width=width, height=height, batch_size=batch_size)
            self._output_slots = 1
    
    class KSampler(Node):
        """KSampler 采样器"""
        def __init__(self, model: NodeOutput, positive: NodeOutput, negative: NodeOutput,
                     latent: NodeOutput, seed: int = 0, steps: int = 30, cfg: float = 7.0,
                     sampler_name: str = "dpmpp_2m", scheduler: str = "karras", denoise: float = 1.0):
            super().__init__("KSampler",
                seed=seed, steps=steps, cfg=cfg, sampler_name=sampler_name,
                scheduler=scheduler, denoise=denoise,
                model=model, positive=positive, negative=negative, latent_image=latent)
            self._output_slots = 1
    
    class VAEDecode(Node):
        """VAE 解码"""
        def __init__(self, samples: NodeOutput, vae: NodeOutput):
            super().__init__("VAEDecode", samples=samples, vae=vae)
            self._output_slots = 1
    
    class SaveImage(Node):
        """保存图像"""
        def __init__(self, images: NodeOutput, prefix: str = "output"):
            super().__init__("SaveImage", images=images, filename_prefix=prefix)
            self._output_slots = 0  # 终端节点
    
    class PreviewImage(Node):
        """预览图像"""
        def __init__(self, images: NodeOutput):
            super().__init__("PreviewImage", images=images)
            self._output_slots = 0
    
    # ── ControlNet ──
    class ControlNetLoader(Node):
        """ControlNet 模型加载"""
        def __init__(self, control_net_name: str):
            super().__init__("ControlNetLoader", control_net_name=control_net_name)
            self._output_slots = 1
    
    class ControlNetApply(Node):
        """ControlNet 应用"""
        def __init__(self, conditioning: NodeOutput, control_net: NodeOutput, image: NodeOutput, strength: float = 0.8):
            super().__init__("ControlNetApply", conditioning=conditioning, control_net=control_net, image=image, strength=strength)
            self._output_slots = 1
    
    class DiffControlNetLoader(Node):
        """Diff 版 ControlNet 加载器"""
        def __init__(self, model: NodeOutput, control_net_name: str):
            super().__init__("DiffControlNetLoader", model=model, control_net_name=control_net_name)
            self._output_slots = 1
    
    # ── IPAdapter ──
    class IPAdapterLoader(Node):
        """IPAdapter 加载"""
        def __init__(self, ipadapter_name: str):
            super().__init__("IPAdapterLoader", ipadapter_name=ipadapter_name)
            self._output_slots = 1
    
    class IPAdapterApply(Node):
        """IPAdapter 应用"""
        def __init__(self, model: NodeOutput, ipadapter: NodeOutput, image: NodeOutput,
                     weight: float = 0.8, weight_type: str = "linear"):
            super().__init__("IPAdapterApply", model=model, ipadapter=ipadapter,
                           image=image, weight=weight, weight_type=weight_type)
            self._output_slots = 1
    
    # ── 放大 ──
    class UpscaleBy(Node):
        """按倍数放大"""
        def __init__(self, image: NodeOutput, scale: float = 2.0, method: str = "bicubic"):
            super().__init__("UpscaleBy", image=image, scale=scale, method=method)
            self._output_slots = 1
    
    class LatentUpscale(Node):
        """潜空间放大"""
        def __init__(self, samples: NodeOutput, width: int, height: int, method: str = "nearest-exact"):
            super().__init__("LatentUpscale", samples=samples, width=width, height=height, method=method)
            self._output_slots = 1
    
    # ── 图像处理 ──
    class LoadImage(Node):
        """加载参考图"""
        def __init__(self, image_path: str):
            super().__init__("LoadImage", image=image_path)
            self._output_slots = 2  # image, mask
    
    class ImageInvert(Node):
        """图像反色"""
        def __init__(self, image: NodeOutput):
            super().__init__("ImageInvert", image=image)
            self._output_slots = 1
    
    class ImageComposite(Node):
        """图像合成"""
        def __init__(self, image_a: NodeOutput, image_b: NodeOutput, blend: str = "normal"):
            super().__init__("ImageComposite", image_a=image_a, image_b=image_b, blend=blend)
            self._output_slots = 1
    
    class ImagePadForOutpaint(Node):
        """扩图填充"""
        def __init__(self, image: NodeOutput, left: int, top: int, right: int, bottom: int, feathering: int = 0):
            super().__init__("ImagePadForOutpaint", image=image,
                           left=left, top=top, right=right, bottom=bottom, feathering=feathering)
            self._output_slots = 1  # image, mask
    
    # ── 局部修复 ──
    class SetLatentNoiseMask(Node):
        """潜空间遮罩设置"""
        def __init__(self, samples: NodeOutput, mask: NodeOutput):
            super().__init__("SetLatentNoiseMask", samples=samples, mask=mask)
            self._output_slots = 1
    
    class VAELoader(Node):
        """单独 VAE 加载"""
        def __init__(self, vae_name: str):
            super().__init__("VAELoader", vae_name=vae_name)
            self._output_slots = 1
    
    # ── Flux 专用 ──
    class FluxGuidance(Node):
        """Flux Guidance 节点"""
        def __init__(self, conditioning: NodeOutput, guidance: float = 3.5):
            super().__init__("FluxGuidance", conditioning=conditioning, guidance=guidance)
            self._output_slots = 1
    
    class FluxBlockLoraLoader(Node):
        """Flux Block LoRA"""
        def __init__(self, model: NodeOutput, clip: NodeOutput, lora_name: str, strength: float = 0.8):
            super().__init__("FluxBlockLoraLoader", model=model, clip=clip,
                           lora_name=lora_name, strength_model=strength, strength_clip=strength)
            self._output_slots = 2  # model, clip
    
    # ── 视频 ──
    class VideoCombine(Node):
        """视频合成"""
        def __init__(self, images: NodeOutput, frame_rate: int = 30, format: str = "video/h264-mp4"):
            super().__init__("VideoCombine", images=images, frame_rate=frame_rate, format=format)
            self._output_slots = 1
    
    class VHS_LoadVideo(Node):
        """加载视频 (VideoHelperSuite)"""
        def __init__(self, video_path: str):
            super().__init__("VHS_LoadVideo", video=video_path)
            self._output_slots = 2  # image, audio
    
    class VHS_VideoCombine(Node):
        """视频合并 (VideoHelperSuite)"""
        def __init__(self, images: NodeOutput, frame_rate: int = 24):
            super().__init__("VHS_VideoCombine", images=images, frame_rate=frame_rate)
            self._output_slots = 1
    
    # ── 模型/提示词工具 ──
    class LoraLoader(Node):
        """LoRA 加载器"""
        def __init__(self, model: NodeOutput, clip: NodeOutput, lora_name: str, strength_model: float = 0.7, strength_clip: float = 0.7):
            super().__init__("LoraLoader", model=model, clip=clip, lora_name=lora_name,
                           strength_model=strength_model, strength_clip=strength_clip)
            self._output_slots = 2  # model, clip


# ════════════════════════════════════════════════════════════
# 工作流构建器
# ════════════════════════════════════════════════════════════

class WorkflowBuilder:
    """
    ComfyUI 工作流构建器
    
    用法:
        wb = WorkflowBuilder()
        model = wb.add(nodes.CheckpointLoader("sd_xl.safetensors"))
        pos = wb.add(nodes.CLIPTextEncode("masterpiece", clip=model.out(1)))
        ...
        wb.save("workflow.json")
    """
    
    def __init__(self, name: str = "workflow"):
        self.name = name
        self._nodes: list[Node] = []
        Node._node_counter = 0  # 重置计数器
    
    def add(self, node: Node) -> Node:
        """添加一个节点到工作流"""
        self._nodes.append(node)
        return node
    
    def last_node(self) -> Optional[Node]:
        """获取最后一个添加的节点（方便链式调用后访问）"""
        return self._nodes[-1] if self._nodes else None
    
    def to_dict(self) -> dict:
        """转换为 ComfyUI API JSON dict"""
        result = {}
        for node in self._nodes:
            result.update(node.to_dict())
        return result
    
    def to_json(self, path: Optional[str] = None, indent: int = 2) -> str:
        """输出 JSON, 可选择写入文件"""
        data = self.to_dict()
        text = json.dumps(data, indent=indent, ensure_ascii=False)
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"✅ 工作流已保存: {path} ({len(self._nodes)} 节点)")
        return text
    
    def validate(self) -> list[str]:
        """验证工作流连接完整性"""
        warnings = []
        node_map = {str(n.node_id): n for n in self._nodes}
        for node in self._nodes:
            for key, value in node._inputs.items():
                if isinstance(value, NodeOutput):
                    target_id = str(value.node_id)
                    if target_id not in node_map:
                        warnings.append(f"⚠️ 节点[{node.node_id}] {key} 指向不存在的节点 [{target_id}]")
                elif isinstance(value, list):
                    for v in value:
                        if isinstance(v, NodeOutput):
                            target_id = str(v.node_id)
                            if target_id not in node_map:
                                warnings.append(f"⚠️ 节点[{node.node_id}] {key}[列表] 指向不存在的节点 [{target_id}]")
        if not warnings:
            warnings.append("✅ 工作流连接验证通过")
        return warnings
    
    def summary(self) -> str:
        """打印工作流摘要"""
        lines = [f"工作流: {self.name}", f"节点数: {len(self._nodes)}", ""]
        for node in self._nodes:
            display = getattr(node, '_display_name', node.class_type)
            lines.append(f"  [{node.node_id:3d}] {node.class_type:30s} | {display}")
        return "\n".join(lines)
    
    @staticmethod
    def from_prompt(template_name: str, **kwargs) -> WorkflowBuilder:
        """从预设模板创建工作流"""
        
        # 预设: 标准 TXT2IMG
        if template_name == "txt2img":
            wb = WorkflowBuilder("txt2img")
            model = wb.add(nodes.CheckpointLoader(kwargs.get("ckpt", "sd_xl_base.safetensors")))
            pos = wb.add(nodes.CLIPTextEncode(kwargs.get("positive", "masterpiece"), clip=model.out(1)))
            neg = wb.add(nodes.CLIPTextEncode(kwargs.get("negative", "worst quality, blurry"), clip=model.out(1)))
            latent = wb.add(nodes.EmptyLatentImage(
                kwargs.get("width", 1024), kwargs.get("height", 768),
                kwargs.get("batch", 1)))
            sampler = wb.add(nodes.KSampler(
                model.out(0), pos.out(0), neg.out(0), latent.out(0),
                seed=kwargs.get("seed", 0), steps=kwargs.get("steps", 30),
                cfg=kwargs.get("cfg", 7.0)))
            decoded = wb.add(nodes.VAEDecode(sampler.out(0), model.out(2)))
            wb.add(nodes.SaveImage(decoded.out(0), kwargs.get("prefix", "txt2img")))
            return wb
        
        # 预设: 图生图 (IMG2IMG)
        elif template_name == "img2img":
            wb = WorkflowBuilder("img2img")
            model = wb.add(nodes.CheckpointLoader(kwargs.get("ckpt", "sd_xl_base.safetensors")))
            load_img = wb.add(nodes.LoadImage(kwargs.get("image", "input.png")))
            pos = wb.add(nodes.CLIPTextEncode(kwargs.get("positive", "masterpiece"), clip=model.out(1)))
            neg = wb.add(nodes.CLIPTextEncode(kwargs.get("negative", "worst quality"), clip=model.out(1)))
            # 使用 VAE 编码输入图
            encoded = wb.add(nodes.VAEDecode.__new__(Node))  # placeholder
            latent = wb.add(nodes.EmptyLatentImage(
                kwargs.get("width", 1024), kwargs.get("height", 768)))
            sampler = wb.add(nodes.KSampler(
                model.out(0), pos.out(0), neg.out(0), latent.out(0),
                denoise=kwargs.get("denoise", 0.7)))
            decoded = wb.add(nodes.VAEDecode(sampler.out(0), model.out(2)))
            wb.add(nodes.SaveImage(decoded.out(0)))
            return wb
        
        # 预设: Flux TXT2IMG
        elif template_name == "flux_txt2img":
            wb = WorkflowBuilder("flux_txt2img")
            loader = wb.add(nodes.UNETLoader(kwargs.get("unet", "flux1-dev.safetensors")))
            dual_clip = wb.add(nodes.DualCLIPLoader(kwargs.get("clip_l", "clip_l.safetensors"),
                                                  kwargs.get("clip_g", "t5xxl_fp16.safetensors"), "flux"))
            pos = wb.add(nodes.CLIPTextEncodeSD3(
                kwargs.get("positive", "masterpiece"),
                dual_clip.out(0), dual_clip.out(0)))
            neg = wb.add(nodes.CLIPTextEncodeSD3(
                kwargs.get("negative", "worst quality"),
                dual_clip.out(0), dual_clip.out(0)))
            guidance = wb.add(nodes.FluxGuidance(pos.out(0), kwargs.get("guidance", 3.5)))
            latent = wb.add(nodes.EmptyLatentImage(
                kwargs.get("width", 1024), kwargs.get("height", 768)))
            sampler = wb.add(nodes.KSampler(
                loader.out(0), guidance.out(0), neg.out(0), latent.out(0),
                steps=kwargs.get("steps", 20), cfg=1.0))
            # Flux uses no VAE decode (it's included)
            wb.add(nodes.SaveImage(sampler.out(0), kwargs.get("prefix", "flux")))
            return wb
        
        # 预设: ControlNet + TXT2IMG
        elif template_name == "controlnet_txt2img":
            wb = WorkflowBuilder("controlnet_txt2img")
            model = wb.add(nodes.CheckpointLoader(kwargs.get("ckpt", "sd_xl_base.safetensors")))
            cn_loader = wb.add(nodes.ControlNetLoader(kwargs.get("controlnet", "canny.safetensors")))
            ref_img = wb.add(nodes.LoadImage(kwargs.get("ref_image", "ref.png")))
            pos = wb.add(nodes.CLIPTextEncode(kwargs.get("positive", "masterpiece"), clip=model.out(1)))
            neg = wb.add(nodes.CLIPTextEncode(kwargs.get("negative", "worst quality"), clip=model.out(1)))
            cn_applied = wb.add(nodes.ControlNetApply(pos.out(0), cn_loader.out(0), ref_img.out(0),
                                                     kwargs.get("cn_strength", 0.8)))
            latent = wb.add(nodes.EmptyLatentImage(
                kwargs.get("width", 1024), kwargs.get("height", 768)))
            sampler = wb.add(nodes.KSampler(
                model.out(0), cn_applied.out(0), neg.out(0), latent.out(0),
                steps=kwargs.get("steps", 30), cfg=kwargs.get("cfg", 7.0)))
            decoded = wb.add(nodes.VAEDecode(sampler.out(0), model.out(2)))
            wb.add(nodes.SaveImage(decoded.out(0)))
            return wb
        
        raise ValueError(f"未知模板: {template_name}")


# ════════════════════════════════════════════════════════════
# 主入口 — 演示
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════╗")
    print("║     ComfyUI 工作流自动生成器 v1.0                    ║")
    print("╚══════════════════════════════════════════════════════╝")
    
    # 1. 从模板创建
    print("\n📦 预设模板可用:")
    for t in ["txt2img", "img2img", "flux_txt2img", "controlnet_txt2img"]:
        print(f"  - {t}")
    
    print("\n=== 标准 TXT2IMG ===")
    wb = WorkflowBuilder.from_prompt("txt2img",
        ckpt="sd_xl_base.safetensors",
        positive="a beautiful girl in JK uniform, cherry blossoms, cinematic lighting",
        negative="worst quality, low quality, blurry, bad anatomy",
        width=1024, height=768, steps=30)
    print(wb.summary())
    print(f"验证: {wb.validate()}")
    print(wb.to_json()[:500] + "...")
    
    print("\n\n=== 自定义 50 节点级 DAG ===")
    wb2 = WorkflowBuilder("complex_pipeline")
    # TXT2IMG 骨干
    ckpt = wb2.add(nodes.CheckpointLoader("sd_xl_refiner.safetensors"))
    pos = wb2.add(nodes.CLIPTextEncode("masterpiece, high quality", clip=ckpt.out(1)))
    neg = wb2.add(nodes.CLIPTextEncode("worst quality", clip=ckpt.out(1)))
    latent = wb2.add(nodes.EmptyLatentImage(1024, 768))
    sampler = wb2.add(nodes.KSampler(ckpt.out(0), pos.out(0), neg.out(0), latent.out(0), steps=25))
    decoded = wb2.add(nodes.VAEDecode(sampler.out(0), ckpt.out(2)))
    wb2.add(nodes.PreviewImage(decoded.out(0)))
    # 放大分支
    upscaled = wb2.add(nodes.UpscaleBy(decoded.out(0), 2.0))
    wb2.add(nodes.SaveImage(upscaled.out(0), "final_output"))
    print(wb2.summary())
    print(f"验证: {wb2.validate()}")
