#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/info_density.py — 信息密度控制知识库 v1.0
==========================================================
密度 = 画面"信息量"（画师减法艺术）——深挖第 62 轮
用法: 画面"乱/空" → 查密度控制（什么该留什么该删）

【密度三档（视觉负载）】
  低密度（极简）: 1 主体+留白（高级/孤独/文艺）
  中密度（平衡）: 主体+1-2 环境元素（商业图默认）
  高密度（丰富）: 多人/多物/细节（华丽/热闹/史诗）
  → 密度 = 情绪选择（低=静/高=闹）——不是越高越好

【减法的原则（画师"删什么"）】
  删与主题无关的: 背景杂物（"simple background"）
  删冲突颜色: 超 3 色系（colorgrade 兜底）
  删重复元素: 同类只留 1 个
  保留焦点: 主体+引导线（信息都指向主体）
  → 减法 = 问"这个元素服务主题吗？"——不服务就删

【焦点密度（注意力集中度）】
  单焦点: 一切指向主体（"single focal point"）——商业图默认
  双焦点: 两个主体+关系（双人图）
  无焦点: 环境图（风景/氛围——"no single focal point"）
  → 焦点数 = 观众注意力分配（1 个=清晰/2 个=关系/0 个=氛围）

【密度×构图（快速映射）】
  留白构图=低密度 中景=中密度 人群/细节=高密度
  → 构图已定密度——密度词是确认（"minimal" / "detailed" / "busy"）

【实战映射（prompt 模板）】
  极简: "minimal composition, single subject, vast clean background"
  平衡: "balanced composition, subject with soft background details"
  丰富: "rich detailed scene, many elements, lively atmosphere"
  焦点: "everything leads to subject, clean surrounding"
