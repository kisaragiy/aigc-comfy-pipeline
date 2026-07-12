# V0.22.0 — 工作流重建工程 实现方案

> **Goal:** 重建 `workflows/` 目录，每个 workflow 为 API 格式、带元数据说明、可被 CLI 直接使用。
>
> **Architecture:** 用 Python 脚本程序化生成 API 格式 JSON 工作流，写入 `workflows/`。

---

## 目标工作流清单

| 文件 | 用途 | 节点数 | 关联 CLI |
|------|------|--------|----------|
| `sdxl_txt2img.json` | SDXL 文生图模板 | 7 | `run` |
| `sdxl_lora.json` | SDXL + LoRA 注入 | 8 | `lora` |
| `sdxl_lora_ipadapter.json` | SDXL + LoRA + IPAdapter 锁脸 | 10+ | `ipa` |
| `sdxl_multi_char.json` | SDXL 多角色同框 + FaceDetailer | 12+ | `multi` |
| `flux_klein_txt2img.json` | Flux.2 Klein 文生图 | 13 | `flux` |
| `flux_klein_lora.json` | Flux.2 Klein + LoRA 注入 | 14 | `flux --lora` |

每个 JSON 包含 `_meta` 字段：
```json
{
  "_meta": {
    "title": "SDXL 文生图",
    "version": "1.0",
    "description": "基础 SDXL 文生图工作流",
    "models": {"checkpoint": "sd_xl_base.safetensors"},
    "custom_nodes": [],
    "cli": "python -m agents run"
  },
  "1": {"class_type": "CheckpointLoaderSimple", ...},
  ...
}
```

---

## Task 1: 创建生成脚本

新建 `scripts/build_workflows.py`，程序化构建所有 API 格式工作流 JSON。

