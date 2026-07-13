# CLI 参考文档

> 自动生成于 2026-07-13

AIGC ComfyUI Pipeline v?

---

## `run`

一句话提交 ComfyUI 文生图（自然语言 → Ollama → 出图）

```
usage: run.py [-h] [--raw] [--negative NEGATIVE] [--seed SEED] [--steps STEPS]
              [--cfg CFG] [--width WIDTH] [--height HEIGHT]
              [--sampler SAMPLER] [--scheduler SCHEDULER] [--preset PRESET]
              [--timeout TIMEOUT] [--model {9b,4b}] [--lora LORA]
              [--lora-strength LORA_STRENGTH] [--prefix PREFIX]
              [--min-score MIN_SCORE] [--retry RETRY] [--no-validate]
              [--video] [--ref REF] [--frames FRAMES] [--fps FPS]
              [--denoise DENOISE]
              [prompt]

一句话提交 ComfyUI 文生图（默认经 Ollama 转写为英文提示词）。 用 --video 切换为视频生成模式。

positional arguments:
  prompt                一句话画面描述；省略时从标准输入读取

options:
  -h, --help            show this help message and exit
  --raw                 跳过 Ollama，将输入整段作为正向提示词
  --negative NEGATIVE   负向提示词
  --seed SEED           随机种子（-1 自动）
  --steps STEPS         采样步数（预设自动）
  --cfg CFG             CFG 引导强度
  --width WIDTH         输出宽度
  --height HEIGHT       输出高度
  --sampler SAMPLER     采样器名称
  --scheduler SCHEDULER
                        调度器名称
  --preset PRESET       质量/视频预设名（自动匹配）
  --timeout TIMEOUT     等待超时秒数
  --model {9b,4b}       Flux 模型变体（仅图片模式）
  --lora LORA           LoRA 权重文件名（仅图片模式）
  --lora-strength LORA_STRENGTH
                        LoRA 权重强度
  --prefix PREFIX       输出文件名前缀（图片模式）
  --min-score MIN_SCORE
                        最低 CLIP 评分（≤0 跳过验证）
  --retry RETRY         质量不合格时最大重试次数
  --no-validate         跳过质量验证
  --video               视频生成模式（Wan2.2）
  --ref REF             参考图路径（I2V 模式）
  --frames FRAMES       视频总帧数（默认 49）
  --fps FPS             视频帧率（默认 15）
  --denoise DENOISE     去噪强度（I2V 默认 0.85）
```

---

## `lora`

角色 LoRA 文生图（Knives / Caster，支持批量）

```
usage: go_knives_lora.py [-h] [--character {caster,knives}] [--outfit OUTFIT]
                         [--pose POSE] [--raw] [--full-raw]
                         [--positive POSITIVE] [--negative NEGATIVE]
                         [--lora LORA] [--lora-strength LORA_STRENGTH]
                         [--ckpt CKPT] [--width WIDTH] [--height HEIGHT]
                         [--steps STEPS] [--cfg CFG] [--prefix PREFIX]
                         [--sd15] [--portrait] [--no-portrait] [--full-body]
                         [--count COUNT] [--out OUT] [--seed SEED]
                         [--preset PRESET] [--min-score MIN_SCORE]
                         [--retry RETRY] [--no-validate]
                         [prompt]

Closers 角色 LoRA 文生图（Knives / Caster，ComfyUI + 可选 Ollama）

positional arguments:
  prompt                服装/场景/姿势等自然语言描述

options:
  -h, --help            show this help message and exit
  --character {caster,knives}
                        角色预设（默认 knives）
  --outfit OUTFIT
  --pose POSE
  --raw                 跳过 Ollama，prompt 作换装 tag
  --full-raw
  --positive POSITIVE
  --negative NEGATIVE
  --lora LORA
  --lora-strength LORA_STRENGTH
  --ckpt CKPT
  --width WIDTH
  --height HEIGHT
  --steps STEPS
  --cfg CFG
  --prefix PREFIX
  --sd15                SD1.5（仅 knives 支持）
  --portrait
  --no-portrait
  --full-body
  --count COUNT         连续提交张数（>1 时等待并复制到 --out）
  --out OUT             批量出图复制目录（默认 C:\DrawingLive\ai生图草稿库）
  --seed SEED           随机种子（-1 自动）
  --preset PRESET       SDXL 质量预设（暂未实现）
  --min-score MIN_SCORE
                        最低 CLIP 评分（≤0 跳过验证）
  --retry RETRY         质量不合格时最大重试次数
  --no-validate         跳过质量验证
```

---

## `ipa`

IPAdapter 锁脸文生图（参考图驱动面部一致性）

