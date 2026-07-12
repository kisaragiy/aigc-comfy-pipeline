# ComfyUI 工作流目录

本目录包含预构建的 **API 格式** ComfyUI 工作流 JSON，可直接通过 `python -m agents` CLI 提交到 ComfyUI。
所有文件由 `scripts/build_workflows.py` 程序化生成。

> ⚠️ 旧版 UI 格式工作流已移入 `archive/` 子目录，可通过 `python -m agents workflow convert` 转为 API 格式。

## 工作流列表

| 文件 | 节点 | CLI 命令 | 说明 |
|------|------|----------|------|
| `sdxl_txt2img.json` | 7 | `python -m agents run` | SDXL 基础文生图 |
| `sdxl_lora.json` | 8 | `python -m agents lora` | SDXL + LoRA 角色注入 |
| `sdxl_lora_ipadapter.json` | 10 | `python -m agents ipa` | SDXL + LoRA + IPAdapter 锁脸 |
| `sdxl_multi_char.json` | 9 | `python -m agents multi` | SDXL 双 LoRA 同框 |
| `flux_klein_txt2img.json` | 13 | `python -m agents flux` | Flux.2 Klein 9B fp8 文生图 |
| `flux_klein_lora.json` | 14 | `python -m agents flux --lora` | Flux.2 Klein + LoRA 注入 |

## 格式说明

所有 JSON 文件均为 **API 格式**（扁平 `node_id → {class_type, inputs}` 结构），可直接通过 ComfyUI `/prompt` 端点提交。

每个文件包含 `_meta` 字段：

```json
{
  "_meta": {
    "title": "SDXL 文生图",
    "version": "1.0",
    "description": "基础 SDXL 文生图工作流",
    "models": {"checkpoint": "sd_xl_base_1.0.safetensors"},
    "cli": "python -m agents run"
  },
  "1": {"class_type": "CheckpointLoaderSimple", ...}
}
```

## 模型依赖

各工作流所需的具体模型文件名见各 JSON 文件的 `_meta.models` 字段。

### SDXL 工作流所需模型

| 模型 | 文件 | 目录 |
|------|------|------|
| SDXL 底模 | `sd_xl_base_1.0.safetensors` | `models/checkpoints/` |
| Knives LoRA | `knives_sdxl.safetensors` | `models/loras/` |
| Caster LoRA | `caster_sdxl.safetensors` | `models/loras/` |
| 参考图 | `knives_face_ref.png` | `ComfyUI/input/` |

### Flux.2 Klein 工作流所需模型

| 模型 | 文件 | 目录 |
|------|------|------|
| UNET | `flux-2-klein-9b-fp8.safetensors` | `models/diffusion_models/` |
| CLIP | `qwen_3_8b_fp8mixed.safetensors` | `models/text_encoders/` |
| VAE | `flux2-vae.safetensors` | `models/vae/` |

## 自定义节点依赖

各工作流所需的自定义节点见各 JSON 文件的 `_meta.custom_nodes` 字段。
可通过 ComfyUI Manager 或 `comfy node install <name>` 安装。
