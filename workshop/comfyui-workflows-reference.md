# ComfyUI 工作流实战参考 — 模型→Prompt→参数映射

> 基于 D:\comyUI-workflows\ 中 424 个工作流提取的最佳实践。

## FLUX 系列 (占比最高)

### FLUX 通用参数

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| Steps | 20-30 | FLUX 不需要很多步，25 步是甜区 |
| CFG | 1.0-4.0 | FLUX 的 CFG 和 SDXL 不同，1-4 之间 |
| Sampler | euler / deis | euler 最稳，deis 细节更多 |

### FLUX 场景 Prompt

**超逼真亚洲美女 (cosplay/写真)**
```
Positive: Short-haired beauty, daily sling at home, film photography,
Renko Kawauchi photography style, half-length portrait
Negative: text, watermark, lowres, bad anatomy
Model: FLUX亚洲超逼真美女V1.safetensors
```

**电商场景/模特**
```
Positive: A woman is sitting on a chair, [product description]
Negative: Deformed, ugly, Low quality
Model: flux1-fill-dev.safetensors 或 epiCRealismXL
```

**动漫二次元 (niji)**
```
Positive: 1girl in a blue dress dancing in the forest with black hair
Negative: (worst quality:2), (low quality:2), lowres, watermark
Model: niji-动漫二次元加强版_f.1d.safetensors
```

**消除 AI 味**
```
核心技巧: 噪波注入 (noise injection) + 低 CFG
Model: flux1-dev-fp8
工作流: flux去除AI味道丨噪波注入.json
```

**FLUX Redux 风格迁移**
```
Positive: 1girl, [风格描述]
Model: flux1-dev-fp8
KSampler: steps=30, cfg=30 (较高), sampler=euler
```

### FLUX 控制类

| 工作流 | 用途 | 关键设置 |
|--------|------|---------|
| Flux ControlNet V2 | 五大控图模式 | 需要特定 ControlNet 节点 |
| ACE++ FFT 换装 | 衣服迁移 | 配合 ACE++ 模型 |
| Flux 电商模特 | 产品+模特融合 | flux1-fill-dev |

---

## Wan2.1 / Wan2.2 视频

### Wan 视频通用参数

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| Steps | 20-30 | 视频生成步数 |
| CFG | 3.5-5.0 | 视频 CFG 比图片低 |
| Sampler | uni_pc / euler | uni_pc 视频专用 |
| Frames | 49-81 | 短=49, 长=81 |

### Wan 视频 Prompt

**图生视频 (I2V)**
```
Prompt with reference:
In the picture, the character rotates the stick in his hand,
the lightning background, the movie texture

Negative(中文):
色调艳丽，过曝，静态，细节模糊不清，字幕，作品，画作，最差质量，
低质量，整体发灰，丑陋的，残缺的，多余的手指，画得不好的手部，
形态畸形的肢体，静止不动的画面

Model: Wan2_1-I2V-14B-480P_fp8 或 Wan2_2-I2V-A14B-LOW
```

**文生视频 (T2V)**
```
Prompt: A wolf standing in the forest / [any scene description]
Negative: 同上中文负向
Model: Wan2_1-T2V-1_3B_fp8
```

**首尾帧视频**
```
Prompt(中文描述场景):
在迷雾缭绕的魔法森林中，一位穿着蓝色梦幻长裙的仙女女孩拉着小提琴，
身后有透明羽翼，周围飞舞着荧光蓝的蝴蝶

Model: Wan2_2-I2V-A14B-LOW + Wan2_2-I2V-A14B-HIGH 双模型
KSampler: steps=20, cfg=3.5, sampler=uni_pc
```

### Wan 视频后处理

```bash
# 修复 (tile LoRA)
workshop video-process / 通义万相视频转视频修复工作流
→ Wan2.1 tile lora 可以修复模糊/崩脸

# 无限循环 (Wan2.2)
→ 09.09 wan2.2视频生成无限循环 工作流
→ 首尾帧衔接实现无缝循环
```