```
usage: go_knives_ipadapter.py [-h] [--outfit OUTFIT] [--pose POSE] [--raw]
                              [--full-raw] [--positive POSITIVE]
                              [--negative NEGATIVE] [--lora LORA]
                              [--lora-strength LORA_STRENGTH] [--ckpt CKPT]
                              [--width WIDTH] [--height HEIGHT]
                              [--steps STEPS] [--cfg CFG] [--prefix PREFIX]
                              [--portrait] [--full-body]
                              [--ref-image REF_IMAGE]
                              [--ipa-weight IPA_WEIGHT] [--ipa-end IPA_END]
                              [--ipa-preset IPA_PRESET]
                              [--weight-type {standard,prompt is more important,style transfer}]
                              [--seed SEED] [--preset PRESET]
                              [--min-score MIN_SCORE] [--retry RETRY]
                              [--no-validate]
                              [prompt]

Knives SDXL LoRA + IPAdapter 锁脸文生图

positional arguments:
  prompt                服装/场景/表情等自然语言

options:
  -h, --help            show this help message and exit
  --outfit OUTFIT
  --pose POSE
  --raw                 跳过 Ollama，prompt 作换装 tag
  --full-raw
  --positive POSITIVE
  --negative NEGATIVE
  --lora LORA
  --lora-strength LORA_STRENGTH
  --ckpt CKPT
  --width WIDTH
  --height HEIGHT
  --steps STEPS
  --cfg CFG
  --prefix PREFIX
  --portrait
  --full-body           全身构图（默认半身锁眼）
  --ref-image REF_IMAGE
                        ComfyUI/input 下参考图文件名（默认 knives_face_ref.png）
  --ipa-weight IPA_WEIGHT
                        IPAdapter 权重；默认偏低让 LoRA 瞳孔渐变主导，不像可升到 0.58
  --ipa-end IPA_END     IPAdapter end_at（<1 可略放松锁脸，便于改表情）
  --ipa-preset IPA_PRESET
                        IPAdapterUnifiedLoader 预设
  --weight-type {standard,prompt is more important,style transfer}
                        IPAdapter 权重类型；改表情建议 prompt is more important
  --seed SEED           随机种子（-1 自动）
  --preset PRESET       SDXL 质量预设（暂未实现）
  --min-score MIN_SCORE
                        最低 CLIP 评分（≤0 跳过验证）
  --retry RETRY         质量不合格时最大重试次数
  --no-validate         跳过质量验证
```

---

## `multi`

多角色 LoRA 同图（Knives + Caster + FaceDetailer）

```
usage: go_multi_char_lora.py [-h] [--raw] [--positive POSITIVE]
                             [--negative NEGATIVE] [--knives-lora KNIVES_LORA]
                             [--caster-lora CASTER_LORA]
                             [--lora-strength LORA_STRENGTH] [--width WIDTH]
                             [--height HEIGHT] [--steps STEPS] [--cfg CFG]
                             [--prefix PREFIX] [--no-face-detail]
                             [--seed SEED] [--preset PRESET]
                             [--min-score MIN_SCORE] [--retry RETRY]
                             [--no-validate]
                             [prompt]

多角色 LoRA 同图（Knives + Caster + FaceDetailer）

positional arguments:
  prompt                场景/服装/姿势自然语言

options:
  -h, --help            show this help message and exit
  --raw                 prompt 作为完整正向词
  --positive POSITIVE
  --negative NEGATIVE
  --knives-lora KNIVES_LORA
  --caster-lora CASTER_LORA
  --lora-strength LORA_STRENGTH
  --width WIDTH
  --height HEIGHT
  --steps STEPS
  --cfg CFG
  --prefix PREFIX
  --no-face-detail      保存 VAEDecode 结果，不用 FaceDetailer
  --seed SEED           随机种子（-1 自动）
  --preset PRESET       SDXL 质量预设（暂未实现）
  --min-score MIN_SCORE
                        最低 CLIP 评分（≤0 跳过验证）
  --retry RETRY         质量不合格时最大重试次数
  --no-validate         跳过质量验证
```

---

## `sweep`

参数网格扫描（Flux.2 Klein，自动对比拼图）

```
usage: go_sweep.py [-h] --grid GRID [--type {image,video}] [--model {9b,4b}]
                   [--lora LORA] [--lora-strength LORA_STRENGTH]
                   [--negative NEGATIVE] [--prefix PREFIX] [--raw]
                   [--preset PRESET] [--seed SEED] [--min-score MIN_SCORE]
                   [--retry RETRY] [--no-validate] [--ref REF]
                   [--denoise DENOISE] [--sampler SAMPLER]
                   [--scheduler SCHEDULER]
                   [prompt]

参数网格扫描 — 支持图片(Flux)和视频(Wan2.2)，自动对比拼图，可选质量门禁

positional arguments:
  prompt                画面描述

options:
  -h, --help            show this help message and exit
  --grid GRID           JSON 网格参数: {"steps":[20,30],"cfg":[1.0,2.0]}
  --type {image,video}  扫描类型：image(Flux) / video(Wan2.2)
  --model {9b,4b}
  --lora LORA
  --lora-strength LORA_STRENGTH
  --negative NEGATIVE
  --prefix PREFIX
  --raw                 跳过 Ollama
  --preset PRESET       质量预设名（内置或自定义）
  --seed SEED           随机种子（-1 自动）
  --min-score MIN_SCORE
                        最低 CLIP 评分（≤0 跳过，默认跳过）
  --retry RETRY         质量不合格时最大重试次数
  --no-validate         跳过质量验证
  --ref REF             参考图（视频 I2V 模式）
  --denoise DENOISE     视频去噪强度
  --sampler SAMPLER     视频采样器
  --scheduler SCHEDULER
                        视频调度器
```

---

## `flux`

Flux.2 Klein 文生图（9B/4B，支持 LoRA 注入）

