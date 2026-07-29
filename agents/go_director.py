#!/usr/bin/env python3
"""go_director.py — 创意导演层

从自然语言需求 → 分镜本 → 工作流编排 → 出图/视频

工作流程:
  1. 理解创意需求 (文本/参考图)
  2. 拆分为分镜头 (storyboard)
  3. 每个镜头: 规划角色/服装/表情/姿势/背景/运镜
  4. 编排子工作流 (依赖 orchestrator)
  5. 执行并监控
  6. 评审结果, 必要时修复

和你的"多熔炉"比喻完全一致:
  - 导演拆剧本 → 分镜师分镜头 → 角色/背景/道具并行生产 → 导演合成
============================================================ """

import json
import sys
import os
from dataclasses import dataclass, field, asdict
from typing import Optional

# 导入创意知识库
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "workshop", "creative"))
try:
    from aigc_knowledge import (
        GARMENTS, HAIRSTYLES, EXPRESSIONS, POSES, STYLES,
        CAMERA_SHOTS, CAMERA_MOVES, suggest_outfit, suggest_hairstyle, suggest_expression
    )
except ImportError:
    print("[知识库] 未找到 aigc_knowledge, 使用内置知识")
    GARMENTS = HAIRSTYLES = EXPRESSIONS = POSES = STYLES = CAMERA_SHOTS = CAMERA_MOVES = {}

# 尝试导入编排器
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
try:
    from orchestrator import detect_hardware, build_orchestration_plan, HardwareSpec
except ImportError:
    print("[编排器] 未找到 orchestrator, 使用模拟模式")
    HardwareSpec = None


# ════════════════════════════════════════════════════════════
# 分镜本
# ════════════════════════════════════════════════════════════

@dataclass
class Shot:
    """一个分镜头"""
    id: int
    duration_sec: float = 5.0       # 视频时长
    scene_desc: str = ""            # 场景描述 (位置/环境/氛围)
    characters: list[dict] = field(default_factory=list)  # 角色列表 [{name, gender, outfit, hairstyle, expression, pose}]
    background_desc: str = ""       # 背景描述
    camera_shot: str = "中景"       # 远景/中景/近景/特写
    camera_move: str = ""           # 推/拉/摇/移/跟/升降
    art_style: str = "动画风"       # 画风
    composition_notes: str = ""     # 构图说明
    lighting: str = ""              # 光线
    color_tone: str = ""            # 色调
    key_items: list[str] = field(default_factory=list)  # 关键道具
    generated: bool = False         # 是否已生成

    def to_prompt(self) -> str:
        """把分镜转换为主提示词"""
        chars = [f"{c.get('gender','')}角色 {c.get('name','未知')}，穿着{c.get('outfit','默认服装')}，{c.get('hairstyle','默认发型')}，表情{c.get('expression','中性')}，姿势{c.get('pose','站姿')}" 
                 for c in self.characters]
        char_str = '，'.join(chars)
        
        camera_str = self.camera_shot
        if self.camera_move:
            camera_str += f"，镜头{self.camera_move}"
        
        parts = [
            self.scene_desc,
            char_str if chars else "",
            f"背景: {self.background_desc}" if self.background_desc else "",
            f"画风: {self.art_style}",
            f"镜头: {camera_str}",
            f"光线: {self.lighting}" if self.lighting else "",
            f"色调: {self.color_tone}" if self.color_tone else "",
            f"道具: {', '.join(self.key_items)}" if self.key_items else "",
            self.composition_notes,
        ]
        return ', '.join(p for p in parts if p)


@dataclass
class Storyboard:
    """完整故事板"""
    title: str
    description: str
    shots: list[Shot] = field(default_factory=list)
    style_universe: str = "动画风"   # 全片统一画风
    total_duration_sec: float = 0
    
    def add_shot(self, shot: Shot):
        self.shots.append(shot)
        self.total_duration_sec = sum(s.duration_sec for s in self.shots)
    
    def summary(self) -> str:
        lines = [f"🎬 {self.title}", f"📝 {self.description}", f"🎨 画风: {self.style_universe}"]
        lines.append(f"\n📋 {len(self.shots)} 个分镜头 (总时长 {self.total_duration_sec:.1f}s):\n")
        for s in self.shots:
            chars = ', '.join(f"{c['gender']}:{c.get('name','?')}" for c in s.characters)
            lines.append(f"  [{s.id:02d}] {s.camera_shot:6s} | {s.scene_desc[:40]:40s} | {chars}")
        return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# 导演 — 从创意到产品