---

## SDXL / Anima / 二次元

### SDXL 动漫

**waiIllustrious 底模**
```
Positive: masterpiece, best quality, 1girl, [描述]
Negative: lowres, bad anatomy, bad hands, worst quality
Steps: 20-25, CFG: 7-9, Sampler: DPM++ 2M Karras
```

**Anima Base (2026.05 新模型, T0 级)**
```
新模型, 二次元生图目前最强
工作流: Anima+Base+V1+动漫生图.json
搭配 Qwen3.5 做漫剧九宫格分镜
工作流: Qwen3.5二次推理+Anima动漫九宫格分镜.json

Prompt 特点:
  - 使用 (worst quality, low quality:1.2) 强负向
  - 配合 "text, logo, watermark" 等额外负向
  - KSampler: steps=30, cfg=5, sampler=er_sde
```

**Ideogram4 (开源版 MJ 美学, 2026.06)**
```
堪称 Midjourney 最佳平替
工作流: Image_Ideogram4_T2I.json
自带 提示词编写指南 文档

Prompt 特点:
  - MJ 风格描述 (cinematic, volumetric lighting, etc.)
  - 需要特定的 Ideogram4 节点
```

### 真实→动漫转换

```
真人转动漫 + 同框合影工作流
Model: flux1-fill-dev + 特定 LoRA
Prompt: Take a picture with the guy on the left
```

---

## 角色一致性 (你最关心的)

从工作流中提取的最佳实践：

```
1. FLUXgym 方法 (01.07)
   - 使用 niji-动漫二次元模型
   - LoRA 绑定角色名 (e.g., "Lala")
   - Prompt: "Lala, 1girl in a blue dress dancing in the forest with black hair"
   
2. 多角度角色卡 (01.07 第二个工作流)
   - "a character sheet, white background, multiple views,
      from multiple angles, visible face, anime-style"
   - 用同一 LoRA 生成不同角度的统一角色
   
3. LoRA 训练 (10.23 芙莉莲完整指南)
   - 工作流: 永恒少女「芙莉莲」LoRA 训练完全指南
   - 从数据准备到参数调优全流程
```

---

## 直接可用命令 (配合你的 workshop CLI)

```bash
# FLUX 动漫
workshop create "1girl, [描述], anime style, masterpiece" \
  --preset anime --steps 25 --seed 42

# FLUX 超逼真
workshop create "Short-haired beauty, film photography, 
  half-length portrait" --preset photoreal --steps 25

# Wan 视频
workshop video "[场景描述]" --frames 49 --fps 8

# Wan 视频 + 负向中文
workshop video "[场景]" --frames 49 \
  --negative "色调艳丽,过曝,静态,细节模糊不清,最差质量"

# 角色 LoRA
workshop train --character "name" --images ./dataset --rank 64
workshop create "name, 1girl, [描述]" --lora "name"
```

## 高质量参考工作流清单

| 工作流文件 | 最佳用途 | 位置 |
|-----------|---------|------|
| FLUX1-小红书追求极致超逼真亚洲美女.json | 写实人像 (亚洲美女) | 02.17 |
| niji-动漫二次元加强版工作流 | 动漫角色一致 | 01.07 |
| FLUX-ACE++换装 | 衣服/产品迁移 | 03.10 |
| Wan2.1+图生视频+Lora | 视频生成 | 03.24 |
| Wan2.2首尾帧工作流 | 首尾帧视频 | 09.09 |
| Qwen3.5+Anima动漫九宫格分镜 | 动漫漫剧 | 2026.05.29 |
| flux去除AI味道丨噪波注入 | 提高真实感 | 12.5 |
| Flux风格参考 | 风格迁移 | 12.7 |
| 全程30秒极速写真 | 快速写真人像 | 03.20 |
| 通义万相视频转视频修复 | 视频修复 | 04.07 |