```
usage: go_flux.py [-h] [--raw] [--negative NEGATIVE] [--seed SEED]
                  [--steps STEPS] [--cfg CFG] [--width WIDTH]
                  [--height HEIGHT] [--model {9b,4b}] [--lora LORA]
                  [--lora-strength LORA_STRENGTH] [--sampler SAMPLER]
                  [--scheduler SCHEDULER] [--prefix PREFIX] [--preset PRESET]
                  [--min-score MIN_SCORE] [--retry RETRY] [--no-validate]
                  [prompt]

Flux.2 Klein 文生图 — 程序化构建工作流（9B/4B，支持 LoRA）

positional arguments:
  prompt                画面描述（自然语言，经 Ollama 转写）

options:
  -h, --help            show this help message and exit
  --raw                 跳过 Ollama，prompt 作正向提示词
  --negative NEGATIVE   负向提示词
  --seed SEED           随机种子（-1 自动）
  --steps STEPS         采样步数（预设自动）
  --cfg CFG             CFG 引导强度（预设自动）
  --width WIDTH         输出宽度
  --height HEIGHT       输出高度
  --model {9b,4b}       模型变体
  --lora LORA           LoRA 权重文件名
  --lora-strength LORA_STRENGTH
                        LoRA 权重
  --sampler SAMPLER     采样器（预设自动）
  --scheduler SCHEDULER
                        调度器（预设自动）
  --prefix PREFIX       输出文件名前缀
  --preset PRESET       质量预设（anime/photoreal 等）
  --min-score MIN_SCORE
                        最低 CLIP 评分（≤0 跳过验证）
  --retry RETRY         质量不合格时最大重试次数
  --no-validate         跳过质量验证
```

---

## `control`

ControlNet 引导生图（depth/openpose/softedge/tile/inpaint/lineart）

```
usage: go_control.py [-h] --ref REF
                     [--type {depth,openpose,softedge,tile,inpaint,lineart}]
                     [--strength STRENGTH] [--model {9b,4b,sdxl}]
                     [--negative NEGATIVE] [--seed SEED] [--steps STEPS]
                     [--cfg CFG] [--width WIDTH] [--height HEIGHT] [--raw]
                     [--sampler SAMPLER] [--scheduler SCHEDULER] [--lora LORA]
                     [--lora-strength LORA_STRENGTH] [--prefix PREFIX]
                     [--preset PRESET] [--min-score MIN_SCORE] [--retry RETRY]
                     [--no-validate]
                     [prompt]

ControlNet 引导生图（Depth/OpenPose/SoftEdge/Tile/Inpaint/LineArt）— 默认 Flux 架构

positional arguments:
  prompt                画面描述

options:
  -h, --help            show this help message and exit
  --ref REF             参考图文件名（ComfyUI/input/ 下）
  --type {depth,openpose,softedge,tile,inpaint,lineart}
                        ControlNet 类型
  --strength STRENGTH   ControlNet 强度
  --model {9b,4b,sdxl}  模型架构：9b/4b(Flux) / sdxl
  --negative NEGATIVE   负向提示词
  --seed SEED
  --steps STEPS         采样步数（预设自动）
  --cfg CFG             CFG 引导强度（预设自动）
  --width WIDTH
  --height HEIGHT
  --raw                 跳过 Ollama
  --sampler SAMPLER     采样器（预设自动）
  --scheduler SCHEDULER
                        调度器（预设自动）
  --lora LORA           LoRA 权重文件名
  --lora-strength LORA_STRENGTH
  --prefix PREFIX
  --preset PRESET       质量预设（anime/photoreal 等）
  --min-score MIN_SCORE
                        最低 CLIP 评分（≤0 跳过验证）
  --retry RETRY         质量不合格时最大重试次数
  --no-validate         跳过质量验证
```

---

## `video`

Wan2.2 视频生成（T2V/I2V + 批量 + 预览）

```
usage: go_video.py [-h] [--ref REF] [--frames FRAMES] [--fps FPS]
                   [--width WIDTH] [--height HEIGHT] [--steps STEPS]
                   [--cfg CFG] [--seed SEED] [--negative NEGATIVE] [--raw]
                   [--prefix PREFIX] [--denoise DENOISE] [--sampler SAMPLER]
                   [--scheduler SCHEDULER] [--timeout TIMEOUT]
                   [--preset {quality,balanced,fast,cinematic,quick}]
                   [--count COUNT] [--preview]
                   [prompt]

Wan2.2 视频生成（Text-to-Video / Image-to-Video）

positional arguments:
  prompt                画面描述

options:
  -h, --help            show this help message and exit
  --ref REF             参考图（I2V 模式，文件名）
  --frames FRAMES       总帧数（预设自动）
  --fps FPS             帧率（预设自动）
  --width WIDTH         视频宽度（预设自动）
  --height HEIGHT       视频高度（预设自动）
  --steps STEPS         采样步数（预设自动）
  --cfg CFG             CFG 强度（预设自动）
  --seed SEED
  --negative NEGATIVE   负向提示词
  --raw                 跳过 Ollama
  --prefix PREFIX       输出文件名前缀
  --denoise DENOISE     去噪强度（I2V 默认 0.85，T2V 固定 1.0）
  --sampler SAMPLER     采样器名称（预设自动）
  --scheduler SCHEDULER
                        调度器名称（预设自动）
  --timeout TIMEOUT     等待出图超时秒数（默认 1800=30 分钟）
  --preset {quality,balanced,fast,cinematic,quick}
                        视频预设（quality/balanced/fast/cinematic）
  --count COUNT         批量生成数量（不同 seed，默认 1）
  --preview             快速预览模式（低帧数/低分辨率/低步数/低CFG）
```

