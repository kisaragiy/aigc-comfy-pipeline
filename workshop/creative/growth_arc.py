#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/growth_arc.py — 角色成长弧线视觉知识库 v1.0
===========================================================
同角色不同时期（小说/漫画常见需求）——深挖第 34 轮
用法: 同一角色"幼年/现在/未来"对比 → 特征保持+年龄差异表达

【同一角色的不变项（认人关键）】
  核心特征保持: 发色/瞳色/泪痣/眼型（"same hair color, same mole"）
  轮廓保持: 脸型基础（圆脸→微尖——但整体可认）
  气质延续: 性格特质（眼神/姿态风格）
  → 多时期图 = 特征固定段 + 年龄变化段（consistency_check 核对核心特征）

【幼年版（年龄-10）】
  变化: 脸更圆/眼更大/头发更长或更短（幼态）
  保持: 发色/泪痣（泪痣从小就有=记忆点）
  词: "younger version, round face, bigger innocent eyes, child"

【现在版（当前年龄）】
  标准: 正常年龄特征
  词: "present version, current age, characteristic look"

【未来/成长版（年龄+5-10）】
  变化: 脸尖/眼稍小/气质成熟/服装升级（校服→职业装）
  保持: 发色/泪痣/眼型基础
  词: "older version, mature features, sharper jaw, confident"

【成长对比图（同框多时期）】
  三格对比: 幼年/现在/未来并列（"three panels showing growth"）
  镜像对比: 过去与现在面对（"past and present facing each other"）
  剪影过渡: 剪影从幼到成（"silhouette progression"）
  → 对比图 = 特征一致 + 年龄差异（重点在"认得出是一个人"）

【成长×情感（叙事）】
  幼年: 天真/依赖    现在: 成长/挣扎    未来: 成熟/释然
  画师规则: 成长图的情绪 = 眼神变化（幼年亮眼→成年深邃）

【实战映射（prompt 模板）】
  幼年版: "same character younger, round face, big innocent eyes, short hair, same mole under eye"
  成长版: "same character older, mature expression, long hair, same mole, elegant outfit"
  对比三格: "three panel growth sequence, same character at 10/16/22, consistent features"
