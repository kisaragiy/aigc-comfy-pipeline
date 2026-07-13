# Changelog

## v1.0.0 (2026-07-13)

V1.0.0 里程碑。达到面试展示门槛。

### 新增
- 一致性验证 `workshop verify` — 跨图片质检比较 + 波动标记 + HTML 报告
- 面试样张管线 `workshop demo` — 5 场景 Gallery + 一致性报告 + Markdown 文档
- README 全面更新为 V1.0.0 版本

### 修复
- 漫画预览框 `景別`→`景别` unicode bug（显示 `?` 的问题）

## v0.98.0 (2026-07-13)

### 新增
- 质量数据库自动学习（每次 `create` 自动写入，`--no-learn` 关闭）
- 角色签名提取（区分不同角色的最优参数）
- `--auto` 返回 TOP-K 多样化参数推荐
- Explore 机制（15%-30% 探索空间）
- `--variety N` 显式多样性模式

## v0.97.0 (2026-07-13)

### 新增
- 自优化 `--auto` 从质量数据库加载最优参数
- `autopilot --report` HTML 质量报告
- 画廊筛选 `--filter` 规则

## v0.96.0 (2026-07-13)

### 新增
- 质量自动重试 `--auto-retry N`
- Gallery 筛选 `--filter`
- `--steps`/`--cfg` 参数暴露

## v0.95.0 (2026-07-13)

### 新增
- Autopilot 子系统：参数网格扫描、空闲模式
- `create --auto` 自动加载最优参数
- 质量数据库 (`quality.json`)

## v0.94.0

### 新增
- Autopilot 子系统
- QualityDB 类
- 参数网格扫描

## v0.93.0 — 方向纠偏

### 新增
- `--variants` 多 prompt 生成
- 一致性验证（初版）
- 漫画全链路验证

## v0.92.0

### 新增
- `--from-scenes` 批量插画生成

## v0.91.0

### 新增
- 轻小说插画管线
- `--cast` 人物表
- `--preset illustration`/`lightnovel`
- `workshop extract`

## v0.90.0

### 新增
- 智能工作流系统 `--save`/`--load`/`--smart`

## v0.89.0

### 新增
- 漫画一致性：角色/场景锚定 + ColorAnchor

## v0.88.0

### 新增
- Gallery 评分条
- annotate 增强

## v0.87.0

### 文档
- docs/cli-reference.md

## v0.86.0

### 新增
- Gallery 一键复制 seed
- 视频 commercial 预设

## v0.85.0

### 新增
- Batch quality 支持 upscale/restore-face
- Manga gallery 角色 ref 缩略图

## v0.84.0

### 新增
- Gallery 对比模式
- `--commercial` 一键快捷预设

## v0.83.0

### 新增
- Create `--lora` 集成
- Manga 支持 preset/upscale/restore-face

## v0.82.0

### 新增
- 商业图 prompt 工程增强

## v0.81.0

### 新增
- `--upscale` + `--restore-face`
- commercial 预设

## v0.80.0

### 新增
- 预设自定义
- ComfyUI 端口配置

## v0.79.0

### 新增
- `inspect --html` 批量质检报告

## v0.78.0

### 新增
- Gallery 幻灯片 + 主题切换

## v0.77.0

### 新增
- Batch-file `--ref` 支持

## v0.76.0

### 新增
- Gallery Lightbox 滚轮缩放
- 质检 overlay

## v0.75.0

### 新增
- `create_from_nl` 核心管线

## 更早版本

参见 git log。
