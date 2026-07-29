# 生图场景实战手册 — 9 大场景全覆盖

> 每个场景 = 推荐模型 + Prompt 模板 + workshop create 命令 + 工作流路径。
> 数据来源: D:\comyUI-workflows\ 中 424 个工作流 + 你的管线能力。

## 场景总览

| # | 场景 | 推荐模型 | 工作流来源 |
|---|------|---------|-----------|
| 1 | 真人写实 | FLUX dev + epiCRealismXL | 02.17 / 03.20 |
| 2 | 数字人 | Sonic / InfiniteTalk | 04.17 / 2026.03.14 |
| 3 | 商业立绘 | Anima Base / SDXL wai | 2026.05.19 |
| 4 | 漫画/漫剧 | Anima + Qwen3.5 / Kontext | 2026.05.29 / 07.31 |
| 5 | 表情差分 | Qwen-Image-Edit | 2026.01.15 |
| 6 | 同人物换装 | ACE++ FFT / FLUX-Redux | 03.10 / 03.14 |
| 7 | 多人构图 | FLUX-fill / ControlNet | 03.27 / 09.03 |
| 8 | Cosplay 后期 | Kontext / FLUX-fill | 02.14 / 07.31 |
| 9 | 二次元↔真人互转 | Qwen-Image / Kontext | 吴老师合集 |

---

## 1. 真人写实 (Realistic Portraits)

### 推荐组合

```
Model: FLUX亚洲超逼真美女V1.safetensors 或 epiCRealismXL
Workshop preset: photoreal
Steps: 25, CFG: 2.5-3.5 (FLUX) / 6-7 (SDXL)
```

### Prompt 模板

```bash
# 亚洲美女/写真风
workshop create "Short-haired beauty, daily sling at home,
film photography, Renko Kawauchi photography style,
half-length portrait" --preset photoreal --steps 25

# 极致超逼真 (小红书风)
workshop create "young Asian woman, natural makeup,
soft window light, casual outfit, film grain texture,
photorealistic, 8k, skin texture" --preset photoreal

# 快速写真 (30秒极速工作流)
workshop create "woman, portrait, professional lighting,
clean background, fashion look" --preset photoreal --steps 20
```

### 工作流清单

| 文件 | 特点 |
|------|------|
| FLUX1-小红书追求极致超逼真亚洲美女.json | 亚洲美女专精 |
| 全程30秒极速写真.json | 闪电出图 (kohya+flux) |
| AI摄影写真工作流 | 商业级写真人像 |

---

## 2. 数字人 (Digital Human)

### 推荐组合

```
Model: Sonic / InfiniteTalk
类型: 照片→说话/唱歌视频
依赖: 单独的 Sonic 节点
```

### 工作流清单

| 文件 | 功能 |
|------|------|
| Sonic数字人.json | 说话/唱歌/Rap |
| InfiniteTalk 数字人I2V.json | 图片→说话视频 |
| InfiniteTalk 数字人V2V.json | 视频→对口型 |
| wan_S2V无限时长数字人.json | 无限时长数字人 |
| 语音驱动图片说话工作流.json | CG动画配音 |

> 数字人需要运行单独的 Sonic/InfiniteTalk 节点，不在 workshop 管线内。需要单独搭建。

---

## 3. 商业立绘 (Commercial Illustration)

### 推荐组合

```
Model: Anima Base V1 (二次元最强) 或 waiIllustriousSDXL
Workshop preset: anime
Steps: 25-30, CFG: 5-7
```

### Prompt 模板

```bash
# Anima Base (T0级二次元)
workshop create "1girl, fantasy outfit, holding staff,
magical girl pose, detailed background,
masterpiece, best quality, anime style" --preset anime --steps 30

# SDXL waiIllustrious
workshop create "1girl, elegant dress, standing in garden,
detailed illustration, professional artwork,
masterpiece, best quality" --preset anime --steps 25

# 角色三视图 (漫剧角色卡)
workflow: Z-Image-Turbo AI 漫剧角色三视图.json
Prompt: "front view, side view, back view of [character],
character sheet, white background"
```

### 负向 Prompt (通用)

```
(worst quality, low quality:1.2), lowres, blurry,
jpeg artifacts, messy drawing, text, logo, watermark
```

---

## 4. 漫画/漫剧 (Manga/Comic)

### 推荐组合

```
管线: workshop manga + Anima + Qwen3.5
工作流: Qwen3.5二次推理+Anima动漫九宫格分镜.json
```

### 工作流

```bash
# 你的管线已有
workshop manga "剧本" --sdxl        # SDXL 版
workshop manga "剧本" --output DIR   # 指定输出

# 九宫格分镜 (Qwen3.5 + Anima)
工作流 → 自动九宫格 → 逐格生图

# 转绘风格 (Kontext)
工作流: Kontext 100种风格转绘
-> 真人视频→转绘为动漫风格
-> 100 种风格可选
```

---

## 5. 表情差分 (Expression Variations)

### 推荐组合

```
Model: Qwen-Image-Edit 或 FLUX
技巧: 同一人物 + 不同表情描述 + 固定 seed
```

### Prompt 模板

