#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/prop_system.py — 道具系统知识库 v1.0
====================================================
道具 = 角色的"第三只手"（画师用道具叙事）——深挖第 23 轮
用法: 角色+道具 → 道具词（名称+材质+位置）→ 手部有依托（顺带防手崩）

【手持道具（身份/性格标识）】
  书/笔记本: 文静/学生/知识（"holding a book"）
  手机/耳机: 现代/社交/沉浸（"holding smartphone, earphones"）
  伞: 优雅/雨天/神秘（"holding umbrella"）
  花束: 约会/毕业/幸福（"holding bouquet"）
  乐器（吉他/小提琴）: 文艺/音乐（"playing guitar"）
  剑/武器: 战士/冒险（"holding sword"——幻想系）
  食物（面包/饮料）: 日常/治愈（"holding a drink"）
  画师规则: 手持道具=手部有依托（防崩）——道具也是性格标签

【环境道具（场景叙事物）】
  课桌+书: 学生日常    窗台+盆栽: 生活感
  路灯: 夜晚孤独       长椅: 等待/休息
  信箱: 等待/思念      时钟: 时间/焦虑
  信/照片: 回忆/离别   日记: 秘密/内心
  → 环境道具 1-2 个就够——多了乱

【道具×情绪（叙事功能）】
  递伞: 温柔/照顾     送花: 喜欢/道歉
  翻书: 安静/沉浸     看表: 焦急/赶时间
  握照片: 思念/回忆   撕纸: 生气/决绝
  道具=无声台词——比对话更有画面感

【道具细节（材质+状态）】
  材质: 旧书（泛黄书页）/新书（光亮封面）——"old worn book" vs "new book"
  状态: 破损=经历/完整=日常——"torn photograph" 有故事
  光效: 发光道具=魔法/科技——"glowing crystal"
  → 道具加材质/状态词 = 叙事深度

【实战映射（prompt 模板）】
  文静少女: "girl holding a book, standing in library, warm light"
  夜晚思念: "girl holding an old photograph, by window, blue night light, nostalgic"
  校园日常: "girl with backpack and drink, walking in school corridor, cheerful"
  魔法系: "girl holding glowing crystal staff, magical light particles, fantasy"