---

## `video-process`

视频后处理（GIF/裁剪/变速/拼接）

```
usage: go_video_process.py [-h] [--to-gif] [--trim TRIM] [--speed SPEED]
                           [--concat] [--output OUTPUT] [--recent]
                           [--run-id RUN_ID] [--gif-fps GIF_FPS]
                           [--scale SCALE] [--extract-frames] [--every EVERY]
                           [--count COUNT] [--quality QUALITY]
                           [--output-dir OUTPUT_DIR]
                           [inputs ...]

视频后处理 — GIF / 裁剪 / 变速 / 拼接

positional arguments:
  inputs                输入文件路径或运行 ID

options:
  -h, --help            show this help message and exit
  --to-gif              转换为 GIF
  --trim TRIM           裁剪片段: START-END (如 00:05-00:15)
  --speed SPEED         变速系数: 0.5=慢放, 2.0=快放
  --concat              拼接模式（所有 inputs 拼接为一个视频）
  --output OUTPUT       输出文件路径
  --recent              使用 outputs/ 中最新视频
  --run-id RUN_ID       使用指定运行 ID 的视频
  --gif-fps GIF_FPS     GIF 帧率（默认 10）
  --scale SCALE         缩放目标（如 480:-1, 320:240）
  --extract-frames      从视频中提取帧为 JPG
  --every EVERY         每隔 N 帧提取一帧（与 --count 互斥）
  --count COUNT         均匀提取 N 帧（与 --every 互斥）
  --quality QUALITY     JPEG 质量 1-31（1=最高, 31=最低, 默认 2）
  --output-dir OUTPUT_DIR
                        帧提取输出目录（默认: 输入文件同目录下 _frames 子目录）
```

---

## `validate`

出图质量评估（CLIP score / 崩脸检测 / 图像质量）

```
usage: go_validate.py [-h] --image IMAGE [--prompt PROMPT] [--verbose]
                      [--json]

出图质量评估

options:
  -h, --help       show this help message and exit
  --image IMAGE    图片路径
  --prompt PROMPT  提示词（用于 CLIP 评分）
  --verbose        详细输出
  --json           JSON 输出
```

---

## `abtest`

Prompt A/B 对比测试（同 seed 控制变量）

```
usage: go_abtest.py [-h] --prompts PROMPTS PROMPTS [--seed SEED]
                    [--model {9b,4b}] [--lora LORA]
                    [--lora-strength LORA_STRENGTH] [--steps STEPS]
                    [--cfg CFG] [--raw] [--preset PRESET]
                    [--min-score MIN_SCORE] [--retry RETRY] [--no-validate]

A/B 测试 — Prompt A vs B 同 seed 对比（走质量门禁）

options:
  -h, --help            show this help message and exit
  --prompts PROMPTS PROMPTS
                        两个 prompt（A vs B）
  --seed SEED           统一 seed（-1=随机）
  --model {9b,4b}
  --lora LORA
  --lora-strength LORA_STRENGTH
  --steps STEPS
  --cfg CFG
  --raw
  --preset PRESET       质量预设 (quality/balanced/fast/portrait/anime/photoreal)
  --min-score MIN_SCORE
                        CLIP 评分阈值（0=跳过验证）
  --retry RETRY         不合格时最大重试次数
  --no-validate         强制跳过质量验证
```

---

## `bestof`

多 seed 自动挑优（CLIP 评分排名）

```
usage: go_abtest.py [-h] [--count COUNT] [--model {9b,4b}] [--lora LORA]
                    [--lora-strength LORA_STRENGTH] [--steps STEPS]
                    [--cfg CFG] [--raw] [--preset PRESET]
                    [--min-score MIN_SCORE] [--retry RETRY] [--no-validate]
                    prompt

Best of N — 多 seed 自动挑优（走质量门禁）

positional arguments:
  prompt                画面描述

options:
  -h, --help            show this help message and exit
  --count COUNT         生成张数
  --model {9b,4b}
  --lora LORA
  --lora-strength LORA_STRENGTH
  --steps STEPS
  --cfg CFG
  --raw
  --preset PRESET       质量预设 (quality/balanced/fast/portrait/anime/photoreal)
  --min-score MIN_SCORE
                        CLIP 评分阈值（0=跳过验证）
  --retry RETRY         不合格时最大重试次数
  --no-validate         强制跳过质量验证
```

---

## `caption`

Ollama VL 自动标图（训练数据准备）

```
usage: go_caption.py [-h] --dir DIR --trigger TRIGGER [--model MODEL]
                     [--dry-run]

Ollama VL 自动标图 — 生成训练数据 .txt 标注

options:
  -h, --help         show this help message and exit
  --dir DIR          训练图片目录（会扫描所有 .png .jpg 等）
  --trigger TRIGGER  角色触发词（如 Ha Eun、Knives、Caster）
  --model MODEL      Ollama VL 模型名（默认 qwen3.5:9b）
  --dry-run          预览模式，不实际调用 API
```

---

## `train`

LoRA 训练编排（数据验证 + AutoDL 命令生成）

