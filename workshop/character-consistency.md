# 角色一致性战术手册

> 基于你已有的实战经验（IP-Adapter 失败、LoRA 成功、dim 对比评估）
> 目标是: 同一个角色在不同 prompt/场景/角度下长相一致

## 你的已有结论（来自 AGENTS.md）

```
1. IP-Adapter (Flux) → ❌ 无法锁住动漫角色特征
   7 个变种全部测试: XLabs/官方/增强版 → 都不兼容
   
2. Flux ReferenceLatent + IFTv3 HARD_LOCK → ⚠️ 部分可行
   需要特定工作流节点

3. LoRA (rank=64, text_encoder) → ✅ 当前最佳方案
   126 张训练图, dim32/dim64 对比评估
```

## LoRA 训练参数速查

### 数据准备最佳实践

```
训练集大小: 20-50 张 (不是越多越好)
  20 张: 角色特征泛化好, 过拟合风险低
  50+ 张: 需要更多 steps, 容易过拟合

图片要求:
  - 统一尺寸 (1024×1024)
  - 禁用 random_flip (角色不对称)
  - 半身/全身混合 (不要全是脸部特写)
  - 多角度 (正面/侧面/45°)
  - 多表情 (微笑/严肃/惊讶)
  - 不同服装 (如果角色有多套衣服)

Caption 策略:
  - 简短: "1girl, character_name, [标签: smile/serious/etc]"
  - 只描述图片中有变化的部分
  - 不要重复写 "character_name" 之外的固定特征
```

### 训练参数

```bash
# SDXL LoRA
workshop train --character "name" \
  --images ./dataset \
  --rank 64 \
  --text-encoder \
  --steps 2000 \
  --batch-size 4 \
  --learning-rate 1e-4

# Flux LoRA (需要 comfyui-fluxtrainer)
workshop train --character "name" \
  --model flux \
  --images ./dataset \
  --rank 64 \
  --steps 1500
```

### 评估方法

```bash
# dim 对比 (你已经用过的)
workshop sweep --grid '{"lora_dim": [32, 64, 128]}' \
  "1girl, character_name, portrait"

# 质检评分
workshop inspect --output ./output

# 人工评估标准:
# 1. 和原角色像不像? (特征保持)
# 2. 质量好不好? (没有崩图)
# 3. 不同角度/表情下像不像? (泛化能力)
```

## 无 LoRA 时的角色保持

当没有 LoRA 可用时:

```
战术1: 种子固定
  找一张好图 → 固定 seed → 微调 prompt
  
战术2: 参考图 prompt 注入
  --ref 走 Ollama 分析 → 输出角色特征描述 → 注入 prompt
  
  你的管线: workshop create "prompt" --ref ref.png
  会自动调用 workshop/engine/ref.py → 提取特征 → 增强 prompt

战术3: 多候选择优
  workshop create "prompt" --count 6
  → 生成 6 张 → 自动选最优
  → 挑中最好的那张后固定 seed
```

## 写实角色 vs 动漫角色

| 维度 | 动漫 (二次元) | 写实 (三次元) |
|------|-------------|-------------|
| LoRA 效果 | ✅ 非常好 | ✅ 好 (需要更多数据) |
| 最佳底模 | SDXL (waiIllustrious) | Flux.2 (photoreal) |
| 特征保持难度 | 中 | 中高 |
| IP-Adapter | ❌ 不兼容 | ⚠️ 部分可行 |
| 参考图分析 | 需要 CLIP | 需要 CLIP |
| Prompt 精确度 | 高 | 中 (随机性强) |
