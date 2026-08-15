#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/outfit_lineup.py — 角色换装谱系知识库 v1.0
==========================================================
同一角色多套服装（换装逻辑——角色服装谱系）——深挖第 68 轮
用法: 角色多套服装 → 换装逻辑（场合/情绪/成长）→ 服装谱系

【换装逻辑（为什么换装）】
  场合: 校服→日常→正式（"school uniform to casual to formal"）
  情绪: 低落穿暗色/开心穿亮色（"mood-based outfit"）
  成长: 学生→职场（服装进化线）
  事件: 祭典浴衣/泳装/舞台装（event outfits）
  → 换装 = 场合+情绪+成长（逻辑清晰=角色立体）

【服装谱系（角色多套装的体系）】
  常服（默认）: 角色识别装（"signature outfit"）——辨识度最高
  变体（换色/换季）: 同款不同色（"color variation"）——系列感
  场合装: 校服/浴衣/礼服（"event outfit"）
  战斗/特殊: 战斗服/魔法装（"battle outfit"）
  → 谱系 = 常服为中心+变体+场合+特殊（4 类）

【换装×辨识度（保持"是同一个人"）】
  核心特征保持: 发色/泪痣/瞳色（"same hair, same mole"）——永远不变
  服装变化: 其他全可变（"different outfit"）
  → 换装 = 服装变+特征不变（认人靠特征不靠衣服）

【服装×性格（服装心理学补充）】
  领口: 高领=保守/低领=开放
  颜色: 素色=内敛/花色=外放
  版型: 宽松=放松/修身=正式
  配饰: 多=精致/少=简约
  → 服装细节 = 性格微表情（换装时性格也微变）

【实战映射（prompt 模板）】
  校服→日常: "same girl, school uniform version and casual dress version, consistent features"
  系列色变: "same outfit in different colors, navy and cream versions, series"
  特殊场合: "same character in yukata for festival, same hair and mole"
  成长换装: "same character, student outfit and professional outfit, growth"
