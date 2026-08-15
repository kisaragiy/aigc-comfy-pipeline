#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/inner_text.py — 画面内文字元素知识库 v1.0
=========================================================
画面内文字（招牌/标语/印章——画师世界观细节）——深挖第 63 轮
用法: 场景加文字元素 → 真实感/世界观（AI 文字易崩——小字/模糊处理）

【文字元素类型（场景真实感）】
  招牌/店名: 街道真实感（"shop sign"）
  标语/海报: 时代感（"poster on wall"）
  告示/黑板: 校园感（"bulletin board, chalkboard writing"）
  印章/标志: 和风/官方（"stamp mark"）
  信封/信件: 剧情道具（"letter with handwriting"）
  → 文字 = 世界观细节（1-2 处就够）

【AI 文字崩坏规避（重要）】
  小字: 远处/模糊（"small text, blurred"）——看不清=不崩
  艺术字: 图形化（"decorative letters"）——不要求可读
  无实意文字: 假文字/符号（"abstract symbols"）——安全
  少文字: 1-2 处（多处=必崩）
  → 规则: 可读文字少用（模型写不对）——模糊/图形化安全

【文字×风格（世界感）】
  日文招牌: 和风街道（"japanese sign"）
  霓虹英文: 赛博（"neon sign letters"）
  手写便签: 日常（"handwritten note"）
  印章: 传统（"red stamp"）
  → 文字风格 = 世界观（日/赛博/日常/传统）

【实战映射（prompt 模板）】
  和风街道: "japanese street, shop signs, lanterns, evening"
  赛博: "neon signs with glowing letters, cyberpunk street"
  校园黑板: "chalkboard with writing, classroom, sunlight"
  信物: "letter in hands, soft window light, intimate"
