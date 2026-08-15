#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/body_type.py — 特殊体型表现知识库 v1.0
======================================================
体型 = 角色物理身份（画师"身形语言"）——深挖第 66 轮
用法: 角色体型 → 身形词+比例词（与年龄/气质联动）

【体型类型（动漫可表达的）】
  纤瘦型: 高挑+细（"slender, willowy"）——气质/优雅
  匀称型: 标准（"balanced figure"）——百搭
  丰满型: 曲线明显（"curvy, hourglass"）——成熟/性感
  幼态型: 娇小（"petite, small stature"）——可爱/萝莉
  运动型: 紧实（"athletic, toned"）——活力
  高大型: 高（"tall, long limbs"）——御姐/帅气
  → 体型 = 气质物理基础（纤瘦=优雅/丰满=成熟）

【体型×气质（联动）】
  纤瘦+清纯=仙气 丰满+御姐=魅惑 娇小+元气=可爱 高+冷淡=女王
  → 体型与气质同向（不一致=撕裂）

【比例控制（画师技巧）】
  头身比: 5 头身=可爱/6.5 头身=标准少女/7+ 头身=御姐/模特
  腰线: 高腰=腿长（"high waistline"）——显高
  肩宽: 窄肩=柔/宽肩=帅（"narrow shoulders, delicate"）
  → 比例词 = 头身+腰线+肩宽（2 个就够）

【体型×服装（搭配）】
  纤瘦+宽松=文艺 丰满+修身=性感 娇小+裙=可爱 高+大衣=气场
  → 服装版型 = 体型配合（修身/宽松/高腰）

【实战映射（prompt 模板）】
  仙气纤瘦: "slender willowy figure, delicate, flowing dress, ethereal"
  御姐丰满: "curvy hourglass figure, elegant mature, fitted dress"
  元气娇小: "petite small stature, cute, cheerful energy"
  女王高挑: "tall elegant figure, long limbs, commanding presence"
