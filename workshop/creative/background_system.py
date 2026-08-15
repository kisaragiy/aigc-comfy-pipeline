#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/background_system.py — 背景透视知识库 v1.0
==========================================================
背景=氛围担当（background_depth 18 场景的使用指南）——深挖第 7 轮
用法: 背景词要"场景+透视+密度"三层——光说"走廊"模型出默认走廊

【透视类型（空间感）】
  一点透视（正对消失点）: 纵深感/引导视线（走廊/街道/隧道——经典）
    - 消失点在主体后 = 主体被环境"推"向观众
    - 消失点在主体旁 = 主体与环境并列（叙事）
  两点透视（转角）: 空间更真实（建筑/房间角落）
  三点透视（仰/俯）: 巨大感/俯视感（高楼仰视/鸟瞰城市）
  空气透视（远淡近浓）: 自然/大气感（远景模糊偏蓝）
  → 词: "one point perspective corridor with vanishing point" / "atmospheric perspective"

【场景叙事（环境讲故事）】
  教室（窗+课桌+阳光）: 青春/校园/怀旧
  走廊（黄昏+人影）: 放学/寂寞/相遇（朋友场景的走廊=黄昏怀旧感）
  天台（围栏+天空）: 青春/告白/自由（日漫经典场景）
  图书馆（书架+光柱）: 文静/知识/神秘
  街道（霓虹/人群）: 都市/繁华/孤独（夜晚霓虹=赛博孤独）
  雨天（窗+水珠）: 忧郁/治愈/回忆
  樱花（树下+花瓣）: 季节/浪漫/离别
  → 场景词决定"故事背景"——情绪由场景+光共同定

【环境细节密度（背景精细度控制）】
  高密度（细节丰富）: 华丽/真实/信息量大（商业插画背景）
  中密度: 平衡（主体为主+背景有层次）
  低密度（虚化/留白）: 突出主体/氛围感（特写必配虚化背景）
  画师规则: 主体特写→背景虚化（bokeh）· 全身→背景中等· 场景图→背景精细
  → 词: "soft bokeh background" / "detailed background" / "minimal background"

【背景与主体分离（纵深三层次）】
  前景（挡在主体前）: 增加层次/临场感（树叶/窗框/栏杆——"foreground element"）
  中景（主体所在）: 焦点区
  背景（远处）: 氛围区（虚化/渐变）
  画师规则: 三层 = 画面立体（没有前景=平）——前景元素是高级感来源
  → 词: "with blurred foreground leaves" / "framed by window"（框架构图已用）

【背景×情绪（快速映射）】
  阳光走廊+虚化 = 温馨/怀旧（朋友场景）   天台+黄昏 = 青春/告别
  雨窗+冷光 = 忧郁/孤独                 霓虹街+湿地面 = 都市/赛博
  图书馆+光柱 = 静谧/神秘               星空+剪影 = 浪漫/幻想

【实战映射（prompt 模板）】
  校园走廊: "school corridor, warm evening sunlight, blurred windows and doors in background, one point perspective"
  天台黄昏: "school rooftop at sunset, chain link fence, wide open sky, dramatic clouds"
  雨窗: "rain on window glass, blurred city outside, cool blue tones, cozy interior"
  赛博街道: "neon-lit street at night, wet asphalt reflections, crowds blurred, cyberpunk atmosphere"
