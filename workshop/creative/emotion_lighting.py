#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/emotion_lighting.py — 情绪光配方知识库 v1.0
===========================================================
特定情绪的光配方（画师"什么场景用什么光"精确表）——深挖第 61 轮
用法: 定情绪场景 → 直接查配方（光+色+氛围词一条龙）

【告白场景配方】
  光: 黄昏侧光+逆光（"golden sunset side light with rim light"）
  色: 橙粉+微紫（"warm orange-pink, hint of purple"）
  氛围: 风吹+花瓣/落叶（"breeze, falling petals"）
  构图: 双人近距+对视（"close distance, eye contact"）
  → 配方: "golden hour, warm side light, rim light on hair, petals in wind, intimate"

【告别场景配方】
  光: 黄昏逆光+剪影感（"backlit sunset, silhouette edge"）
  色: 橙红+灰蓝（"orange-red sky, blue-grey shadows"）
  氛围: 车站/月台+列车（"train station platform"）
  构图: 背影/隔窗（"viewed from behind, separated"）
  → 配方: "train station, sunset backlight, long shadows, nostalgic farewell"

【治愈场景配方】
  光: 柔窗光+暖白（"soft window light, warm white"）
  色: 米/奶油/浅粉（"cream, pastel, gentle"）
  氛围: 猫/茶/毯子（"cat, tea, blanket"）
  构图: 室内+近景（"cozy interior, close"）
  → 配方: "soft window light, cozy room, tea and blanket, gentle warm"

【孤独场景配方】
  光: 冷月光+单点路灯（"cold moonlight, single lamp"）
  色: 蓝黑+一点暖（"dark blue, single warm point"）
  氛围: 长椅/路灯/夜晚（"bench, streetlight, night"）
  构图: 小主体大环境（"small figure, vast scene"）
  → 配方: "night, cool blue tones, single warm streetlight, small lonely figure"

【战斗高潮配方】
  光: 强侧光+爆闪（"hard side light, explosion flash"）
  色: 高对比+火花橙（"high contrast, ember orange"）
  氛围: 碎片+烟尘（"debris, smoke"）
  构图: 对角+动态（"diagonal, dynamic"）
  → 配方: "battle, hard dramatic light, ember particles, debris, dynamic diagonal"

【回忆场景配方】
  光: 柔光+泛白（"soft hazy light, slightly overexposed"）
  色: 褪色+暖黄（"faded, warm yellow tint"）
  氛围: 旧物/相册（"old objects, photo album"）
  构图: 特写+虚化（"close-up, soft focus"）
  → 配方: "hazy soft light, faded warm tones, old photos, nostalgic dreamlike"

【梦幻场景配方】
  光: 光粒子+辉光（"glowing particles, soft bloom"）
  色: 粉紫+星蓝（"pink-purple, star blue"）
  氛围: 漂浮+星尘（"floating, stardust"）
  构图: 主体发光（"subject glowing softly"）
  → 配方: "dreamy, glowing particles, pink-purple palette, floating, ethereal glow"

【20 个常用情绪配方表（速查）】
  告白=黄昏侧光+花瓣   告别=逆光剪影+车站   治愈=柔窗光+茶
  孤独=冷月+路灯       战斗=硬光+火花       回忆=泛白+旧物
  期待=晨光+窗         紧张=闪烁+暗         安心=暖光+毯
  思念=夜窗+灯光       释然=晴空+微风       愤怒=红光+暗角
  惊讶=强光+定格       甜蜜=粉光+柔焦       悲伤=灰蓝+雨
  恐惧=底光+黑影       兴奋=霓虹+动态       平静=月光+湖
  神圣=圣光+光柱       童趣=亮色+圆润
