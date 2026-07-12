# ComfyUI 管线 — Agent 初始任务书

## 定位

**AIGC 工程化管线** — Python 编排 ComfyUI · LoRA 训练 · 批量生图 · 模型管理

不是作品展示仓库，是工程化工具链。生成的图片是产出，编排脚本是产品。

## 版本规约

V0.X.0 = 大功能，V0.0.XXX = 小修。

- **V0.15.0** — 当前：ComfyUI 队列管理
- V0.14.0 — 上一版：管线验收报告
- V0.13.0 — 自动标图 + LoRA 训练闭环
- V0.12.0 — 批量迭代 + 参数扫描
- V0.11.0 — 输出管理深度集成（自动归档 + metadata）
- V0.10.0 — Flux.2 Klein 原生 CLI
- V0.9.0 — 模型管理（列表/查询/依赖检查）
- V0.8.0 — 工作流模板管理 + 依赖检查
- V0.7.0 — 管线健壮性 + 验证
- V0.6.0 — 统一 CLI + 输出管理
- V0.5.0 — LoRA 训练/批处理/IPAdapter/多角色/Flux.2 Klein 均已可用
- V0.0.XXX — 小修

## 当前版本：V0.15.0

## 核心能力

| 能力 | 入口 | 统一 CLI | 说明 |
|------|------|----------|------|
| 一句话出图 | `run.py` | `python -m agents run` | 自然语言 → Ollama 转写英文 tag → ComfyUI 提交 |
| 角色 LoRA 文生图 | `go_knives_lora.py` | `python -m agents lora` | SDXL/SD1.5 多角色（Knives / Caster）、批量、换装 |
| IPAdapter 锁脸 | `go_knives_ipadapter.py` | `python -m agents ipa` | 参考图驱动面部一致性、权重可调 |
| 多角色同框 | `go_multi_char_lora.py` | `python -m agents multi` | 双 LoRA + FaceDetailer 修脸 |
| 批处理 | `go_knives_lora.py --count N` | `python -m agents lora --count N` | 多张自动复制到草稿库 |
| 产出管理 | `output_manager.py` | `python -m agents outputs` | 结构化元数据、list/show/clean，**所有命令自动归档** |
| 环境检查 | `comfy_utils.py` | `python -m agents check` | 运行前探活 ComfyUI/Ollama，自助诊断 |
| Dry-run 验证 | `comfy_utils.DRY_RUN` | `--dry-run` 全局参数 | 跳过真实提交，验证参数正确性 |
| Flux.2 Klein 身份一致性 | agents 脚本加载 workflows/JSON | — | 身份引导 + 单图工作流 |
| Prompt 优化 | `comfy_utils.optimize_prompt()` | — | 六维度构图法转为结构化英文 tag |
| 工作流管理 | `workflow_manager.py` | `python -m agents workflow` | 模板扫描、参数 schema 提取、节点依赖检查 |
| 模型管理 | `model_manager.py` | `python -m agents models` | 列出已安装模型、查询详情、workflow 模型检查 |
| Flux.2 Klein 生图 | `go_flux.py` | `python -m agents flux` | 程序化构建 Flux 工作流（9B/4B、LoRA 注入） |
| 参数扫描 | `go_sweep.py` | `python -m agents sweep` | 网格参数迭代、自动对比拼图 |
| 自动标图 | `go_caption.py` | `python -m agents caption` | Ollama VL 自动生成训练数据 .txt 标注 |
| 训练编排 | `go_train.py` | `python -m agents train` | 数据验证 + AutoDL 训练命令生成 |
| 管线报告 | `go_report.py` | `python -m agents report` | 一键验收：ComfyUI/模型/workflow/产出全貌 |
| 队列管理 | `go_queue.py` | `python -m agents queue` | 查看/清空/中断队列、释放显存 |

## 项目结构

