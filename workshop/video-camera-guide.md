# AI 视频运镜实战指南 — 分镜→Prompt→Wan2.2

> 把电影级运镜知识翻译成 AI 视频 Prompt，直接用 `workshop video` 出片。

## 核心认知：AI 视频 vs 实拍

```
AI 视频 (Wan2.2/Seedance) 能做的:
  ✅ 推/拉/摇/移/跟/升降/环绕 → 大部分能稳定生成
  ✅ 固定镜头 + 人物运动 → 最容易
  ✅ 慢速均匀运动 → 最稳
  ⚠️ 快速/剧烈运动 → 可能崩
  ⚠️ 手持抖动 → AI 难控制抖动量
  ❌ 多段组合运镜 (推+摇同时) → 不稳定
  
策略: 每个视频只做一种运镜，保证质量
```

## 运镜→Prompt 翻译表

### 1. 推镜头 (Dolly In)

```
效果: 逐渐靠近主体，放大情绪

Wan2.2 Prompt:
"camera slowly pushes in towards [subject],
[scene description], cinematic, smooth motion"

workshop video 示例:
workshop video "camera slowly pushes in towards a girl
standing in cherry blossom park, soft sunlight,
cinematic, masterpiece" --frames 49

最佳场景: 人物情绪爆发、揭示细节、紧张感建立
```

### 2. 拉镜头 (Dolly Out)

```
效果: 逐渐远离主体，揭示环境

Wan2.2 Prompt:
"camera slowly pulls back from [subject],
revealing [environment], cinematic, wide shot"

workshop video 示例:
workshop video "camera slowly pulls back from a woman
sitting alone, revealing empty train station,
melancholic atmosphere, cinematic" --frames 49

最佳场景: 结尾收束、孤独感、环境交代
```

### 3. 横摇 (Pan)

```
效果: 水平扫描环境

Wan2.2 Prompt:
"camera panning right across [scene],
discovering [elements], smooth tracking shot"

workshop video 示例:
workshop video "camera panning right across
ancient temple courtyard, cherry blossoms falling,
cinematic, ambient lighting" --frames 65

最佳场景: 环境展示、空间连接、多人场景
```

### 4. 平移跟拍 (Tracking/Follow)

```
效果: 平行跟随移动主体

Wan2.2 Prompt:
"camera tracking alongside [subject walking/running],
[environment], dolly shot, cinematic movement"

workshop video 示例:
workshop video "camera tracking alongside a girl
walking through market street, vibrant atmosphere,
cinematic tracking shot" --frames 65
```

### 5. 环绕镜头 (Orbit)

```
效果: 围绕主体旋转

Wan2.2 Prompt:
"camera orbiting around [subject],
[environment], slow rotation, cinematic 360 view"

workshop video 示例:
workshop video "camera orbiting around a dancer
on stage, spotlight, slow elegant rotation,
cinematic, smooth" --frames 49
```

### 6. 升降镜头 (Crane Up/Down)

```
效果: 垂直升降，宏大/渺小

Wan2.2 Prompt:
"camera rising up from [subject],
revealing vast [landscape], crane shot, epic scale"

workshop video 示例:
workshop video "camera rising up from a warrior
standing on cliff, revealing vast mountain range,
epic cinematic, golden hour" --frames 81
```

### 7. 俯仰 (Tilt)

```
效果: 上下扫视

Wan2.2 Prompt:
"camera tilting up from [feet] to [face] of [subject],
revealing full figure, slow cinematic tilt"

workshop video 示例:
workshop video "camera tilting up from feet to face
of a woman in red dress, elegant reveal shot,
cinematic lighting" --frames 49
```

### 8. 固定镜头 (Static)

```
效果: 画面静止，主体运动

Wan2.2 Prompt:
"static shot, [subject] [action] in frame,
[environment], cinematic composition"

workshop video 示例:
workshop video "static shot, a girl playing violin
in sunset field, wind blowing hair,
cinematic composition, masterpiece" --frames 49
```

## 景别 Prompt 速查

| 景别 | Prompt 关键词 | 适合 |
|------|-------------|------|
| 远景 (Wide) | `wide shot, full body, distant view` | 环境交代 |
| 中景 (Medium) | `medium shot, waist up` | 日常/对话 |
| 近景 (Close-up) | `close up shot, face focus` | 情绪表现 |
| 特写 (CU) | `extreme close up, eyes/ hands` | 细节强化 |

## 分镜→视频实战流程

```
步骤1: 写剧本 → 拆分为 N 个镜头
步骤2: 每个镜头选一种运镜 (不要组合)
步骤3: 用上面的模板写 Wan2.2 Prompt
步骤4: workshop video 逐条生成
步骤5: 后期拼接 (视频编辑软件)
```

### 示例: 30 秒短片分镜

```
镜号 | 景别 | 运镜 | Prompt
01 | 远景 | 推镜头 | camera slowly pushes in towards a castle on the hill, morning mist, cinematic, establishing shot
02 | 中景 | 横摇 | camera panning right across a knight preparing sword, torchlight, medieval atmosphere
03 | 近景 | 固定 | static shot, knight putting on helmet, determined expression, dramatic lighting
04 | 全景 | 跟拍 | camera tracking alongside knight walking through gate, sunrise behind, heroic mood
05 | 特写 | 环绕 | camera orbiting around knight's sword, sunlight reflecting, epic cinematic
```

## 常见问题

```
Q: 运镜太快/太慢怎么办?
A: 改 frames 参数: 49帧≈6秒(适中), 81帧≈10秒(慢速)
   运镜描述加 "slowly" / "smooth" 控制速度

Q: 人物崩脸怎么办?
A: 用固定镜头或慢速推/拉, 快速运动最容易崩
   不要用复杂的组合运镜

Q: 视频不连贯怎么办?
A: 每个镜头单独生成, 后期用视频编辑软件拼接
   AI 还不能完美做多镜头连续叙事
```
