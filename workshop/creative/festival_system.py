#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/festival_system.py — 节日/庆典场景知识库 v1.0
=============================================================
节日 = 情感峰值（画师"集体欢乐"表达）——深挖第 59 轮
用法: 节日图 → 元素（灯/花/烟火）+人群+光 → 庆典感

【节日元素（快速识别）】
  夏日祭: 灯笼+浴衣+摊位（"summer festival, lanterns, yukata"）
  花火大会: 烟花+夜空+人群（"fireworks festival, night sky"）——经典
  圣诞: 圣诞树+灯饰+雪（"christmas tree, lights, snow"）
  新年: 初日+和服+门松（"new year, kimono, shrine"）
  中秋: 圆月+灯笼+团圆（"moon festival, lanterns"）
  元宵: 花灯+汤圆（"lantern festival"）
  → 节日 = 符号元素（灯/花/月/树——1-2 个就认出）

【灯饰（节日氛围核心）】
  灯笼: 红/暖光（"red paper lanterns, warm glow"）——东方
  彩灯: 星星点点（"string lights, bokeh"）——浪漫
  烟花: 空中绽放（"fireworks blooming"）——高潮
  烛光: 温馨（"candlelight"）——安静
  → 灯 = 节日的光（暖色+光斑——"warm glow, light bokeh"）

【人群/氛围（庆典感）】
  人群模糊: 热闹（"crowd, blurred motion"）——活力
  双人独处（人群背景）: 节日里的两人（"alone together in festival crowd"）——浪漫
  摊位烟火气: 蒸汽+灯光（"food stalls, steam, lights"）——生活
  → 人群 = 背景热闹/前景主角（对比）

【节日×情绪（快速映射）】
  祭典=热闹/恋爱 烟花=浪漫/离别 圣诞=温馨/礼物 新年=希望/团聚
  → 节日 = 情感峰值时刻（告白/离别都在这发生）

【实战映射（prompt 模板）】
  花火大会: "fireworks festival, girl in yukata, lanterns, night sky explosion, festive"
  圣诞: "christmas, tree with lights, snow, cozy warm, gift box"
  夏日祭: "summer festival, paper lanterns, food stalls, yukata girls, warm evening"
  新年: "new year shrine visit, kimono girl, torii, morning light, hopeful"
