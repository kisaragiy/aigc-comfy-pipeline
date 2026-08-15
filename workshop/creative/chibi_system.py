#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/chibi_system.py — Q版/表情包知识库 v1.0
========================================================
Q版 = 萌系核心（2-3 头身——表情包/插画点缀）——深挖第 46 轮
用法: Q版需求 → 比例+表情+动作（与正常比例区分）

【Q版比例（2-3 头身）】
  2 头身: 极简萌（头=身体——"2 heads tall chibi"）
  3 头身: 经典 Q 版（头大身小——"3 heads tall chibi"）——最常用
  特征: 头大/眼大（占脸 1/2+）/手脚短小/身体圆润
  → 词: "chibi style, 3 heads tall, oversized head, big sparkling eyes"

【Q版表情（颜艺/夸张）】
  夸张笑: 嘴大+眼眯（"huge grin, closed happy eyes"）
  泪奔: 喷泪+嘴张（"crying with fountain tears"）
  生气: 鼓腮+红晕（"puffed cheeks, angry"）
  震惊: 眼珠变小+嘴成 O（"shocked, small pupils, O mouth"）
  卖萌: 歪头+眨眼（"head tilt, winking"）
  → Q版表情 = 放大情绪（比正常比例夸张 2 倍）

【Q版动作（萌点）】
  蹦跳: 双脚离地（"jumping happily"）
  举手: 回答/欢呼（"raising hand"）
  抱物: 抱玩偶/食物（"hugging plushie"）
  打滚: 开心/耍赖（"rolling on ground"）
  歪头杀: 经典萌（"head tilt with confused look"）
  → Q版动作 = 简化+萌化（动作幅度大）

【Q版×场景（用途）】
  表情包: 单角色+纯色背景（"chibi, plain background"）——贴纸感
  插画点缀: 主图角落小 Q 版（"small chibi in corner"）——可爱
  漫画格: 分镜 Q 版（"chibi panel"）——搞笑/吐槽
  → Q版用途 = 表情/点缀/搞笑（不是主图）

【实战映射（prompt 模板）】
  经典 Q 版: "chibi girl, 3 heads tall, big sparkling eyes, cheerful jump"
  表情包: "chibi crying with fountain tears, exaggerated, plain background, sticker style"
  卖萌: "chibi head tilt, winking, hands together, kawaii"
  生气: "chibi puffed cheeks, angry stomping, comical"
