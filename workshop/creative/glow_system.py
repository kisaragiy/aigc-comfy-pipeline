#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/glow_system.py — 发光材质/霓虹知识库 v1.0
=========================================================
发光 = 幻想/科技/氛围（画师"光污染"艺术）——深挖第 44 轮
用法: 幻想/赛博/魔法 → 发光元素（自发光/辉光/霓虹）→ 画面"亮起来"

【自发光材质（本身发光）】
  魔法水晶/能量: 内部发光（"glowing crystal, inner light"）
  符文/纹路: 线条发光（"glowing runes on surface"）
  火焰: 橙红发光+热气（"fire glow"）
  圣光: 白金光晕（"divine glow"）
  幽灵光: 青蓝冷光（"ghostly cyan glow"）
  → 自发光 = 光源本身（照亮周围——"glow illuminating surroundings"）

【辉光效果（bloom——光溢出）】
  特征: 亮部光晕溢出（"soft bloom, light halo"）——梦幻/华丽
  控制: 小面积辉光=精致/大面积=俗
  适用: 魔法/圣光/霓虹/梦幻
  → 词: "soft bloom effect, gentle glow halo"

【霓虹（赛博/都市夜）】
  霓虹招牌: 彩色发光字（"neon signs, colorful glow"）——赛博标配
  霓虹管: 线条光（"neon tube lighting"）
  霓虹反光: 湿地面倒影（"neon reflection on wet ground"）——电影感
  颜色: 粉/青/紫（"pink and cyan neon"）——经典赛博色
  → 霓虹 = 夜的城市色彩（与时间系统"夜晚"联动）

【光效×场景（快速映射）】
  魔法: 水晶+符文+粒子    赛博: 霓虹+反光+雾
  圣洁: 圣光+光柱+光环    鬼怪: 冷光+漂浮+淡
  战斗: 能量轨迹+爆闪    治愈: 暖光+光点+柔和

【实战映射（prompt 模板）】
  魔法少女: "glowing magic circle, light particles, sparkle effects, magical girl"
  赛博少女: "neon lights reflecting on girl, pink cyan glow, cyberpunk night street"
  圣洁: "divine golden glow, light rays from above, halo, sacred atmosphere"
  幽灵: "pale cyan ghostly glow, floating light, eerie translucent"
