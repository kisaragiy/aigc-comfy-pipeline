#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/color_system.py — 色彩体系知识库 v1.0
=======================================================
商业图色彩管理（画师配色理论）——深挖第 3 轮
用法: 生成前定"色调情绪"+ 主色 → 拼 prompt → colorgrade 统一

【色调情绪（整体色相决定感受）】
  高饱和暖色（橙红黄）: 活力/热情/食欲/危险（节日/战斗/美食）
  低饱和冷色（灰蓝）: 冷静/高级/忧郁（都市/科技/文艺）
  高饱和冷色（宝蓝/青）: 清爽/科技/未来（夏季/科幻）
  低饱和暖色（米灰/驼）: 温馨/复古/质感（日常/怀旧）
  粉紫色调: 浪漫/少女/幻想
  黑白灰（无彩）: 极简/高级/肃穆
  → 词: "warm saturated palette" / "muted cool tones" / "pastel pink dreamy"

【配色结构（画师主色/辅色/点缀色）】
  主色 60%（背景/大面积）——定调
  辅色 30%（服装/次要）——丰富
  点缀色 10%（眼睛/饰品/细节）——焦点
  画师规则: 画面最多 3 个主色系——超了=花（colorgrade 救不回）
  → 词: "limited palette, navy blue and white with red accent"

【互补色（撞色——视觉冲击）】
  红↔绿 / 橙↔蓝 / 黄↔紫
  用法: 主体用互补色背景 → 主体自动突出（不需要大对比度）
  例: 暖橙光照 + 蓝阴影 = 经典电影配色（青橙）
  → 词: "complementary colors, orange and teal"

【相似色（和谐——温柔统一）】
  相邻色相（蓝-青-绿）: 和谐/安静/自然
  用法: 整体统一氛围（森林绿系/海洋蓝系）
  → 词: "analogous palette, blues and teals"

【低饱和氛围（高级感/怀旧）】
  降低饱和度 → 高级感/真实感（电影化）
  保留主体高饱和 → 主体突出（背景低饱和）
  → 词: "desaturated background, vibrant subject"

【色彩叙事（角色用色心理学）】
  白色/浅色: 纯洁/天使/圣女
  黑色/深色: 神秘/反派/力量
  红色: 热情/危险/主角（红发角色=主角标配）
  蓝色: 冷静/忧郁/理性
  粉色: 少女/温柔/恋爱
  绿色: 自然/病态/嫉妒
  金色: 高贵/财富/神圣
  → 角色发色瞳色选择 = 性格暗示（character_design 已接此逻辑）

【colorgrade 应用（管线 G22）】
  生成后统一: 自动白平衡（去偏色）+ 饱和度微调（去"花"）
  手动控制: --warm 0.1（暖调偏移）/ --saturation 0.95（降饱和高级感）
  顺序: 先 colorgrade 再泪痣（泪痣色 55,40,50 深棕黑——与肤色融合）

【实战映射（prompt 模板）】
  温馨校园: "warm muted palette, cream and navy, soft gold accents"
  高级冷淡: "muted cool tones, desaturated blue-grey, minimal palette"
  浪漫幻想: "pastel pink and lavender, dreamy soft colors"
  电影冲击: "teal and orange complementary, vibrant cinematic color"