```
usage: go_train.py [-h] --dir DIR --trigger TRIGGER [--output OUTPUT]
                   [--rank RANK] [--steps STEPS] [--lr LR] [--dry-run]

LoRA 训练编排 — 数据验证 + AutoDL 命令生成

options:
  -h, --help         show this help message and exit
  --dir DIR          训练数据目录（含图片和 .txt 标注）
  --trigger TRIGGER  角色触发词
  --output OUTPUT    输出目录（默认 ./lora_output）
  --rank RANK        LoRA rank
  --steps STEPS      训练步数
  --lr LR            学习率
  --dry-run          仅验证数据，不生成命令
```

---

## `report`

管线验收报告（ComfyUI/模型/workflow/产出全貌）

```
usage: go_report.py [-h] [--json]

管线验收报告

options:
  -h, --help  show this help message and exit
  --json      JSON 格式输出
```

---

## `queue`

ComfyUI 队列管理（list/clear/interrupt/free）

```
usage: go_queue.py [-h] {list,clear,interrupt,free} ...

ComfyUI 队列管理

positional arguments:
  {list,clear,interrupt,free}
    list                查看队列状态
    clear               清空待处理队列
    interrupt           中断当前任务
    free                释放显存

options:
  -h, --help            show this help message and exit
```

### `queue list`

```
usage: go_queue.py list [-h]

options:
  -h, --help  show this help message and exit
```

### `queue clear`

```
usage: go_queue.py clear [-h]

options:
  -h, --help  show this help message and exit
```

### `queue interrupt`

```
usage: go_queue.py interrupt [-h]

options:
  -h, --help  show this help message and exit
```

### `queue free`

```
usage: go_queue.py free [-h] [--all]

options:
  -h, --help  show this help message and exit
  --all       释放所有（包括当前运行）
```

---

## `gallery`

输出画廊（HTML 产出展示，支持视频）

```
usage: go_gallery.py [-h] [--output OUTPUT] [--serve] [--port PORT]
                     [--type {all,image,video}] [--refresh-posters]

Output Gallery — 产出画廊

options:
  -h, --help            show this help message and exit
  --output OUTPUT       输出 HTML 路径（默认 outputs/gallery.html）
  --serve               启动 HTTP 服务（浏览器实时查看）
  --port PORT           HTTP 服务端口（默认 8765）
  --type {all,image,video}
                        过滤类型: all(全部) / image(仅图片) / video(仅视频)
  --refresh-posters     强制重新提取视频海报帧
```

---

## `serve`

REST API 服务（FastAPI，异步作业队列，支持图像/视频）

```
usage: go_serve.py [-h] [--port PORT]

REST API 服务（FastAPI）

options:
  -h, --help   show this help message and exit
  --port PORT  端口
```

---

## `doctor`

一键诊断修复（环境/依赖/模型检查）

```
usage: go_doctor.py [-h] [--fix] [--json]

管线一键诊断修复

options:
  -h, --help  show this help message and exit
  --fix       尝试自动修复
  --json      JSON 格式输出
```

---

## `check`

环境检查（ComfyUI / Ollama 连通性）

```
环境检查:
  ComfyUI (http://127.0.0.1:8188/prompt): ❌ 未连接
    处理: 启动 ComfyUI 或检查环境变量 COMFY_URL
  Ollama  (http://127.0.0.1:11434/api/generate): ❌ 未连接（将自动降级到原始输入模式）
```

---

## `workflow`

工作流模板管理（list / show / schema / check / convert）

```
用法: python -m agents workflow list|show <name>|schema <name>|check <name>|convert <name>
```

### `workflow list`

```
名称                                       节点    API    类型
----------------------------------------------------------------------
Flux.2+Klein+身份一致性引导+单图工作流                   0 ❌      
flux_klein_lora                             14 ✅      CFGGuider, CLIPLoader, CLIPTextEncode ... (+11)
flux_klein_txt2img                          13 ✅      CFGGuider, CLIPLoader, CLIPTextEncode ... (+10)
galgame_heroine_gacha_sdxl                   0 ❌      
galgame_heroine_knives_lora_sdxl             0 ❌      
sdxl_lora                                    8 ✅      CLIPTextEncode, CheckpointLoaderSimple, EmptyLatentImage ... (+4)
sdxl_lora_ipadapter                         10 ✅      CLIPTextEncode, CheckpointLoaderSimple, EmptyLatentImage ... (+6)
sdxl_multi_char                              9 ✅      CLIPTextEncode, CheckpointLoaderSimple, EmptyLatentImage ... (+4)
sdxl_txt2img                                 7 ✅      CLIPTextEncode, CheckpointLoaderSimple, EmptyLatentImage ... (+3)
workflow_knives_lora_sdxl                    8 ✅      CLIPTextEncode, CheckpointLoaderSimple, EmptyLatentImage ... (+4)
workflow_knives_lora_sdxl_ipadapter          0 ❌      
workflow                                     7 ✅      CLIPTextEncode, CheckpointLoaderSimple, EmptyLatentImage ... (+3)
workflow_caster_lora_sdxl                    8 ✅      CLIPTextEncode, CheckpointLoaderSimple, EmptyLatentImage ... (+4)
workflow_multi_char_lora_sdxl               11 ✅      CLIPTextEncode, CheckpointLoaderSimple, EmptyLatentImage ... (+6)
```

### `workflow show`

```
未找到 workflow: --help
```

### `workflow schema`

```
未找到 workflow: --help
```

### `workflow check`

```
未找到 workflow: --help
```

### `workflow convert`

```
未找到 UI 格式 workflow: --help
```

---

## `models`

模型管理（list / info / check / download）

