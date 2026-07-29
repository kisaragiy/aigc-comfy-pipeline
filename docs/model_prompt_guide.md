# 三模型提示词体系 + 工作流完整指南

## 一、模型架构差异

| 维度 | SDXL (Illustrious) | Flux.2 Klein 9B | Anima |
|------|:------------------:|:---------------:|:-----:|
| **架构** | UNet + DualCLIP + VAE | Diffusion Transformer + Qwen3 + VAE | UNet + DualCLIP + VAE (SDXL衍生) |
| **加载方式** | CheckpointLoaderSimple 或 UNETLoader + DualCLIPLoader | UNETLoader + CLIPLoader(type=flux2) + VAELoader | **仅 UNETLoader + DualCLIPLoader** |
| **CLIP** | clip_l.safetensors + sd_xl_base_1.0.safetensors | qwen_3_8b_fp8mixed.safetensors | clip_l.safetensors + sd_xl_base_1.0.safetensors |
| **VAE** | sdxl_vae.safetensors | flux2-vae.safetensors | sdxl_vae.safetensors |
| **Prompt 格式** | 逗号分隔标签 + 质量词 | 自然语言段落（无质量词） | 自然语言 + 质量词混合 |
| **质量标签** | ✅ `MASTERPIECE, best quality, ultra-detailed, 8k` | ❌ 不需要 | ✅ `MASTERPIECE, best quality` |
| **负向提示词** | ✅ 必须 | ⚠️ 可选 | ✅ 推荐 |
| **CFG** | 6.5–7.0 | 1.0 | 6.5–7.0 |
| **工作流模板** | workflow_multi_char_lora_sdxl.json (无LoRA) / workflow_knives_lora_sdxl.json (有LoRA) | go_flux.py build_flux_workflow() 程序化构建 | ❌ 尚未实现 |

## 二、提示词模板

### SDXL / Anima 正向提示词

```
MASTERPIECE, best quality, ultra-detailed, 8k,
[角色外貌、服装、表情、姿势],
[场景环境、背景],
[构图和镜头: 特写/中景/全景, 仰角/俯角/平视],
[光线氛围: 逆光/柔光/体积光/暖/冷],
[色彩: 主色调/配色方案],
[画风: anime style, cel shading, clean lineart, vibrant colors, detailed illustration],
professional artwork, highres, absurdres
```

**多层角色示例:**
```
MASTERPIECE, best quality, ultra-detailed, 8k,
silver-haired half-elf Emilia, amethyst purple eyes,
white and violet gradient dress with golden trim, white flower hair ornament,
sitting under cherry blossom tree at school gate,
book on knees, gentle smile, soft expression,
medium shot, eye-level angle,
warm afternoon sunlight filtering through petals, soft volumetric lighting,
pink and gold color palette,
anime style, cel shading, clean lineart, vibrant colors, detailed illustration
```

**多人/动作场景示例:**
```
MASTERPIECE, best quality, ultra-detailed, 8k,
two characters dynamic action scene,
left side: Emilia in white and violet dress casting magic, hand raised with glowing rune, determined expression,
right side: Subaru in school uniform reaching out, surprised expression,
cherry blossom petals flying, magical energy swirling around them,
wide shot, low angle, dramatic perspective,
rim lighting from magical glow, volumetric light rays through petals,
blue and pink contrasting colors,
anime style, dynamic pose, motion lines, impact frames, speed lines
```

### SDXL / Anima 负向提示词

```
worst quality, low quality, normal quality, blurry, jpeg artifacts,
bad anatomy, bad hands, ugly, deformed, bad proportions,
extra limbs, fused fingers, missing fingers, extra fingers,
mutated hands, poorly drawn face, bad eyes, cross-eyed,
signature, watermark, username, text, error,
extra digit, fewer digits, cropped, monochrome, grayscale,
nsfw, lowres, bad composition, mutated body parts
```

### Flux.2 Klein 提示词

Flux 不需要质量标签，不需要负向提示词，写清晰的自然语言段落即可：

```
A silver-haired half-elf Emilia with amethyst eyes wearing a white and violet gradient dress with golden trim, sitting under a cherry blossom tree at a school gate. She's reading a book with a gentle smile, warm afternoon sunlight filtering through pink petals, soft volumetric lighting. Medium shot, eye-level camera. Anime style with cel shading and vibrant colors.
```

## 三、提示词反推（图→Prompt）

见 `agents/prompt_reversal.py`

通过 VLM (qwen3-vl:8b) 分析图片 → 生成 SDXL/Flux/Anima 三种格式的提示词。
支持 `targeted` 参数：如 `make her wear a red combat uniform instead` 可在保持角色特征的同时改变服装。

## 四、工作流清单

| 工作流 | 用于 | 模型 | 加载方式 |
|--------|------|------|----------|
| `workflow_multi_char_lora_sdxl.json` | 通用SDXL（多角色，无LoRA） | SDXL Illustrious | CheckpointLoaderSimple |
| `workflow_knives_lora_sdxl.json` | 角色LoRA（如knives_sdxl_dim32） | SDXL Illustrious | CheckpointLoaderSimple + LoraLoader |
| `go_flux.py build_flux_workflow()` | Flux.2 Klein | Flux.2 Klein 9B | UNETLoader + CLIPLoader |
| ❌ (待建) Anima工作流 | Anima | Anima | UNETLoader + DualCLIPLoader |

## 五、Anima 工作流（待建）

当前 `CheckpointLoaderSimple` 无法用于 Anima（checkpoint不含内嵌CLIP）。
需要新建工作流:

1. UNETLoader → unet_name="anima-base-v1.0.safetensors" (从diffusion_models/)
2. DualCLIPLoader → clip_name1="clip_l.safetensors", clip_name2="sd_xl_base_1.0.safetensors", type="sdxl"
3. VAELoader → vae_name="sdxl_vae.safetensors"
4. CLIPTextEncode → 正向/负向 prompt
5. KSampler → cfg=6.5, steps=28
6. SaveImage
