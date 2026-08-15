"""
SDXL 文生图 — 程序化构建工作流 + 质量增强管线。

用法示例:
  python -c "from go_sdxl import build_sdxl_workflow; wf,s=build_sdxl_workflow('test'); print(len(wf))"

支持:
  - CheckpointLoaderSimple（SDXL 底模）
  - LoRA 注入
  - IPAdapter 参考图
  - FaceDetailer 修脸
  - Upscale 1.5x 放大
"""

from __future__ import annotations

import os
import random
from typing import Any

from comfy_utils import AGENTS_DIR, bootstrap_agents_path

bootstrap_agents_path()

# SDXL 底模预设
SDXL_CHECKPOINT = os.environ.get("SDXL_CHECKPOINT", "waiIllustriousSDXL_v160.safetensors")
UPSCALE_MODEL = "RealESRGAN_x4plus.pth"


def nxt(counter: list[int]) -> str:
    """自增节点 ID。"""
    counter[0] += 1
    return str(counter[0])


def build_sdxl_workflow(
    prompt: str,
    *,
    negative_prompt: str = "",
    seed: int = -1,
    steps: int = 28,
    cfg: float = 7.0,
    width: int = 896,
    height: int = 1152,
    checkpoint: str = SDXL_CHECKPOINT,
    lora_name: str | None = None,
    lora_strength: float = 0.8,
    lora_block_weights: str | None = None,
    lora_type: str = "lora",
    sampler: str = "dpmpp_2m",
    scheduler: str = "karras",
    denoise: float = 1.0,
    filename_prefix: str = "pipeline_sdxl",
    # 参考图
    ref_image: str | None = None,
    ip_weight: float = 0.7,
    ip_balance: float = 0.5,   # ⚠️ SDXL 走 InstantID/ControlNet 分支，此参数仅兼容 create.py 传参，不生效
    # 质量增强
    face_detailer: bool = False,
    upscale: float = 1.0,
    # InstantID / ControlNet
    faceid: bool = False,          # InstantID 单图保脸
    controlnet_type: str | None = None,  # "openpose" / "canny" / "depth" / None
    controlnet_strength: float = 0.7,
    **kwargs: Any,
) -> tuple[dict[str, Any], int]:
    """构建 SDXL API 格式工作流。

    Args:
        prompt: 正向提示词
        negative_prompt: 负向提示词
        seed: 随机种子（-1 自动）
        steps: 采样步数
        cfg: CFG 强度
        width/height: 输出尺寸
        checkpoint: 底模文件名
        lora_name: LoRA 权重名（可选）
        lora_strength: LoRA 强度
        lora_block_weights: Block weights（22 逗号分隔），不支持时仅记录日志
        lora_type: LoRA 类型（lora/locon/loha/lokr），影响提示
        sampler/scheduler/denoise: KSampler 参数
        filename_prefix: 输出前缀
        ref_image: 参考图（IPAdapter）
        ip_weight: IPAdapter 权重
        face_detailer: 启用 FaceDetailer
        upscale: 放大倍数（1.0=不放大）

    Returns:
        (workflow_dict, actual_seed)
    """
    cid = [0]
    wf: dict[str, Any] = {}

    # 1. CheckpointLoaderSimple → [MODEL, CLIP, VAE]
    n1 = nxt(cid)
    wf[n1] = {"class_type": "CheckpointLoaderSimple", "inputs": {
        "ckpt_name": checkpoint}}

    model_out: list = [n1, 0]   # MODEL
    clip_out: list = [n1, 1]    # CLIP
    vae_out: list = [n1, 2]     # VAE

    # 2. LoRA（可选）
    if lora_name:
        from lora_manager import parse_block_weights
        # ── 多 LoRA 叠加 ──
        # lora_name 可以是单个 str（兼容旧用法）或 list[{"name":.., "weight":..}]
        lora_list: list[tuple[str, float, str | None]]
        if isinstance(lora_name, str):
            lora_list = [(lora_name, lora_strength, lora_block_weights)]
        elif isinstance(lora_name, list):
            lora_list = []
            for item in lora_name:
                if isinstance(item, dict):
                    nm = item.get("name", "")
                    w = item.get("weight", lora_strength)
                    bw = item.get("block_weights", lora_block_weights if len(lora_list) == 0 else None)
                    if nm:
                        lora_list.append((nm, w, bw))
                elif isinstance(item, str):
                    lora_list.append((item, lora_strength, None))
        else:
            lora_list = [(str(lora_name), lora_strength, lora_block_weights)]

        current_model = [n1, 0]
        current_clip = [n1, 1]
        for li, (ln, lw, lbw) in enumerate(lora_list):
            nl = nxt(cid)
            # Block weights 记录（仅记录元数据）
            if lbw:
                bw_parsed = parse_block_weights(lbw)
                if bw_parsed and len(bw_parsed) >= 22:
                    note = nxt(cid)
                    wf[note] = {"class_type": "Note", "inputs": {
                        "text": f"BLOCK_WEIGHTS[{li}]: {lbw}\nTYPE: {lora_type}"}}
            wf[nl] = {"class_type": "LoraLoader", "inputs": {
                "model": current_model, "clip": current_clip,
                "lora_name": ln,
                "strength_model": lw,
                "strength_clip": lw}}
            current_model = [nl, 0]
            current_clip = [nl, 1]

        model_out = current_model
        clip_out = current_clip

    # 3. CLIPTextEncode（正 + 负）
    n4 = nxt(cid)
    wf[n4] = {"class_type": "CLIPTextEncode", "inputs": {
        "text": prompt, "clip": clip_out}}
    n5 = nxt(cid)
    neg_text = negative_prompt or "worst quality, low quality, blurry, bad anatomy, bad hands"
    wf[n5] = {"class_type": "CLIPTextEncode", "inputs": {
        "text": neg_text, "clip": clip_out}}

    pos_cond = [n4, 0]
    neg_cond = [n5, 0]
    k_model = model_out

    # 4. InstantID（可选）- 单图保脸
    if faceid and ref_image:
        _id_out = _add_instantid(wf, cid, model_out, ref_image, pos_cond, neg_cond)
        if _id_out:
            k_model, pos_cond, neg_cond = _id_out

    # 5. ControlNet（可选）- 姿势/边缘/深度控制（不启用 FaceID 时）
    elif controlnet_type and ref_image:
        _cn_out = _add_controlnet(wf, cid, controlnet_type, ref_image, pos_cond, neg_cond, controlnet_strength)
        if _cn_out:
            pos_cond, neg_cond = _cn_out

    # 6. EmptyLatentImage
    n6 = nxt(cid)
    wf[n6] = {"class_type": "EmptyLatentImage", "inputs": {
        "width": width, "height": height, "batch_size": 1}}

    # 7. KSampler
    seed_actual = seed if seed != -1 else random.randint(1, 2**48 - 1)
    n7 = nxt(cid)
    wf[n7] = {"class_type": "KSampler", "inputs": {
        "seed": seed_actual,
        "steps": steps,
        "cfg": cfg,
        "sampler_name": sampler,
        "scheduler": scheduler,
        "denoise": denoise,
        "model": k_model,
        "positive": pos_cond,
        "negative": neg_cond,
        "latent_image": [n6, 0]}}

    # 8. VAEDecode
    n8 = nxt(cid)
    wf[n8] = {"class_type": "VAEDecode", "inputs": {
        "samples": [n7, 0], "vae": vae_out}}

    # ── 质量增强后处理 ──
    current_image: list = [n8, 0]

    # 9. FaceDetailer（可选）
    if face_detailer:
        n_fd_det = nxt(cid)
        wf[n_fd_det] = {"class_type": "UltralyticsDetectorProvider", "inputs": {
            "model_name": "bbox/face_yolov8m.pt"}}
        n_fd = nxt(cid)
        wf[n_fd] = {
            "class_type": "FaceDetailer",
            "inputs": {
                "image": current_image,
                "model": model_out,
                "clip": clip_out,
                "vae": vae_out,
                "guide_size": 512,
                "guide_size_for": True,
                "max_size": 1024,
                "seed": seed_actual,
                "steps": 12,
                "cfg": 1.5,
                "sampler_name": "euler",
                "scheduler": "sgm_uniform",
                "positive": [n4, 0],
                "negative": [n5, 0],
                "denoise": 0.4,
                "feather": 10,
                "noise_mask": True,
                "force_inpaint": False,
                "bbox_threshold": 0.5,
                "bbox_dilation": 10,
                "bbox_crop_factor": 3.0,
                "bbox_detector": [n_fd_det, 0],
                "drop_size": 10,
                "wildcard": "",
                "cycle": 1,
                "sam_detection_hint": "center-1",
                "sam_dilation": 0,
                "sam_threshold": 0.93,
                "sam_bbox_expansion": 0,
                "sam_mask_hint_threshold": 0.7,
                "sam_mask_hint_use_negative": "False",
            },
        }
        current_image = [n_fd, 0]

    # 10. Upscale（可选）
    if upscale > 1.0:
        n_us_l = nxt(cid)
        wf[n_us_l] = {"class_type": "UpscaleModelLoader", "inputs": {
            "model_name": UPSCALE_MODEL}}
        n_us = nxt(cid)
        wf[n_us] = {"class_type": "ImageUpscaleWithModel", "inputs": {
            "upscale_model": [n_us_l, 0], "image": current_image}}
        current_image = [n_us, 0]

    # 11. SaveImage
    n_save = nxt(cid)
    wf[n_save] = {"class_type": "SaveImage", "inputs": {
        "images": current_image, "filename_prefix": filename_prefix}}

    return wf, seed_actual