```
用法: python -m agents models list [category] [--disk]|info <name>|check <workflow_name>|check video|download <url>|download video|refresh|prune [--force]
```

### `models list`

```
共 88 个模型 (合计 162190MB):

  📁 animatediff (1) :
    mm_sdxl_v10_beta.ckpt                        

  📁 checkpoint (10) :
    index.bin                                    
    postings.bin                                 
    base_sd15.safetensors                        
    waiIllustriousSDXL_v160.safetensors          
    anima-base-v1.0.safetensors                  
    anima-preview.safetensors                    
    anima-preview2.safetensors                   
    anima-preview3-base.safetensors              
    flux-2-klein-9b-fp8.safetensors              
    wan2.2_ti2v_5B_fp16.safetensors              

  📁 clip (9) :
    t5xxl_fp8_e4m3fn_scaled.safetensors          
    clip-vit-large-patch14.safetensors           
    mistral_3_small_flux2_fp8.safetensors        
    qwen_3_06b_base.safetensors                  
    qwen_3_8b_fp8mixed.safetensors               
    sd_xl_base_1.0.safetensors                   
    t5xxl_fp8_e4m3fn.safetensors                 
    t5xxl_fp8_e4m3fn_scaled.safetensors          
    umt5_xxl_fp8_e4m3fn_scaled.safetensors       

  📁 controlnet (17) :
    control-lora-openposeXL2-rank256.safetensors 
    controlnet-depth-sdxl-1.0.safetensors        
    controlnet-sd-xl-1.0-softedge-dexined.safetensors
    controlnet-tile-sdxl-1.0.safetensors         
    controlnet_inpaint_sdxl1.safetensors         
    diffusion_pytorch_model.safetensors          
    dw-ll_ucoco.pth                              
    dw-ll_ucoco_384.pth                          
    dw-mm_ucoco.pth                              
    dw-ss_ucoco.pth                              
    dw-tt_ucoco.pth                              
    rtm-l_ucoco_256-95bb32f5_20230822.pth        
    rtm-x_ucoco_256-05f5bcb7_20230822.pth        
    rtm-x_ucoco_384-f5b50679_20230822.pth        
    Kataragi_lineartXL-lora128.safetensors       
    noobaiXLControlnet_openposeModel.safetensors 
    OpenPoseXL2.safetensors                      

  📁 ipadapter (18) :
    clip-vit-la
```

### `models info`

```
未找到模型: --help
```

### `models check`

```
未找到 workflow: --help
```

### `models download`

```
usage: python -m agents models download [-h]
                                        [--type {checkpoint,lora,vae,clip,embedding,controlnet,ipadapter,upscale}]
                                        [--name NAME] [--hf-mirror]
                                        [--civitai-token CIVITAI_TOKEN]
                                        [--preview]
                                        url

下载模型到 ComfyUI 目录

positional arguments:
  url                   下载 URL（HuggingFace / CivitAI / 直链），或使用 'video' 下载
                        Wan2.2 模型预设

options:
  -h, --help            show this help message and exit
  --type {checkpoint,lora,vae,clip,embedding,controlnet,ipadapter,upscale}
                        模型类型
  --name NAME           保存文件名（可选）
  --hf-mirror           使用 HF 镜像（hf-mirror.com）
  --civitai-token CIVITAI_TOKEN
                        CivitAI API Token（从 https://civitai.com/user/account
                        获取）
  --preview             预览模式，不实际下载
```

---

## `outputs`

产出管理（list / show / clean）

```
未知的 outputs 子命令: --help
可用: list, show <id>, clean [--days N]
```

### `outputs list`

```
暂无产出记录。
```

### `outputs show`

```
未找到产出: --help
```

### `outputs clean`

```
已清理 0 个旧产出目录。
```

---

## `workshop`

创作工坊 — 自然语言驱动的 AIGC 创作入口。

```
usage: python -m agents workshop <subcommand> [args...]

子命令:
  create  "描述"   — 一句话出图（引擎 → 多张生成 → 质检 → 选最优）
  engine  "描述"   — 测试 prompt 引擎（显示优化后提示词）
  inspect <图片|目录|通配符> — 逐部位质检（支持批量）
  manga   "剧本"   — 漫画/分镜生成
  video   "描述"   — 视频生成
```

### `workshop create`

一句话出图：端到端管线 `NL → Prompt引擎 → generate_with_quality×N → 逐张质检 → 综合排序 → 选最优 → (超分) → (修脸) → Gallery`。

