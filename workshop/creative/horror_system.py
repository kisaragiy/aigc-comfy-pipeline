#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/horror_system.py — 恐怖/暗黑系知识库 v1.0
=========================================================
恐怖氛围（暗黑系/悬疑插画）——深挖第 40 轮
用法: 暗黑/恐怖图 → 光+构图+色彩三件套（日常图反用）

【恐怖光（光线异常=恐惧源）】
  底光: 从下往上照（"light from below, unsettling"）——鬼片标配
  闪烁光: 忽明忽暗（"flickering light"）——不安
  单点冷光: 黑暗中一点冷光（"single cold light in darkness"）——孤独恐怖
  逆光剪影（恐怖版）: 黑影+边缘光（"dark silhouette with rim light"）——压迫
  → 恐怖光 = 光的"异常"（底光/闪烁/单点）

【恐怖构图（空间压迫）】
  巨物压迫: 巨大阴影/巨物笼罩（"oversized shadow looming"）
  狭窄空间: 走廊/通道挤压（"narrow claustrophobic corridor"）
  窥视视角: 从暗处看（"viewed from darkness"）——观众=窥视者
  背影: 看不见脸（"figure from behind, face hidden"）——未知恐惧
  留白恐怖: 大量黑暗+小主体（"vast darkness, tiny figure"）——虚无
  → 恐怖构图 = 空间压迫/未知（看不见=最恐怖）

【恐怖色彩（冷暗为主）】
  暗蓝/黑: 基本盘（"dark blue-black tones"）
  血红点缀: 危险（"blood red accent"）
  惨绿: 病态/鬼（"pale green, sickly"）
  灰白（褪色）: 死亡/苍白（"desaturated pale, lifeless"）
  → 恐怖色 = 低明度冷色 + 小面积强色点缀

【恐怖元素（细节）】
  影子异常: 影子方向不对/影子有自己的动作（"shadow moving independently"）
  镜子异常: 镜中不同（"mirror showing something else"）
  娃娃/人偶: 恐怖经典（"doll with empty eyes"）
  雾/烟: 隐藏（"thick fog hiding something"）
  → 恐怖细节 = 日常元素"不对劲"

【暗黑系（非恐怖——哥特/暗黑美学）】
  区别: 暗黑系=美/优雅（哥特）· 恐怖=吓人
  暗黑系词: "dark gothic aesthetic, elegant darkness, candlelight, roses, ornate"
  → 暗黑系 = 暗色+精致（不是吓人——是氛围）

【实战映射（prompt 模板）】
  恐怖走廊: "dark school corridor at night, flickering single light, long shadow, unsettling"
  哥特暗黑: "gothic girl in dark elegant dress, candlelight, dark roses, mysterious beauty"
  剪影恐怖: "dark silhouette in mist, rim light, face hidden, ominous"
  镜中异常: "girl looking at mirror, reflection different, cold blue tone, eerie"
