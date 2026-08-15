#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/texture_system.py — 质感细节知识库 v1.0
=======================================================
质感 = 真实感来源（画师"材质语言"）——深挖第 26 轮
用法: 关键物体加材质词（高光/反射/纹理）——画面"贵"起来

【皮肤质感（动漫 vs 写实）】
  动漫: 干净/无毛孔/柔光（"smooth clean skin, soft glow"）
  写实: 毛孔/纹理/光泽（"realistic skin texture, natural pores"）
  高光: 鼻尖/嘴唇/眼睑（动漫高光点——"glossy highlights on nose and lips"）
  画师规则: 动漫皮肤 = 干净+柔光（"脏"的图皮肤纹理乱=失败）

【金属质感（剑/铠甲/饰品）】
  高反射: 亮部集中+环境反射（"polished metal, sharp reflections"）
  哑光金属: 均匀漫射（"brushed metal, matte finish"）
  锈蚀: 旧/战斗（"rusted iron, worn"）
  金/银/铜: 颜色+反光度不同（"gold with warm reflections"）
  → 词: "shiny silver armor with reflections" / "gold ornaments gleaming"

【布料质感（服装真实感）】
  丝绸: 高光流动+垂坠（"silky, flowing highlights"）
  棉: 哑光柔软（"soft cotton"）
  牛仔: 缝合线+磨白（"denim with stitching and fading"）
  皮革: 光泽+纹理（"leather jacket with sheen"）
  毛衣: 编织纹理（"knitted sweater, visible knit pattern"）
  → 布料词=服装词后加——真实感 10 倍

【液体/透明（水/玻璃/冰）】
  水: 反射+折射+波纹（"water surface with reflections and ripples"）
  玻璃: 高光+透视（"glass with specular highlights, see-through"）
  冰: 半透明+裂纹（"ice, translucent, internal cracks"）
  雨滴: 高光+圆润（"raindrops with highlights"）

【环境质感（背景真实感）】
  木头: 年轮/纹理（"wood grain texture"）
  石墙: 粗糙/苔藓（"rough stone wall with moss"）
  雪: 松软反光（"soft snow, sparkling"）
  雾/烟: 体积感（"volumetric mist"）

【实战映射（prompt 模板）】
  精致少女: "smooth skin with soft glow, glossy hair highlights, silk ribbon sheen"
  战士: "shiny steel armor with reflections, leather straps, worn edges"
  雨天: "wet asphalt with reflections, rain droplets on umbrella, glass glistening"