```text
usage: python -m agents workshop create [-h] [--count COUNT] [--style STYLE]
                                        [--ref REF] [--ip-weight IP_WEIGHT]
                                        [--balance BALANCE] [--preset PRESET]
                                        [--preset-define PRESET_DEFINE]
                                        [--preset-file PRESET_FILE]
                                        [--min-score MIN_SCORE] [--retry RETRY]
                                        [--no-inspect] [--preview] [--ollama]
                                        [--output OUTPUT] [--gallery GALLERY]
                                        [--seed SEED] [--open]
                                        [--negative NEGATIVE] [--verbose]
                                        [--clean] [--upscale UPSCALE]
                                        [--restore-face [RESTORE_FACE]]
                                        [--lora LORA] [--lora-strength LORA_STRENGTH]
                                        [--commercial] [--batch-file BATCH_FILE]
                                        [nl_text ...]

参数:
  --count COUNT          生成候选数（默认: 4）
  --style STYLE          画风提示 (anime/anime_commercial/photoreal/cg/cosplay/...)
  --ref REF              参考图路径（ReferenceLatent VAE 视觉参考 + Ollama 文本分析）
                          V0.72+: Flux.2 Klein 原生视觉参考管线
  --ip-weight IP_WEIGHT  参考图影响权重 0~1（默认 0.7，传给 RefLatentController）
  --balance BALANCE      文字/参考注意力平衡 0~1（默认 0.5，0=纯参考 1=纯文字）
  --preset PRESET        质量预设 (quality/commercial/balanced/fast/portrait)
                         使用 --preset-list 查看全部
  --preset-define DEF    自定义预设: "my:steps=35,cfg=7.5;v:steps=20,cfg=5.0"
  --preset-file PATH     从 JSON 文件加载自定义预设
  --min-score SCORE      最低 CLIP 分
  --retry RETRY          失败重试次数
  --no-inspect           跳过质检
  --preview              预览模式（跳过生成，显示引擎推测 + 负向）
  --ollama               使用 Ollama 优化 prompt
  --output OUTPUT        结果输出目录（保存 metadata.json + best.png，自动生成 gallery）
                          metadata.json 含 ref_image/ip_weight/ip_balance + 逐候选信息
  --gallery GALLERY      候选画廊输出目录
  --seed SEED            起始种子（0=随机，固定种子可复现）
  --open                 生成后打开 Gallery 页面（优先）或最优图
  --negative NEGATIVE    负向提示词（不设置时使用风格预设默认值 + 自动 NL 检测）
                          自动检测: "不要模糊"→blurry, "别崩手"→bad hands
  --verbose              详细信息
  --clean                生成前清理输出目录旧文件
  --upscale UPSCALE      超分倍数 (2.0/4.0, 0=不超分)
  --restore-face [MODEL] 修脸模型 (GFPGANv1.4.pth / codeformer-v0.1.0.pth)
  --lora LORA            LoRA 权重文件名（ComfyUI/models/loras/ 下）
  --lora-strength FLOAT  LoRA 强度（默认 1.0）
  --commercial           一键商业图: --style anime_commercial --preset commercial
                          --upscale 2.0 --restore-face GFPGANv1.4.pth
  --batch-file PATH      批量文件路径（每行一条 prompt，空行和 # 注释行跳过）
                          支持 "prompt | ref_path.png" 每行独立参考图
                          支持 --upscale/--restore-face 批量后处理

Gallery 特性 (V0.46-V0.86):
  - 键盘导航: ← → 切换候选，ESC 关闭
  - 下载按钮: Lightbox 右上角 ⬇ 下载当前图片
  - 逐部位质检: Face/L-Eye/R-Eye/Hand/Foot/Blur 彩色标签 (绿≥0.8 黄≥0.3 红<0.3)
  - 滚轮缩放: 鼠标滚轮 0.5x~10x + 拖动平移 + 双击还原
  - 质检 overlay: Lightbox 显示逐部位浮标 + 综合分
  - 主题切换: 右上角 ☀️/🌙 亮色/暗色切换 (localStorage 持久化)
  - 幻灯片: Space 键 3 秒自动轮播
  - 参考图展示: 有 --ref 时顶部显示参考图 + 权重/平衡参数
  - 对比模式: 按 C 或点击 🔍 对比，参考图半透明叠加
  - 一键复制 seed: 卡片 📋 按钮复制种子到剪贴板

示例:
  python -m agents workshop create "银发精灵 森林 商业插画" --commercial
  python -m agents workshop create "银发精灵" --commercial --ref ref.png
  python -m agents workshop create "银发精灵" --lora char.sft --preset commercial
  python -m agents workshop create "校服少女" --style anime --preset quality
  python -m agents workshop create "精灵弓箭手" --count 6 --no-inspect
  python -m agents workshop create "prompt" --ref ref.png --ip-weight 0.5 --balance 0.3
  python -m agents workshop create "prompt" --batch-file prompts.txt --upscale 2.0
  python -m agents workshop create "赛博朋克少女" --preset-define "hd:steps=35,cfg=7.0"
  python -m agents workshop create "银发少女" --open --negative "blurry, watermark"
  python -m agents workshop create "prompt" --preview  # 预览 prompt + 引擎推测
```

### `workshop engine`

测试 Prompt 引擎，显示自然语言优化后的专业提示词及风格/构图/光照推测。

```text
usage: python -m agents workshop engine [-h] [--style STYLE] [--ollama]
                                        [--ref REF] [--list-presets]
                                        nl_text [nl_text ...]

参数:
  --style STYLE    画风提示 (anime/photoreal/cg/...)
  --ollama         使用 Ollama 增强 prompt
  --ref REF        参考图路径（测试角色/画风特征分析）
  --list-presets   列出全部预设

示例:
  python -m agents workshop engine "赛博朋克少女，霓虹雨夜"
  python -m agents workshop engine "古风少女竹林抚琴" --style photoreal
  python -m agents workshop engine "银发少女" --ollama  # 对比模板 vs Ollama
  python -m agents workshop engine "银发少女校服" --ref ref.png  # 测试参考图分析
  python -m agents workshop engine --list-presets  # 列出全部预设
```

### `workshop inspect`

逐部位质检报告：`[脸:ok] [左眼:ok] [右眼:ok] [手:正常] [脚:ok] [模糊:正常]`

