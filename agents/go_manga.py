#!/usr/bin/env python3
"""
漫画连续性与角色一致性系统 v1.0

你问到的: "生成有漫画剧情的连续性的图"

核心问题:
  现有 ComfyUI 工作流是单张出图, 无"角色记忆"和"场景记忆"
  漫画需要: 同一角色保持脸/服装/体态一致 × N张图
  
本系统用 Agent 工程实现角色/场景一致性:

  方案 A (不依赖额外模型):
    通过提示词工程 + Seed 规律 + IP-Adapter 参考图 维持一致性
  
  方案 B (最强一致性):
    InstantID/FaceID/IP-Adapter + 角色参考图 + 背景ControlNet
  
  方案 C (漫画专用):
    分格布局 → 批量生成 → 漫画风格统一色板 → 排版合成

工作流:
  剧本 → 角色设计 → 角色卡 → 场景卡 → 分镜序列 → 批量生成 → 排版
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

# ════════════════════════════════════════════════════════════
# 角色卡 — 维持角色一致性的关键
# ════════════════════════════════════════════════════════════

@dataclass
class CharacterCard:
    """
    角色卡: 一个角色的完整描述 + 生成参数
    
    用于跨场景保持同一角色外观一致。
    也是 IP-Adapter/FaceID 的参考图描述。
    """
    name: str
    gender: str = "女"
    age_group: str = "高中生"
    
    # 外观描述 (提示词核心部分)
    appearance: dict = field(default_factory=lambda: {
        "face": "oval face, big eyes, delicate features",
        "hair": "long black hair, straight, hime cut, ahoge",
        "eyes": "purple eyes, sharp gaze",
        "body": "slender, small bust, average height",
        "outfit": "school uniform, blazer, red ribbon tie, pleated skirt",
        "accessories": "red ribbon, knee socks, loafers",
    })
    
    # 关键参数
    seed_base: int = 0           # 基础 seed (所有图以 seed_base + idx 生成)
    ref_image_path: str = ""     # 参考图路径 (IP-Adapter用)
    lora_name: str = ""          # 角色 LoRA (如果有)
    lora_strength: float = 0.7
    
    # 提示词
    positive_prompt: str = ""
    negative_prompt: str = "worst quality, low quality, blurry, bad anatomy, bad hands, extra fingers, mutated"
    
    # IP-Adapter/FaceID 参数
    ip_adapter_weight: float = 0.8
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def get_prompt(self, scene_context: str = "") -> str:
        """生成完整提示词"""
        parts = [
            f"1{self.gender if self.gender else 'girl'}",
            self.appearance.get("face", ""),
            self.appearance.get("hair", ""),
            self.appearance.get("eyes", ""),
            self.appearance.get("body", ""),
            self.appearance.get("outfit", ""),
            self.appearance.get("accessories", ""),
        ]
        if self.positive_prompt:
            parts.append(self.positive_prompt)
        if scene_context:
            parts.append(scene_context)
        parts.append("masterpiece, best quality, ultra detailed, highres")
        return ", ".join(p for p in parts if p)
    
    def get_negative(self) -> str:
        return self.negative_prompt
    
    def get_seed(self, panel_idx: int = 0) -> int:
        """每个分镜用不同的 seed, 但基于 seed_base 可复现"""
        return self.seed_base + panel_idx * 7 + panel_idx * panel_idx * 3
    
    def describe(self) -> str:
        return f"[{self.name}] {self.age_group} {self.appearance['hair']}, {self.appearance['eyes']}"


@dataclass
class SceneCard:
    """
    场景卡: 一个场景/背景的完整描述
    
    用于跨分镜保持同一场景的视觉一致性。
    """
    name: str
    location: str = ""
    atmosphere: str = ""
    lighting: str = ""
    color_palette: str = ""
    
    elements: list[str] = field(default_factory=list)
    prompt_tags: list[str] = field(default_factory=list)
    
    # 场景参考图 (ControlNet用)
    ref_image_path: str = ""
    
    def get_prompt(self) -> str:
        parts = [self.location, self.atmosphere, self.lighting, self.color_palette]
        parts.extend(self.elements)
        parts.extend(self.prompt_tags)
        return ", ".join(p for p in parts if p)


# ════════════════════════════════════════════════════════════
# 分镜/剧本
# ════════════════════════════════════════════════════════════

@dataclass
class Panel:
    """
    一个分镜 (单格画面)
    
    每个分镜指向:
      - 哪个角色
      - 在哪个场景
      - 什么姿势/表情
      - 什么视角/运镜
      - 对话/旁白
    """
    panel_number: int
    character_names: list[str]
    scene: str
    character_state: dict = field(default_factory=dict)
    # {角色名: {pose, expression, action, position}}
    
    camera: str = "medium shot"        # 景别/运镜
    camera_angle: str = "eye level"    # 视角
    dialogue: str = ""                  # 台词
    narration: str = ""                 # 旁白
    emotional_beat: str = "neutral"     # 情感标签 (LLM生成: joyful/sad/tense/romantic...)
    composition_notes: str = ""         # 构图备注
    action_description: str = ""        # 动作描述
    
    # ComfyUI 参数
    width: int = 1024
    height: int = 768
    seed: int = -1
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass 
class Storyboard:
    """
    故事板: N个分镜的序列
    """
    title: str = "Untitled"
    characters: dict[str, CharacterCard] = field(default_factory=dict)
    scenes: dict[str, SceneCard] = field(default_factory=dict)
    panels: list[Panel] = field(default_factory=list)
    
    # 面板布局 (漫画排版用)
    layout: str = "4koma"  # 4koma / standard / freeform


# ════════════════════════════════════════════════════════════
# 连续性策略工厂
# ════════════════════════════════════════════════════════════

def build_consistency_strategy(char: CharacterCard) -> dict:
    """
    构建角色一致性的 ComfyUI 策略
    
    根据角色卡的配置, 决定使用:
      - 纯提示词 (弱一致性, 简单)
      - 提示词+Seed (中一致性, 可靠)
      - IP-Adapter/InstantID (强一致性, 需要参考图)
      - LoRA (最强一致性, 需要训练)
    
    返回结构化配置
    """
    strategy = {
        "method": "prompt+seed",
        "confidence": "medium",
        "nodes": [],
        "description": "",
    }
    
    if char.lora_name:
        strategy["method"] = "lora"
        strategy["confidence"] = "very_high"
        strategy["description"] = f"LoRA: {char.lora_name} @{char.lora_strength}"
        strategy["nodes"].append({
            "type": "LoraLoader",
            "lora_name": char.lora_name,
            "strength_model": char.lora_strength,
            "strength_clip": char.lora_strength,
        })
    elif char.ref_image_path and os.path.exists(char.ref_image_path):
        strategy["method"] = "ip_adapter"
        strategy["confidence"] = "high"
        strategy["description"] = f"IP-Adapter: {char.ref_image_path}"
        strategy["nodes"].append({
            "type": "IPAdapterLoader",
            "ipadapter_name": "ip-adapter-faceid-plusv2_sd15.bin",
        })
        strategy["nodes"].append({
            "type": "IPAdapterApply",
            "weight": char.ip_adapter_weight,
            "weight_type": "linear",
        })
    else:
        strategy["method"] = "prompt+seed"
        strategy["confidence"] = "medium"
        strategy["description"] = f"Prompt+Seed({char.seed_base})"
    
    return strategy


# ════════════════════════════════════════════════════════════
# 漫画排版
# ════════════════════════════════════════════════════════════

MANGA_LAYOUTS = {
    "4koma": {
        "name": "四格漫画",
        "rows": 2,
        "cols": 2,
        "read_direction": "right-to-left",  # 日式
        "description": "经典4格漫画, 起承转结",
        "panel_aspect": (1, 1),
    },
    "yonkoma_v": {
        "name": "纵四格",
        "rows": 4,
        "cols": 1,
        "read_direction": "top-to-bottom",
        "description": "竖版四格, 手机阅读优化",
        "panel_aspect": (9, 16),
    },
    "manga_page": {
        "name": "漫画单页",
        "rows": 4,
        "cols": 3,
        "read_direction": "right-to-left",
        "description": "标准日式漫画单页 (含跨格/对角)",
        "panel_aspect": (1, 1.4),
    },
    "storyboard": {
        "name": "标准故事板",
        "rows": 3,
        "cols": 1,
        "read_direction": "top-to-bottom",
        "description": "左→右, 上→下, 标准导演故事板",
        "panel_aspect": (16, 9),
    },
}


def layout_panels(storyboard: Storyboard, layout_name: str = "4koma") -> dict:
    """
    将故事板按指定布局排版
    返回排版配置 (用于后续批量生成或ComfyUI ControlNet拼格)
    """
    layout = MANGA_LAYOUTS.get(layout_name, MANGA_LAYOUTS["4koma"])
    panels = storyboard.panels[:layout["rows"] * layout["cols"]]
    
    return {
        "layout": layout_name,
        "rows": layout["rows"],
        "cols": layout["cols"],
        "total_panels": len(panels),
        "read_direction": layout["read_direction"],
        "panels": [p.to_dict() for p in panels],
    }


# ════════════════════════════════════════════════════════════
# 漫画/连续性生成引擎
# ════════════════════════════════════════════════════════════

class MangaEngine:
    """
    漫画生成引擎 — 从故事板到批量生成配置
    
    工作流:
      1. build_storyboard(script) → Storyboard
      2. assign_characters() → 分配角色卡到每个分镜
      3. build_batch_config() → 生成批量 ComfyUI 参数列表
      4. generate_layout() → 页面排版配置
    """
    
    def __init__(self):
        self.storyboard: Optional[Storyboard] = None
    
    def from_script(self, script: str) -> Storyboard:
        """
        从自然语言剧本创建故事板
        
        示例:
          "校园日常故事:
           第1镜: 教室, 早上, 女主角在窗边看书
           第2镜: 走廊, 男主角走过遇见她
           第3镜: 屋顶, 两人对话"
        """
        lines = script.strip().split("\n")
        title = lines[0] if lines else "故事"
        panels = []
        
        char_names_seen = set()
        
        for line in lines:
            m = re.match(r'第(\d+)镜[：:]?\s*(.+?)[，,]\s*(.+?)[，,]\s*(.+)', line)
            if not m:
                m = re.match(r'(\d+)[\.:：]?\s*(.+?)[，,]\s*(.*)', line)
            
            if m:
                groups = m.groups()
                if len(groups) >= 3:
                    panel_num = len(panels) + 1
                    scene = groups[1].strip() if len(groups) > 1 else ""
                    desc = groups[2].strip() if len(groups) > 2 else ""
                    detail = groups[3].strip() if len(groups) > 3 else ""
                    
                    # 简单解析: 找到可能的角色名 (中文名词)
                    # 这里先简单处理
                    panel = Panel(
                        panel_number=panel_num,
                        character_names=[],
                        scene=scene,
                        composition_notes=desc + " " + detail,
                        action_description=desc,
                        dialogue="",
                    )
                    panels.append(panel)
        
        self.storyboard = Storyboard(
            title=title,
            panels=panels,
            characters={},
            scenes={},
        )
        return self.storyboard
    
    def add_character(self, name: str, card: CharacterCard) -> CharacterCard:
        if self.storyboard:
            self.storyboard.characters[name] = card
        return card
    
    def add_scene(self, name: str, card: SceneCard) -> SceneCard:
        if self.storyboard:
            self.storyboard.scenes[name] = card
        return card
    
    def assign_characters_to_panels(self) -> list[dict]:
        """
        把角色分配到每个分镜 (基于角色名匹配)
        返回每个分镜的生成参数
        """
        if not self.storyboard:
            return []
        
        batch = []
        for panel in self.storyboard.panels:
            # 找到这个分镜需要的所有角色
            chars_for_panel = []
            for char_name in panel.character_names:
                if char_name in self.storyboard.characters:
                    card = self.storyboard.characters[char_name]
                    chars_for_panel.append({
                        "name": char_name,
                        "card": card,
                        "prompt": card.get_prompt(panel.composition_notes),
                        "negative": card.get_negative(),
                        "seed": card.get_seed(panel.panel_number),
                        "strategy": build_consistency_strategy(card),
                    })
            
            # 找到场景
            scene_for_panel = self.storyboard.scenes.get(panel.scene)
            
            batch.append({
                "panel": panel.panel_number,
                "scene": panel.scene,
                "scene_card": scene_for_panel.to_dict() if scene_for_panel else None,
                "characters": chars_for_panel,
                "camera": panel.camera,
                "angle": panel.camera_angle,
                "width": panel.width,
                "height": panel.height,
                "composition": panel.composition_notes,
            })
        
        return batch
    
    def to_comfyui_batch(self) -> list[dict]:
        """
        生成批量 ComfyUI 工作流参数
        每个元素是一个完整的 workflow JSON
        
        多角色分镜: 生成多次(每个角色独立) + 合成
        """
        batch_config = self.assign_characters_to_panels()
        workflows = []
        
        for item in batch_config:
            panel_num = item["panel"]
            
            for char_info in item["characters"]:
                strategy = char_info["strategy"]
                
                workflow = {
                    "panel": panel_num,
                    "character": char_info["name"],
                    "prompt": char_info["prompt"],
                    "negative": char_info["negative"],
                    "seed": char_info["seed"],
                    "width": item["width"],
                    "height": item["height"],
                    "strategy": strategy["method"],
                    "strategy_nodes": strategy["nodes"],
                }
                workflows.append(workflow)
            
            # TODO: 多角色合并的工作流
            
        return workflows
    
    def describe_story(self) -> str:
        """输出故事板文本描述"""
        if not self.storyboard:
            return "无故事板"
        
        lines = [f"📖 {self.storyboard.title}", f"   角色: {list(self.storyboard.characters.keys())}"]
        lines.append(f"   场景: {list(self.storyboard.scenes.keys())}")
        lines.append(f"   分镜数: {len(self.storyboard.panels)}\n")
        
        for i, panel in enumerate(self.storyboard.panels):
            chars = panel.character_names or ["(未分配)"]
            lines.append(f"  [{panel.panel_number}] 场景:{panel.scene} | 角色:{chars}")
            lines.append(f"      镜头:{panel.camera} {panel.camera_angle}")
            if panel.action_description:
                lines.append(f"      动作:{panel.action_description}")
            if panel.composition_notes:
                lines.append(f"      构图:{panel.composition_notes[:80]}")
        
        return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# 漫画连续性 — 背景连续性增强
# ════════════════════════════════════════════════════════════

def build_background_continuity(scene: SceneCard, panel_sequence: list[Panel]) -> dict:
    """
    跨分镜保持背景连续性
    
    策略:
      - 同一场景的所有分镜共享相同的场景prompt
      - 同一场景使用 ControlNet 参考图 (用第一镜的生成图作为ControlNet)
      - 同一场景使用统一的 seed 系列
    """
    shared_tags = scene.prompt_tags.copy()
    
    # 每个分镜的视角变化
    angle_variations = []
    for p in panel_sequence:
        angle_variations.append({
            "panel": p.panel_number,
            "camera": p.camera,
            "angle": p.camera_angle,
            "variation": f"{scene.name}, {p.camera} view, {p.camera_angle} angle",
        })
    
    return {
        "scene": scene.name,
        "shared_prompt": scene.get_prompt(),
        "continuity_method": "shared_prompt",
        "has_ref_image": bool(scene.ref_image_path),
        "panel_variations": angle_variations,
    }


# ════════════════════════════════════════════════════════════
# 预置漫画故事模板
# ════════════════════════════════════════════════════════════

MANGA_TEMPLATES = {
    "galgame_opening": {
        "name": "Galgame 开场",
        "panels": [
            {"scene": "樱花树道", "action": "女主角站在樱花树下, 微风吹起花瓣", "camera": "wide shot"},
            {"scene": "教室", "action": "女主角在窗边, 逆光", "camera": "medium shot"},
            {"scene": "学校屋顶", "action": "两人相遇, 对视", "camera": "over-the-shoulder"},
        ]
    },
    "日常四格": {
        "name": "日常四格 (起承转结)",
        "panels": [
            {"scene": "教室", "action": "早上, 女主角刚到教室", "camera": "wide shot"},
            {"scene": "走廊", "action": "遇到同学, 打招呼", "camera": "medium shot"},
            {"scene": "食堂", "action": "一起吃午饭, 聊天", "camera": "two shot"},
            {"scene": "回家路", "action": "夕阳下一起走, 微笑", "camera": "long shot"},
        ]
    },
    "战斗场景": {
        "name": "战斗分镜",
        "panels": [
            {"scene": "异世界草原", "action": "两人对峙, 距离50米", "camera": "wide shot"},
            {"scene": "异世界草原", "action": "冲刺! 近身!", "camera": "close up"},
            {"scene": "异世界草原", "action": "武器碰撞, 火花四溅", "camera": "action shot"},
            {"scene": "异世界草原", "action": "胜负已分, 一方倒地", "camera": "high angle"},
        ]
    },
}



# ════════════════════════════════════════════════════════════
# StoryboardAgent — LLM 驱动的语义级故事板理解
# ════════════════════════════════════════════════════════════

class StoryboardAgent:
    """
    用 LLM 理解剧本语义 → 生成结构化故事板

    替代 regex 模板匹配, 真正理解:
      - 人物关系与视觉描写
      - 场景氛围与光线
      - 情感线索与节拍
      - 人物关系隐含的互动

    用法:
      agent = StoryboardAgent()
      storyboard = agent.from_script("你的剧本...")
      print(agent.summarize())
    """

    OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
    MODEL = "qwen3:14b"
    TIMEOUT = 120

    SYSTEM_PROMPT = """You are a manga storyboard artist. Analyze the given script and output structured storyboard data as **pure JSON only** — no markdown, no code fences, no extra text.

