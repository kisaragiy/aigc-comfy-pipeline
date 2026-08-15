#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/prompt_system.py — Prompt 工程知识库 v1.0
==========================================================
SDXL 标签式 prompt 完整体系（精确特征用 SDXL——Flux 自然语言执行弱）——深挖第 8 轮
用法: 写 SDXL prompt 按此结构——顺序/权重/负面三件套

【SDXL prompt 结构（顺序=优先级）】
  MASTERPIECE, best quality → 风格 → 镜头/角度 → 光照 → 场景 → 主体 → 主体细节 → 画质尾缀
  例: MASTERPIECE, best quality, anime style, medium shot, soft lighting, school corridor, 1girl, black hair, mole under eye, detailed illustration
  - 主体放中段（模型注意力中心）
  - 细节（发色/瞳色/泪痣/服装）放主体后——越靠后权重越低（重要特征可提前+加权）

【权重语法（(word:1.2) 加重 / [word:0.8] 减轻）】
  关键特征加权: (black hair:1.2) (mole under left eye:1.3)——模型容易漏的特征加权
  冲突特征排除: [white dress:0.8] 减权（参考图黑裙时防白裙跑偏——memory 实战）
  规则: 加权不超过 1.4（过重=变形）；权重词之间用逗号分隔
  → 精确特征（泪痣/纯黑发/特定服装）必须加权——SDXL 才能稳定出

【质量词体系（分级）】
  顶级: MASTERPIECE, best quality, ultra detailed, 8k
  商业: MASTERPIECE, best quality, clean lineart, soft cel shading（管线 commercial 已含）
  基础: best quality, high quality
  - 不要堆太多质量词（MASTERPIECE 出现 1-2 次即可——堆了没用还占 token）
  - 画风词（clean lineart/soft shading）比质量词更影响"脏不脏"

【负面词库（分层）】
  基础必带: worst quality, low quality, blurry, bad anatomy, bad hands, extra fingers, watermark, text
  画风防脏: noise, grainy, dirty, messy lineart, jpeg artifacts（商业图必须）
  特征防偏: colorful hair, gradient hair, tears（黑发角色——防模型自由发挥）
  场景防乱: extra people, crowd（单人图）
  → 负面词 = 告诉模型"不要什么"——比正面词更精准控制

【角色卡模板（一致性——character.py 已接）】
  固定段: 发色+发型+瞳色+服装+特征（泪痣/伤疤）——多图共用同一段
  例: "1girl, natural black hair, short bob, blue eyes, mole under left eye, navy sailor uniform"
  变体段: 场景/表情/角度（每张不同）
  规则: 固定段放 prompt 前（权重高）——变体段放后——多图一致性靠固定段

【风格词（画风控制——commercial preset 已含）】
  动漫（Illustrious）: anime style, cel shading
  精致动漫: anime style, clean lineart, soft cel shading, smooth gradients（商业图默认）
  厚涂: painterly, thick paint, brush strokes
  水彩: watercolor, soft edges
  写实: photorealistic, detailed skin texture
  → 风格词放质量词后（风格定调——影响整体质感）

【Flux 自然语言 vs SDXL 标签（选型）】
  SDXL 标签: 精确特征（发色/泪痣/服装）强——动漫风格主力
  Flux 自然语言: 场景描述/氛围/复杂关系强——但精确特征执行弱（今天实测泪痣/纯黑发出不来）
  实战规则: 精确特征角色图 → SDXL · 氛围叙事图 → Flux

【实战映射（完整商业 prompt 模板）】
  SDXL 商业图: "MASTERPIECE, best quality, anime style, clean lineart, soft cel shading, medium shot, warm golden sunlight, school corridor, 1girl, (natural black hair:1.2), short bob, side braid near ear, (mole under left eye:1.3), cheerful smile, navy sailor uniform, detailed illustration"
  负面: "worst quality, low quality, blurry, noise, grainy, dirty, bad hands, extra fingers, watermark, text, colorful hair, gradient hair, tears"
