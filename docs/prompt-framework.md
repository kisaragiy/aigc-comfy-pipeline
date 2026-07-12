# Prompt 工程框架 — 六维度构图法

> 当向 Ollama / LLM 请求生成 SDXL / Flux 提示词时，按以下六维度组织输入，确保输出结构完整、风格可控。

---

## 六维架构总览

```
[画风定位] + [主体细节] + [环境与氛围] + [光影魔法] + [镜头语言] + [质量修饰词]
```

每个维度用逗号分隔，组合成一条完整的英文 danbooru 风格标签串。

---

## 维度一：画风定位

定义整体视觉风格基调。

| 风格 | 标签示例 |
|------|----------|
| 厚涂 | `painterly style, thick brush strokes, oil painting texture` |
| 虚幻 5 渲染 | `unreal engine 5 render, octane render, cinematic` |
| 胶片感 | `film grain, kodak portra 400, analog photography, warm tones` |
| 写实动漫 | `anime style, realistic shading, detailed anime, semi-realistic` |
| 赛璐璐 | `cel shading, flat colors, crisp lines, anime screentone` |
| 水彩 | `watercolor style, soft edges, paper texture, light washes` |
| 像素风 | `pixel art, retro game, 8-bit, dithering` |
| 概念设计 | `concept art, rough sketch, design sheet, turn around` |

---

## 维度二：主体细节

描述角色的神态、动作、材质、眼神情绪。

### 神态 / 表情

| 情绪 | 标签 |
|------|------|
| 微笑 | `smile, gentle smile, warm expression` |
| 严肃 | `serious expression, stern look, intense stare` |
| 忧郁 | `sad expression, melancholic, teary eyes, looking away` |
| 惊讶 | `surprised expression, wide eyes, open mouth` |
| 自信 | `confident smirk, smug, arrogant look, raised eyebrow` |
| 专注 | `focused expression, concentrated, determined look` |

### 动作 / 姿势

| 姿势 | 标签 |
|------|------|
| 站姿 | `standing, full body, straight posture` |
| 坐姿 | `sitting, cross-legged, on chair` |
| 战斗 | `fighting pose, dynamic action, mid-air, weapon drawn` |
| 奔跑 | `running, motion blur, dynamic angle` |
| 回眸 | `looking back, over shoulder, looking at viewer` |

### 材质描写

| 材质 | 标签 |
|------|------|
| 丝绸 | `silk dress, glossy fabric, smooth texture, reflective` |
| 皮革 | `leather jacket, matte finish, stitched details` |
| 金属 | `metallic armor, polished steel, reflective surface, scratches` |
| 透明 | `transparent fabric, sheer, see-through, lace` |
| 毛绒 | `fluffy, soft fur, wool sweater, fuzzy texture` |

### 眼神情绪

```
detailed eyes, expressive eyes, eye catchlight, 
pupil reflection, defined eyelashes, symmetrical eyes
```

---

## 维度三：环境与氛围

| 元素 | 标签 |
|------|------|
| 城市夜景 | `city street at night, neon signs, wet pavement reflection, street lamps` |
| 自然风光 | `mountain landscape, sunset sky, clouds, forest path, golden hour` |
| 室内 | `cozy room, warm lighting, wooden floor, bookshelf background` |
| 科幻 | `sci-fi corridor, holographic displays, metallic walls, blue ambient light` |
| 废墟 | `ruins, overgrown vines, broken pillars, moss, abandoned` |
| 季节 | `spring cherry blossoms, autumn leaves, snowy winter, summer beach` |
| 天气 | `rain, heavy rain, rain puddles, mist, fog, cloudy sky, clear sky` |
| 微粒 | `dust particles, floating pollen, fireflies, snowflakes, cherry blossom petals` |

---

## 维度四：光影魔法

| 效果 | 标签 |
|------|------|
| 逆光 | `backlighting, rim light, silhouette, sun flare, golden outline` |
| 丁达尔效应 | `god rays, volumetric lighting, light beams through clouds` |
| 霓虹映射 | `neon lighting, colorful reflection on face, cyberpunk lighting` |
| 侧光 | `side lighting, dramatic shadows, half face shadow, chiaroscuro` |
| 顶光 | `top lighting, harsh shadows, portrait lighting` |
| 烛光 | `candlelight, warm orange glow, flickering light, soft shadows` |
| 舞台聚光 | `spotlight, center stage lighting, dramatic contrast` |

---

## 维度五：镜头语言

### 景别

| 景别 | 标签 |
|------|------|
| 特写 | `close-up, face close-up, extreme close-up, detailed face` |
| 中景 | `cowboy shot, upper body, waist up` |
| 半身 | `medium shot, half body, from waist up` |
| 全身 | `full body, full shot, from feet to head` |
| 远景 | `wide shot, long shot, establishing shot, landscape` |

### 焦距 / 镜头

| 效果 | 标签 |
|------|------|
| 浅景深 | `bokeh background, shallow depth of field, blurred background` |
| 广角 | `wide angle lens, fisheye, perspective distortion, dynamic angle` |
| 长焦 | `telephoto lens, compressed background, flat perspective` |
| 鱼眼 | `fisheye lens, extreme wide angle, curved edges` |
| 微距 | `macro shot, extreme close-up, detailed texture` |

### 机位

| 机位 | 标签 |
|------|------|
| 平视 | `eye level, straight on, front view` |
| 俯视 | `from above, top-down view, bird's eye view, overhead` |
| 仰视 | `from below, low angle, looking up, worm's eye view` |
| 侧视 | `side view, profile, from the side` |
| 过肩 | `over shoulder, POV, third person view` |

---

## 维度六：质量修饰词

```text
masterpiece, best quality, ultra detailed, high resolution, 
8k, 4k, detailed background, sharp focus, intricate details, 
cinematic lighting, professional, highres, highly detailed
```

负面修饰词（negative prompt 通用模板）：

```text
worst quality, low quality, blurry, jpeg artifacts, bad anatomy, 
extra limbs, deformed hands, extra fingers, missing fingers, 
bad face, duplicate, watermark, text, logo, 
photorealistic, 3d render, western cartoon, ugly, deformed
```

---

## 组合示例

### 输入：`赛博朋克少女，雨中，半身像，紫色调`

```text
masterpiece, best quality, ultra detailed,
[画风] anime style, cyberpunk aesthetic, vibrant neon colors,
[主体] 1girl, detailed face, wet hair, raincoat, cyberpunk outfit, 
       glowing cybernetic implants, serious expression, looking at viewer,
[环境] cyberpunk city street at night, heavy rain, rain puddles, 
       neon signs, holographic ads, wet pavement reflection,
[光影] neon lighting, purple and blue ambient light, 
       colorful reflection on face, volumetric rain lighting,
[镜头] cowboy shot, upper body, shallow depth of field, 
       dynamic angle, cinematic composition,
[质量] 8k, intricate details, sharp focus, cinematic lighting
```

### 组合函数接口

`optimize_prompt()` 接收用户自然语言描述，按六维度生成结构化提示词。
当前实现用模板拼接 + Ollama 辅助补全（见 `comfy_utils.optimize_prompt`）。
