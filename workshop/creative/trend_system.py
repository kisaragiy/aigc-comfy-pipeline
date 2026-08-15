#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/trend_system.py — 审美趋势/业界参考知识库 v1.0
==============================================================
现代审美特征（原神/鸣潮/碧蓝幻想等大厂角色设计分析）——深挖第 30 轮
用法: 画"现代感"角色 → 按大厂设计特征（精致/层次/氛围）

【现代大厂角色设计特征（米哈游/库洛/cygames 共识）】
  精致五官: 眼大但有神/睫毛细致/表情微差（不是"大眼无神"）
  服装层次: 多层穿搭（外套+内搭+配饰——不是单件）
  细节密度: 高（花纹/绑带/金属件——但统一色系不杂乱）
  动态姿势: 有张力（站姿有曲线/微动态）
  色彩控制: 主色+辅色+点缀（3 色内——但层次丰富）
  → 现代感 = 精致+层次+统一（"detailed elegant design"）

【现代感 vs 老式动漫（区别）】
  老式: 简单服装/表情单一/颜色平面
  现代: 服装层次/表情细腻/光影丰富
  → 词: "modern anime style, detailed design"（"modern" 词有实际作用）

【"高级感"来源（画师/大厂共识）】
  ① 光影真实（柔光+层次——不是平涂）
  ② 色彩克制（低饱和主调+小面积高饱和点缀）
  ③ 线条干净（粗细变化——"line variation"）
  ④ 留白呼吸（构图不挤）
  ⑤ 细节精致（关键处精细——不是全图均匀）
  → 高级感五要素 = 光影+色彩+线条+留白+细节

【避免"AI 味"（现代审美红线）】
  AI 味特征: 油腻高光/塑料皮肤/过度对称/空洞眼神/背景糊成一片
  修正: 皮肤哑光+自然高光 / 表情有微差 / 构图不对称 / 背景有内容
  → 词: "natural skin, subtle highlights, asymmetrical composition"

【角色设计趋势（当前流行）】
  异色瞳: 神秘感（"heterochromia"——点缀）
  泪痣/雀斑: 记忆点（泪痣=朋友场景——经典记忆点设计）
  挑染/发尾渐变: 时尚感（用户已禁——现实发色优先）
  耳饰/发饰: 精致感（"delicate earrings"）
  眼妆: 下睫毛/眼影（"detailed eye makeup"——现代感）
  → 记忆点设计: 泪痣/雀斑/异色瞳（选一个——不堆叠）

【业界参考（审美库——用户提供 IP 的共性）】
  原神/鸣潮: 服装层次+元素设计（"elemental motif, layered outfit"）
  碧蓝幻想: 华丽+金属件（"ornate fantasy armor"）
  影之实力者/回复术士: 暗系+氛围（"dark fantasy atmosphere"）
  命运石之门: 写实系+冷色调（"realistic proportions, cool palette"）
  → 参考 IP = 提取"设计语言"（层次/配色/氛围）——不是抄角色

【实战映射（prompt 模板）】
  现代精致: "modern anime style, layered outfit, delicate details, natural skin, subtle glow"
  高级感: "elegant design, muted palette with red accent, clean lines, breathing space"
  记忆点: "character with mole under eye, unique feature, memorable design"
  大厂感: "game key art quality, refined features, detailed costume, dynamic pose"
