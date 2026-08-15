#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/relationship_system.py — 角色关系叙事知识库 v1.0
=================================================================
关系 = 距离+视线+接触三语言（画师用空间讲关系）——深挖第 21 轮
用法: 双人图先定"关系"→ 距离/视线/接触三参数 → 拼 prompt

【距离语言（人物间距=关系刻度）】
  亲密距离（<30cm）: 恋人/闺蜜/家人（"very close, intimate distance"）
  个人距离（30-120cm）: 朋友/同事（"close friendly distance"）
  社交距离（1.2-3.6m）: 陌生人/正式（"social distance"）
  公共距离（>3.6m）: 对立/仰望/陌生（"far apart, distant"）
  画师规则: 距离一变关系就变——同两人不同距离=不同故事

【视线语言（谁看谁=关系方向）】
  对视: 平等/情感交流（恋人/对手——"making eye contact"）
  单方注视: 暗恋/观察/守护（"one looking at other"）
  错开视线: 害羞/尴尬/隐瞒（"both looking away"）
  俯视/仰视: 地位差（"looking down at" / "looking up at"）
  望向远方: 同向=同伴感（"both looking into distance"）

【肢体接触层级（接触点=关系进度条）】
  零接触: 普通/陌生/冷战
  衣角/手部: 试探/暧昧（"gently touching sleeve"）
  牵手: 确定关系（"holding hands"）
  搭肩/挽臂: 亲密朋友/情侣（"arm around shoulder"）
  拥抱: 情感爆发/重逢（"hugging"）
  依偎/枕肩: 深度亲密（"resting head on shoulder"）
  捧脸/额头相抵: 极致亲密（"forehead touching"）
  画师规则: 接触点越多=关系越近——一次图选 1-2 个层级

【关系×构图（双人站位）】
  情侣: 近距离+对视+手部接触（依偎构图）
  暗恋: 一前一后+单方注视+保持距离（背影+目光——经典）
  对手: 社交距离+对峙眼神+对称站位（对抗构图）
  姐妹/闺蜜: 并肩+同向+相似姿态（同伴构图）
  师生: 前后+尊重距离+单方指导（"teacher and student"）

【实战映射（prompt 模板）】
  暗恋视角: "girl looking at another girl from behind, longing gaze, slight distance, one-sided"
  闺蜜日常: "two girls walking side by side, arms linked, both laughing, close friendly"
  重逢拥抱: "two girls embracing tightly, emotional reunion, close intimate"
  对峙: "two girls facing at distance, tense eye contact, social distance, confrontational"