def _resolve_ref(ref_image: str) -> str | None:
    """解析参考图路径。确保文件在 ComfyUI input/ 下，返回文件名（供 LoadImage 使用）。"""
    import shutil
    from pathlib import Path

    ref_path = Path(str(ref_image))

    if ref_path.is_file():
        # 完整路径 → 复制到 ComfyUI input/ 并返回文件名
        from comfy_utils import resolve_comfy_root
        comfy_input = Path(str(resolve_comfy_root())) / "input"
        target = comfy_input / ref_path.name

        if ref_path.resolve() != target.resolve() or not target.is_file():
            shutil.copy2(str(ref_path), str(target))

        return ref_path.name

    # 可能是纯文件名，检查 ComfyUI input/ 下是否存在
    from comfy_utils import resolve_comfy_root
    comfy_input = Path(str(resolve_comfy_root())) / "input"
    target = comfy_input / ref_path.name
    if target.is_file():
        return ref_path.name

    return None


def _add_instantid(
    wf: dict[str, Any],
    cid: list[int],
    model_out: list,
    ref_image: str,
    pos_cond: list,
    neg_cond: list,
    weight: float = 0.8,
) -> tuple | None:
    """添加 InstantID 节点链。返回 (model_out, pos_cond, neg_cond) 或 None。"""
    ref_path = _resolve_ref(ref_image)
    if not ref_path:
        return None

    # LoadImage
    n_img = nxt(cid)
    wf[n_img] = {"class_type": "LoadImage", "inputs": {"image": ref_path}}

    # InstantIDModelLoader
    n_model = nxt(cid)
    wf[n_model] = {"class_type": "InstantIDModelLoader", "inputs": {
        "instantid_file": "ip-adapter.bin"}}

    # InstantIDFaceAnalysis
    n_face = nxt(cid)
    wf[n_face] = {"class_type": "InstantIDFaceAnalysis", "inputs": {
        "provider": "CUDA"}}

    # ControlNetLoader (OpenPose for InstantID pose guidance)
    n_cn = nxt(cid)
    wf[n_cn] = {"class_type": "ControlNetLoader", "inputs": {
        "control_net_name": "OpenPoseXL2.safetensors"}}

    # ApplyInstantID
    n_apply = nxt(cid)
    wf[n_apply] = {
        "class_type": "ApplyInstantID",
        "inputs": {
            "instantid": [n_model, 0],
            "insightface": [n_face, 0],
            "control_net": [n_cn, 0],
            "image": [n_img, 0],
            "model": model_out,
            "positive": pos_cond,
            "negative": neg_cond,
            "weight": weight,
            "start_at": 0.0,
            "end_at": 1.0,
        },
    }
    # ApplyInstantID outputs: [MODEL, CONDITIONING, CONDITIONING]
    return [n_apply, 0], [n_apply, 1], [n_apply, 2]


