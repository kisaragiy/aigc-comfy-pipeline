#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/animal_system.py — 动物/精灵配饰知识库 v1.0
===========================================================
动物/使魔 = 角色萌点放大器（画师角色设计常用）——深挖第 24 轮
用法: 角色+动物 → 动物词（种类+位置+互动）→ 画面生动度提升

【动物×角色性格（选型）】
  猫: 神秘/傲娇/可爱（猫系角色——"with a cat"）
  狗: 忠诚/阳光/陪伴（犬系——"with a dog"）
  兔子: 胆小/可爱/纯洁（"with a rabbit"）
  狐狸: 狡猾/魅惑/灵气（"with a fox"）
  鸟（乌鸦/鹦鹉）: 神秘/预告/陪伴（"with a raven"）
  龙/幻兽: 力量/幻想（"with a baby dragon"）
  画师规则: 动物=角色性格的外化——猫配傲娇/狗配阳光

【动物位置/互动（构图用法）】
  怀抱: 亲密/保护（"holding a cat in arms"）
  肩头: 陪伴/日常（"bird on shoulder"）
  脚边: 跟随/守护（"dog at feet"）
  头顶: 可爱/搞笑（"cat on head"——萌点）
  对视: 对话/默契（"looking at the cat"）
  → 互动位置 = 关系亲密度

【兽耳/兽尾（兽娘元素——动漫特色）】
  猫耳+尾巴: 萌系/兽娘（"cat ears and tail"）
  犬耳: 活泼/忠诚
  狐耳: 魅惑/灵气
  兔耳: 纯洁/可爱
  注意: 兽耳是"角色自身特征"不是配饰——画风要统一（人+兽耳=兽娘）
  → 词: "cat girl with ears and tail"（设定明确——模型才不画崩）

【动物×情绪（氛围）】
  猫+雨天窗边 = 治愈孤独    狗+夕阳 = 陪伴温暖
  鸟+清晨 = 新生             兔+花丛 = 纯洁春天
  → 动物加入场景 = 画面"活"了（有生命感）

【实战映射（prompt 模板）】
  猫系少女: "girl with black cat in arms, mysterious smile, cozy room"
  兽娘: "cat girl, black cat ears and tail, playful pose, school uniform"
  陪伴: "girl and golden retriever walking at sunset, warm companionship"
  使魔: "girl with tiny dragon on shoulder, magical sparkles, fantasy"
