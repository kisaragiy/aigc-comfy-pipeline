# AIGC ComfyUI Pipeline

> Python 编排 ComfyUI workflow · Ollama 提示词 · SDXL LoRA / IPAdapter 批处理出图  
> 作者：张伟强 · 作品集仓库（块 C）

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](requirements.txt)

## 演示（公开展示 · 工作流截图）

| 拼图 | 说明 |
|------|------|
| ![gallery](docs/samples/00_gallery_grid.jpg) | ComfyUI **节点/workflow 界面**截图（不含成图） |

打开 **[docs/GALLERY.html](docs/GALLERY.html)** 浏览完整作品集。成图能力可在面试时本地演示。

## 能力概览

- **自然语言 → 出图**：`run.py` 经 Ollama 将中文场景转为 SDXL 英文 tag，再提交 ComfyUI
- **角色 LoRA 文生图**：`go_knives_lora.py` 支持多角色、批量、SDXL/SD1.5
- **IPAdapter 锁脸**：`go_knives_ipadapter.py` 参考图驱动一致性
- **多角色同框**：`go_multi_char_lora.py` 双 LoRA + FaceDetailer 工作流
- **批处理归档**：轮询 `/history`、输出目录整理（见各脚本 `--help`）

## 环境要求

- Windows / WSL，本机 [ComfyUI](https://github.com/comfyanonymous/ComfyUI) 已启动（默认 `http://127.0.0.1:8188`）
- [Ollama](https://ollama.com/)（可选，用于提示词转写；可用 `--raw` 跳过）
- Python 3.10+，`pip install -r requirements.txt`
- 模型与 LoRA 权重**需自行准备**，本仓库仅含 workflow JSON 与编排脚本

### 环境变量

| 变量 | 默认 |
|------|------|
| `COMFY_URL` | `http://127.0.0.1:8188/prompt` |
| `COMFY_ROOT` | `C:\DrawingLive\ComfyUI`（可改） |
| `OLLAMA_URL` | `http://127.0.0.1:11434/api/generate` |
| `OLLAMA_MODEL` | `qwen3:1.7b` |

## 快速开始

```bash
git clone https://github.com/kisaragiy/aigc-comfy-pipeline.git
cd aigc-comfy-pipeline
pip install -r requirements.txt

# 1) 启动 ComfyUI 后 — 一句话出图
python agents/run.py "夕阳下的赛博朋克少女，半身像"

# 2) 角色 LoRA 文生图（需已训练/放置 LoRA）
python agents/go_knives_lora.py --character knives "白色连衣裙，海边日落" --count 2

# 3) IPAdapter 参考图锁脸
python agents/go_knives_ipadapter.py --ref path/to/ref.png "校服，教室窗边"
```

将 `workflows/` 内 JSON 拖入 ComfyUI 可查看节点图；与 `agents/` 内同名 workflow 文件对应。

## 目录结构

```
agents/           # Python 编排脚本 + 内嵌 workflow JSON
workflows/        # ComfyUI 导出工作流（可在 UI 中打开）
docs/
  samples/        # 压缩样张（作品集）
  assets/         # ComfyUI 工作流界面截图
  GALLERY.html    # 浏览器作品集页
  PORTFOLIO.md    # 三项目作品集索引
scripts/
  bootstrap_portfolio.py   # 从本机 DrawingLive 重新同步样张
  finalize_portfolio.py    # 样张 + 示例截图一键整理
```

## 与其他项目

| 项目 | 链接 |
|------|------|
| Memory Agent OS | https://github.com/kisaragiy/Memory-Agent-OS |
| 电影推荐系统 | https://github.com/kisaragiy/Movie-Recomand-System |
| 作者 GitHub | https://github.com/kisaragiy |

## 说明

- 公开仓库仅含 **工作流截图与脚本**，用于展示工程化能力；角色模型与成图样张在本地，面试时可演示。
- 完整素材与 kohya 训练环境在本地 `C:\DrawingLive`，未纳入本仓库。

## License

MIT
