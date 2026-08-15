#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/rhythm_system.py — 画面节奏感知识库 v1.0
========================================================
节奏 = 画面"韵律"（画师抽象美——疏密/重复/对比）——深挖第 67 轮
用法: 画面"平/闷" → 加节奏（疏密对比/元素重复）→ 生动

【节奏三要素（点线面）】
  点: 细节/亮点（眼睛/光斑/花瓣——"scattered dots, sparkles"）
  线: 动势/引导（道路/衣褶——"flowing lines"）
  面: 色块/区域（大色块/背景——"bold shapes"）
  → 好画面 = 点线面都有（只有面=平/只有点=乱）

【疏密对比（节奏核心）】
  疏: 留白/简单区（"open space"）
  密: 细节/复杂区（"detailed area"）
  画师规则: 疏密对比 = 视觉休息+聚焦（全密=累/全疏=空）
  例: 背景疏+主体密（"simple background, detailed subject"）——经典
  → 疏密 = 对比度（差异产生节奏）

【重复与变化（韵律）】
  重复: 同类元素（窗格/灯串/花瓣——"repeating elements"）——秩序
  变化: 重复中的差异（大小/颜色——"varied repetition"）——趣味
  画师规则: 重复 3 次以上成节奏（1-2 次不算）
  → 重复 = 节奏感（建筑/灯/花最易用）

【节奏×情绪（快速映射）】
  强节奏（重复+对比）: 活力/现代 弱节奏（均匀）: 平静/极简
  不规则节奏: 自然/野趣 规则节奏: 秩序/庄严
  → 节奏 = 画面心跳（强=快/弱=慢）

【实战映射（prompt 模板）】
  点线面: "scattered petals (dots), flowing hair line, bold background shapes"
  疏密: "clean simple background, highly detailed subject, contrast"
  重复: "repeating lanterns, rhythmic pattern, festival street"
  自然: "irregular natural rhythm, scattered leaves, organic"
