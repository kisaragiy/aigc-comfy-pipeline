#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/motion_system.py — 动态模糊/速度感知识库 v1.0
=============================================================
动态 = 画面活力（静态图表达运动——深挖第 27 轮）
用法: 动作场景加动态词（速度线/残影/模糊）→ 画面"动"起来

【速度表达（三种方式）】
  速度线（speed lines）: 漫画手法（"speed lines behind"）——动感/冲击
  运动模糊（motion blur）: 摄影手法（"motion blur on background"）——真实感
  残影（afterimage/trail）: 能量感（"energy trail behind"）——幻想/高速
  画师规则: 主体清晰+背景模糊=速度（主体也模糊=看不清）

【动态部位（谁动谁模糊）】
  头发/衣摆飘动: 微动态（"hair and skirt flowing"）——风/运动
  肢体动作: 大动态（"mid-action pose"）——跳跃/奔跑
  背景: 横向模糊（"horizontal motion blur background"）——速度
  粒子/尘埃: 空气感（"dust particles swirling"）

【动作张力（画师动态技巧）】
  动势线（action line）: 全身一条曲线（"dynamic action line"）
  重心偏移: 前倾=奔跑/后仰=躲避
  关节极限: 手臂展开=跳跃（"limbs fully extended"）
  准备动作: 蓄力=即将爆发（"crouching ready to jump"）
  → 动态图 = 重心+动势线+飘动三件套

【动态×场景（快速映射）】
  奔跑: 前倾+发飘+背景横糊
  跳跃: 舒展+裙摆上扬+粒子
  战斗: 残影+特效+冲击线
  舞蹈: 旋转+衣摆弧线+光点

【实战映射（prompt 模板）】
  奔跑少女: "running girl, forward lean, hair and skirt flowing behind, motion blur background"
  跳跃: "mid-jump, limbs extended, skirt flaring, dynamic action line, dust particles"
  战斗: "action pose with energy trail, speed lines, dynamic impact"
  风动: "standing in strong wind, hair and clothes blowing dramatically, petals flying"