Required JSON structure:
{
  "title": "Story title (Chinese)",
  "characters": [
    {
      "name": "Character name (Chinese)",
      "gender": "male/female",
      "age_group": "teenager/adult/child/elder",
      "appearance": {
        "face": "facial features in English (e.g. 'oval face, delicate features, fair skin')",
        "hair": "hair style and color in English",
        "eyes": "eye color and shape in English",
        "body": "body type in English",
        "outfit": "clothing description in English (can be used directly as AI prompt)",
        "accessories": "accessories in English"
      },
      "personality": "Personality in Chinese",
      "role": "protagonist/love_interest/supporting/antagonist"
    }
  ],
  "scenes": [
    {
      "name": "Scene name (Chinese)",
      "location": "location in English",
      "atmosphere": "atmosphere description in English",
      "lighting": "lighting setup in English",
      "elements": ["element1", "element2"],
      "mood": "Mood tag in Chinese"
    }
  ],
  "panels": [
    {
      "panel_number": 1,
      "scene": "Scene name (must match a scenes[].name above)",
      "characters_in_panel": ["Character A", "Character B"],
      "action": "Action description in English",
      "camera": "one of: extreme wide / wide shot / medium wide / medium shot / medium close / close up / extreme close / two shot / over shoulder / point of view / dutch angle / bird's eye / worm's eye",
      "camera_angle": "one of: eye level / low angle / high angle / tilt up / tilt down / dutch / overhead",
      "composition_notes": "Composition notes in English",
      "dialogue": "Any dialogue text here",
      "emotional_beat": "one of: joyful / sad / romantic / tense / conflict / suspense / peaceful / melancholic / exciting / mysterious",
      "mood": "Short mood description in Chinese"
    }
  ]
}

