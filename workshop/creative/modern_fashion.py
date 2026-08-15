#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/modern_fashion.py — 现代穿搭深挖 v1.0
======================================================
现代穿搭 = 日常角色风格（画师"时尚语言"）——深挖第 65 轮
用法: 非校服角色 → 穿搭风格词（单品+风格名）

【穿搭风格（六系）】
  学院风（preppy）: 衬衫+针织背心+格纹裙（"preppy, blouse, knit vest, plaid skirt"）——优雅学生
  街头风（street）: 卫衣+工装裤+球鞋（"streetwear, hoodie, cargo pants, sneakers"）——酷
  简约风（minimal）: 纯色+基础款（"minimal style, plain colors, basic fit"）——高级
  甜美风（girly）: 连衣裙+蕾丝+蝴蝶结（"girly, dress, lace, bows"）——可爱
  OL 风: 衬衫+西装裙/裤（"office look, blouse, pencil skirt"）——职业
  休闲风（casual）: T恤+牛仔裤（"casual, tee, jeans"）——日常
  → 穿搭风格 = 角色日常定位（非校服时）

【单品搭配（风格核心）】
  外套: 针织开衫（温柔）/牛仔外套（街头）/风衣（气质）/西装外套（干练）
  下装: 百褶裙（学院）/阔腿裤（休闲）/紧身裙（OL）/牛仔裤（百搭）
  鞋: 小白鞋（清新）/帆布鞋（文艺）/乐福鞋（学院）/靴子（酷）
  包: 帆布包（学生）/单肩包（日常）/手提包（OL）
  → 单品 = 风格的最小单位（换外套=换风格）

【穿搭×季节（联动）】
  春: 薄外套+裙（"spring coat, dress"）
  夏: T恤+短裤/裙（"summer tee, shorts"）
  秋: 毛衣+风衣（"autumn sweater, trench"）
  冬: 大衣+围巾（"winter coat, scarf"）
  → 穿搭季节化 = 场景真实感（与季节系统联动）

【穿搭×气质（风格匹配）】
  清纯=简约/学院 元气=街头/运动 文静=文艺/针织 御姐=OL/气质
  → 穿搭 = 气质外衣（与气质系统联动——四要素的服装 15%）

【实战映射（prompt 模板）】
  学院: "preppy style, white blouse, knit vest, plaid skirt, loafers"
  街头: "streetwear, oversized hoodie, cargo pants, sneakers, cool vibe"
  OL: "office wear, silk blouse, pencil skirt, blazer, elegant professional"
  休闲: "casual outfit, white tee, blue jeans, sneakers, relaxed daily"
