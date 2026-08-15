#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/multichar_system.py — 多角色构图知识库 v1.0
===========================================================
双人/多人图（比单人难——关系/空间/主次）——深挖第 13 轮
用法: 多角色图 → 先定"关系"→ 空间布局 → 分别描述每个角色

【双人关系（互动决定构图）】
  并肩（同向）: 同伴/战友/朋友（"standing side by side"）
  面对面: 对话/对峙/深情（"facing each other"）
  背靠背: 信赖/并肩作战（"back to back"）
  一前一后: 守护/跟随（"one behind the other"）
  依偎: 亲密/情侣/姐妹（"leaning on each other"）
  距离感: 远=陌生/暗恋 · 近=亲密/紧张
  → 词: "two girls facing each other, close distance" / "leaning shoulder to shoulder"

【空间关系（谁在哪——prompt 顺序）】
  SDXL 规则: 先分别描述每个角色 → 再写空间关系（左/右/前/后）
  例: "1girl with black hair on the left, 1girl with brown hair on the right, they face each other"
  主次: 主角描述详细（服装/表情）——配角简略（避免模型抢戏）
  → 词: "girl with black hair on the left" / "second girl in background"

【双人互动手势（关系表达）】
  牵手: 亲密/伙伴（"holding hands"）
  搭肩: 哥们/姐妹（"arm around shoulder"）
  捧脸: 深情/审视（"holding face in hands"）
  递物: 交流/赠予（"handing something"）
  对视: 情感核心（"making eye contact with each other"）
  → 互动手势 = 关系的直接表达——比站位更有信息

【多人（三人+）构图】
  三角站位: 稳定/团体（三人经典——"triangular arrangement"）
  前后层次: 主角前/配角后（景深分层）
  动作呼应: 中间主角+两侧配角动作呼应
  → 词: "group of three, triangular composition, main girl in center"

【多角色×情绪（快速映射）】
  朋友: 并肩+笑+手部接触      对手: 面对面+距离+对峙眼神
  恋人: 依偎+对视+肢体接触    主仆: 前后+恭敬姿态
  师生: 一前一后+距离感        姐妹: 并肩+相似服装

【质检注意（多角色崩坏点）】
  手部崩坏×2（每人多一双手——风险翻倍）
  角色特征混淆（黑发角色画成棕发——用固定段区分）
  多角色建议: 半身/中景（全身多人=细节崩）
  → 一致性: 每个角色独立固定段（发色+服装）+ 空间关系句

【实战映射（prompt 模板）】
  闺蜜: "two girls standing side by side, black hair girl on left, brown hair girl on right, both smiling, arms linked"
  对峙: "two girls facing each other at distance, tense atmosphere, one with arms crossed"
  守护: "girl standing behind protective older sister, hand on shoulder"
  三人组: "three girls triangular composition, main girl in center with twin tails"