```text
|usage: python -m agents workshop inspect [-h] [--verbose] [--annotate] [--open] [--json] image_path

参数:
  --verbose    详细信息（各部位置信度等）
  --annotate   生成标注图（绘制质检结果到图片上，保存为 <图片名>_annotated.png）
  --open       生成后自动打开标注图（仅 --annotate 时有效）
  --json       以 JSON 格式输出结构化的质检结果（适合管道/程序处理）

示例:
  python -m agents workshop inspect output/001.png
  python -m agents workshop inspect output/001.png --verbose
  python -m agents workshop inspect output/001.png --annotate     # 质检 + 视觉标注
  python -m agents workshop inspect output/001.png --annotate --open  # 质检 + 标注 + 打开
  python -m agents workshop inspect output/001.png --json         # JSON 输出
  python -m agents workshop inspect ./outputs/                    # 目录全部图片
  python -m agents workshop inspect "outputs/*.png"               # 通配符

批量模式额外输出：失败原因聚合（⚠️ 脸: 2张 · ⚠️ 手: 1张）
批量模式 --json：输出 JSON 数组 [{path, result}, ...]
```

### `workshop manga`

剧本→分镜表→逐格生图→拼页+台词。

```text
usage: python -m agents workshop manga [-h] [--style STYLE] [--preview]
                                       [--layout LAYOUT] [--char CHAR ...]
                                       [--script-file SCRIPT_FILE]
                                       [--output OUTPUT] [--retry RETRY]
                                       [--sdxl] [--ref REF ...]
                                       [--ip-weight IP_WEIGHT]
                                       [--preset PRESET]
                                       [--upscale UPSCALE]
                                       [--restore-face [RESTORE_FACE]]
                                       script_text [script_text ...]

参数:
  --style STYLE           画风 (默认: anime)
  --preview               预览分镜表 + 面板（含种子/尺寸/Prompt，不生成）
  --layout LAYOUT         拼页布局 (auto/4koma)
  --char "名:服饰:发型:特征"  角色定义 (可重复，支持 1~4 个)
  --script-file FILE       从文件读取剧本（替代命令行参数）
  --output DIR             输出目录（保存拼页 + 逐格图 + metadata.json + 画廊）
  --retry N                每格失败后最大重试次数（默认 0=不重试）
  --sdxl                   使用 SDXL 代替 Flux（更快，支持 LoRA）
  --ref REF                参考图路径: "Alice=path.png"（角色专属）或 "path.png"（全局）
  --ip-weight FLOAT        参考图影响权重 0~1（默认 0.7）
  --preset PRESET          质量预设 (commercial/quality/balanced/fast)
  --upscale UPSCALE        超分倍数 (2.0/4.0, 0=不超分，对拼页生效)
  --restore-face [MODEL]   修脸模型 (GFPGANv1.4.pth / codeformer-v0.1.0.pth)
  script_text              剧本/场景描述

示例:
  python -m agents workshop manga "教室中，两人相对而立。" --preview
  # 默认角色 Knives / Caster，预览完整分镜表 + 面板

  python -m agents workshop manga "森林里的追逐" \
    --char "战士:重甲:金发:巨剑" --char "法师:法袍:银发:魔法书"

  python -m agents workshop manga "精灵与骑士" --output ./manga \
    --char "精灵:银发:精灵耳:蓝瞳" "骑士:铠甲:金发:绿瞳" \
    --ref "精灵=C:/ref_elf.png" "骑士=C:/ref_knight.png" \
    --preset commercial --upscale 2.0 --restore-face
  # 从文件读取剧本

  python -m agents workshop manga "教室中，两人相对而立。" --output ./manga-out
  # 保存拼页 + 逐格图 + metadata.json + gallery.html（面板+拼页+角色信息）
```

### `workshop video`

一句话视频生成（Wan2.2 T2V/I2V）。使用 workshop.video 模块，支持预览和参数控制。

```text
usage: python -m agents workshop video [-h] [--ref REF] [--frames FRAMES] [--fps FPS]
                                        [--seed SEED] [--preset PRESET] [--preview]
                                        [--steps STEPS] [--cfg CFG] [--width WIDTH]
                                        [--height HEIGHT] [--denoise DENOISE]
                                        [--neg NEG] [--output OUTPUT]
                                        [prompt ...]

参数:
  prompt             画面描述（多个词自动拼接）
  --ref REF          参考图路径（I2V 模式）
  --frames FRAMES    帧数（默认 49）
  --fps FPS          帧率（默认 15）
  --seed SEED        随机种子（-1=自动）
  --preset PRESET    视频预设 (cinematic/quality/fast)
  --preview          预览参数不生成
  --steps STEPS      采样步数（默认 30）
  --cfg CFG          CFG scale（默认 7.0）
  --width WIDTH      输出宽度（默认 848）
  --height HEIGHT    输出高度（默认 480）
  --denoise DENOISE  去噪强度（默认 1.0）
  --neg NEG          负向提示词
  --output OUTPUT    输出目录（复制视频到指定目录）

示例:
  python -m agents workshop video "赛博朋克城市，霓虹灯闪烁，雨夜"
  python -m agents workshop video "人物行走" --frames 81 --fps 15
  python -m agents workshop video "人物奔跑" --ref start.png --frames 49
  python -m agents workshop video "城市夜景" --preview       # 预览不生成
  python -m agents workshop video "风景" --output ./video-out  # 输出到目录
```
