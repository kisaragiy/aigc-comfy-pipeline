# AIGC ComfyUI Pipeline

> Python 编排 ComfyUI · LoRA 训练 · 批量生图 · 模型管理  
> **工程化工具链** — Python 脚本是产品，生图是产出  
> 作者：张伟强

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](requirements.txt)
![Version](https://img.shields.io/badge/version-v0.5.0-green)

## 定位

**AIGC 工程化管线**。不是作品展示仓库——编排脚本是产品，生成的图片是产出。

通过 Python 脚本编排 [ComfyUI](https://github.com/comfyanonymous/ComfyUI) REST API，实现自然语言 → 出图、角色 LoRA 批处理、IPAdapter 面部一致性、多角色同框等工作流。

## 能力概览

| 能力 | 命令 | 说明 |
|------|------|------|
| 一句话出图 | `run.py` | 自然语言 → Ollama 转写 → 提交 ComfyUI |
| 角色 LoRA 文生图 | `go_knives_lora.py` | SDXL/SD1.5，多角色预设，批量，换装 |
| IPAdapter 锁脸 | `go_knives_ipadapter.py` | 参考图驱动面部一致性 |
| 多角色同框 | `go_multi_char_lora.py` | 双 LoRA + FaceDetailer |
| 批处理 | `go_knives_lora.py --count N` | 多张自动归档 |
| Flux.2 Klein 身份一致性 | 加载 `workflows/Flux...json` | 身份引导工作流 |

详见 [AGENTS.md](AGENTS.md)（Agent 初始任务书）。

## 快速开始

```bash
git clone https://github.com/kisaragiy/aigc-comfy-pipeline.git
cd aigc-comfy-pipeline
pip install -r requirements.txt

# 1) 启动 ComfyUI 后 — 一句话出图
python agents/run.py "夕阳下的赛博朋克少女，半身像"

# 2) 角色 LoRA 文生图（需已放置 LoRA 权重）
python agents/go_knives_lora.py --character knives "白色连衣裙，海边日落" --count 2

# 3) IPAdapter 参考图锁脸
python agents/go_knives_ipadapter.py --ref path/to/ref.png "校服，教室窗边"
```

## 环境要求

- Windows / WSL，本机 [ComfyUI](https://github.com/comfyanonymous/ComfyUI) 已启动（默认 `http://127.0.0.1:8188`）
- [Ollama](https://ollama.com/)（可选，用于提示词转写；可用 `--raw` 跳过）
- Python 3.10+，`pip install -r requirements.txt`
- 模型与 LoRA 权重**需自行准备**，本仓库仅含 workflow JSON 与编排脚本

### 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `COMFY_URL` | `http://127.0.0.1:8188/prompt` | ComfyUI API |
| `COMFY_ROOT` | `C:\DrawingLive\ComfyUI` | ComfyUI 安装目录 |
| `OLLAMA_URL` | `http://127.0.0.1:11434/api/generate` | Ollama API |
| `OLLAMA_MODEL` | `qwen3:14b` | 提示词转写模型 |

## 目录结构

```
agents/           # Python 编排脚本（产品核心）
  run.py          #   一句话出图
  comfy_utils.py  #   共享工具库
  go_knives_lora.py  #   角色 LoRA 文生图（主力）
  go_knives_ipadapter.py  #   IPAdapter 锁脸
  go_multi_char_lora.py  #   多角色同框
workflows/        # ComfyUI 工作流 JSON（可在 UI 中打开查看节点图）
scripts/          # 辅助脚本（开发用）
  bootstrap_portfolio.py  #   从本机 DrawingLive 同步样张
docs/             # 作品展示（工作流界面截图）
  GALLERY.html    #   浏览器作品集页
  PORTFOLIO.md    #   三项目作品集索引
  samples/        #   压缩样张
  assets/         #   ComfyUI 界面截图源文件
```

## 演示

打开 **[docs/GALLERY.html](docs/GALLERY.html)** 查看 ComfyUI 工作流截图（不含成图）。

完整出图能力可在面试时本地演示。工作流可以拖入 ComfyUI 查看节点配置。

## 不做什么

- 不开在线服务/API
- 不接灵枢（复用 lingShu-core 以后再说）
- 不做 ControlNet / T2I-Adapter / AnimateDiff
- 不包含模型权重
- 不包含成图样张

详见 [AGENTS.md](AGENTS.md) 的「不做什么」节。

## 版本

当前 **V0.5.0** — V0.X.0 = 大功能，V0.0.XXX = 小修。

## License

MIT