```python
"""程序化构建 API 格式工作流 JSON。"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / "workflows"


def _meta(title, desc, models, cli, nodes=None):
    m = {
        "title": title, "version": "1.0", "description": desc,
        "models": models, "cli": cli,
    }
    if nodes:
        m["custom_nodes"] = nodes
    return {"_meta": m}


def build_sdxl_txt2img():
    """基础 SDXL 文生图。"""
    wf = {}
    wf["1"] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_base.safetensors"}}
    wf["2"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "prompt", "clip": ["1", 1]}}
    wf["3"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "negative", "clip": ["1", 1]}}
    wf["4"] = {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}}
    wf["5"] = {"class_type": "KSampler", "inputs": {"seed": 42, "steps": 28, "cfg": 6.5,
        "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0,
        "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0]}}
    wf["6"] = {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}}
    wf["7"] = {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "sdxl"}}
    meta = _meta("SDXL 文生图", "基础 SDXL 文生图工作流（Ollama 转写 → 提交）",
                 {"checkpoint": "sd_xl_base_1.0.safetensors"}, "python -m agents run")
    return {**meta, **wf}


def build_sdxl_lora():
    """SDXL + LoRA 注入。"""
    wf = {}
    wf["4"] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_base.safetensors"}}
    wf["12"] = {"class_type": "LoraLoader", "inputs": {"model": ["4", 0], "clip": ["4", 1],
        "lora_name": "lora.safetensors", "strength_model": 0.9, "strength_clip": 0.9}}
    wf["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "prompt", "clip": ["12", 1]}}
    wf["7"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "negative", "clip": ["12", 1]}}
    wf["5"] = {"class_type": "EmptyLatentImage", "inputs": {"width": 896, "height": 1152, "batch_size": 1}}
    wf["3"] = {"class_type": "KSampler", "inputs": {"seed": 42, "steps": 28, "cfg": 6.5,
        "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0,
        "model": ["12", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}}
    wf["8"] = {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}}
    wf["9"] = {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "lora"}}
    meta = _meta("SDXL LoRA 文生图", "SDXL + LoRA 角色注入",
                 {"checkpoint": "sd_xl_base_1.0.safetensors", "lora": "lora.safetensors"},
                 "python -m agents lora")
    return {**meta, **wf}


def build_sdxl_ipadapter():
    """SDXL + LoRA + IPAdapter。"""
    wf = {}
    # 先构建基础 LoRA 部分
    wf["4"] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_base.safetensors"}}
    wf["12"] = {"class_type": "LoraLoader", "inputs": {"model": ["4", 0], "clip": ["4", 1],
        "lora_name": "knives_sdxl.safetensors", "strength_model": 0.85, "strength_clip": 0.85}}
    wf["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "prompt", "clip": ["12", 1]}}
    wf["7"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "negative", "clip": ["12", 1]}}
    wf["5"] = {"class_type": "EmptyLatentImage", "inputs": {"width": 896, "height": 1152, "batch_size": 1}}

    # IPAdapter 部分
    wf["10"] = {"class_type": "IPAdapterUnifiedLoader", "inputs": {
        "model": ["12", 0], "preset": "PLUS FACE (portraits)"}}
    wf["11"] = {"class_type": "IPAdapterApply", "inputs": {
        "ipadapter": ["10", 0], "model": ["10", 1],
        "image": "ref_image.png", "weight": 0.48, "end_at": 1.0,
        "weight_type": "prompt is more important"}}

    wf["3"] = {"class_type": "KSampler", "inputs": {"seed": 42, "steps": 28, "cfg": 6.5,
        "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0,
        "model": ["11", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}}
    wf["8"] = {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}}
    wf["9"] = {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "ipa"}}
    meta = _meta("SDXL IPAdapter 锁脸", "SDXL + LoRA + IPAdapter PLUS FACE",
                 {"checkpoint": "sd_xl_base_1.0.safetensors", "lora": "knives_sdxl.safetensors"},
                 "python -m agents ipa", ["IPAdapter"])
    return {**meta, **wf}


def build_sdxl_multi_char():
    """SDXL 多角色同框。"""
    wf = {}
    wf["4"] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_base.safetensors"}}
    wf["12"] = {"class_type": "LoraLoader", "inputs": {"model": ["4", 0], "clip": ["4", 1],
        "lora_name": "knives_sdxl.safetensors", "strength_model": 0.72, "strength_clip": 0.72}}
    wf["13"] = {"class_type": "LoraLoader", "inputs": {"model": ["12", 0], "clip": ["12", 1],
        "lora_name": "caster_sdxl.safetensors", "strength_model": 0.72, "strength_clip": 0.72}}
    wf["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "prompt", "clip": ["13", 1]}}
    wf["7"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "negative", "clip": ["13", 1]}}
    wf["5"] = {"class_type": "EmptyLatentImage", "inputs": {"width": 1344, "height": 896, "batch_size": 1}}
    wf["3"] = {"class_type": "KSampler", "inputs": {"seed": 42, "steps": 32, "cfg": 7.0,
        "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0,
        "model": ["13", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}}
    wf["8"] = {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}}
    meta = _meta("SDXL 多角色同框", "SDXL + 双 LoRA + FaceDetailer",
                 {"checkpoint": "sd_xl_base_1.0.safetensors", "lora": "knives_sdxl.safetensors, caster_sdxl.safetensors"},
                 "python -m agents multi", ["FaceDetailer", "comfyui-impact-pack"])
    return {**meta, **wf}


def build_flux_klein_txt2img():
    """Flux.2 Klein 文生图（同 go_flux.py）。"""
    wf = {}
    wf["1"] = {"class_type": "UNETLoader", "inputs": {"unet_name": "flux-2-klein-9b-fp8.safetensors", "weight_dtype": "default"}}
    wf["2"] = {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_8b_fp8mixed.safetensors", "type": "flux2"}}
    wf["3"] = {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}}
    wf["4"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "prompt", "clip": ["2", 0]}}
    wf["5"] = {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["4", 0]}}
    wf["6"] = {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}}
    wf["7"] = {"class_type": "Flux2Scheduler", "inputs": {"steps": 20, "width": 1024, "height": 1024}}
    wf["8"] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}}
    wf["9"] = {"class_type": "RandomNoise", "inputs": {"noise_seed": 42}}
    wf["10"] = {"class_type": "CFGGuider", "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0], "cfg": 1.0}}
    wf["11"] = {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["9", 0], "guider": ["10", 0],
        "sampler": ["8", 0], "sigmas": ["7", 0], "latent_image": ["6", 0]}}
    wf["12"] = {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["3", 0]}}
    wf["13"] = {"class_type": "SaveImage", "inputs": {"images": ["12", 0], "filename_prefix": "flux_klein"}}
    meta = _meta("Flux.2 Klein 文生图", "Flux.2 Klein 9B fp8 基础文生图",
                 {"unet": "flux-2-klein-9b-fp8.safetensors", "clip": "qwen_3_8b_fp8mixed.safetensors", "vae": "flux2-vae.safetensors"},
                 "python -m agents flux")
    return {**meta, **wf}


def build_flux_klein_lora():
    """Flux.2 Klein + LoRA 注入。"""
    wf = build_flux_klein_txt2img()
    # 移除 _meta 和原连接
    wf.pop("_meta", None)
    # 插入 LoRA 节点（id=14）
    wf["14"] = {"class_type": "LoraLoader", "inputs": {"model": ["1", 0], "clip": ["2", 0],
        "lora_name": "lora.safetensors", "strength_model": 1.0, "strength_clip": 1.0}}
    # 重连 CFGGuider 到 LoRA 输出
    wf["10"]["inputs"]["model"] = ["14", 0]
    # CLIP 也需要重连
    wf["4"]["inputs"]["clip"] = ["14", 1]
    meta = _meta("Flux.2 Klein LoRA", "Flux.2 Klein + LoRA 角色注入",
                 {"unet": "flux-2-klein-9b-fp8.safetensors", "lora": "lora.safetensors"},
                 "python -m agents flux --lora")
    return {**meta, **wf}


BUILDERS = [
    ("sdxl_txt2img", build_sdxl_txt2img),
    ("sdxl_lora", build_sdxl_lora),
    ("sdxl_lora_ipadapter", build_sdxl_ipadapter),
    ("sdxl_multi_char", build_sdxl_multi_char),
    ("flux_klein_txt2img", build_flux_klein_txt2img),
    ("flux_klein_lora", build_flux_klein_lora),
]


def main():
    WORKFLOWS.mkdir(parents=True, exist_ok=True)
    total = 0
    for name, builder in BUILDERS:
        path = WORKFLOWS / f"{name}.json"
        wf = builder()
        path.write_text(json.dumps(wf, indent=2, ensure_ascii=False), encoding="utf-8")
        nid_count = len([v for v in wf.values() if isinstance(v, dict) and "class_type" in v])
        print(f"  {name:30s} {nid_count:2d} nodes  {path.stat().st_size//1024}KB")
        total += 1
    print(f"\n✅ {total} 个工作流已生成")


if __name__ == "__main__":
    main()
```

