#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/battle_system.py — 战斗场景知识库 v1.0
======================================================
战斗 = 动态+特效+冲击（画师"爆发"表达）——深挖第 56 轮
用法: 战斗图 → 冲击/特效/姿态三件套（与动态系统联动）

【冲击表达（hit impact）】
  冲击线: 从碰撞点放射（"impact lines radiating"）——漫画感
  冲击波: 环形扩散（"shockwave ring"）——力量感
  尘土/碎片: 地面破裂（"debris, dust clouds"）——真实冲击
  定格瞬间: 碰撞前一刻（"freeze frame before impact"）——张力
  → 冲击 = 放射线+碎片+定格（选 2 个）

【战斗姿态（攻防）】
  攻击: 前冲+发力（"lunging attack"）
  防御: 格挡+后撤（"blocking stance"）
  闪避: 侧身+衣摆甩动（"dodging, clothes trailing"）
  蓄力: 收势+能量聚集（"charging energy"）——发招前
  收招: 落地+烟尘（"landing, dust settling"）
  → 姿态 = 战斗"动词"（攻/防/闪/蓄/收）

【技能特效（幻想系）】
  能量波: 光束/光弹（"energy beam, projectile"）——经典
  元素: 火球/冰晶/雷电（"fireball" / "ice crystals" / "lightning"）
  魔法阵: 脚下法阵（"magic circle under feet"）——仪式感
  剑光/刀气: 弧形轨迹（"blade arc, slash trail"）——速度
  → 特效 = 属性可视化（火=橙红/冰=蓝白/雷=黄白）

【战斗×构图（动态构图）】
  对角冲突: 双方对角对峙（"diagonal confrontation"）
  俯冲: 从上方攻击（"diving attack from above"）
  仰视反击: 从下方反击（"counter from below"）
  速度线背景: 高速移动（"speed lines background"）
  → 战斗构图 = 对角线+速度（静止构图=没战斗感）

【实战映射（prompt 模板）】
  拔刀: "drawing sword, blade arc trail, dynamic pose, speed lines"
  魔法: "casting spell, magic circle, glowing energy, particles, fantasy battle"
  冲击: "impact moment, shockwave ring, debris flying, freeze frame tension"
  对决: "two fighters diagonal confrontation, weapons crossed, dramatic lighting"
