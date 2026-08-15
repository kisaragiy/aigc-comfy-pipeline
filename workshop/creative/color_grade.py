#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/color_grade.py — 调色叙事知识库 v1.0
====================================================
电影调色（LUT 概念移植到 AI prompt）——深挖第 51 轮
用法: 生成后 colorgrade 之外——生成前用"调色词"定叙事基调

【电影调色（LUT 风格——prompt 可表达的）】
  青橙（teal-orange）: 好莱坞标配（肤色暖+背景冷——"teal and orange grade"）
  低饱和灰: 写实/压抑/文艺（"desaturated muted grade"）
  高饱和: 广告/活力（"vibrant saturated grade"）
  暗调（low-key）: 神秘/悬疑（"dark low-key grade"）
  亮调（high-key）: 明亮/治愈（"bright high-key grade"）
  复古胶片: 褪色/偏黄（"vintage film look, faded warm"）
  → 调色词 = 整图色调方向（比单色词更整体）

【分色技巧（暗部/亮部不同色）】
  暗部偏蓝+亮部偏暖: 层次（"cool shadows, warm highlights"）——经典
  暗部偏紫: 梦幻（"purple shadows"）
  暗部偏绿: 诡异（"greenish shadows"）
  亮部偏粉: 少女（"pink highlights"）
  → 分色 = 暗部色+亮部色分开控制（层次丰富）

【对比度曲线（软/硬）】
  低对比: 柔和/雾感/文艺（"low contrast, soft"）
  高对比: 强烈/硬朗/戏剧（"high contrast, punchy"）
  S 曲线: 暗部更深+亮部更亮（"cinematic S-curve contrast"）
  → 对比度 = 画面"软硬"（低=柔/高=硬）

【调色×情绪（快速映射）】
  青橙=电影 低饱和灰=文艺/压抑 暗调=悬疑 亮调=治愈 复古=怀旧
  → 调色 = 情绪的整体包装（与色彩心理学联动）

【实战映射（prompt 模板）】
  电影感: "teal and orange cinematic grade, cool shadows warm skin, film look"
  文艺灰: "desaturated muted tones, low contrast, literary film aesthetic"
  复古: "vintage film look, faded warm colors, slight grain, nostalgic"
  梦幻亮调: "bright high-key grade, soft pink highlights, airy dreamy"
