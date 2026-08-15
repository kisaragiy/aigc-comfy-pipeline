#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/anime_studio_styles.py — 动漫流派特征知识库 v1.0
================================================================
动画公司画风特征（AI 可表达的关键词）——深挖第 33 轮
用法: 想要"某社感觉" → 用特征词组合（不是直接说公司名）

【京都动画（京阿尼）——精致日常】
  特征: 精细可爱/柔光/日常细节/眼睛大而有神
  词: "kyoto animation style, refined cute characters, soft glow, detailed eyes"
  适用: 日常/治愈/校园（朋友场景"青春感"可选）

【新海诚——光影唯美】
  特征: 光影写实/高饱和天空/细节背景/云彩绝美
  词: "makoto shinkai style, realistic lighting, vivid sky, detailed clouds, beautiful background"
  适用: 风景/氛围/离别（黄昏走廊=新海诚感）

【吉卜力——手绘自然】
  特征: 手绘感/自然色/田园/魔法日常
  词: "ghibli style, hand-drawn, warm natural colors, gentle whimsy"
  适用: 治愈/冒险/奇幻日常

【新房昭之（SHAFT）——另类构图】
  特征: 倾斜构图/极简背景/大色块/符号化
  词: "shaft style, tilted compositions, minimal background, bold color blocks"
  适用: 心理/另类/艺术感（慎用——非大众审美）

【骨头社（BONES）——动作张力】
  特征: 动作流畅/打斗张力/肌肉线条
  词: "bones studio style, dynamic action, fluid movement"
  适用: 战斗/动作

【PA Works——风景文艺】
  特征: 风景细腻/青春文艺/职场日常
  词: "pa works style, detailed scenery, youth literary mood"
  适用: 青春/文艺（朋友场景"青春感"备选）

【Ufotable——特效华丽】
  特征: 特效粒子/光影爆炸/动作华丽
  词: "ufotable style, flashy effects, particle effects, dramatic lighting"
  适用: 战斗/奇幻（鬼灭感）

【画风混搭注意】
  公司风格词 1 个就够（2+ 冲突=模型混乱）
  公司名可能不识别（训练数据少）——用特征词更稳（"refined cute" 比 "kyoto animation" 稳）
  → 首选特征词组合——公司名作补充

【实战映射（prompt 模板）】
  京阿尼日常: "refined cute style, soft glow, detailed sparkling eyes, cozy school daily"
  新海诚黄昏: "realistic sunset lighting, vivid gradient sky, detailed clouds, emotional scenery"
  吉卜力田园: "warm hand-drawn style, lush nature, gentle magical daily life"
