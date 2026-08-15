#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/pose_system.py — 姿势/动态学知识库 v1.0
========================================================
姿势=角色状态的第一信号（画师基础）——深挖第 11 轮
用法: 生成前想"角色在做什么状态"→ 选姿势词——姿势错了整张图气质就错

【站姿（气质基础）】
  直立放松: 自然/日常（重心在双脚——"standing relaxed"）
  重心单脚（交叉腿/倚靠）: 随意/俏皮/松弛（"leaning on one leg"）
  双手抱胸: 防御/自信/审视（"arms crossed"）
  背手: 文静/从容/老师感
  手插口袋: 酷/随意/少年感
  挺胸抬头: 自信/舞台/正式（"confident standing posture"）
  → 词: "standing with weight on one leg" / "arms crossed, confident"

【坐姿（情绪/场景）】
  端正坐（并腿）: 文静/淑女/上课（"sitting properly, knees together"）
  翘腿坐: 优雅/从容/职场（"sitting with crossed legs"）
  盘腿坐: 随意/居家/放松（"sitting cross-legged"）
  侧坐（腿并一侧）: 可爱/少女/日式（"sitting with legs to the side"）
  坐地（抱膝）: 孤独/脆弱/等待（"sitting on ground hugging knees"）
  倚窗坐: 文青/沉思/氛围（"sitting by window, looking out"）

【动态姿势（运动感——动势线）】
  奔跑: 身体前倾+手臂摆动+头发后飘（"running with forward lean"）
  跳跃: 身体舒展+四肢展开（"mid-jump, limbs extended"）
  转身: 回眸（头部转+身体微侧——"turning back with skirt flaring"）
  挥手: 打招呼/告别（"waving hand, cheerful"）
  伸手: 邀请/抓取（"reaching out hand"）
  动势线（action line）: 从头顶到脚的一条曲线——姿势的骨架（S 形=优雅/动态）
  → 词: "dynamic action line" / "S-curve posture"

【S 曲线/重心（画师人体基础）】
  人体美 = 曲线（S 形——颈-腰-腿的转折）
  重心线: 从锁骨中心垂直向下——站姿重心在双脚间=稳
  重心偏移 = 动感（重心不在支撑面=即将移动）
  画师规则: 姿势要"一条主曲线"（不要直板板）——直=僵硬
  → 词: "elegant S-curve figure" / "natural contrapposto stance"

【姿势×情绪（快速映射）】
  开心: 跳/挥/双手举高     害羞: 低头+手绞/抓裙角
  委屈: 低头+肩膀微缩       自信: 挺胸+手叉腰
  疲惫: 驼背+垂手           紧张: 双手握紧+肩耸
  放松: 倚靠+重心单脚       拒绝: 别过脸+手挡
  → 词: "shyly looking down, hands clasped" / "confident with hands on hips"

【姿势细节（手/脚/头的位置）】
  头部: 微歪=可爱/疑惑 · 微抬=高傲 · 低=害羞/沮丧
  手: 贴脸=思考 · 捂嘴=惊讶 · 指尖相对=紧张/祈祷
  脚: 内八=可爱/幼态 · 外八=随意 · 踮脚=期待/偷看
  → 词: "head tilted slightly, curious" / "hand touching chin, thinking"

【实战映射（prompt 模板）】
  青春少女: "cheerful jumping pose, arms raised, skirt flaring, dynamic S-curve"
  文静学姐: "sitting by window, knees together, hands in lap, serene"
  酷感: "standing with hand in pocket, weight on one leg, confident gaze"
  孤独: "sitting on ground hugging knees, head lowered, small figure"
