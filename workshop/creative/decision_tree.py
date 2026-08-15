#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/decision_tree.py — AI 生图决策树 v1.0（终轮整合）
=================================================================
60+ 知识文件的整合入口——从需求到成图的完整决策流程
用法: 任何生图需求 → 按决策树走（每步查对应知识文件）→ 一次到位

═══════════════════════════════════════════════
AI 生图决策树（商业画师标准流程）
═══════════════════════════════════════════════

STEP 0: 需求解析（delivery_system.py）
  ├─ 用途? → 插画(竖版768x1344) / 封面(竖版+文字区) / 宣传(横版1344x768) / 头像(方896)
  ├─ 角色? → 发色/发型/瞳色/服装/特征（character_design.py + hair_system.py）
  ├─ 情绪? → 青春/温柔/冷淡/治愈（aura_system.py + emotion_lighting.py）
  ├─ 参考? → 有 ref 图（风格/氛围参考）
  └─ 数量? → 单张 / 系列（worldview_system.py）

STEP 1: 角色定型
  ├─ 发色: black/brown（用户规范——hair_system.py）
  ├─ 发型: 长发/短发/双马尾/侧辫（hair_system.py）
  ├─ 面部: 眼型/表情/泪痣（face_aesthetics.py）
  ├─ 服装: 校服/日常/传统（clothing_system.py + traditional_clothes.py + modern_fashion.py）
  ├─ 气质: 清纯/元气/文静/御姐/冷淡（aura_system.py）
  └─ 体型: 纤瘦/匀称/丰满/娇小（body_type.py）

STEP 2: 构图选择（thumbnail.py 24 方向 + composition_psychology.py）
  ├─ 情绪→构图: 孤独=留白/浪漫=黄昏+双人/神秘=剪影（composition_psychology.py）
  ├─ 进阶: S形/包围/张力（composition_advanced.py）
  └─ 裁切: 特写/半身/全身（cropping_system.py）

STEP 3: 光影设计（lighting_system.py + lighting_advanced.py）
  ├─ 光源: 柔窗光/黄昏光/月光/霓虹（emotion_lighting.py 配方）
  ├─ 层次: 投影/AO/轮廓光/体积光（lighting_advanced.py）
  └─ 验证: compose --value 灰度检查（G19）

STEP 4: 色彩设计（color_system.py + color_psychology.py + color_grade.py）
  ├─ 色调: 暖橙=温馨/冷蓝=孤独/粉紫=梦幻（color_psychology.py）
  ├─ 配色: 60-30-10（点缀用互补色）
  └─ 调色: 青橙=电影/低饱和=文艺（color_grade.py）

STEP 5: 场景构建（background_system.py + school_life.py + architecture_system.py）
  ├─ 场景: 走廊/教室/天台/街道/海边（scene_lighting_recipes.py 抄配方）
  ├─ 天气: 晴/雨/雪/雾（weather_system.py）
  ├─ 季节: 春樱/夏海/秋叶/冬雪（season_system.py）
  └─ 时间: 晨/午/黄昏/夜（time_system.py）

STEP 6: 动态/道具（pose_system.py + motion_system.py + prop_system.py）
  ├─ 姿势: 站/坐/动态（pose_system.py）
  ├─ 手: 安全姿势（hand_system.py——背手/垂手/抱胸）
  ├─ 道具: 书/伞/花（prop_system.py）
  └─ 动态: 风/飘动/速度（cloth_motion.py + motion_system.py）

STEP 7: 生成（prompt_system.py——SDXL 标签 + 精确特征加权）
  ├─ prompt 结构: 质量词→风格→镜头→光照→场景→主体→细节
  ├─ 精确特征加权: (black hair:1.2) (mole:1.3)
  └─ 负面词: 基础+防脏+防偏（commercial_flow.py 已封装）

STEP 8: 质检/迭代（质检降级链 + agent loop）
  ├─ VLM 评分: 低于阈值重跑（YOLO 误报→目视确认）
  ├─ 缺陷分析: 手崩→改姿势/脸崩→face-detailer/色彩花→colorgrade
  └─ 一致性: 多图 consistency_check

STEP 9: 后处理（postprocess_system.py——顺序固化）
  ├─ 生成(含 face-detailer) → colorgrade → 泪痣(比例自适应) → 交付
  └─ 终检: finalcheck --flip --focus（G20/G21）

═══════════════════════════════════════════════
实战示例（朋友场景——短发少女黑发侧辫泪痣）
═══════════════════════════════════════════════
需求: 小说女主插画——原图有感觉+泪痣+短发侧辫青春感+多张
决策: 竖版插画(768x1344) · 黑发短发侧辫(发型) · 清纯+青春(气质)
      中景半身(构图2) · 黄昏走廊光(场景配方) · 校服(服装)
Prompt: MASTERPIECE, best quality, anime style, clean lineart,
        medium shot, golden hour corridor light, school corridor,
        1girl, (natural black hair:1.2), short bob, side braid near ear,
        (mole under left eye:1.3), cheerful smile, navy sailor uniform,
        detailed illustration
负面: worst quality, low quality, blurry, noise, colorful hair, gradient, tears
流程: thumbnail 选方向 → commercial_flow 生成 → colorgrade → 泪痣后处理 → 交付
