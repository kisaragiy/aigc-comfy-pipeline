#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/cloth_motion.py — 服装动态知识库 v1.0
======================================================
布料动态 = 画面生命力（画师"风"的表达）——深挖第 45 轮
用法: 静态图加布料动态（裙摆/衣角/发丝）→ 画面"活"起来

【布料动态类型（风吹/动作）】
  裙摆飘起: 动态/可爱/优雅（"skirt flaring up"）——经典
  衣角飘动: 微风/奔跑（"jacket fluttering"）
  发丝飞扬: 风感/氛围（"hair blowing in wind"）——最常用
  围巾/丝带飘: 飘带感（"scarf flowing behind"）——角色辨识度
  斗篷扬起: 英雄/威严（"cape billowing"）
  裙摆+发丝同向: 风统一（"hair and skirt flowing same direction"）——协调

【布料物理（真实感细节）】
  褶皱方向: 沿动作方向（"folds following motion"）
  重力下垂: 静止时垂坠（"fabric draping naturally"）
  布料分层: 内外层分离（"layered fabric"）
  贴身感: 风吹贴身（"fabric clinging"）——动态贴身
  → 布料物理 = 褶皱方向+重力（错了=飘着不自然）

【风的方向（统一性）】
  单方向风: 所有飘动同向（"wind from left, everything flowing right"）——协调
  乱风: 多方向（"chaotic wind"）——混乱/战斗
  无风微动: 呼吸感（"gentle breeze, subtle movement"）——静态图
  → 风方向 = 飘动统一性（多向=乱）

【动态×情绪（快速映射）】
  轻风+微笑=治愈 强风+奔跑=自由 裙摆+回眸=经典
  斗篷+暗色=英雄/神秘 丝带+跳跃=活力
  → 布料动态 = 情绪的"外放"（静=内敛/动=外放）

【实战映射（prompt 模板）】
  经典回眸: "turning back, skirt and hair flaring, dynamic moment, school corridor"
  英雄登场: "cape billowing dramatically, strong wind, heroic stance"
  微风少女: "gentle breeze, hair and ribbon floating softly, serene peaceful"
  奔跑自由: "running with arms open, hair and skirt streaming behind, freedom"
