# CLI 参考文档

> 自动生成于 2026-07-12 19:13

AIGC ComfyUI Pipeline v?

---

## `run`

一句话提交 ComfyUI 文生图（自然语言 → Ollama → 出图）

```
usage: run.py [-h] [--raw] [prompt]

一句话提交 ComfyUI 文生图（默认经 Ollama 转写为适用于 SDXL 的英文提示词）。可用环境变量
COMFY_URL、OLLAMA_URL、OLLAMA_MODEL 覆盖默认地址与模型。

positional arguments:
  prompt      一句话画面描述；省略时从标准输入读取

options:
  -h, --help  show this help message and exit
  --raw       跳过 Ollama，将输入整段作为正向提示词（建议写英文；中文效果因底模而异）
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
                         [--count COUNT] [--out OUT]
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
```

---

## `sweep`

参数网格扫描（Flux.2 Klein，自动对比拼图）

```
usage: go_sweep.py [-h] --grid GRID [--model {9b,4b}] [--lora LORA]
                   [--lora-strength LORA_STRENGTH] [--negative NEGATIVE]
                   [--prefix PREFIX] [--raw]
                   [prompt]

参数网格扫描 — Flux.2 Klein（自动对比拼图）

positional arguments:
  prompt                画面描述

options:
  -h, --help            show this help message and exit
  --grid GRID           JSON 网格参数: {"steps":[20,30],"cfg":[1.0,2.0]}
  --model {9b,4b}
  --lora LORA
  --lora-strength LORA_STRENGTH
  --negative NEGATIVE
  --prefix PREFIX
  --raw                 跳过 Ollama
```

---

## `flux`

Flux.2 Klein 文生图（9B/4B，支持 LoRA 注入）

```
usage: go_flux.py [-h] [--raw] [--negative NEGATIVE] [--seed SEED]
                  [--steps STEPS] [--cfg CFG] [--width WIDTH]
                  [--height HEIGHT] [--model {9b,4b}] [--lora LORA]
                  [--lora-strength LORA_STRENGTH] [--sampler SAMPLER]
                  [--scheduler SCHEDULER] [--prefix PREFIX]
                  [prompt]

Flux.2 Klein 文生图 — 程序化构建工作流（9B/4B，支持 LoRA）

positional arguments:
  prompt                画面描述（自然语言，经 Ollama 转写）

options:
  -h, --help            show this help message and exit
  --raw                 跳过 Ollama，prompt 作正向提示词
  --negative NEGATIVE   负向提示词
  --seed SEED           随机种子（-1 自动）
  --steps STEPS         采样步数
  --cfg CFG             CFG 引导强度
  --width WIDTH         输出宽度
  --height HEIGHT       输出高度
  --model {9b,4b}       模型变体
  --lora LORA           LoRA 权重文件名
  --lora-strength LORA_STRENGTH
                        LoRA 权重
  --sampler SAMPLER     采样器
  --scheduler SCHEDULER
                        调度器
  --prefix PREFIX       输出文件名前缀
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

输出画廊（HTML 产出展示）

```
usage: go_gallery.py [-h] [--output OUTPUT] [--serve] [--port PORT]

Output Gallery — 产出画廊

options:
  -h, --help       show this help message and exit
  --output OUTPUT  输出 HTML 路径（默认 outputs/gallery.html）
  --serve          启动 HTTP 服务（浏览器实时查看）
  --port PORT      HTTP 服务端口（默认 8765）
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
Flux.2+Klein+身份一致性引导+单图工作流                   2 ❌      
galgame_heroine_gacha_sdxl                   2 ❌      
galgame_heroine_knives_lora_sdxl             2 ❌      
workflow_knives_lora_sdxl                    8 ✅      CLIPTextEncode, CheckpointLoaderSimple, EmptyLatentImage ... (+4)
workflow_knives_lora_sdxl_ipadapter          2 ❌      
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
用法: python -m agents models list [category]|info <name>|check <workflow_name>|download <url>
```

### `models list`

```
未找到 --help 模型。
处理: 确认 ComfyUI 已安装模型到 COMFY_ROOT/models/ 目录下。
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
  url                   下载 URL（HuggingFace / CivitAI / 直链）

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