Rules:
- Max 6 characters, max 6 scenes
- 3 to 12 panels total
- Narrative pacing: establish setting → character intro → interaction → climax → resolution
- appearance fields must be in English, suitable as AI image prompts
- Every panel.scene must reference an existing scene in scenes[]
- Every character in characters_in_panel must reference an existing character in characters[]"""

    def __init__(self, model: str = None, timeout: int = None):
        self.model = model or self.MODEL
        self.timeout = timeout or self.TIMEOUT
        self._last_raw = ""

    def _call_llm(self, user_prompt: str) -> str:
        """调用 Ollama API 获取纯文本响应"""
        import http.client
        import json as json_mod

        payload = json_mod.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "options": {
                "temperature": 0.5,
                "num_predict": 4096,
                "stop": ["<|im_end|>"]
            }
        })

        conn = http.client.HTTPConnection("127.0.0.1", 11434, timeout=self.timeout)
        try:
            conn.request("POST", "/api/chat", body=payload,
                         headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            body = resp.read().decode("utf-8")
            data = json_mod.loads(body)

            msg = data.get("message", {})
            content = msg.get("content", "")

            # Clean potential markdown code fences
            content = content.strip()
            if "```json" in content:
                content = content.split("```json", 1)[-1]
            elif "```" in content:
                content = content.split("```", 1)[-1]
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]

            self._last_raw = content.strip()
            return self._last_raw
        except Exception as e:
            raise RuntimeError(f"LLM call failed: {e}")
        finally:
            conn.close()

    def parse_script(self, script: str) -> dict:
        """
        Parse script → structured dict.
        Uses LLM first; falls back to regex on failure.
        """
        try:
            prompt = f"Analyze this script and output the JSON storyboard data:\n\n{script}"
            raw = self._call_llm(prompt)
            data = json.loads(raw)
            return self._validate(data)
        except Exception as e:
            print(f"⚠️ LLM parsing failed ({e}), falling back to regex")
            return self._regex_fallback(script)

    def _validate(self, data: dict) -> dict:
        """Validate LLM output structure, supply defaults"""
        errors = []
        for key in ["panels", "characters", "scenes"]:
            if key not in data or not data[key]:
                errors.append(f"missing {key}")

        if errors:
            raise ValueError(f"LLM output validation: {', '.join(errors)}")

        data.setdefault("title", "Untitled")
        for p in data["panels"]:
            p.setdefault("camera", "medium shot")
            p.setdefault("camera_angle", "eye level")
            p.setdefault("characters_in_panel", [])
            p.setdefault("composition_notes", "")
            p.setdefault("dialogue", "")
            p.setdefault("emotional_beat", "neutral")

        return data

    def _regex_fallback(self, script: str) -> dict:
        """Fallback to regex-based parsing from MangaEngine"""
        engine = MangaEngine()
        sb = engine.from_script(script)
        return {
            "title": sb.title,
            "characters": [{"name": k} for k in sb.characters.keys()],
            "scenes": [{"name": k} for k in sb.scenes.keys()],
            "panels": [
                {
                    "panel_number": p.panel_number,
                    "scene": p.scene,
                    "characters_in_panel": p.character_names,
                    "action": p.action_description,
                    "camera": p.camera,
                    "camera_angle": p.camera_angle,
                    "composition_notes": p.composition_notes,
                    "dialogue": p.dialogue,
                    "emotional_beat": "neutral",
                }
                for p in sb.panels
            ]
        }

    def to_storyboard(self, data: dict) -> Storyboard:
        """Convert LLM structured data → Storyboard objects"""
        sb = Storyboard(title=data.get("title", "故事"))

        # Characters
        for c in data.get("characters", []):
            card = CharacterCard(
                name=c.get("name", "角色"),
                gender=c.get("gender", "女"),
                age_group=c.get("age_group", "成人"),
                appearance=c.get("appearance", {
                    "face": "", "hair": "", "eyes": "",
                    "body": "", "outfit": "", "accessories": ""
                }),
                seed_base=abs(hash(c.get("name", ""))) % 99999,
            )
            sb.characters[c["name"]] = card

        # Scenes
        for s in data.get("scenes", []):
            card = SceneCard(
                name=s.get("name", ""),
                location=s.get("location", ""),
                atmosphere=s.get("atmosphere", ""),
                lighting=s.get("lighting", ""),
                elements=s.get("elements", []),
                prompt_tags=s.get("elements", []),
            )
            sb.scenes[s["name"]] = card

        # Panels
        for p in data.get("panels", []):
            panel = Panel(
                panel_number=p.get("panel_number", len(sb.panels) + 1),
                character_names=p.get("characters_in_panel", []),
                scene=p.get("scene", ""),
                camera=p.get("camera", "medium shot"),
                camera_angle=p.get("camera_angle", "eye level"),
                action_description=p.get("action", ""),
                composition_notes=p.get("composition_notes", ""),
                dialogue=p.get("dialogue", ""),
                emotional_beat=p.get("emotional_beat", "neutral"),
            )
            sb.panels.append(panel)
        return sb

    def from_script(self, script: str) -> Storyboard:
        """One-call: script → Storyboard objects"""
        data = self.parse_script(script)
        return self.to_storyboard(data)

    def summarize(self, data: dict = None) -> str:
        """Human-readable storyboard summary"""
        d = data
        if d is None and self._last_raw:
            try:
                d = json.loads(self._last_raw)
            except json.JSONDecodeError:
                d = {}
        if not d:
            return "无故事板数据"

        lines = [f"📖 {d.get('title', '故事')}\n"]

        # Characters
        chars = d.get("characters", [])
        if chars:
            lines.append("🎭 角色:")
            for c in chars:
                app = c.get("appearance", {})
                desc = ", ".join(filter(None, [
                    app.get("hair"), app.get("eyes"), app.get("outfit")
                ]))
                arch = c.get("role", "")
                lines.append(f"  {c['name']} ({c.get('gender','')}/{c.get('age_group','')}): {desc[:100]}")
                if arch:
                    lines.append(f"     定位: {arch}")
            lines.append("")

        # Scenes
        scenes = d.get("scenes", [])
        if scenes:
            lines.append("🏞 场景:")
            for s in scenes:
                light = s.get("lighting", "")
                mood = s.get("mood", "")
                lines.append(f"  {s['name']}: {s.get('atmosphere','')} | 光线={light} | 情绪={mood}")
            lines.append("")

        # Panels
        lines.append("🎬 分镜:")
        for p in d.get("panels", []):
            chars_str = ", ".join(p.get("characters_in_panel", [])) or "(无)"
            cam = p.get("camera", "")
            beat = p.get("emotional_beat", "")
            scene = p.get("scene", "")
            lines.append(f"  [{p['panel_number']:2d}] {cam:15s} | {scene:10s} | {chars_str}")
            if p.get("action"):
                lines.append(f"      动作: {p['action'][:70]}")
            if beat:
                lines.append(f"      情感: {beat}")
            if p.get("dialogue"):
                lines.append(f"      台词: 「{p['dialogue'][:50]}」")

        return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# 便捷 API: 一键剧本 → 故事板
# ════════════════════════════════════════════════════════════

def storyboard_from_script(script: str, use_llm: bool = True) -> Storyboard:
    """
    从自然语言剧本生成故事板

    use_llm=True (默认):
      用 qwen3:14b 理解语义 → 生成结构化分镜
    use_llm=False:
      用正则模板匹配 (传统 fallback)
    """
    if use_llm:
        agent = StoryboardAgent()
        try:
            sb = agent.from_script(script)
            print(agent.summarize())
            return sb
        except Exception as e:
            print(f"⚠️ LLM 模式失败: {e}, 回退正则")

    engine = MangaEngine()
    engine.from_script(script)
    return engine.storyboard or Storyboard()


# ════════════════════════════════════════════════════════════
# LLM 驱动: 根据上下文设计角色外观
# ════════════════════════════════════════════════════════════

def llm_design_character(char_name: str, context: str) -> CharacterCard:
    """
    用 LLM 根据故事上下文补全角色视觉设计

    示例: llm_design_character("女主角", "一个黑长直傲娇的高中生")
    → 自动生成完整的 CharacterCard (发型/瞳色/服装/配饰)
    """
    prompt = f"""Design character "{char_name}" based on this context.
