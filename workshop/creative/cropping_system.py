#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/cropping_system.py — 构图与裁切知识库 v1.0
==========================================================
裁切 = 构图的一半（画师"框住什么"比"画什么"重要）——深挖第 42 轮
用法: 决定主体怎么入画（裁切位置=情绪）

【裁切位置（主体怎么被框）】
  头部完整+胸部裁切: 标准特写（安全）
  额头裁切: 极近特写/压迫（"face cropped at forehead"）——情绪重
  下巴裁切（无下巴）: 神秘/半遮（"face cropped at chin"）
  眼裁切（只露眼）: 大特写/惊悚/极致情绪
  腰部裁切: 半身（商业图默认）
  膝盖裁切: 中景（叙事）
  脚踝裁切: 全身略裁（电影感——"cropped at ankles"）
  画师规则: 裁在关节处=不舒服（裁在肉感处）——"不要裁关节"

【裁切×情绪（快速映射）】
  裁额头=压迫 裁下巴=神秘 裁眼=冲击 裁腰=日常 裁踝=电影感
  面部裁切越狠=情绪越重（商业图用"安全裁切"）

【延伸感（裁切外推）】
  主体面向方向留空间（"space in looking direction"）——不闷
  动作方向留空间（"space in movement direction"）——前进感
  视线出画: 看向画外（"looking out of frame"）——想象空间
  画师规则: 主体朝向侧留白 60%（朝向空间>背后空间）

【画面边缘（重要元素别贴边）】
  安全区: 主体/脸避开边缘 5%（"safe margins"）——裁切不丢
  出血区: 背景铺满边缘（"bleed to edge"）——海报
  边缘物体: 前景框架（"foreground element at edge"）——层次
  → 词: "safe margins, subject clear of edges"

【实战映射（prompt 模板）】
  电影半身: "half body, cropped at waist, looking left with space, cinematic"
  压迫特写: "extreme close-up cropped at forehead, intense eyes, tight framing"
  神秘: "face cropped at chin, partial view, mysterious veil"
  远景裁切: "full scene, figure cropped at ankles, sense of continuation"
