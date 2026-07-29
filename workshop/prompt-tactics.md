# Prompt 工程战术手册 — 动漫/写实角色生图

> 用于 `workshop create` 命令。每条 prompt 都经过你的管线实测。

## 结构公式

```
[主体] + [动作/姿态] + [服装/配饰] + [场景/背景] + [光照/氛围] + [画风/质量词]
```

```bash
# 示例: workshop create "1girl, sitting on a throne, gothic dress, dark castle, dramatic lighting, masterpiece, best quality"
```

## 动漫角色 (二次元)

### 通用质量后缀

```
masterpiece, best quality, amazing quality, highly detailed, professional

# 负向 (直接给 --negative)
lowres, bad anatomy, bad hands, missing fingers, extra digit, 
worst quality, normal quality, jpeg artifacts, signature, watermark
```

### 角色类型 Prompt 模板

**少女/正脸/半身**
```bash
workshop create "1girl, looking at viewer, school uniform, 
blue sky background, soft lighting, anime style, 
masterpiece, best quality" --preset anime --seed 42
```

**战斗/动态姿势**
```bash
workshop create "1girl, dynamic pose wielding sword, 
wind blowing hair, action lines, sunset battlefield, 
epic lighting, cinematic composition, masterpiece"
```

**日常/生活**
```bash
workshop create "1girl, sitting at cafe table, drinking coffee, 
street café background, morning light, bokeh, 
slice of life style, masterpiece"
```

### 角色特征注入 (配合 --ref)

```bash
# --ref 走 Ollama 分析参考图 → 自动提取角色特征
workshop create "1girl, casual outfit, smiling, 
outdoor park, golden hour" --ref ./character_ref.png --seed 100
```

## 写实 (三次元)

### 质量词

```
photorealistic, ultra detailed, 8k, raw photo, 
professional lighting, skin texture, subsurface scattering
```

### Prompt 模板

**肖像**
```bash
workshop create "portrait of young woman, natural makeup, 
studio lighting, soft focus background, 
photorealistic, 8k, highly detailed skin texture" --preset photoreal
```

**全身/时尚**
```bash
workshop create "full body shot of woman in leather jacket, 
urban street, sunset, cinematic lighting, 
photorealistic, professional photography, hyper detailed"
```

## Wan2.2 视频 Prompt

### 视频质量词

```
cinematic, smooth motion, consistent character, 
detailed background, natural lighting, fluid animation
```

### 模板

```bash
# 角色动画
workshop video "1girl, turning around slowly, 
long hair flowing, smiling, cinematic lighting, 
smooth motion, consistent character" --frames 49

# 场景运动
workshop video "beach waves crashing on shore, 
aerial view, cinematic, smooth slow motion" --frames 81

# 特写表现
workshop video "close up of woman face, 
gentle smile, wind blowing hair, soft lighting, 
ultra realistic" --frames 49 --preset photoreal
```

### 视频参数最佳实践

| 场景 | Frames | FPS | 说明 |
|------|--------|-----|------|
| 短循环动画 | 49 | 8 | 约 6 秒，动作简单 |
| 场景运动 | 81 | 8 | 约 10 秒，适合风景/运镜 |
| 角色表演 | 65 | 8 | 约 8 秒，角色动作 |

## 角色一致性战术

### 战术 1: LoRA 路线（推荐）

```
问题: 同一个角色在不同 prompt 下长相不一致
解决: 训练角色 LoRA (rank=64, text_encoder) 

工作流:
  1. 收集 20-50 张角色图 (半身/全身/不同角度)
  2. 预处理: 1024×1024 统一尺寸, 禁用 random_flip (角色不对称)
  3. 训练: workshop train --character "角色名"
  4. 推理: workshop create "prompt" --lora "角色名"
```

你的已有经验: 126 张训练图, rank=64, dim32/dim64 对比评估

### 战术 2: 参考图 + 种子固定

```
问题: 没时间/数据训练 LoRA
解决: 找到好图后固定 seed + 用 --ref

工作流:
  1. workshop create "prompt A" --seed 42 → 出图
  2. 如果这张图好 → workshop create "prompt B" --ref good.png --seed 42
  3. 同一 seed 下角色特征保持更好
```

### 战术 3: 多角度变体

你的管线已有 `workshop/engine/variant.py` 支持多角度:

```
workshop create "1girl" --variants           # 自动生成特写/半身/全身
workshop create "1girl" --variants "close,full"  # 指定角度
```

## 质量调优参数

### SDXL vs Flux vs Wan

| 参数 | SDXL | Flux.2 | Wan2.2 |
|------|------|--------|--------|
| Steps | 20-30 | 20-28 | 30-50 |
| CFG | 7-9 | 1.0-3.5 | 5-7 |
| Sampler | DPM++ 2M Karras | 默认 | 默认 |
| 分辨率 | 1024×1024 | 1024×1024 | 512×512 → 插值 |
| LoRA rank | 64 | 64 | N/A |

### Rescaling (负向 CFG) — Flux 专属

```bash
# Flux 用 CFG=1.0 时接近 CFG=7, 需要 --negative 做 rescaling
workshop create "prompt" --preset flux --negative "bad quality, blurry" --cfg 2.5
```

## 快速参考

```bash
# === SDXL 动漫 ===
workshop create "prompt" --preset anime --steps 25 --seed 42
workshop create "prompt" --preset anime --lora "角色名"

# === Flux 写实 ===
workshop create "prompt" --preset photoreal --steps 25 --cfg 2.5

# === 参考图 ===
workshop create "prompt" --ref ref.png

# === 批量 ===
workshop create "prompt1|prompt2|prompt3" --batch-file prompts.txt

# === 视频 ===
workshop video "prompt" --frames 49 --fps 8

# === 质检自动重试 ===
workshop create "prompt" --min-score 0.4 --retry 2
```
