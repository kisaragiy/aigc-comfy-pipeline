#!/usr/bin/env python3
"""
修复动作库 (D2) — 七维质检定位弱项 → 定向修复动作

按七维弱项分派的修复动作。每种动作对应一个具体 ComfyUI/prompt 修复手段。

【七维弱项 → 修复动作映射】
| 弱项维度 | 典型问题 | 修复动作 | 手段 |
|---------|---------|---------|------|
| 手部&身体 | 手崩/缺指/融合 | hand_fix | HandDetailer 局部重绘 或换seed重生成 |
| 面部 | 脸崩/五官歪 | face_fix | FaceDetailer 局部重绘 |
| 线条完成度 | 断裂/噪点/糊 | line_fix | 超分+锐化 或 denoise 降低重绘 |
| 光影色彩 | 过曝/平淡 | color_fix | 调色/调光影(重生成加光效词) |
| 构图背景 | 层次弱/背景吞主体 | compose_fix | 重构图(换尺寸/加前景/主体前置) |
| 整体精致度 | 细节不足/像素化 | detail_fix | 超分4x + 重绘细节 |
| 氛围感 | 无感染力 | mood_fix | 增强光影对比/加氛围元素(重生成) |

【优先级】
1. 硬伤(手崩/脸崩/线条断) > 细节/精致度 > 氛围
2. 手/脸崩 = 必修(不及格线), 光效/氛围 = 可接受(属风格)

用法:
  python fix_actions.py map <weak_points_json>   # 弱项→修复动作
  python fix_actions.py run <action> <img> <seed> # 执行修复动作
"""
from __future__ import annotations
import json, os, sys

# 弱项维度名 → 修复动作(主)+ 说明
ACTION_MAP = {
    "手部": {"action": "hand_fix", "desc": "HandDetailer局部重绘 或 换seed重生成(手部是AI弱区)"},
    "手部&身体": {"action": "hand_fix", "desc": "HandDetailer局部重绘 或 换seed重生成(手部是AI弱区)"},
    "身体": {"action": "body_fix", "desc": "检查比例/穿模, 局部重绘或重生成"},
    "面部": {"action": "face_fix", "desc": "FaceDetailer局部重绘(脸是近景命门)"},
    "线条完成度": {"action": "line_fix", "desc": "超分+锐化 或 降低denoise重绘(修噪声/断裂)"},
    "线条": {"action": "line_fix", "desc": "超分+锐化 或 降低denoise重绘"},
    "光影色彩": {"action": "color_fix", "desc": "调色/重生成加光效/冷暖对比词"},
    "光影": {"action": "color_fix", "desc": "调色/重生成加光效词"},
    "构图背景": {"action": "compose_fix", "desc": "重构图: 换尺寸/前景/主体前置"},
    "构图": {"action": "compose_fix", "desc": "重构图: 换尺寸/主体突出"},
    "整体精致度": {"action": "detail_fix", "desc": "超分4x + 细节重绘"},
    "细节": {"action": "detail_fix", "desc": "超分4x + 细节重绘"},
    "氛围感": {"action": "mood_fix", "desc": "增强光影对比/加氛围元素(重生成)"},
    "氛围": {"action": "mood_fix", "desc": "增强光影对比/加氛围元素"},
}


def map_actions(weak_points):
    """弱项列表 → 修复动作列表(按优先级排序)。"""
    actions = []
    for wp in weak_points or []:
        dim = wp.get("dim", "")
        score = wp.get("score", 0)
        # 映射维度名 → 动作
        info = None
        for key, val in ACTION_MAP.items():
            if key.lower() in dim.lower() or dim.lower() in key.lower():
                info = val
                break
        if not info:
            # 兜底: 按分数低=优先修
            info = {"action": "detail_fix", "desc": "通用细节补强"}
        actions.append({
            "dim": dim, "score": score,
            "action": info["action"], "desc": info["desc"],
            "why": wp.get("why", ""),
        })
    # 优先级: 手/脸(硬伤) > 线条 > 光影 > 构图 > 细节 > 氛围; 分数低的优先
    prio = {"hand_fix": 0, "face_fix": 1, "body_fix": 1, "line_fix": 2,
            "color_fix": 3, "compose_fix": 4, "detail_fix": 5, "mood_fix": 6}
    actions.sort(key=lambda a: (prio.get(a["action"], 9), a["score"]))
    return actions


def test():
    # 用 battle 的七维质检弱项测试
    weak = [
        {"dim": "手部&身体", "score": 2, "why": "手指熔块/缺指"},
        {"dim": "线条完成度", "score": 4, "why": "发丝/裙边断裂噪点"},
        {"dim": "面部", "score": 6, "why": "五官轻微"},
    ]
    print("=== battle 弱项 → 修复动作 ===")
    for a in map_actions(weak):
        print(f"  [{a['action']}] {a['dim']}({a['score']}): {a['desc']}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "map":
        weak = json.loads(sys.argv[2])
        print(json.dumps(map_actions(weak), ensure_ascii=False, indent=1))
    else:
        test()