def _add_controlnet(
    wf: dict[str, Any],
    cid: list[int],
    cn_type: str,
    ref_image: str,
    pos_cond: list,
    neg_cond: list,
    strength: float = 0.7,
) -> tuple | None:
    """添加 ControlNet 节点链（姿势/边缘/深度）。返回 (pos_cond, neg_cond) 或 None。"""
    ref_path = _resolve_ref(ref_image)
    if not ref_path:
        return None

    # ControlNet 模型映射
    cn_models = {
        "openpose": "OpenPoseXL2.safetensors",
        "canny": "control-lora-openposeXL2-rank256.safetensors",  # 用 OpenPose 做 Canny 的 fallback
        "depth": "controlnet-depth-sdxl-1.0.safetensors",
    }
    cn_model = cn_models.get(cn_type, "OpenPoseXL2.safetensors")

    # 预处理器映射
    preprocessors = {
        "openpose": ("OpenposePreprocessor", {}),
        "canny": ("CannyEdgePreprocessor", {}),
        "depth": ("DepthPreprocessor", {}),  # 不一定有，用 OpenPose fallback
    }

    # LoadImage
    n_img = nxt(cid)
    wf[n_img] = {"class_type": "LoadImage", "inputs": {"image": ref_path}}

    # 预处理（可选）
    proc_name = preprocessors.get(cn_type, ("OpenposePreprocessor", {}))[0]
    n_proc = nxt(cid)
    try:
        wf[n_proc] = {"class_type": proc_name, "inputs": {"image": [n_img, 0]}}
        proc_out = [n_proc, 0]
    except Exception:
        proc_out = [n_img, 0]  # 降级到原图

    # ControlNetLoader
    n_cn = nxt(cid)
    wf[n_cn] = {"class_type": "ControlNetLoader", "inputs": {
        "control_net_name": cn_model}}

    # ControlNetApply (positive only, strength)
    n_apply = nxt(cid)
    wf[n_apply] = {
        "class_type": "ControlNetApply",
        "inputs": {
            "conditioning": pos_cond,
            "control_net": [n_cn, 0],
            "image": proc_out,
            "strength": strength,
        },
    }
    return [n_apply, 0], neg_cond
