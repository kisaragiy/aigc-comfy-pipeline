#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/text_layout.py — 构图与文字排版知识库 v1.0
==========================================================
封面/海报 = 图+字（文字区设计与构图联动）——深挖第 38 轮
用法: 封面/海报需求 → 图留文字位 → 文字与主体平衡

【文字位置选择（与主体的关系）】
  上部: 标题经典（主体在下——"title space at top"）
  下部: 副标题/标语（主体在上）
  左/右侧: 竖排文字/侧边（"text space on right side"）
  中心: 大字压图（主体让位——"text overlay center"）
  对角: 动感排版（"diagonal text placement"）
  → 文字区 = 主体的"对立面"（图满字少/字满图少）

【文字区设计（构图预留）】
  文字区留白: 纯色/虚化（"clean space for text"）——可读性
  文字区带纹理: 渐变/光效（"gradient area for text"）——美观
  主体避开文字区: 主体放文字区外（"subject positioned away from text area"）
  画师规则: 文字区要"干净"（背景复杂=字看不清）

【视觉平衡（图+字）】
  字重图轻: 文字是主角（海报/宣传——"bold typography, minimal art"）
  图重字轻: 图片是主角（插画封面——"art dominant, small title"）
  平衡: 图字各半（"balanced art and text"）
  → 用途决定: 宣传海报字重/轻小说封面图重

【标题/文字风格（与画风匹配）】
  日漫风: 手写体/粗体（"manga style title"）
  轻小说: 优雅衬线/斜体（"elegant serif title"）
  现代: 无衬线粗体（"modern sans-serif bold"）
  复古: 装饰体（"vintage decorative font"）
  → 文字风格 = 画风延续（不是随便字体）

【实战映射（prompt 模板）】
  轻小说封面: "cover art, girl on lower half, clean gradient space at top for title, elegant"
  海报: "bold poster, subject on right, strong color block on left for text, dynamic"
  游戏 KV: "key visual, character center-bottom, dramatic sky top with space, epic"