Output pure JSON only (no markdown):
{{
  "gender": "male/female",
  "age_group": "teenager/adult/child",
  "appearance": {{
    "face": "facial features in English",
    "hair": "hair style and color in English",
    "eyes": "eye color and shape in English",
    "body": "body type in English",
    "outfit": "clothing in English",
    "accessories": "accessories in English"
  }},
  "personality": "Personality in Chinese"
}}

Context: {context}"""

    agent = StoryboardAgent()
    try:
        raw = agent._call_llm(prompt)
        data = json.loads(raw)
        return CharacterCard(
            name=char_name,
            gender=data.get("gender", "female"),
            age_group=data.get("age_group", "adult"),
            appearance=data.get("appearance", {}),
        )
    except Exception as e:
        print(f"⚠️ LLM character design failed: {e}")
        return CharacterCard(name=char_name)


# ════════════════════════════════════════════════════════════
# 情感弧分析
# ════════════════════════════════════════════════════════════

def analyze_emotional_arc(storyboard: Storyboard) -> dict:
    """
    分析故事板中的情感弧线

    输出: 整体趋势 + 每个分镜的情感标签
    """
    if not storyboard.panels:
        return {"arc": "unknown", "beats": []}

    beats = []
    for p in storyboard.panels:
        beat = getattr(p, "emotional_beat", "neutral") or "neutral"
        beats.append({"panel": p.panel_number, "scene": p.scene, "emotion": beat})

    # Simple trend analysis
    positive = sum(1 for b in beats if b["emotion"] in (
        "joyful", "romantic", "peaceful", "exciting"))
    negative = sum(1 for b in beats if b["emotion"] in (
        "sad", "tense", "conflict", "melancholic"))

    if positive > negative * 2:
        arc = "⬆ 上升 (积极结局)"
    elif negative > positive * 2:
        arc = "⬇ 下降 (悲剧/沉重)"
    else:
        arc = "↕ 波动 (有起有伏)"

    return {"arc": arc, "beats": beats, "total_panels": len(beats)}

# ════════════════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║         漫画连续性与角色一致性系统 v1.0                      ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    
    # 创建角色卡
    heroine = CharacterCard(
        name="女主角",
        gender="女",
        age_group="高中生",
        appearance={
            "face": "oval face, delicate features, fair skin",
            "hair": "long black hair, hime cut, purple ribbon",
            "eyes": "violet eyes, gentle gaze",
            "body": "slender, petite, graceful",
            "outfit": "sailor school uniform, red necktie, pleated skirt",
            "accessories": "purple ribbon, knee-high socks, loafers",
        },
        seed_base=42,
    )
    
    hero = CharacterCard(
        name="男主角",
        gender="男",
        age_group="高中生",
        appearance={
            "face": "sharp features, cool expression",
            "hair": "black messy hair, medium length",
            "eyes": "dark blue eyes, strong gaze",
            "body": "tall, athletic",
            "outfit": "gakuran school uniform, white shirt",
            "accessories": "none",
        },
        seed_base=100,
    )
    
    # 创建场景卡
    classroom = SceneCard(
        name="教室",
        location="high school classroom",
        atmosphere="peaceful, morning sunlight",
        lighting="warm natural light from windows",
        elements=["desks in rows", "blackboard", "open windows", "white curtains"],
        prompt_tags=["classroom", "school", "morning", "sunlight"],
    )
    
    sakura_path = SceneCard(
        name="樱花树道",
        location="cherry blossom avenue",
        atmosphere="romantic, spring breeze",
        lighting="golden hour backlight",
        elements=["cherry trees full bloom", "falling petals", "stone path", "bench"],
        prompt_tags=["cherry blossoms", "sakura", "spring", "petals"],
    )
    
    rooftop = SceneCard(
        name="学校屋顶",
        location="school rooftop",
        atmosphere="quiet afternoon, secret place",
        lighting="golden hour, backlight",
        elements=["wire fence", "water tower", "blue sky", "wind"],
        prompt_tags=["rooftop", "after school", "sunset", "sky"],
    )
    
    # 创建故事板 (日式漫画4格)
    engine = MangaEngine()
    engine.add_character("女主角", heroine)
    engine.add_character("男主角", hero)
    engine.add_scene("教室", classroom)
    engine.add_scene("樱花树道", sakura_path)
    engine.add_scene("学校屋顶", rooftop)
    
    # 分镜
    engine.storyboard = Storyboard(
        title="樱花下的相遇",
        characters={"女主角": heroine, "男主角": hero},
        scenes={"教室": classroom, "樱花树道": sakura_path, "学校屋顶": rooftop},
        panels=[
            Panel(1, ["女主角"], "櫻花樹道", camera="wide shot", camera_angle="eye level",
                  composition_notes="女主角站在樱花树下, 花瓣飘落, 逆光"),
            Panel(2, ["女主角", "男主角"], "教室", camera="medium shot", camera_angle="eye level",
                  composition_notes="两人在教室擦肩而过, 目光短暂相遇"),
            Panel(3, ["女主角"], "教室", camera="close up", camera_angle="slightly low",
                  composition_notes="女主角回头, 脸微红, 樱花花瓣从窗外飘入"),
            Panel(4, ["女主角", "男主角"], "学校屋顶", camera="long shot", camera_angle="eye level",
                  composition_notes="夕阳下两人并肩, 远处城市天际线"),
        ]
    )
    
    print(f"\n📖 故事: {engine.storyboard.title}")
    print(engine.describe_story())
    
    print("\n\n🔍 批量生成配置 (前2镜):")
    configs = engine.to_comfyui_batch()
    for cfg in configs[:4]:
        char = cfg["character"]
        strategy = cfg["strategy"]
        print(f"  镜{cfg['panel']} [{char}] seed={cfg['seed']} | {strategy['description'][:40]}")
        print(f"    提示词: {cfg['prompt'][:80]}...")
    
    print("\n\n🔍 漫画排版选项:")
    for name, layout in MANGA_LAYOUTS.items():
        print(f"  {name:15s} | {layout['rows']}×{layout['cols']} | {layout['description']}")
    
    print("\n\n🔍 预置漫画模板:")
    for name, tmpl in MANGA_TEMPLATES.items():
        print(f"  {name:15s} | {tmpl['name']} | {len(tmpl['panels'])}镜")
