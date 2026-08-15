#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/film_texture.py — 胶片/颗粒质感知识库 v1.0
==========================================================
胶片感 = 怀旧/文艺（画师"时间感"表达）——深挖第 52 轮
用法: 怀旧/文艺图 → 胶片词（颗粒/色偏/光晕）→ 时间感

【胶片颗粒（grain）】
  颗粒度: 细颗粒=现代胶片/粗颗粒=老照片（"fine grain" / "heavy grain"）
  作用: 统一画面/掩盖瑕疵（"film grain" 同时是遮丑）
  注意: 颗粒+清晰主体（颗粒在暗部明显）
  → 词: "film grain texture" / "grainy vintage photo"

【胶片色偏（不同胶卷的色）】
  Kodak 暖: 肤色偏暖黄（"kodak film look, warm skin tones"）
  Fuji 绿: 偏青绿（"fuji film, greenish tones"）
  Portra 柔: 柔和低饱和（"portra film, soft muted"）
  Polaroid 复古: 褪色+暗角（"polaroid look, faded, vignette"）
  → 胶卷名 = 色偏方向（模型可能不认识——用"warm film/ faded"更稳）

【胶片特征（其他）】
  暗角（vignette）: 四角变暗（"vignette, darker edges"）——聚焦+复古
  漏光（light leak）: 橙红光斑（"film light leak, orange streak"）——LOMO感
  眩光（halation）: 亮部光晕（"halation glow"）——梦幻
  划痕/灰尘: 老照片（"scratches, dust on old photo"）——年代感
  → 胶片特征 = 颗粒+色偏+暗角+漏光（选 2-3 个）

【胶片×情绪（快速映射）】
  胶片+暖=怀旧 胶片+冷=文艺 胶片+粗颗粒=回忆/日记
  → 胶片 = 时间滤镜（"这张图是过去"）

【实战映射（prompt 模板）】
  老照片: "vintage photo look, heavy grain, faded warm colors, scratches, nostalgic"
  LOMO: "lomo style, light leak orange streak, high contrast, vivid colors"
  文艺日记: "film photo, fine grain, muted tones, soft light, literary"
  宝丽来: "polaroid photo, faded, vignette, instant photo feel"