```bash
# 方法1: 同一个 LoRA + 不同表情 Prompt
workshop create "character_name, 1girl, smiling,
happy expression, open mouth" --lora "角色名" --seed 42

workshop create "character_name, 1girl, angry expression,
furrowed brows, glaring" --lora "角色名" --seed 42

workshop create "character_name, 1girl, crying,
sad expression, tears" --lora "角色名" --seed 42

# 方法2: Qwen-Image-Edit 多角度 (含表情变化)
工作流: Qwen Edit2511 智能多角度生成.json
# 输入一张图 → 自动生成不同角度和表情
```

### 技巧

```
seed 固定: 同一 seed + 改表情描述 = 保持脸型一致
LoRA 绑定: 先训练角色 LoRA, 再用不同表情 prompt
```

---

## 6. 同人物换服装 (Outfit Change)

### 推荐组合

```
Model: ACE++ FFT / FLUX-Redux
工作流: 03.10 ACE++FLUX换装 / 03.14 ACE++FFT万物迁移
```

### Prompt 模板

```bash
# ACE++ 换装 (保留人物, 换衣服)
workshop create "1girl wearing [new outfit description],
same person" --ref character.png --preset anime

# FLUX-Redux 换装 (基于参考图换衣)
工作流: 换装换产品电商工作流.json
# 输入: 人物图 + 衣服图 → 输出: 人物穿上衣服

# 电商场景换装
工作流: 电商模特换装工作流（带裁切）.json
# 适合批量跟品
```

### 工作流清单

| 工作流 | 方法 | 适合 |
|--------|------|------|
| FLUX-ACE++换装 | ACE++ 模型 | 动漫/写实均可 |
| ACE_Plus FFT换装 | FFT 快速迁移 | 电商产品 |
| 一键换装换产品电商工作流 | FLUX + ControlNet | 高还原度 |
| FLUX-Redux万物可换 | Redux 风格迁移 | 产品/人物 |

---

## 7. 多人构图 (Multi-Character)

### 推荐组合

```
Model: FLUX-fill (inpainting) 或 FLUX + ControlNet
技巧: 分别生成人物 → 合成 → 重绘
```

### Prompt 模板

```bash
# 方法1: 同框生成 (直接prompt描述多人)
workshop create "1girl and 1boy, standing together,
holding hands, park background, anime style,
masterpiece" --preset anime --seed 42

# 方法2: 真人+动漫合影 (03.27 工作流)
工作流: 真人与动漫角色合影.json
# 输入: 真人照片 + 动漫角色描述
# Prompt: "Take a picture with the guy on the left"

# 方法3: 分别生成→合成→重绘 (推荐)
Step 1: workshop create "1girl, [描述]" --seed 101 --output girl.png
Step 2: workshop create "1boy, [描述]" --seed 102 --output boy.png
Step 3: 用 FLUX-fill 或 PS 合成 → 用 inpainting 修复接缝
```

### 工作流清单

| 工作流 | 方法 |
|--------|------|
| 真人与动漫角色合影.json | 真人+动漫同框 (FLUX-fill) |
| 03 多人图像控制 | ControlNet 多人控制 |

---

## 8. Cosplay 后期 (Cosplay Post-processing)

### 推荐组合

```
Model: FLUX-fill / Kontext
工作流: 02.14 漫展海报COS后期 / 07.31 Kontext转绘
```

### 工作流清单

| 工作流 | 功能 |
|--------|------|
| Cosplay一键换背景(适用性强).json | COS 照片换背景 |
| Kontext 100种风格转绘 | COS 转动漫风格 |
| 产品&角色360°展示.json | 360° 展示 |

```bash
# COS 换背景
workshop create --ref cos_photo.png "elegant castle background,
renaissance painting style" --preset photoreal
```

---

## 9. 二次元↔真人互转 (Anime ↔ Real)

### 推荐组合

```
Model: Qwen-Image / Kontext / FLUX
工作流: 吴老师合集
```

### 工作流清单

| 工作流 | 方向 | 方法 |
|--------|------|------|
| 真人与动漫角色合影.json | 真人+动漫同框 | FLUX-fill |
| Qwen-image超强动漫转真人_真人转动漫洗图工作流 | 双向 | Qwen-Image |
| 动漫真人互转，漫画上色低显存工作流 | 双向 | 低显存 |

```bash
# 真人→动漫 (需要特定节点)
workshop create --ref photo.png "anime style,
studio ghibli aesthetic, masterpiece" --preset anime

# 动漫→真人 (使用 Kontext 转绘)
workshop create --ref anime.png "realistic style,
photorealistic, film lighting" --preset photoreal
```

---

## 快速命令参考

```bash
# 真人写真
workshop create "portrait, [描述]" --preset photoreal

# 动漫立绘
workshop create "1girl, [描述], masterpiece" --preset anime

# 表情差分 (固定 seed + 改表情)
workshop create "name, smiling" --lora "name" --seed 42
workshop create "name, angry" --lora "name" --seed 42

# 换装 (ACE++)
workshop create --ref char.png "wearing [衣服]" --preset anime

# 漫画
workshop manga "剧本" --sdxl

# 漫剧九宫格
# 工作流: Qwen3.5二次推理+Anima动漫九宫格分镜.json

# 真人转动漫
# 工作流: Qwen-image超强动漫转真人_真人转动漫洗图工作流
```
