#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/weather_system.py — 天气系统知识库 v1.0
=======================================================
天气 = 情绪放大器（画师氛围三件套之一）——深挖第 17 轮
用法: 场景词+天气词+光词组合——天气词改变整个氛围

【晴天（太阳直射）】
  氛围: 明快/活力/希望（青春图默认）
  光: 硬光/高对比/影子清晰
  词: "clear sunny day, bright sunlight, blue sky"
  适用: 校园/运动/约会（happy 场景）

【雨天（雨+湿润）】
  氛围: 忧郁/治愈/思念/浪漫（经典情绪天气）
  光: 灰暗漫射/地面反光/水珠
  词: "rainy day, raindrops on window, wet ground reflections, soft grey light"
  变体: 小雨（温柔忧郁）/暴雨（强烈情绪）/雨后（清新希望——彩虹）
  适用: 离别/思念/室内窗边/共伞（浪漫）

【雪天】
  氛围: 静谧/纯净/浪漫/孤独
  光: 高亮漫射（雪反光）/蓝白冷调
  词: "snow falling, white landscape, cold blue tones, quiet serene"
  变体: 大雪纷飞（浪漫）/雪后初晴（清新）/雪夜（静谧孤独）
  适用: 冬季/告白/孤独感/童话

【雾天】
  氛围: 神秘/朦胧/梦境/悬疑
  光: 漫射无影/层次感（空气透视强）
  词: "misty fog, soft diffused light, mysterious atmosphere, faded distance"
  适用: 幻想/神秘角色出场/回忆场景

【阴天（无直射）】
  氛围: 平静/日常/略带沉闷
  光: 软光无影/低对比（天然柔光箱）
  词: "overcast sky, soft diffused light, muted colors"
  适用: 日常/文艺/写实感（高级感——低饱和）

【天气×情绪（快速映射）】
  晴=开心 雨=忧郁/浪漫 雪=浪漫/孤独 雾=神秘 阴=平静
  画师规则: 天气与情绪一致——开心图配雨=反讽（高级用法——慎用）

【天气×光（组合技巧）】
  雨后+夕阳: 金色反光+湿润感（绝美——"rainbow after rain, golden light"）
  雪+夜景: 蓝白+路灯暖光（冷暖对比经典）
  雾+清晨: 神秘+新生（"morning mist, golden sunrise"）

【实战映射（prompt 模板）】
  雨天窗边: "rainy day, girl by window, raindrops on glass, soft grey light, melancholic cozy"
  雪夜路灯: "snowy night, warm streetlight glow, falling snow, cold blue atmosphere"
  雨后夕阳: "after rain, golden sunset reflections on wet ground, fresh air, hopeful"
  晨雾校园: "misty morning schoolyard, soft diffused light, mysterious serene"
