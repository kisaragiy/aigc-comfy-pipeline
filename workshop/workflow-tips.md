# ComfyUI 工作流实战技巧

> 直接可用的节点配置模式，用于你已有的 C:\DrawingLive\ComfyUI

## 通用质量节点链

```
KSampler 设置:
  ┌─────────────────────────────────────────┐
  │ SDXL:  steps=25, cfg=7, sampler=DPM++ 2M Karras │
  │ Flux:  steps=25, cfg=2.5, sampler=默认         │
  │ Wan:   steps=30, cfg=5                        │
  └─────────────────────────────────────────┘
  
负面 Prompt (对所有模型通用):
  lowres, bad anatomy, bad hands, missing fingers,
  extra digit, worst quality, normal quality
```

## 常用节点组合

### 1. 图片放大 (Upscale)

```
[原始图] → [Upscale Image (Model)] → [4x UltraSharp] → [输出]
    参数: 模型=4x-UltraSharp, 模式=bilinear
    或: [原始图] → [Ultimate SD Upscale] → [降噪 0.3-0.5]
```

### 2. 面部修复

```
[生成图] → [FaceDetailer] → [修复后图]
    参数: 检测模型=yolov8x, 降噪=0.3, 尺寸=512
    → 专门用来修崩脸/崩眼/崩嘴
```

### 3. 背景替换

```
[图] → [BRIA RMBG (去除背景)] → [新背景图] → [ImageComposite] → [合成]
```

## 视频提升技巧

```
Wan2.2 → [后处理顺序]:
  1. 帧提取 (workshop video-process --extract-frames)
  2. 每帧超分 (Real-ESRGAN 批量)
  3. 组帧回视频 (workshop video-process --frames-to-video)
  4. 插帧 (RIFE 或 DAIN) 提升流畅度
```

## 直接可用的 workflow JSON 模板

工作流路径: `C:\DrawingLive\ComfyUI\user\default\workflows\`

```json
{
  "name": "SDXL Anime Character",
  "nodes": {
    "checkpoint": {"model": "waiIllustriousSDXL_v160.safetensors"},
    "ksampler": {"steps": 25, "cfg": 7, "sampler": "dpmpp_2m_karras"},
    "positive": "1girl, character_name, masterpiece",
    "negative": "lowres, bad anatomy, bad hands",
    "vae": {"name": "sdxl_vae.safetensors"},
    "upscale": {"model": "4x_NMKD-Superscale-SP_178000_G"},
    "output": {"format": "png", "size": "1024x1024"}
  }
}
```
