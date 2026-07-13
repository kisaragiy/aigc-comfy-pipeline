# AIGC ComfyUI Pipeline

> Python 编排 ComfyUI · LoRA 训练 · 批量生图 · 模型管理  
> **工程化工具链** — Python 脚本是产品，生图是产出  
> 作者：张伟强

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](requirements.txt)
![Version](https://img.shields.io/badge/version-v1.0.0-green)

## 定位

**AIGC 工程化管线**。通过 Python 脚本编排 [ComfyUI](https://github.com/comfyanonymous/ComfyUI) REST API，实现自然语言→出图、角色一致性、批量生图、质量自动控制等工作流。

## 能力概览

| 能力 | 命令 | 说明 |
|------|------|------|
| 一句话出图 | `workshop create` | 自然语言 → 引擎转写 → 多张候选 → 质检 → 选最优 |
| 自动优化 | `--auto` | 从质量数据库加载历史最优参数 |
| 多样性保持 | `--variety N` | 多参数风格轮换，防止同质化 |
| 质量自动重试 | `--auto-retry N` | 质检低于阈值时自动微调重试 |
| 质量数据库 | `autopilot --report` | 参数网格扫描 + HTML 质量报告 |
| Gallery 筛选 | `--filter` | 按部位得分/CLIP 分多规则筛选 |
| 参考图引导 | `--ref` | Flux.2 Klein ReferenceLatent |
| 漫画/分镜 | `workshop manga` | 分镜故事板 → 逐格生图 |
| 视频生成 | `workshop video` | 文生视频 + 质量重试 |
| 角色表 | `--cast` | 多角色预设 + 专属 ref |
| 超分修脸 | `--upscale --restore-face` | GFPGAN/CodeFormer 后处理 |
| 一致性验证 | `workshop verify` | 跨图片质检比较 + 波动标记 |
| 面试样张 | `workshop demo` | 5 场景 Gallery + 质量报告 |
| 批量处理 | `--batch-file` | 文件驱动的批量管线 |

## 快速开始

```bash
# 环境安装
pip install -r requirements.txt

# 一句话出图
python -m agents workshop create "银发精灵 Alice，森林，逆光" --count 4

# 带参考图 + 自动优化
python -m agents workshop create "银发精灵 Alice，校服" --ref ref.png --auto

# 多样性模式
python -m agents workshop create "银发精灵 Alice" --variety 3 --count 6

# 面试样张
python -m agents workshop demo "银发精灵 Alice, 蓝瞳, 白色长裙" --count 1

# 一致性验证
python -m agents workshop verify ./output_dir --character Alice --html

# Autopilot 质量报告
python -m agents workshop autopilot --report
```

## 环境要求

- Windows / WSL，本机 [ComfyUI](https://github.com/comfyanonymous/ComfyUI) 已启动（默认 `http://127.0.0.1:8188`）
- [Ollama](https://ollama.com/)（可选，用于提示词优化；可用 `--ollama` 启用）
- Python 3.10+，`pip install -r requirements.txt`
- 模型与 LoRA 权重**需自行准备**，本仓库仅含 workflow JSON 与编排脚本
- 显卡推荐 RTX 4070S 12GB+（Flux.2 Klein 需模型 offload）

### 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `COMFY_URL` | `http://127.0.0.1:8188/prompt` | ComfyUI API |
| `COMFY_ROOT` | `C:\\DrawingLive\\ComfyUI` | ComfyUI 安装目录 |
| `COMFY_PORT` | `8188` | ComfyUI 端口 |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama API |
| `OLLAMA_MODEL` | `qwen3:14b` | 提示词转写模型 |

## 目录结构

```
agents/           # Python 编排脚本（产品核心）
  __main__.py     #    CLI 入口 (workshop/manga/video/autopilot)
  comfy_utils.py  #    共享工具库
  go_flux.py      #    Flux 工作流构建
  __init__.py     #    版本号
workshop/         # Workshop 子系统
  create.py       #    出图管线（核心）
  engine/         #    Prompt 引擎
  manga/          #    漫画/分镜生成
  video/          #    视频生成
  inspect/        #    逐部位质检
  autopilot.py    #    Autopilot + 质量数据库
  consistency.py  #    一致性验证
  demo.py         #    面试样张管线
  postprocess.py  #    超分/修脸后处理
workflows/        # ComfyUI 工作流 JSON
scripts/          # 辅助脚本
docs/             # 文档
  cli-reference.md #     CLI 命令参考
```

## 核心特性

### 自然语言驱动的创作工坊

不写 prompt，说人话。引擎自动识别角色、场景、光照、构图，转写为模型可理解的高质量提示词。

### 质量自检管线（V1.0）

1. 生成多张候选（参数多样性保证）
2. 逐部位质检（面部/手/脚/模糊）
3. 不合格自动重试（参数微调）
4. 一致性跨图验证
5. Gallery 展示 + 筛选

### 面试展示

```bash
python -m agents workshop demo "银发精灵 Alice, 蓝瞳, 白色长裙" --count 1
```

生成 5 场景 Gallery + 一致性报告 + Markdown 文档，直接打开浏览器展示。

## 版本

当前 **V1.0.0** — 已达到面试展示门槛。

| 版本 | 说明 |
|------|------|
| V0.X.0 | 大功能 |
| V0.0.XXX | 小修 |
| VX.0.0 | 架构级里程碑 |

## License

MIT
