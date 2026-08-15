#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/color_psychology.py — 色彩心理学深挖 v1.0
=========================================================
颜色×情绪精确表（画师/营销用色）——深挖第 37 轮
用法: 定情绪 → 查"情绪→颜色"表 → 选主色调 → 拼 prompt

【单色情绪表（色相→情绪）】
  红: 激情/危险/爱/愤怒（主角/战斗/爱情）
  橙: 活力/温暖/食欲/快乐（日常/秋）
  黄: 希望/明快/警告/幼稚（晨光/童趣）
  绿: 自然/和平/病态/嫉妒（治愈/诡异）
  蓝: 冷静/忧郁/理性/科技（孤独/都市）
  紫: 神秘/高贵/幻想/病娇（魔法/贵族）
  粉: 恋爱/少女/温柔/梦幻（浪漫/治愈）
  棕: 踏实/怀旧/温暖/朴素（日常/木质）
  灰: 冷淡/高级/压抑/绝望（性冷淡风/末日）
  黑: 力量/神秘/死亡/优雅（反派/时尚）
  白: 纯洁/神圣/空虚/极简（天使/虚无）

【双色冲突/组合（情绪强化）】
  红+黑: 危险/反派/强烈（"red and black, menacing"）
  蓝+橙（互补）: 电影感/对立（"teal and orange"）——最常用
  粉+紫: 梦幻/少女（"pink and purple, dreamy"）
  蓝+白: 清爽/洁净（"blue and white, fresh"）
  金+黑: 高贵/奢华（"gold and black, luxurious"）
  绿+紫: 诡异/魔幻（"green and purple, eerie"）
  → 双色 = 情绪强化（互补=冲突/相似=和谐）

【三色系统（60-30-10 深挖）】
  60% 主色（背景/大面）: 定情绪基调
  30% 辅色（服装/中等）: 丰富层次
  10% 点缀（细节/小面积）: 视觉焦点
  画师规则: 点缀色用"互补色"（在 60% 主色的补色方向）——主体自动突出
  例: 蓝背景（60%）+ 白服装（30%）+ 红领结（10%）——红是蓝的对比=焦点
  → 词: "navy blue dominant, white secondary, red accent"

【色彩×角色（性格用色——补充）】
  主角色: 红/白（主角光环）
  女二: 粉/紫（可爱/神秘）
  反派: 黑/紫/绿（危险/诡异）
  治愈系: 米/粉/浅蓝（温柔）
  → 服装主色 = 角色定位（角色设计联动）

【实战映射（prompt 模板）】
  治愈日常: "soft warm palette, cream and light blue, gentle cozy"
  电影冲突: "teal and orange complementary, cinematic contrast"
  神秘高贵: "deep purple and gold, mysterious elegant"
  清新校园: "blue and white fresh palette, navy uniform white accents, red ribbon"