# ════════════════════════════════════════════════════════════

class CreativeDirector:
    """
    创意导演: 
    1. 理解需求
    2. 生成故事板
    3. 选择合适的画风/服装/运镜
    4. 编排子工作流
    5. 评审输出
    """
    
    def __init__(self, hardware: Optional['HardwareSpec'] = None):
        self.hardware = hardware
        if hardware is None and HardwareSpec is not None:
            self.hardware = detect_hardware()
    
    def understand_request(self, text: str) -> dict:
        """分析用户需求, 提取关键元素
        
        这里用规则 + 将来可以接 LLM 做更深理解
        """
        analysis = {
            "raw": text,
            "has_character": "人物" in text or "角色" in text or "人" in text,
            "has_background": True,
            "has_action": any(w in text for w in ["战斗", "跑", "跳", "走", "飞", "游泳"]),
            "has_specific_style": None,
            "gender_hint": None,
            "suggested_style": None,
        }
        
        # 风格识别
        for style_name in STYLES:
            if style_name in text:
                analysis["suggested_style"] = style_name
                break
        if not analysis["suggested_style"]:
            analysis["suggested_style"] = "动画风"
        
        # 性别推断
        if any(w in text for w in ["男", "帅哥", "少年", "男生"]):
            analysis["gender_hint"] = "男"
        elif any(w in text for w in ["女", "美女", "少女", "女生"]):
            analysis["gender_hint"] = "女"
        
        return analysis
    
    def create_storyboard(self, text: str, shots_count: int = 1) -> Storyboard:
        """从需求创建分镜故事板"""
        analysis = self.understand_request(text)
        
        storyboard = Storyboard(
            title=text[:30] + ("..." if len(text) > 30 else ""),
            description=text,
            style_universe=analysis.get("suggested_style", "动画风"),
        )
        
        gender = analysis.get("gender_hint", "女")
        style = analysis.get("suggested_style", "甜系")
        
        # 将风格名映射到知识库风格标签
        style_to_vibe = {
            "动画风": "甜系", "厚涂": "酷系", "赛璐珞": "甜系",
            "写实": "通勤", "水彩": "甜系", "水墨": "古风",
            "赛博": "赛博", "哥特": "哥特", "汉服古风": "汉服",
            "3D渲染": "酷系", "像素": "休闲", "复古": "通勤",
        }
        vibe = style_to_vibe.get(style, "甜系")
        
        for i in range(shots_count):
            # 推荐服装/发型
            outfit = suggest_outfit(gender, vibe, "春")
            hairstyles = suggest_hairstyle(gender, "温柔")
            
            shot = Shot(
                id=i + 1,
                scene_desc=self._compose_scene(text, i, shots_count),
                camera_shot=self._pick_shot(i, shots_count),
                camera_move=self._pick_move(i, shots_count) if shots_count > 1 else "",
                art_style=style,
                characters=[{
                    "name": f"角色{i+1}",
                    "gender": gender,
                    "outfit": str(outfit.get("方案B(分体)", {})),
                    "hairstyle": hairstyles[0] if hairstyles else "披肩长发",
                    "expression": "微笑",
                    "pose": list(POSES.keys())[i % len(POSES)] if POSES else "站姿",
                }],
                background_desc=self._compose_background(text),
                composition_notes=self._compose_composition(text, i),
            )
            storyboard.add_shot(shot)
        
        return storyboard
    
    def _compose_scene(self, text: str, index: int, total: int) -> str:
        """根据需求生成场景描述"""
        # 这个将来接 LLM 会有质的提升
        scene_template = [
            lambda t: f"{t} — 日间, 自然环境",
            lambda t: f"{t} — 黄昏, 城市背景",
            lambda t: f"{t} — 夜晚, 灯光氛围",
        ]
        if total == 1:
            return f"{text}"
        return scene_template[index % len(scene_template)](text)
    
    def _compose_background(self, text: str) -> str:
        keywords = {
            "樱花": "樱花园, 花瓣飘落, 粉色花海",
            "城市": "霓虹城市, 高楼, 夜景",
            "咖啡": "咖啡厅, 暖光, 木制家具",
            "战斗": "废墟, 碎石, 硝烟弥漫",
            "海": "沙滩, 海浪, 蓝色天际",
            "教室": "教室, 课桌, 黑板, 阳光洒入",
        }
        for kw, bg in keywords.items():
            if kw in text:
                return bg
        return "自然公园, 绿树成荫, 柔和阳光"
    
    def _compose_composition(self, text: str, index: int) -> str:
        """构图建议"""
        templates = [
            "黄金分割构图, 主体在右侧1/3处",
            "中心构图, 主体居中对齐",
            "引导线构图, 利用道路/树木引导视线",
        ]
        return templates[index % len(templates)]
    
    def _pick_shot(self, index: int, total: int) -> str:
        """根据镜头索引选择分镜类型"""
        shots_sequence = ["远景", "中景", "近景", "特写", "全景", "过肩", "双人"]
        if total <= 1:
            return "中景"
        return shots_sequence[index % len(shots_sequence)]
    
    def _pick_move(self, index: int, total: int) -> str:
        """多镜头时, 选择运镜方式"""
        moves = ["推", "拉", "摇", "移", "跟", "环绕"]
        return moves[index % len(moves)]
    
    def recommend(self, shot: Shot) -> dict:
        """为分镜提供创意推荐 — 服装/表情/姿势/画风组合"""
        gender = shot.characters[0]["gender"] if shot.characters else "女"
        style_label = shot.art_style
        
        vibe_map = {
            "动画风": "甜系", "厚涂": "酷系", "赛璐珞": "甜系",
            "写实": "通勤", "水彩": "自然", "水墨": "古风",
            "赛博": "酷系", "哥特": "酷系",
        }
        vibe = vibe_map.get(style_label, "甜系")
        
        return {
            "outfit_options": suggest_outfit(gender, vibe, "春"),
            "hairstyle_options": suggest_hairstyle(gender, "温柔"),
            "expression_options": suggest_expression(vibe),
            "pose_options": [p for p in POSES.keys()][:3],
            "style_info": STYLES.get(style_label, {}),
            "shot_info": CAMERA_SHOTS.get(shot.camera_shot, {}),
        }
    
    def orchestrate(self, storyboard: Storyboard) -> list[dict]:
        """编排整个故事板的生成计划"""
        plans = []
        for shot in storyboard.shots:
            plan = build_orchestration_plan(
                prompt=shot.to_prompt(),
                hardware=self.hardware,
                has_character=len(shot.characters) > 0,
                has_background=bool(shot.background_desc),
            )
            plans.append({
                "shot_id": shot.id,
                "prompt": shot.to_prompt(),
                "plan": plan.summary() if hasattr(plan, 'summary') else str(plan),
            })
        return plans


