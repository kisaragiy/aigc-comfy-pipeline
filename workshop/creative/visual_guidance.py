#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/visual_guidance.py — 视觉引导线系统知识库 v1.0
==============================================================
引导线 = 控制观众眼睛（画师/广告核心技法）——深挖第 31 轮
用法: 想让观众"先看主体→再看环境" → 设计引导线 → prompt 加入

【引导线种类（眼睛的路径）】
  实线引导: 道路/轨道/栏杆/河流（"path leading to subject"）
  虚线引导: 光柱/影子/脚印/花瓣（"light beam guiding to subject"）
  视线引导: 角色看向主体（"character looking toward subject"）
  手势引导: 手指方向（"hand pointing toward"）
  明暗引导: 亮区在主体（"bright area on subject"）
  色彩引导: 点缀色在主体（"color accent on subject"）
  → 引导线 = 环境元素指向主体（观众自然跟着走）

【路径节奏（眼睛停留点）】
  单线直达: 快速/直接（"direct path to subject"）——冲击
  曲折路径: 慢/探索（"winding path"）——神秘/叙事
  多线汇聚: 聚焦（"multiple lines converging on subject"）——隆重
  断点节奏: 停-走-停（"rhythmic visual stops"）——层次
  → 路径节奏 = 观感速度（直=快/曲=慢）

【入口/出口（画面流程）】
  入口: 观众眼睛进入处（通常左上方——"entry point at top left"）
  出口: 眼睛离开处（避免——主体旁不要出口线）
  画师规则: 画面只有一个"出口"（其他线都指向主体）
  → 词: "all lines lead to subject, single focal point"

【引导线×构图（组合）】
  三分法+引导线: 主体在交点+线指向它（经典商业构图）
  对角线+引导线: 对角路径+主体在中点
  S 形+引导线: 曲线路径+主体在曲线弯点
  → 引导线是"骨架"——构图是"框架"——两者叠加

【终检验证（finalcheck --focus——管线已有）】
  VLM 评估: "主体是否一眼可见/引导是否清晰"
  失败修复: 加引导词（path/beam/line）重跑
  → 词: "clear focal point" / "visual path to subject"

【实战映射（prompt 模板）】
  走廊引导: "corridor with vanishing point leading to girl, natural eye path"
  光柱引导: "light beam from window illuminating girl, rays guide the eye"
  花瓣路径: "cherry petals scattered in path toward girl, soft guidance"
  多线汇聚: "railings and shadows all converging toward subject, strong focus"
