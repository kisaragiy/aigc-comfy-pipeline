#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/hand_system.py — 手部细节知识库 v1.0
=====================================================
手 = AI 最大崩坏点（手指多/少/扭曲）——深挖第 12 轮
用法: 手部出现概率高的姿势（挥手/捧/指）→ prompt 明确手部 → 质检重点查手

【手指结构（画师基础——为什么 AI 崩手）】
  正常手: 5 指（拇指+4 指）——拇指与其他 4 指对侧
  常见崩坏: 6 指/4 指/手指粘连/手从腕部弯折
  画师规则: 手比脸难画——AI 同理——少露手或明确手部姿势
  → 词: "well-drawn hands" / "detailed fingers" 用处有限——关键是姿势明确

【手势语言（情绪/动作）】
  招手: 召唤/告别（"waving hand"）
  比心: 可爱/表达（"heart hand gesture"）
  竖拇指: 赞/OK（"thumbs up"）
  指尖轻触: 温柔/思索（"fingertips touching"）
  握拳: 决心/愤怒（"clenched fist"）
  手心向上: 邀请/给予（"open palm offering"）
  捧脸: 可爱/惊讶（"hands cupping face"）
  托腮: 思考/慵懒（"hand resting on chin"）
  → 手部姿势越具体——AI 越不容易崩（抽象"hands"=自由发挥=崩）

【手部姿势库（常用安全姿势——AI 表现好的）】
  插兜/背手: 隐藏手（零风险——"hands in pockets"）
  垂手: 自然下垂（低风险——"arms relaxed at sides"）
  抱胸: 隐藏手指（低风险——"arms crossed"）
  捧物（花/书/杯）: 手部有依托（中风险——"holding a book"）
  牵/挽: 接触型（中风险——"holding hands"）
  指/挥: 手指张开（高风险——"pointing" 慎用）
  画师规则: 非必要不露手——露手必具体

【手部×情绪（快速映射）】
  紧张: 绞手指/握紧      放松: 自然张开/垂
  害羞: 抓衣角/捂脸      生气: 握拳/拍桌
  期待: 十指相扣/搓手    拒绝: 手掌推出（stop 手势）
  → 词: "nervously twisting fingers" / "shyly gripping skirt hem"

【手部质检（管线 inspect——手是质检重点）】
  质检"手: ok/异常"——异常时: 重跑（改姿势词——隐藏手）
  修复: face-detailer 不修手——手崩只能重生成（或裁剪构图避开）
  构图规避: 半身/特写（手不入画——脚同理）——"half body portrait" 天然避手

【实战映射（prompt 模板）】
  安全: "cheerful girl with hands behind back, smiling"（背手=零崩坏）
  捧书: "holding a book with both hands, gentle expression"
  挥手: "waving with one hand raised, dynamic pose"（高风险——备重跑）
  无手构图: "half body portrait, hands not visible"（最安全）
