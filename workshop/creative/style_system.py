#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/style_system.py — 特殊画风知识库 v1.0
======================================================
画风 = 作品的"皮"（风格词决定质感方向）——深挖第 16 轮
用法: 定画风 → 风格词放 prompt 前部（质量词后）——与商业默认（赛璐璐）对比选

【主流画风（SDXL/Illustrious 可表达的）】
  赛璐璐（cel shading）: 干净平涂+硬阴影——日漫商业默认（管线 commercial）
    → "cel shading, clean lineart, flat colors"（朋友场景默认——干净）
  厚涂（painterly）: 笔触感+光影融合——游戏原画/写实感
    → "painterly, thick brush strokes, rich colors"（质感重——"脏"风险高）
  水彩（watercolor）: 透明感+边缘晕染——文艺/治愈/回忆
    → "watercolor style, soft edges, translucent colors"（温柔——低饱和）
  吉卜力: 手绘感+自然色——温馨/冒险（宫崎骏风）
    → "ghibli style, hand-drawn, warm nature colors"
  新海诚: 光影写实+高饱和蓝天——唯美/风景（天气之子风）
    → "makoto shinkai style, realistic lighting, vivid sky"
  京阿尼: 精细可爱+柔光——日常/萌系
    → "kyoto animation style, refined cute, soft glow"
  黑白线稿: 线稿/漫画原稿——插画过程/极简
    → "black and white lineart, sketch, clean lines"

【风格×场景（选型）】
  商业插画/封面: 赛璐璐（干净）——默认
  游戏原画: 厚涂（质感）
  小说插画/治愈系: 水彩/吉卜力（温柔——朋友小说女主可选）
  风景/氛围图: 新海诚（光影）
  日常萌系: 京阿尼
  漫画分镜: 线稿/赛璐璐

【风格混搭（进阶——两种风格组合）】
  赛璐璐+厚涂阴影: 干净+立体（"cel shading with painterly shadows"）
  水彩+线稿: 文艺+清晰（"watercolor with clean lineart"）
  风险: 风格词冲突=模型混乱（不要 3 个以上风格词）

【画风×"脏"（质量守门）】
  厚涂/水彩天然"笔触感"——不等于"脏"（脏=噪点/线条乱/阴影糊）
  用户标准（商业图）: 干净优先——赛璐璐/水彩安全 · 厚涂慎用
  画风词冲突质检: 风格不统一 → 换单一风格词重跑

【实战映射（prompt 模板）】
  水彩小说插画: "watercolor style, soft edges, gentle colors, literary illustration"
  新海诚风景: "makoto shinkai style, vivid blue sky, realistic sun light, detailed clouds"
  吉卜力少女: "ghibli style, warm colors, hand-drawn feeling, cozy atmosphere"
  厚涂原画: "painterly style, rich brush strokes, dramatic lighting, game key art"
