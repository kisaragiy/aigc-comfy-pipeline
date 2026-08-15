#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/architecture_system.py — 建筑/场景体系知识库 v1.0
=================================================================
建筑风格 = 世界观锚点（背景进阶——深挖第 22 轮）
用法: 场景定"建筑风格"→ 关键词（风格+材质+时代感）→ 背景自动有世界观

【和风建筑（日式——校园/日常/异世界常用）】
  神社/鸟居: 传统/神秘/仪式（"shrine, torii gate, vermilion"）
  和室/障子: 日常/温馨/日式生活（"tatami room, shoji screens"）
  木造町屋: 老街/怀旧（"traditional wooden townhouse street"）
  学校（日本校舍）: 走廊/教室/天台（朋友场景——"japanese school building"）
  关键词: 瓦片/木构/纸窗/暖光

【欧式建筑（异世界/贵族/魔法）】
  哥特教堂: 高穹顶/彩窗/石雕（神圣/神秘——"gothic cathedral, stained glass"）
  城堡: 石墙/塔楼/旗帜（贵族/童话——"medieval castle, stone walls"）
  小镇/石街: 异世界日常（"european old town, cobblestone street"）
  学院（霍格沃茨风）: 尖顶/长廊/壁炉（"magic academy, candlelit hall"）

【现代/都市（日常/赛博）】
  公寓/房间: 日常/个人空间（"modern apartment room, cozy"）
  写字楼/玻璃幕墙: 都市/职场（"glass skyscraper, city"）
  地铁/车站: 都市/等待/相遇（"train station, platform"）
  便利店: 深夜/日常/孤独（"convenience store, fluorescent light"）
  霓虹街: 赛博/夜生活（"neon city street, holographic signs"）

【幻想建筑（异世界/游戏）】
  浮空岛/天空城: 幻想/宏大（"floating islands, sky city"）
  地牢/遗迹: 冒险/神秘（"ancient ruins, mossy stone"）
  魔法塔: 法师/力量（"towering mage tower, magical glow"）
  精灵森林: 自然/优雅（"elven forest, glowing trees, crystal"）

【建筑×情绪（快速映射）】
  神社黄昏=神秘 城堡夜景=贵族/孤独 霓虹街=都市/赛博 遗迹=冒险/历史
  画师规则: 建筑材质词（stone/wood/glass）比风格词更让模型"懂"

【实战映射（prompt 模板）】
  日式学校: "japanese school building, wooden hallway, warm light through shoji, nostalgic"
  哥特教堂: "gothic cathedral interior, tall stained glass windows, light beams, sacred"
  异世界小镇: "fantasy european town, cobblestone street, timber houses, warm evening lamps"
  赛博都市: "cyberpunk city, neon signs, wet streets, towering skyscrapers, night"
