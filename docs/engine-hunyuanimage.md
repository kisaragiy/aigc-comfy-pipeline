# HunyuanImage-3.0 Lite 工作流固化

> 2026-09-02 固化 · 实测证据：2026-08-31 望月测试一次全对
> 模型：`hunyuanimage-lite-v2.2-iq4_nl.gguf`（80B MoE，IQ4_NL 量化）

## 定位（引擎分工最终版，三引擎实测完毕）

| 引擎 | 速度 | 语义 | 定位 |
|---|---|---|---|
| SDXL + LoRA | 8-20s | 弱 | **批量主力** |
| **HunyuanImage Lite** | **10.5min** | ✅ 强（中文友好） | **角色定稿/难图首选** |
| Qwen-2512 | 23min | ✅ 强 | 备胎 |
| Qwen-Edit | 52min | 编辑 | 应急改图 |

**结论**：HunyuanImage 取代 Qwen 成为语义引擎首选（更快 2x+、中文场景理解更强、画质在线）。

## 工作流（已验证）

节点链：UnetLoaderGGUF → CLIPLoader(hunyuan_image) → CLIPTextEncode×2 → EmptyLatent → KSampler → VAEDecode → SaveImage

```python
# 关键参数
MODEL   = "hunyuanimage-lite-v2.2-iq4_nl.gguf"
CLIP    = "qwen-image/qwen_2.5_vl_7b_fp8_scaled.safetensors"  # type=hunyuan_image
VAE     = "pig_hunyuan_image_vae_fp32-f16.gguf"
STEPS   = 8          # 快出图
CFG     = 1.5
SIZE    = 896x1152   # 竖版人像
SAMPLER = euler, scheduler=simple
```

## 用法

```bash
# 完整脚本在管线 scripts/probe_hunyuanimage.py（已可复用）
cd ~/aigc-comfy-pipeline
unset PYTHONPATH
python scripts/probe_hunyuanimage.py --text "你的prompt" --seed 20260901
```

## 坑

1. **VaeGGUF 节点**需要 ComfyUI gguf custom_node 完整注册（pig.py 的 VaeGGUF 类，曾因依赖失败静默不注册——object_info 查不到就修）
2. 单张 ~10.5 分钟（80B MoE 推理，比 Qwen-2512 的 23min 快 2 倍+）
3. 与 SDXL 互补：SDXL 快但语义弱，Hunyuan 慢但语义强——**先想清楚要"快"还是"准"**
4. prompt 可以直接中文（腾讯模型对中文场景理解强），但建议仍用英文保持一致性

## 复现记录

- 2026-08-31 望月测试（红发带/红领结/灰格裙/白袜黑帆布鞋）→ 一次全对
- 角色特征核对可用百炼 qwen3.8-flash 视觉审图（免费额度）