```
agents/                    # Python 编排脚本（产品）
  __init__.py              #   包标识 + 版本
  __main__.py              #   统一 CLI 入口
  run.py                   #   一句话出图入口
  comfy_utils.py           #   共享工具库（ComfyUI API / Ollama / 图片等待）
  output_manager.py        #   产出管理（结构化元数据）
  workflow_manager.py      #   工作流模板管理（扫描/schema/检查）
  model_manager.py         #   模型管理（列表/查询/依赖检查）
  go_flux.py               #   Flux.2 Klein 文生图
  go_sweep.py              #   参数网格扫描
  go_caption.py             #   自动标图（Ollama VL）
  go_train.py               #   训练编排（数据验证 + 命令生成）
  go_report.py              #   管线验收报告
  go_queue.py               #   ComfyUI 队列管理
  go_knives_lora.py        #   角色 LoRA 文生图（主力脚本）
  go_knives_ipadapter.py   #   IPAdapter 锁脸（复用 go_knives_lora 的构建函数）
  go_multi_char_lora.py    #   多角色同框
  go_caster_lora.py        #   [兼容] 转发到 go_knives_lora.py --character caster
  run_knives_lora_batch.py #   [兼容] 转发到 go_knives_lora.py --count
workflows/                 # ComfyUI 工作流 JSON（可以从 UI 打开查看节点图）
scripts/                   # 辅助脚本（开发用）
  bootstrap_portfolio.py   #   从本机 DrawingLive 同步 + 生成 SFW 样张
  finalize_portfolio.py    #   [弃用] 仅调用 bootstrap，待删除
docs/                      # 作品展示 + 知识库
  GALLERY.html
  PORTFOLIO.md
  prompt-framework.md      # 六维度构图法 prompt 工程参考
  storyboard-spec.md        # 分镜提示词规范、乒乓镜头、打斗物理化
  samples/
  assets/
outputs/                   # 出图产出（gitignored，本地自动生成）
  .gitkeep                 #   占位文件
```

## 技术栈

- **ComfyUI** REST API (`http://127.0.0.1:8188`)
- **Python** 编排（requests + json → POST /prompt → poll /history）
- **Ollama** 可选提示词转写（中文 → 英文 danbooru tag）
- **SDXL / SD1.5 / Flux.2 Klein** 底模支持
- **LoRA** 角色身份保持
- **IPAdapter PLUS FACE** 面部参考一致性

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `COMFY_URL` | `http://127.0.0.1:8188/prompt` | ComfyUI API |
| `COMFY_ROOT` | `C:\DrawingLive\ComfyUI` | ComfyUI 安装目录 |
| `OLLAMA_URL` | `http://127.0.0.1:11434/api/generate` | Ollama API |
| `OLLAMA_MODEL` | `qwen3:14b` | 提示词转写模型 |

## 不做什么

- ❌ 不开在线服务/API for others
- ❌ 不接灵枢（复用 lingShu-core 以后再说）
- ❌ 不做模型训练以外的生图优化（不碰 ControlNet / T2I-Adapter / AnimateDiff 等）
- ❌ 不做 LoRA 训练自动化（用 kohya，本仓库仅编排生图管线）
- ❌ 不包含模型权重（所有 .safetensors / .ckpt 都在本地 `.gitignore` 排除）
- ❌ 不包含成图样张（仅公开展示工作流界面截图）

## 如何工作

所有 agent 脚本遵循同一模式：
1. 加载 workflow JSON（模板）
2. 填入正向/负向提示词、LoRA 名称、seed 等参数
3. POST 到 ComfyUI `/prompt`
4. 轮询 `/history` 等待出图
5. （批量模式）复制到草稿目录或 outputs/

## 统一 CLI

`python -m agents` 提供统一入口，避免记忆多个脚本名：

```bash
# 一句话出图
python -m agents run "夕阳下的赛博朋克少女，半身像"

# 角色 LoRA 文生图
python -m agents lora --character knives "白色连衣裙，海边日落" --count 2

# IPAdapter 锁脸
python -m agents ipa --ref path/to/ref.png "校服，教室窗边"

# 多角色同框
python -m agents multi "Knives校服在左，Caster连衣裙在右，街道背景"

# 产出管理
python -m agents outputs list
python -m agents outputs show 2026-07-12_153022-lora
python -m agents outputs clean --days 30
```

旧脚本入口依然可用，完全向后兼容。

## 产出管理

产出自动保存到 `outputs/YYYY-MM-DD_HHMMSS-<命令>/`：

