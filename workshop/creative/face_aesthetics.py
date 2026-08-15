#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/face_aesthetics.py — 面部美学细节知识库 v1.0
=============================================================
商业图面部细节（画师/角色设计）——深挖第 4 轮
用法: 生成"表情/眼神"时查此表——眼睛是灵魂（观众先看眼睛）

【眼睛美学（灵魂所在）】
  瞳孔高光（catchlight）: 眼睛里的白点/高光——"有神"的关键
    - 大高光（2 点）: 活泼/少女/元气
    - 小高光（1 点）: 冷静/深邃/成熟
    - 无高光: 死寂/黑化/失神（恐怖/悲伤极限）
  虹膜细节: 渐变/星形/圆环——精致感
  眼型（character_design 11 眼型——情绪补充）:
    圆眼（大）: 天真/可爱/惊讶     吊梢眼: 精明/强势/反派
    下垂眼: 温柔/可怜/无辜          丹凤眼: 古典/神秘/气质
  睫毛: 上翘=少女感 · 长而下垂=温柔 · 浓密=华丽
  → 词: "large sparkly eyes with big catchlights" / "calm eyes with subtle highlight" / "sharp upturned eyes"

【眉毛（情绪杠杆——比眼睛变化更快）】
  上挑: 生气/惊讶/强势    下垂（八字）: 委屈/可怜/哀伤
  平直: 冷静/中性/坚毅    微皱: 担忧/思考
  画师规则: 眉毛动 1px = 情绪大不同——表情主要由眉+嘴决定
  → 词: "raised eyebrows, surprised" / "slightly furrowed brows, worried"

【嘴/表情（情绪定型）】
  微笑（嘴角上翘）: 友好/满足    大笑（露齿）: 开朗/爽快
  抿嘴: 隐忍/紧张/思考         嘴角下垂: 不高兴/哭
  微张（惊讶/喘息）: 呆滞/诱惑  咬唇: 紧张/挑逗
  → 词: "gentle smile" / "bright smile with teeth" / "tight-lipped, nervous"

【面部比例（美型标准——动漫化）】
  三庭五眼（真人）→ 动漫放宽: 眼睛更大/下巴更尖/鼻子简化为点
  脸宽 = 5 眼宽（标准）· 动漫 4-4.5 眼宽（眼更宽）
  眼距 = 1 眼宽（标准）· 眼距宽 = 天真/呆 · 眼距窄 = 精明/锐利
  下巴: 尖=精致/成熟 · 圆=可爱/幼态
  腮红（blush）: 位置/形状 = 情绪（颧骨=害羞 · 眼下=委屈 · 鼻梁=醉/晒）
  → 词: "beautiful large eyes, small nose, delicate chin" / "cute round face with blush"

【表情微差（同一情绪的不同程度）】
  害羞: 微低头+眼神上瞟+腮红+抿嘴笑
  委屈: 八字眉+含泪+嘴微嘟
  冷淡: 平眉+半睁眼+嘴角平直（无表情但有微差）
  微笑的三种: 礼貌笑（嘴角+眼神不变）/ 真心笑（眼睛眯起——笑到眼）/ 假笑（嘴角+眼神冷）
  画师规则: 眼睛笑不笑 = 真笑假笑关键（眼睛眯=真心）
  → 词: "eyes crinkling in genuine smile" / "shy glance upward with blush"

【泪痣细节（用户 2026-08-15 定——内眼角）】
  位置: 左眼内眼角下方（x≈0.445, y≈0.40——不是眼下正中）
  大小: 小点（r≈0.0022 比例——视觉 2-3px）——画师画泪痣就是"点一下"
  作用: 记忆点/色气/楚楚可怜（泪痣=经典萌点）
  注意: 泪痣 vs 泪滴（tear 歧义——模型常画成泪珠）——用 beauty mark/mole 词

【实战映射（prompt 模板）】
  元气少女: "large sparkling eyes with big catchlights, bright genuine smile, rosy blush"
  温柔学姐: "gentle soft eyes, subtle smile, long lashes, serene expression"
  冷淡美人: "calm half-lidded eyes, composed expression, slight upturned eyes"
  委屈哭颜: "downturned eyebrows, teary sparkling eyes, pouting mouth, blush"
