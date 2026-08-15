#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/age_system.py — 年龄表现知识库 v1.0
====================================================
年龄感（动漫角色年龄表达——画师造型基础）——深挖第 14 轮
用法: 设定角色年龄 → 查年龄特征 → 五官+体型+气质三要素

【幼态（萝莉/小学生 6-12）】
  五官: 眼大（占脸 1/2+）· 鼻小（点）· 脸圆 · 额头宽
  体型: 矮（3-4 头身）· 手脚短 · 肩窄
  特征: 头身比大（头大身小）· 腮红 · 牙齿微露（虎牙）
  气质: 天真/好奇/爱哭
  → 词: "young girl, large innocent eyes, round face, small stature"

【少女（初中-高中 12-18——主力年龄段）】
  五官: 眼大但比例协调（1/3）· 脸微尖 · 五官精致化
  体型: 5-6.5 头身（纤长）· 曲线初现
  特征: 青春感（笑容/活力）· 校服 · 水灵
  气质: 元气/害羞/成长中（朋友场景"短发少女青春感"=此段）
  → 词: "high school girl, youthful, bright eyes, slender figure"

【成年（20+——御姐/成熟）】
  五官: 眼稍小（更真实比例）· 下巴尖 · 轮廓分明（颧骨/下颌）
  体型: 7+ 头身 · 曲线明显（胸/腰/臀）
  特征: 睫毛长 · 嘴唇丰满 · 妆容感
  气质: 从容/性感/知性/威严
  → 词: "mature woman, elegant, defined features, long lashes, full lips"

【年龄×服装（年龄识别辅助）】
  幼: 连衣裙/背带裤/动物帽
  少女: 校服/便服/运动装（青春）
  成年: 职业装/礼服/成熟穿搭
  画师规则: 服装+发型+五官三一致——年龄才立住（校服+圆脸+短发=少女）

【年龄×脸型（核心差异）】
  圆脸（宽下巴）: 幼   瓜子脸（尖下巴）: 成年
  婴儿肥（腮部鼓）: 幼  颧骨显（脸有骨感）: 成年
  额头: 幼宽大 · 成年正常
  → 词: "round baby face" / "mature cheekbones"

【实战映射（prompt 模板）】
  高中少女: "high school girl, 16 years old, round face with slight baby fat, big sparkling eyes, school uniform"
  大学生: "college student, 19, slender, soft mature look, casual outfit"
  御姐: "mature elegant woman, sharp cheekbones, long lashes, confident gaze, business attire"
