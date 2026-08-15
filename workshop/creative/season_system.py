#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/season_system.py — 季节表现知识库 v1.0
======================================================
季节 = 时间锚点（画师用季节符号快速定时代）——深挖第 18 轮
用法: 场景加季节符号词（花/叶/雪/蝉）+ 季节色——画面立刻有"季节感"

【春（樱/新生）】
  符号: 樱花/新芽/校服入学季/春风花瓣
  色: 粉/嫩绿/淡黄（樱花粉+新绿）
  氛围: 开始/恋爱/希望/离别（毕业）
  词: "spring, cherry blossoms falling, pink petals, fresh green"
  经典场景: 樱花树下/开学典礼/花见

【夏（海/蝉/烈日）】
  符号: 大海/蝉/西瓜/风铃/祭典/泳装
  色: 蓝（海天）/绿（树叶）/白（阳光高亮）
  氛围: 活力/自由/青春/冒险
  词: "summer, bright blue sky, sea, cicada summer, intense sunlight"
  经典场景: 海边/夏日祭/教室窗边风扇/蝉鸣午后

【秋（叶/丰收/凉）】
  符号: 红叶/落叶/校服+外套/柿子
  色: 橙红黄（枫叶）/暖棕
  氛围: 成熟/怀旧/文艺/萧瑟
  词: "autumn, red maple leaves falling, golden orange tones, crisp air"
  经典场景: 红叶林/银杏道/黄昏放学（朋友场景走廊也可配秋——黄昏怀旧）

【冬（雪/暖/年末）】
  符号: 雪/围巾/暖气/圣诞/新年
  色: 白蓝（雪）/暖黄（室内光）
  氛围: 静谧/浪漫/团聚/孤独（反差）
  词: "winter, snow, warm scarf, cozy indoor lighting, cold blue outside"
  经典场景: 雪中漫步/窗边暖气/圣诞街灯

【季节×校园（校服图快速季节化）】
  春: 樱花+新校服    夏: 短袖+风扇/海    秋: 外套+红叶    冬: 大衣+围巾
  （朋友场景校服少女——可加季节——春樱/秋叶走廊都适合"青春感"）

【季节×情绪（快速映射）】
  春=开始/恋爱    夏=自由/热烈    秋=怀旧/成熟    冬=静谧/浪漫
  画师规则: 季节色 = 天然色板（选一个季节的色系——画面自动统一）

【实战映射（prompt 模板）】
  春樱少女: "spring, cherry blossom petals floating, pink petals in air, school uniform girl"
  夏日祭: "summer festival, yukata girl, lanterns, fireworks in sky, warm summer night"
  秋叶走廊: "autumn school corridor, red maple leaves outside window, golden evening light"
  冬雪窗边: "winter, snow outside window, girl in warm sweater by heater, cozy contrast"
