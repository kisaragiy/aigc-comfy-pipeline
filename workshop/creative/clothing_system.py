#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/clothing_system.py — 服装结构知识库 v1.0
=========================================================
服装=角色第二识别特征（fashion_depth 148 条目的使用指南）——深挖第 6 轮
用法: 服装词要"具体到结构"（款式+细节+材质）——光说"校服"模型自由发挥会乱

【制服体系（校园/职业——日常场景主力）】
  水手服: 领子（关东领/关西领/名古屋领）+ 领巾/领结（红蓝黄）
    - 关东领（方形大领）: 经典/可爱
    - 关西领（v形尖领）: 干练/优雅
  西式校服（blazer）: 西装外套+领带+百褶裙——英伦/精英感
  白衬衫+百褶裙: 通用/清新（中国校服变体）
  运动服（中国校服）: 红白/蓝白——国风怀旧
  → 词: "sailor uniform with square collar and red neckerchief" / "blazer school uniform with tie"

【日常穿搭（非制服场景）】
  连衣裙: 温柔/少女（碎花=田园 · 纯色=简约）
  衬衫+裙子: 知性/清爽
  T恤+牛仔裤: 日常/休闲/真实感
  毛衣（oversize）: 慵懒/温暖/居家感
  大衣/风衣: 气质/成熟/都市
  洛丽塔（lolita）: 华丽/可爱/幻想（蕾丝+裙撑）
  → 词: "white blouse with pleated skirt" / "cozy oversized sweater" / "elegant trench coat"

【幻想服装（非日常角色——异世界/战斗）】
  铠甲: 骑士/战士（胸甲+护肩+裙甲——"knight armor with pauldrons"）
  魔法袍: 法师/神秘（长袍+兜帽+符文——"wizard robe with hood"）
  和服/汉服: 传统/东方（振袖=正式 · 浴衣=夏日祭）
  军装风: 指挥官/威风（双排扣+勋章——"military uniform with medals"）
  朋克: 叛逆（皮衣+铆钉+链子）
  → 幻想服装关键词要带"材料"（leather/metal/fabric）——模型才知道质感

【面料质感（画师细节——决定真实感）】
  丝绸: 反光/顺滑/垂坠（"silky fabric with sheen"）
  蕾丝: 半透/花纹（"lace trim"）
  牛仔: 硬挺/缝合线（"denim with stitching"）
  针织/毛衣: 纹理/柔软（"knitted texture"）
  皮革: 光泽/硬（"shiny leather"）
  纱/薄纱: 透光/轻盈（"sheer tulle"）
  → 面料词加在服装词后——"silk dress" 比 "dress" 真实 10 倍

【服装细节（褶皱/配件——精致度来源）】
  褶皱（folds）: 关节处自然褶皱——"natural fabric folds at elbows"
  领子/袖口: 翻领/荷叶边/泡泡袖——"ruffled collar" / "puff sleeves"
  配饰: 项链/手链/腰带/胸针——"with delicate necklace"
  袜子/鞋: 白袜+皮鞋=校服经典 · 过膝袜=萌点（fashion_depth 有详细 D 数）
  → 细节词 = 精致度（少=普通 · 多=华丽——按角色定位控制密度）

【服装×性格（角色设计联动——character_design 已有）】
  水手服+黑发+泪痣 = 经典文学少女/温柔系
  西装+短发 = 干练/强势
  洛丽塔+双马尾 = 可爱/幻想
  军装+红瞳 = 冷峻/战士
  → 服装+发型+表情三者一致 = 角色立住

【实战映射（prompt 模板）】
  校服少女: "navy sailor uniform, white square collar, red neckerchief, pleated skirt, black stockings"
  日常清新: "white blouse, light blue pleated skirt, cardigan over shoulders"
  温柔文学: "cream knit sweater, long skirt, soft fabric folds"
  和风: "furisode kimono with floral pattern, obi sash, wooden geta"
