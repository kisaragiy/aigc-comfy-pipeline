# 分镜→视频生成工作流

> 从剧本到逐镜视频的完整管线。配合 video-cinematography skill 使用。

## 工作流概览

```
剧本 (TXT)
    ↓
script-to-storyboard (分镜表)
    ↓ 自动: 镜号 | 景别 | 运镜 | 画面 | Prompt | 时长
    ↓
逐镜生成 (workshop video) × N
    ↓
视频片段 (MP4 × N)
    ↓
后期拼接 (剪辑软件)
    ↓
成片 (MP4)
```

## 步骤1: 写剧本 → 分镜表

输入剧本示例:

```txt
场景: 黄昏海滩
人物: 少女A
动作: 独自走在沙滩上, 眺望远方

镜头1: 远景, 少女走在沙滩上, 海浪声
镜头2: 中景, 少女停下脚步
镜头3: 特写, 少女的侧脸, 风吹动头发
```

→ 用 `script-to-storyboard` skill 转换为结构化分镜表:

```
| 镜号 | 景别 | 运镜 | 画面内容 | Prompt | 帧数 |
|------|------|------|----------|--------|------|
| 01 | 远景 | 固定 | 少女在黄昏海滩独行 | static shot, a girl walking alone on sunset beach, waves, cinematic | 49 |
| 02 | 中景 | 推 | 少女停下 | camera pushes in towards a girl stopping on beach, evening sky | 49 |
| 03 | 特写 | 环绕 | 侧脸吹风 | camera orbiting around girl's face, wind blowing hair, golden hour | 49 |
```

## 步骤2: 批量生成

```bash
# 逐镜生成 (每条一个命令)
workshop video "static shot, a girl walking alone on sunset beach, waves, cinematic, masterpiece" --frames 49 --seed 101

workshop video "camera pushes in towards a girl stopping on beach, evening sky, soft lighting, cinematic" --frames 49 --seed 102

workshop video "camera orbiting around girl's face, wind blowing hair, golden hour light, cinematic portrait" --frames 49 --seed 103
```

## 步骤3: 最佳实践

| 经验 | 说明 |
|------|------|
| 每镜一个 seed | 固定 seed 方便复现 |
| 优先固定镜头 | 最容易出高质量, 人物最稳 |
| 慢速运镜 | "slowly" 关键词大幅提高成功率 |
| 帧数=49 | 6秒够大部分镜头, 太长容易崩 |
| 统一风格 | 所有 Prompt 保持相同的 lighting/color 描述 |
| 简单运镜 | 一次只做一个方向, 不组合 |

## 参考 skill 链

```
分镜任务 → skill_view('video-cinematography') → 运镜选择
         → skill_view('script-to-storyboard') → 分镜表生成
         → workshop video "prompt" → 出片
```
