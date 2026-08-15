#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/mythology_system.py — 神话/宗教意象知识库 v1.0
=============================================================
天使/恶魔/神 = 象征体系（画师用符号讲故事）——深挖第 47 轮
用法: 神话角色 → 象征元素（翅膀/光环/符号）→ 身份立现

【天使系（圣洁/救赎）】
  翅膀: 白羽翼（"white feathered wings"）——圣洁
  光环: 头顶光环（"golden halo"）——神圣
  圣光: 背后光芒（"divine light behind"）
  服饰: 白/金（"white and gold robes"）
  堕落天使: 黑羽/断翼（"black tattered wings, fallen angel"）——反差
  → 天使 = 白翼+光环+圣光（堕落=黑化版本）

【恶魔系（堕落/诱惑）】
  翅膀: 蝙蝠翼（"bat-like wings"）——恶魔
  角: 黑角/红角（"dark horns"）
  尾巴: 尖尾（"pointed tail"）
  眼睛: 红瞳/竖瞳（"red glowing eyes"）
  服饰: 黑/红（"black and red, gothic"）
  → 恶魔 = 角+翼+尾+红瞳（可爱恶魔=小角+小尾）

【神/女神（权威/威严）】
  光辉: 全身光辉（"radiant divine aura"）
  服饰: 华服/长袍（"ornate divine robes"）
  法器: 权杖/圣物（"holding divine scepter"）
  背景: 神座/神殿（"divine throne, temple background"）
  → 神 = 光辉+华服+法器（"divine" 词带出）

【宗教符号（背景点缀）】
  十字架: 圣/牺牲（"cross"）
  教堂彩窗: 神圣（"stained glass"）
  符文/法阵: 魔法/仪式（"magic circle, ancient runes"）
  莲花: 东方/佛性（"lotus flower"）
  → 符号 = 世界观宗教感（1-2 个点缀）

【神话×情绪（快速映射）】
  天使+泪痣=悲悯美 恶魔+微笑=诱惑 女神+冷面=威严
  堕落天使+暗=赎罪/挣扎（小说角色常见——朋友小说可用）
  → 神话角色 = 象征+情绪（反差=故事）

【实战映射（prompt 模板）】
  天使: "angel girl, white feathered wings, golden halo, divine glow, gentle sacred"
  堕落: "fallen angel, black torn wings, dim halo, dark elegant, tragic beauty"
  小恶魔: "cute devil girl, small horns, bat wings, playful grin, gothic dress"
  女神: "goddess in radiant robes, divine aura, holding scepter, majestic"
