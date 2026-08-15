#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/lighting_system.py — 光影体系知识库 v1.0
=========================================================
光影是商业图 70% 成败（画师共识）——深挖第 2 轮
用法: 生成前先定"光源三要素"（类型/方向/光色）→ 拼 prompt → compose --value 验证

【光源类型（光的"质感"）】
  硬光（直射/小光源）: 阴影锐利/对比强/戏剧性（正午/聚光灯）
  软光（漫射/大光源）: 阴影柔和/过渡自然/温馨（阴天/窗户光）
  点光: 舞台感/聚焦（烛光/路灯）
  轮廓光（rim light）: 主体边缘亮线——从背景分离/仙气/神秘
  体积光（volumetric）: 光柱可见（丁达尔）——神圣/氛围/尘埃可见
  逆光（backlight）: 剪影/光晕/发丝光——梦幻/回忆
  → 词: "soft window light" / "hard direct sunlight" / "rim light" / "volumetric god rays"

【光的方向（决定体积感）】
  前光: 平/少体积（证件照感——少用）
  侧光: 立体/情绪（经典人像光——明暗各半）
  顶光: 神秘/压迫（正午顶光——眼窝阴影）
  底光: 恐怖/异常（手电从下照）
  后上方 45°: 最自然/最美（伦勃朗光——商业图默认）
  → 词: "45 degree key light" / "side lighting" / "rim light from behind"

【光色（情绪调色板）】
  暖橙（夕阳/烛光）: 温馨/怀旧/治愈
  冷蓝（月光/夜景）: 孤独/冷静/科幻
  青橙对比（赛博）: 现代/冲突/电影感
  粉紫（黄昏魔幻时刻）: 浪漫/幻想
  绿（霓虹/森林）: 诡异/自然/科技
  → 词: "warm golden hour" / "cool moonlight" / "teal and orange" / "magic hour pink"

【光比（明暗强度）】
  低光比（1:2）: 明亮/清新/日常
  中光比（1:4）: 立体/商业图默认
  高光比（1:8+）: 戏剧/神秘/暗黑
  → 词: "low key lighting"（暗调）/ "high key"（明亮柔和）

【光影子分支展开——材质光感】
  皮肤: 柔光显嫩/硬光显质感——商业少女图用柔光
  头发: 高光（发丝反光）——"hair highlights" 增加精致度
  布料: 褶皱阴影（明暗交界）——"fabric folds with shadow"
  玻璃/水: 高光+折射——"reflective surface, caustics"
  → 词: "soft skin light" / "hair highlights" / "caustics"

【value study 验证（管线 G19——compose --value）】
  生成前先灰度看明暗结构（确认光源/体积对）
  明暗分不清 = 光影词没生效——换光词重跑
  画师规则: 先明暗后颜色——value 对了颜色随便上

【实战映射（prompt 模板）】
  温馨校园: "warm golden afternoon sunlight from right, soft shadows, gentle rim light"
  梦幻回忆: "magic hour pink-purple sky, backlit silhouette, soft glow"
  孤独夜晚: "cold blue moonlight, high contrast, deep shadows, lonely streetlight"
  电影感: "teal and orange color grade, cinematic side lighting, volumetric haze"
