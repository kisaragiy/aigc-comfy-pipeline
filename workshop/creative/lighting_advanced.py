#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/lighting_advanced.py — 光影进阶知识库 v1.0
==========================================================
光影进阶（基础光之外的层次——深挖第 36 轮）
用法: 基础光不够 → 加层次（投影/接触阴影/反射）→ 立体感翻倍

【投影（阴影形状=光源/地面）】
  硬投影（清晰边缘）: 直射光/正午/戏剧（"hard cast shadow"）
  软投影（模糊边缘）: 漫射光/阴天/柔和（"soft cast shadow"）
  拉长投影: 低角度光（"long elongated shadow"）——黄昏/清晨
  窗格投影: 窗光经典（"window shadow pattern on floor"）——氛围
  → 投影 = 光源方向的可视化（加投影=空间感）

【接触阴影（AO——物体贴合处）】
  接触处暗色（"contact shadow, ambient occlusion"）——物体"落地"
  裙摆下/脚下/腋下（AO 让角色"站在地面上"——不漂浮）
  → AO = 真实感关键（无 AO=角色悬浮）

【反射（光滑面）】
  地面反射: 湿地面/镜面（"reflection on wet ground"）——电影感
  眼睛反射: 环境反射在眼中（"environment reflection in eyes"）——精致
  金属反射: 高光+环境（"metallic reflections"）
  水面倒影: 对称倒影（"water reflection, mirrored"）
  → 反射 = 材质真实感（哪里反射=哪里是光滑材质）

【焦散（caustics——水/玻璃光斑）】
  水面焦散: 水底光纹（"caustics underwater, light patterns"）
  玻璃焦散: 透过玻璃的光斑（"light caustics through glass"）
  泳池光纹: 壁面波纹（"pool caustic patterns on wall"）
  → 焦散 = 特定场景（水/玻璃）——日常图少用

【光效细节（氛围加分）】
  丁达尔（体积光）: 光柱可见（"volumetric god rays, dust in light"）
  光晕（lens flare）: 镜头感（"subtle lens flare"）——慎用（多了俗）
  光斑（bokeh）: 背景光点（"bokeh lights"）
  边缘光（rim）: 主体轮廓亮线（"rim light separating from background"）
  → 光效 = 每张图 1-2 个（多了=俗）

【实战映射（prompt 模板）】
  窗光午后: "window light with cast shadow pattern, contact shadows, dust in light beams"
  湿街夜景: "wet street with reflections, neon reflections on ground, contact shadows"
  仙气轮廓: "strong rim light on hair and shoulders, dark background, ethereal"
  水下: "underwater scene, caustics light patterns, floating hair, bubbles"
