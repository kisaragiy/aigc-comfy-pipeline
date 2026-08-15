#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/job_system.py — 角色职业体系知识库 v1.0
======================================================
职业 = 角色社会身份（画师用服装+道具+场景定职业）——深挖第 54 轮
用法: 职业角色 → 职业装+职业道具+职业场景三件套

【职业装+道具（快速识别）】
  咖啡师: 围裙+咖啡机（"barista apron, coffee machine"）
  医生/护士: 白大褂/护士服+听诊器（"doctor coat, stethoscope"）
  警察: 制服+警徽（"police uniform, badge"）
  教师: 西装/职业装+书本（"teacher, glasses, holding book"）
  程序员: 连帽衫+电脑（"programmer, hoodie, laptop, code glow"）
  厨师: 厨师服+高帽（"chef uniform, toque"）
  空姐: 制服+丝巾（"flight attendant uniform, scarf"）
  作家: 书桌+稿纸+咖啡（"writer at desk, papers, coffee"）
  → 职业 = 服装+道具（2 件就认出）

【职业场景（工作环境）】
  咖啡店: 吧台+豆袋+暖光（"cafe interior, warm"）
  医院: 白+蓝+器械（"hospital, clean white, medical equipment"）
  办公室: 工位+电脑+文件（"office desk, monitor, documents"）
  厨房: 灶台+食材+热气（"kitchen, stove, steam"）
  书店: 书架+灯光（"bookstore, shelves, warm light"）
  → 场景 = 职业氛围（环境光/道具）

【职业×性格（反差/匹配）】
  匹配: 温柔护士/干练警察（职业气质一致）
  反差: 冷酷医生（外冷内热）/可爱程序员（呆萌）
  → 职业+性格 = 角色立体（反差=记忆点）

【职业×情绪（快速映射）】
  工作专注: 认真表情+工作姿态（"focused working"）
  下班放松: 解围裙/松领带（"relaxing after work"）
  职业自豪: 挺胸+专业姿势（"professional confident"）
  → 职业场景 = 工作/下班两种状态（下班=真实感）

【实战映射（prompt 模板）】
  咖啡师: "barista girl in apron, making coffee, warm cafe light, steam"
  护士: "nurse in white uniform, stethoscope, gentle smile, hospital"
  作家: "writer girl at desk, typewriter, coffee, window light, literary"
  程序员: "programmer girl, hoodie, laptop with code glow, night office"
