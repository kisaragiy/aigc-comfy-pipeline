# 本地 ComfyUI 工作流地图

> 路径: C:\DrawingLive\ComfyUI\user\default\workflows\

## 目录结构

| 目录 | 数量 | 用途 |
|------|------|------|
| **01_文生图** | 3 | 文本生成图片 |
| **02_图生图** | 3 | 图片转图片 |
| **03_二次修图** | 3 | 修图/放大/面部修复 |
| **04_分镜静帧** | 3 | 漫画分镜/静帧生成 |
| **05_视频** | 3 | Wan2.2 视频生成 |
| **06_配音** | 3 | TTS 配音相关 |
| **07_批量与QC** | 3 | 批量处理+质检 |
| **08_高级多模态** | 2 | VLM/高级多模态 |

## 特殊工作流

| 文件 | 用途 |
|------|------|
| `anima/` | Anima Base 动漫生成 (新T0模型) |
| `manju_seedance_api` | Seedance API 视频生成 |
| `manju_shopping` | 电商场景 |
| `manju_standing` | 角色立绘 |
| `manju_wan22` | Wan2.2 视频 |
| `urban_rift_*` | 都市裂隙系列 (分镜/视频) |
| `SCAIL动作迁移...json` | 动作迁移到另一角色 |
| `参考图融合.json` | 多参考图融合 |
| `换脸Flux2Klein...json` | Flux.2 Klein 换脸 |
| `李瑟钰*.json` | 角色专属工作流 |
| `workflow_caster_tts_ollama.json` | TTS 配音工作流 |
| `workflow_knives_lora_sdxl_ipadapter.json` | LoRA+IPAdapter |
| `一致性练习.json` | 角色一致性训练 |
| `银河与黑龙.json` | 灭世级史诗长图生成 |

## 与 workshop 关联

```bash
# workshop create 命令对应文生图
workshop create "1girl, silver_hair..." --engine sdxl

# 本地工作流可直接在 ComfyUI 中 Load
# 先打开 ComfyUI，然后 Load → 选择对应 json
```