# ════════════════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    prompt = " ".join(sys.argv[1:]) or "一位穿JK制服的少女站在樱花树下微笑"
    
    print("╔═══════════════════════════════════════════════╗")
    print("║      AIGC 创意导演 v1.0                       ║")
    print("╚═══════════════════════════════════════════════╝")
    print(f"\n🎯 需求: {prompt}\n")
    
    director = CreativeDirector()
    
    # 1. 理解需求
    analysis = director.understand_request(prompt)
    print(f"🔎 需求分析: 含角色={'✅' if analysis['has_character'] else '❌'} | "
          f"性别={analysis['gender_hint'] or '自动'} | "
          f"画风={analysis['suggested_style']}")
    
    # 2. 创建故事板 (单镜头图片 / 多镜头视频)
    storyboard = director.create_storyboard(prompt, shots_count=3)
    print(f"\n{storyboard.summary()}\n")
    
    # 3. 创意推荐
    print("🎨 创意推荐 (第1镜):")
    rec = director.recommend(storyboard.shots[0])
    print(f"  服装: {list(rec['outfit_options'].keys())}")
    print(f"  发型: {rec['hairstyle_options'][:3]}...")
    print(f"  表情: {rec['expression_options'][:3]}...")
    print(f"  镜头: {rec['shot_info'].get('描述','')}")
    
    # 4. 编排计划
    print("\n📋 编排计划:")
    plans = director.orchestrate(storyboard)
    for p in plans:
        print(f"\n  [镜{p['shot_id']}] 提示词({len(p['prompt'])}字)")
        plan_text = p['plan'].split('\n')
        for line in plan_text[:4]:
            print(f"    {line}")
        print(f"    ...(共{len(plan_text)}行)")
    
    print("\n✅ 导演准备完毕, 等待执行指令")
