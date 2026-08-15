#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/aura_system.py — 气质类型学知识库 v1.0
=======================================================
气质 = 角色的"味道"（画师最值钱的能力——比五官更难）——深挖第 15 轮
用法: 定角色气质 → 五官+表情+服装+姿势四要素统一 → 气质才立

【八大气质类型（日漫角色体系）】
  清纯系: 圆眼+白肤+黑长直+校服+浅笑（国民初恋——温柔纯真）
    → "innocent, pure, gentle smile, natural beauty"
  元气系: 大眼亮+双马尾/短发+运动感+大笑（活力担当）
    → "energetic, bright smile, lively eyes"
  文静系: 半垂眼+长发+读书姿势+低饱和色（文学少女——安静知性）
    → "quiet, reserved, soft calm eyes, holding book"
  御姐系: 吊梢眼+长睫毛+成熟穿搭+自信笑（从容魅力）
    → "mature confident, sharp eyes, elegant"
  冷淡系: 半睁眼+面无表情+简约（无口——高冷疏离）
    → "expressionless, cool, distant gaze"
  病弱系: 苍白+黑眼圈+柔若无骨（易碎感——怜爱）
    → "pale fragile, delicate, gentle"
  可爱系: 圆脸+腮红+小动作（卖萌担当）
    → "cute, rosy cheeks, adorable"
  神秘系: 半遮眼+异色瞳/泪痣+微笑（谜之魅力）
    → "mysterious, enigmatic smile, mole under eye"（泪痣=神秘系标配）

【气质×五官（四要素统一）】
  眼型定气质 50%（圆=清纯/元气 · 吊梢=御姐 · 半垂=文静/冷淡）
  表情定气质 25%（笑=亲和 · 无表情=冷淡 · 微抿=文静）
  服装定气质 15%（校服=清纯 · 职业装=御姐 · 简约=冷淡）
  姿势定气质 10%（抱书=文静 · 叉腰=御姐 · 绞手=清纯）
  画师规则: 四要素必须同方向——眼型可爱+表情冷淡=气质撕裂

【气质×泪痣（朋友场景联动）】
  泪痣 + 清纯 = 楚楚可怜（小说女主经典——"有感觉"的来源）
  泪痣 + 御姐 = 魅惑     泪痣 + 冷淡 = 谜之吸引力
  泪痣 + 元气 = 调皮     泪痣 + 神秘 = 经典配置
  → 泪痣不是随便加的——它改变气质方向（朋友"加泪痣就完美"=气质升级）

【气质×发色（用户规范内）】
  黑发: 清纯/文静/经典（黑长直=清纯标配）
  棕发: 温和/日常/自然（棕短发=元气/邻家）
  （金/粉=幻想系——非日常角色才用——用户已禁用）

【实战映射（prompt 模板）】
  清纯系: "innocent pure girl, long black hair, gentle smile, school uniform, soft natural look"
  元气系: "energetic girl, bright smile, short hair, lively sparkling eyes"
  文静系: "quiet literary girl, soft eyes, holding book, muted colors"
  冷淡系: "cool expressionless girl, half-lidded eyes, minimal expression, stylish simple outfit"
  神秘系: "mysterious girl, enigmatic smile, mole under left eye, calm composed"
