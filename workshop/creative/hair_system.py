#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/hair_system.py — 发型体系知识库 v1.0
=====================================================
发型 = 角色第一识别特征（画师共识——背影认人靠发型）——深挖第 5 轮
用法: 设计角色发型时查此表——发型词放 prompt 前半（与脸同等权重）

【发型×性格（发型的叙事功能）】
  长发及腰: 温柔/古典/公主/圣洁（拉长线条——优雅感）
  中长发（过肩）: 日常/亲切/邻家（平衡——最百搭）
  短发（齐肩/耳下）: 活泼/干练/清爽（青春感——朋友场景"短发少女"）
  极短（男仔头）: 帅气/叛逆/中性
  双马尾: 元气/活泼/幼态（高=活力 · 低=温柔）
  单马尾: 运动/清爽/认真（高马尾=元气 · 低马尾=温柔）
  麻花辫/侧辫: 朴素/田园/文学少女（侧辫=可爱细节——朋友场景要求）
  丸子头: 居家/俏皮
  卷发（大波浪）: 成熟/华丽/魅惑
  直发（黑长直）: 清纯/经典/大和抚子（中国高中女生标配——黑长直=国民初恋感）
  → 词: "long straight black hair" / "short bob" / "twin tails" / "low ponytail"

【刘海（脸型修饰+性格）】
  齐刘海（覆盖额）: 幼态/可爱/害羞（眼更突出）
  空气刘海: 时尚/轻盈/温柔
  中分: 成熟/气质/神秘
  斜刘海: 活泼/随性
  无刘海（全露额）: 自信/飒/大气
  画师规则: 刘海长度=情绪开关（长遮眼=阴郁/害羞 · 短露眉=精神）
  → 词: "blunt bangs" / "see-through air bangs" / "side swept bangs"

【鬓发（脸侧修饰——动漫特有细节）】
  前鬓（脸两侧垂发）: 修饰脸型+增加精致度（动漫角色标配）
  鬓发长=优雅 · 鬓发卷=华丽 · 鬓发翘=活泼
  侧辫位置（用户 2026-08-15 定）: 耳朵前一点（平时在耳朵稍微前面）
  → 词: "long side locks framing face" / "side braid in front of ear"

【发饰（点睛）】
  发带/发圈: 元气/运动    蝴蝶结: 少女/可爱
  发簪: 古典/和风        发夹: 日常/细节
  皇冠/发冠: 公主/高贵    耳机: 现代/宅
  → 词: "with red ribbon" / "hair ornament" / "small butterfly bow"

【动态发（头发会说话）】
  静止: 垂顺=安静/端庄
  微飘: 微风=氛围/灵动（"hair slightly blowing"）
  大飘: 强风/战斗/动态感（"flowing hair in wind"）
  逆光发丝: 边缘发光=梦幻/神性（"hair glowing in backlight"）
  → 词: "hair flowing gently in breeze" / "dramatic wind-blown hair"

【发色（用户 2026-08-15 定——中国高中女生现实发色）】
  ✅ 黑（自然黑）/ 棕（深棕/浅棕——天生或自然染）
  ❌ 金/粉/蓝/渐变/白（幻想色——"像中专小太妹"——角色非日常场景才考虑）
  黑发的表现: 纯黑 + 光照反光（蓝/紫高光=自然——不是染发）
  → 词: "natural black hair with blue sheen"（黑发反光——比死黑自然）

【实战映射（prompt 模板）】
  青春短发少女: "short black bob, side braid in front of ear, blunt bangs, hair gently swaying"
  温柔长发学姐: "long straight black hair to waist, air bangs, gentle flowing"
  元气双马尾: "high twin tails, ribbon hair ties, side swept bangs, energetic"
  黑长直经典: "very long straight jet black hair, center part, elegant and pure"
