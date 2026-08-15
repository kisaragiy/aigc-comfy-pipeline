#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/time_system.py — 时间表现知识库 v1.0
======================================================
时间段 = 光色+叙事双锚点（画师用光定时间）——深挖第 19 轮
用法: 定时间 → 光色词+场景词（每个时间段的色温独特）

【清晨（6-9 点）】
  光: 低角度金白/空气清新/影子长
  色: 淡金+蓝（冷清感+初光暖）
  氛围: 出发/新生/安静
  词: "early morning, low golden sunlight, fresh air, long shadows"
  经典: 晨跑/上学路上/晨读

【正午（11-14 点）】
  光: 顶光硬/高对比/影子短
  色: 高饱和蓝白（曝光感）
  氛围: 活力/直接/炎热（或圣洁——教堂顶光）
  词: "noon, bright overhead sunlight, harsh shadows, vivid blue sky"

【黄昏（16-19 点——商业图黄金时段）】
  光: 低角度暖橙/影子长/天空渐变（橙-粉-紫）
  色: 橙金+粉紫（全天最美）
  氛围: 怀旧/浪漫/告别/回家（朋友场景走廊=黄昏）
  词: "golden hour, warm orange sunlight, long shadows, pink-purple sky"
  经典: 放学/夕阳走廊/海边日落（"魔幻时刻"——商业图最爱）

【夜晚（19-24 点）】
  光: 月光冷蓝+人造光暖（路灯/室内）
  色: 蓝黑+暖黄点缀（经典冷暖对比）
  氛围: 静谧/孤独/秘密/浪漫
  词: "night, moonlight, warm streetlight glow, cool blue tones"
  经典: 夜景街道/室内灯下/星空

【深夜（0-5 点）】
  光: 几乎无自然光（月光/屏幕光/台灯）
  色: 深蓝黑+小面积冷白
  氛围: 孤独/压抑/专注/秘密
  词: "deep night, desk lamp glow, dark blue atmosphere, quiet"
  经典: 熬夜学习/失眠窗边/路灯下

【时间×情绪（快速映射）】
  晨=希望 午=活力/直白 黄昏=怀旧/浪漫 夜=静谧/秘密 深夜=孤独/专注
  画师规则: 黄昏=商业图默认（最美光）· 深夜=情绪重图

【时间×场景（光色组合）】
  黄昏走廊+窗光: 怀旧（朋友场景）   夜晚教室+灯: 秘密/努力
  清晨海边+金白: 出发感              深夜房间+台灯: 孤独/专注

【实战映射（prompt 模板）】
  黄昏走廊: "golden hour, warm orange light through corridor windows, long shadows, nostalgic"
  夜晚路灯: "night, blue hour, warm streetlamp glow on girl's face, cool background"
  清晨教室: "early morning classroom, soft golden light, dust particles in light beams"
  深夜台灯: "late night, single desk lamp, warm light circle, dark surroundings, focused mood"
