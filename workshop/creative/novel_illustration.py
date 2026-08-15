#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/novel_illustration.py — 轻小说插画/封面规范 v1.0
================================================================
轻小说插画（朋友小说女主场景——专业规范）——深挖第 29 轮
用法: 小说插画/封面需求 → 按此规范（角色+氛围+文字区）

【插画 vs 封面（用途差异）】
  插画（内页）: 竖版/叙事性/角色+场景（竖版 768x1344——"vertical illustration"）
  封面: 竖版/角色突出+文字留白（"cover art, space for title"）
  卷头彩页: 大画面/氛围优先（"opening color page"）
  → 用途决定: 插画讲场景 · 封面卖角色

【封面规范（商业封面三要素）】
  ① 角色突出（占画面 50%+——读者第一眼看到女主）
  ② 文字区（上/下留白——"space for title at top"）
  ③ 氛围色（全书基调色——系列封面统一色系）
  画师规则: 封面 = 角色+情绪+留白（不是场景图）

【小说插画叙事（场景选型）】
  登场（角色首次出场）: 全景/环境+角色（交代世界）
  情感（内心戏）: 特写/表情+光（情绪为主）
  场景（重要情节）: 中景/动作+环境（叙事）
  关系（双人）: 双人互动（关系表达）
  → 每章插画 = 选一个叙事类型（不是每张都特写）

【系列统一（一套小说插画）】
  角色卡固定: 发色/发型/服装/泪痣——所有图一致（consistency_check 核对）
  画风统一: 同一风格词（水彩/赛璐璐——整套一致）
  色系统一: 每卷一个主色（卷一蓝/卷二粉——系列感）
  光源统一: 共用光源句
  → 系列 = 角色卡+风格+色系三统一（多图一致性）

【文字区/版式（交付给编辑/排版）】
  封面: 上 1/3 留空（标题位）——"top third empty for title"
  插画: 不占文字位（主体避开边缘）
  出血（bleed）: 边缘留 3-5% 安全区（裁切不掉重要内容）
  → 词: "safe margins, subject centered with space around"

【实战映射（prompt 模板）】
  卷头彩页: "opening illustration, full scene, girl in school corridor at golden hour, novel art"
  封面: "light novel cover, girl character prominent, space for title at top, soft dreamy colors"
  情感插画: "emotional scene, close-up, tear mole visible, warm light, introspective mood"
  系列统一: "same character, consistent black hair and mole, uniform style across series"