---

## Task 2: workflows/README.md

```markdown
# ComfyUI 工作流目录

本目录包含预构建的 API 格式 ComfyUI 工作流 JSON，可直接通过 `python -m agents` CLI 提交。

## 工作流列表

| 文件 | 节点 | CLI 命令 | 说明 |
|------|------|----------|------|
| `sdxl_txt2img.json` | 7 | `run` | SDXL 基础文生图 |
| `sdxl_lora.json` | 8 | `lora` | SDXL + LoRA 角色注入 |
| `sdxl_lora_ipadapter.json` | 11 | `ipa` | SDXL + LoRA + IPAdapter 锁脸 |
| `sdxl_multi_char.json` | 8 | `multi` | SDXL 双 LoRA 同框 |
| `flux_klein_txt2img.json` | 13 | `flux` | Flux.2 Klein 9B fp8 文生图 |
| `flux_klein_lora.json` | 14 | `flux --lora` | Flux.2 Klein + LoRA |

## 格式说明

所有 JSON 文件均为 **API 格式**，可直接通过 ComfyUI `/prompt` 端点提交。
每个文件包含 `_meta` 字段记录版本、模型依赖和用途说明。

## 模型依赖

各工作流所需模型见各文件 `_meta.models` 字段。
```

---

## Task 3: AGENTS.md + commit

- 版本 V0.21.0 → V0.22.0
- 项目结构更新

---

## 验证清单

- [ ] `python scripts/build_workflows.py` 生成 6 个 API 格式工作流
- [ ] 每个 JSON 包含 `_meta` 字段
- [ ] `python -m agents workflow list` 显示新增工作流
- [ ] `python -m agents workflow schema sdxl_txt2img` 可识别
