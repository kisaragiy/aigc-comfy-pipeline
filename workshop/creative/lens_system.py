#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/lens_system.py — 镜头语言知识库 v1.0
====================================================
镜头 = 视角+景深+焦点（影视语言移植到插画）——深挖第 20 轮
用法: 构图方向已定 → 加镜头词（景深/焦距）——画面"电影感"来源

【景深（虚实控制——电影感关键）】
  浅景深（大光圈）: 主体清晰+背景虚化——聚焦/梦幻/特写
    → "shallow depth of field, blurred background"（特写标配）
  深景深（小光圈）: 全部清晰——环境感/纪实/大场景
    → "deep depth of field, everything in focus"（远景标配）
  选择性聚焦: 前景虚+主体实+背景虚——层次（"foreground and background blurred"）
  画师规则: 商业图 80% 浅景深（突出主体）——场景图深景深

【焦距（透视效果）】
  广角（24mm 感）: 透视夸张/环境纳入多/边缘拉伸——大气/冲击
    → "wide angle lens, dynamic perspective"
  标准（50mm 感）: 自然/人眼视角——真实/日常
    → "standard lens, natural perspective"
  长焦（85mm+ 感）: 压缩感/背景拉近/人像最美（脸不畸变）
    → "telephoto, compressed background"（人像默认——脸型最美）
  画师规则: 人像特写用长焦感（脸不变形）· 场景用广角感

【焦点（观众注意力控制）】
  主体对焦: 清晰主体（默认）
  失焦主体（柔焦）: 梦幻/回忆/朦胧美（"soft focus, dreamy"）
  光斑（bokeh）: 背景光点虚化——氛围（"bokeh lights in background"）
  焦点引导: 主体锐利+周围渐虚——一眼看到（finalcheck --focus 验证）

【镜头×构图（组合）】
  特写+浅景深 = 情感聚焦（表情/泪痣特写）
  中景+浅景深 = 主体叙事（朋友场景半身+走廊虚化）
  远景+深景深 = 环境叙事（大场景）
  广角+仰视 = 冲击（英雄感）
  长焦+黄昏 = 压缩暖调（电影感经典）

【实战映射（prompt 模板）】
  电影感半身: "half body portrait, telephoto compression, shallow depth of field, blurred corridor background"
  梦幻特写: "close-up, soft focus, dreamy bokeh lights, shallow depth"
  大场景: "wide angle, deep focus, vast environment, everything sharp"
  光斑氛围: "bokeh city lights background, sharp subject, night atmosphere"