```
outputs/
  2026-07-12_153022-lora/
    metadata.json     # prompt, seed, 参数, 时间
    images/           # 出图副本
```

metadata.json 包含完整的生成参数，面试时打开即可证明工程化能力。

## 依赖

- `requests>=2.28.0`（核心）
- `pillow`（可选，仅 scripts/bootstrap_portfolio.py 需要）

## 开发约定

- `comfy_utils.py` 是共享工具库，新增脚本要 import 它而非重复代码
- 新增能力时要更新 AGENTS.md 的「核心能力」表
- workflow JSON 放 `workflows/`，同时在 `agents/` 放一份副本让脚本能找到
- 兼容性 wrapper（转发到主力脚本）要加 deprecation warning
- 所有脚本必须支持 `--help`

## Verification Checklist

- [ ] `python agents/run.py` 能调用 ComfyUI 并提交任务
- [ ] `python agents/go_knives_lora.py --help` 显示完整参数
- [ ] `python agents/go_knives_ipadapter.py --help` 显示完整参数
- [ ] `python agents/go_multi_char_lora.py --help` 显示完整参数
- [ ] `python -m agents --help` 显示 6 个子命令（含 check）
- [ ] `python -m agents check` 显示 ComfyUI/Ollama 状态
- [ ] `python -m agents run --dry-run "test"` 使用降级提示词 + 跳过提交
- [ ] `python -m agents lora --dry-run --character knives "test"` 参数可见
- [ ] `python -m agents ipa --dry-run "test"` 参数可见
- [ ] `python -m agents multi --dry-run "test"` 参数可见
- [ ] `python -m agents outputs list` 正常列出（或提示"暂无"）
- [ ] 无 ComfyUI/Ollama 运行不崩溃（自动降级 + warn 提示）
- [ ] 各脚本从任意工作目录运行都能找到 comfy_utils
- [ ] `.gitignore` 正确排除生图输出
- [ ] `from agents.comfy_utils import optimize_prompt` 可导入
- [ ] `docs/prompt-framework.md` 包含六维度构图法完整说明
- [ ] `docs/storyboard-spec.md` 包含八列分镜表、乒乓镜头、打斗物理化规则
- [ ] `python -m agents workflow list` 列出所有 workflow（含 API 格式标识）
- [ ] `python -m agents workflow show <name>` 显示节点连接图
- [ ] `python -m agents workflow schema <name>` 提取可控参数
- [ ] `python -m agents workflow check <name>` ComfyUI 离线时友好提示
- [ ] `python -m agents models list` 按类型分组列出模型
- [ ] `python -m agents models info <name>` 显示模型详情
- [ ] `python -m agents models check <workflow>` 检查模型依赖
- [ ] `python -m agents flux --help` 显示 Flux 完整参数
- [ ] `python -m agents flux --dry-run "test"` 构建 13 节点工作流并跳过提交
- [ ] `python -m agents flux --lora <name> --dry-run "test"` LoRA 注入
- [ ] `python -m agents run --dry-run "test"` dry-run 不归档
- [ ] `python -m agents lora --dry-run "test"` dry-run 不归档
- [ ] `python -m agents flux --dry-run "test"` dry-run 不归档
- [ ] `python -m agents sweep --help` 显示完整参数
- [ ] `python -m agents sweep --grid '{"steps":[20,30]}' --dry-run "test"` 2 组合 + dry-run
- [ ] `python -m agents sweep --grid '{"steps":[20,30],"cfg":[1.0,2.0]}' --dry-run "test"` 4 组合
- [ ] `python -m agents caption --help` 显示完整参数
- [ ] `python -m agents caption --dir <path> --trigger "Test" --dry-run` 预览模式
- [ ] `python -m agents train --help` 显示完整参数
- [ ] `python -m agents train --dir <path> --trigger "Test" --dry-run` 验证报告
- [ ] `python -m agents report` 显示 6 个章节
- [ ] `python -m agents report --json` 输出 JSON 格式
- [ ] `python -m agents queue list` ComfyUI 离线时友好提示
- [ ] `python -m agents queue --help` 显示 4 个子命令
