#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/worldview_system.py — 系列世界观整合知识库 v1.0
=============================================================
系列作品（一套插画/漫画/游戏设定——世界观统一）——深挖第 50 轮
用法: 系列多图 → 世界观符号（重复元素）+场景关联 → 成套感

【世界观符号（系列识别——重复出现的元素）】
  角色符号: 泪痣/发饰/服装细节（角色固定段）
  环境符号: 特定建筑/物件（"the bell tower" / "the red umbrella"）
  色彩符号: 系列主色（每卷基调色）
  光线符号: 特定光源（"golden hour always"）
  → 符号 = 系列"签名"（观众看到就认出系列）

【场景关联（多图间的连接）】
  同一场景不同时间: 走廊晨/午/昏（"same corridor at different times"）——时间叙事
  同一场景不同季节: 春樱/秋叶走廊（"same place, different seasons"）
  同一角色不同场景: 学校/家/天台（"same character, multiple locations"）
  远景→特写递进: 环境→角色（"establishing shot to close-up"）——系列开场
  → 场景关联 = 空间/时间的连续性（系列"活"起来）

【系列节奏（图与图的关系）】
  开头: 环境/氛围（世界建立）
  中段: 角色/事件（叙事推进）
  高潮: 特写/情绪（情感爆点）
  结尾: 留白/远景（余韵）
  → 系列节奏 = 远景↔特写交替（单调=审美疲劳）

【统一性检查（系列交付——consistency_check 已实现）】
  角色统一: 发色/泪痣/服装（每张核对）
  画风统一: 同一风格词（水彩/赛璐璐）
  光源统一: 共用光源句
  色彩统一: 系列色板（每卷基调色）
  → 统一性 = 角色卡+风格+光源+色板四件套

【世界观×情绪（系列基调）】
  治愈系: 暖色+日常+微笑（朋友小说——温暖基调）
  暗黑系: 冷色+阴影+压抑
  冒险系: 动态+广阔+热血
  悬疑系: 雾+暗+异常
  → 系列基调 = 全系列统一情绪（不串味）

【实战映射（prompt 模板）】
  系列开场: "establishing shot, school at golden hour, warm nostalgic, series opening"
  系列角色: "same character, black hair and mole, consistent uniform, series style"
  四季: "same school corridor, cherry blossoms spring / maple autumn, series"
  系列高潮: "emotional close-up, same character, tears and mole, series climax"
