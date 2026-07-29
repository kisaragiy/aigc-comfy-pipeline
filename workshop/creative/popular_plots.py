#!/usr/bin/env python3
"""
大众喜闻乐见的情节模板库 v1.0

常见故事原型 (Narrative Archetypes) → 可验证的故事板

每个模板含:
  - 名称 + 一句话梗概
  - 情感弧线 (上升/下降/波动)
  - 角色数 / 场景数 / 推荐分镜数
  - 分镜序列 (场景+角色+动作+镜头+情感)
  - 目标受众 + 喜闻乐见原因

用途:
  1. 手动验收: run 此文件验证故事板生成质量
  2. 自动测试: 每个模板可用 LLM StoryboardAgent 生成并验证
  3. 创意参考: 填充 go_director / go_manga 的预设模板
"""

from __future__ import annotations

from typing import Any


# ════════════════════════════════════════════════════════════
# 情节模板
# ════════════════════════════════════════════════════════════

from dataclasses import dataclass

@dataclass
class PlotTemplate:
    """一个故事原型"""
    id: str
    name: str
    genre: str
    summary: str
    arcs: list[str]             # 情感弧线关键词
    characters: list[dict]      # 角色列表
    scenes: list[str]           # 场景列表
    beats: list[dict]           # 分镜节拍
    audience_appeal: str        # 喜闻乐见原因
    panel_count: int = 4        # 推荐分镜数
    character_count: int = 2    # 角色数

PLOT_TEMPLATES: dict[str, PlotTemplate] = {}

def register(entry_id: str = None, **kw):
    """注册一个情节模板"""
    name = kw.pop("name", entry_id)
    if not name and entry_id:
        name = entry_id
    kw.setdefault("id", name)
    PLOT_TEMPLATES[name] = PlotTemplate(name=name, **kw)

# ════════════════════════════════════════════════════════════
# 1) 校园·樱花树下的偶遇
# ════════════════════════════════════════════════════════════

register(
    "校园·樱花树下的偶遇",
    name="樱花树下的偶遇",
    genre="校园恋爱",
    summary="新学期的樱花树下, 女主角在等朋友, 男主角路过时被她的身影吸引。两人目光相遇, 樱花飘落——经典的命运般邂逅。",
    arcs=["寂寞→心动→浪漫→期待"],
    characters=[
        {"name": "女主角", "gender": "女", "age": "高中生", "archetype": "元气/温柔"},
        {"name": "男主角", "gender": "男", "age": "高中生", "archetype": "清爽/冷淡"},
    ],
    scenes=["樱花树道", "教室"],
    beats=[
        {"panel": 1, "scene": "樱花树道", "characters": ["女主角"],
         "action": "女主角站在樱花树下看花瓣飘落",
         "camera": "wide shot", "emotion": "melancholic"},
        {"panel": 2, "scene": "樱花树道", "characters": ["男主角"],
         "action": "男主角从远处走来, 被女主角的身影吸引驻足",
         "camera": "medium shot", "emotion": "curious"},
        {"panel": 3, "scene": "樱花树道", "characters": ["女主角", "男主角"],
         "action": "女主角转头, 两人目光相遇, 樱花从中间落下",
         "camera": "close up", "emotion": "romantic"},
        {"panel": 4, "scene": "教室", "characters": ["女主角"],
         "action": "女主角在教室回想刚才的画面, 脸微红",
         "camera": "medium close", "emotion": "peaceful"},
    ],
    audience_appeal="校园恋爱是最容易共情的题材之一, 樱花+相遇+目光接触是经典记忆锚点。"
)

# ════════════════════════════════════════════════════════════
# 2) 夏日·烟花大会
# ════════════════════════════════════════════════════════════

register(
    "夏日·烟花大会",
    name="烟花下的告白",
    genre="夏日浪漫",
    summary="夏日祭典的夜晚, 两人穿着浴衣在人群中走散。男主角在烟花塔下找到女主角, 在烟花绽放的瞬间鼓起勇气告白。",
    arcs=["兴奋→焦虑→紧张→幸福"],
    characters=[
        {"name": "女主角", "gender": "女", "age": "高中生", "archetype": "害羞/内向"},
        {"name": "男主角", "gender": "男", "age": "高中生", "archetype": "温柔/腼腆"},
    ],
    scenes=["祭典街道", "烟花观赏台"],
    beats=[
        {"panel": 1, "scene": "祭典街道", "characters": ["女主角", "男主角"],
         "action": "两人在人群中并肩走, 烟花在远处绽放",
         "camera": "wide shot", "emotion": "joyful"},
        {"panel": 2, "scene": "祭典街道", "characters": ["女主角"],
         "action": "女主角被人群挤散, 回头找不到男主角, 表情焦虑",
         "camera": "medium close", "emotion": "tense"},
        {"panel": 3, "scene": "烟花观赏台", "characters": ["女主角", "男主角"],
         "action": "男主角在烟花塔下找到她, 拉住她的手腕",
         "camera": "close up", "emotion": "romantic"},
        {"panel": 4, "scene": "烟花观赏台", "characters": ["女主角", "男主角"],
         "action": "烟花绽放在夜空中, 两人相视而笑",
         "camera": "two shot", "emotion": "peaceful"},
    ],
    audience_appeal="祭典+浴衣+烟花是夏日浪漫的经典组合。走散→寻找→重逢天然制造情感起伏。"
)

# ════════════════════════════════════════════════════════════
# 3) 异世界·典藏开局
# ════════════════════════════════════════════════════════════

register(
    "异世界·典藏开局",
    name="异世界转生·觉醒",
    genre="异世界冒险",
    summary="主角在现实世界意外死亡后转生到异世界, 醒来发现自己拥有特殊能力。面对未知的世界和威胁, 主角握紧武器踏上冒险。",
    arcs=["困惑→觉醒→决心→行动"],
    characters=[
        {"name": "主角", "gender": "男/女", "age": "青年", "archetype": "沉着/适应力强"},
        {"name": "精灵向导", "gender": "女", "age": "神秘", "archetype": "神秘/智慧"},
    ],
    scenes=["异世界草原", "遗迹"],
    beats=[
        {"panel": 1, "scene": "异世界草原", "characters": ["主角"],
         "action": "主角在草地上醒来, 看到天空两个月亮, 表情困惑",
         "camera": "wide shot", "emotion": "mysterious"},
        {"panel": 2, "scene": "异世界草原", "characters": ["主角"],
         "action": "主角抬手, 手心发光, 意识到这是新世界的力量",
         "camera": "close up", "emotion": "exciting"},
        {"panel": 3, "scene": "遗迹", "characters": ["主角", "精灵向导"],
         "action": "精灵向导出现, 告诉主角他的使命",
         "camera": "medium shot", "emotion": "suspense"},
        {"panel": 4, "scene": "遗迹", "characters": ["主角"],
         "action": "主角握紧剑, 目光坚定, 准备出发",
         "camera": "low angle", "emotion": "peaceful"},
    ],
    audience_appeal="异世界是最热门的 ACG 题材之一。觉醒力量+使命召唤+未知世界激发探索欲。"
)

# ════════════════════════════════════════════════════════════
# 4) 战斗·最终对决
# ════════════════════════════════════════════════════════════

register(
    "战斗·最终对决",
    name="巅峰对决",
    genre="战斗",
    summary="主角与宿敌在废弃城堡顶层的决战。双方都已受伤疲惫, 但都不愿放弃。最后的碰撞——胜负在一瞬之间。",
    arcs=["对峙→激战→悬念→终结"],
    characters=[
        {"name": "主角", "gender": "男", "age": "青年", "archetype": "热血/不屈"},
        {"name": "宿敌/反派", "gender": "男", "age": "青年", "archetype": "冷酷/强大"},
    ],
    scenes=["城堡顶层", "破碎城堡远景"],
    beats=[
        {"panel": 1, "scene": "城堡顶层", "characters": ["主角", "宿敌/反派"],
         "action": "两人在雨中举剑对峙, 表情决绝",
         "camera": "bird's eye", "emotion": "conflict"},
        {"panel": 2, "scene": "城堡顶层", "characters": ["主角"],
         "action": "主角冲刺, 脚下溅起水花",
         "camera": "action shot", "emotion": "tense"},
        {"panel": 3, "scene": "城堡顶层", "characters": ["主角", "宿敌/反派"],
         "action": "两人武器碰撞, 火花四溅, 特写双方表情",
         "camera": "close up", "emotion": "conflict"},
        {"panel": 4, "scene": "破碎城堡远景", "characters": ["主角"],
         "action": "主角站在废墟上, 剑尖指地, 背对夕阳",
         "camera": "worm's eye", "emotion": "peaceful"},
    ],
    audience_appeal="热血战斗是永不过时的题材。对峙→激战→胜负的节奏感让观众肾上腺素飙升。"
)

# ════════════════════════════════════════════════════════════
# 5) 日常·青梅竹马
# ════════════════════════════════════════════════════════════

register(
    "日常·青梅竹马",
    name="青梅竹马·放学路",
    genre="日常治愈",
    summary="放学的路上, 两人如往常一样一起回家。今天的夕阳特别美, 女主角突然意识到身边的这个人, 已经陪伴了自己这么多年。",
    arcs=["日常→温馨→感动→温暖"],
    characters=[
        {"name": "女主角", "gender": "女", "age": "高中生", "archetype": "迟钝/天然"},
        {"name": "青梅竹马(男)", "gender": "男", "age": "高中生", "archetype": "包容/温柔"},
    ],
    scenes=["放学街道", "河畔长椅"],
    beats=[
        {"panel": 1, "scene": "放学街道", "characters": ["女主角", "青梅竹马(男)"],
         "action": "两人并排走着, 夕阳把影子拉得很长",
         "camera": "wide shot", "emotion": "peaceful"},
        {"panel": 2, "scene": "放学街道", "characters": ["女主角", "青梅竹马(男)"],
         "action": "男主角买了两份冰淇淋, 递给她一份",
         "camera": "medium shot", "emotion": "joyful"},
        {"panel": 3, "scene": "河畔长椅", "characters": ["女主角"],
         "action": "女主角看着男主角的侧脸, 突然心跳加速",
         "camera": "close up", "emotion": "romantic"},
        {"panel": 4, "scene": "河畔长椅", "characters": ["女主角", "青梅竹马(男)"],
         "action": "夕阳落在河面上, 两人并肩坐着, 女主角偷偷笑了",
         "camera": "two shot", "emotion": "peaceful"},
    ],
    audience_appeal="青梅竹马是日式 ACG 最经典的设定之一。日常中的温馨瞬间让人产生「我也想要这样的日常」的共鸣。"
)

# ════════════════════════════════════════════════════════════
# 6) 悬疑·秘密档案
# ════════════════════════════════════════════════════════════

register(
    "悬疑·秘密档案",
    name="深夜的档案室",
    genre="悬疑",
    summary="深夜, 侦探在学校的旧档案室里发现了被藏起来的文件。正当他翻看时, 身后传来脚步声...",
    arcs=["平静→紧张→恐惧→悬念"],
    characters=[
        {"name": "侦探", "gender": "男", "age": "青年", "archetype": "聪明/谨慎"},
    ],
    scenes=["旧档案室", "学校走廊"],
    beats=[
        {"panel": 1, "scene": "旧档案室", "characters": ["侦探"],
         "action": "侦探用手电筒照着一份旧文件, 眉头紧锁",
         "camera": "medium shot", "emotion": "tense"},
        {"panel": 2, "scene": "旧档案室", "characters": ["侦探"],
         "action": "文件上写着关键线索, 侦探的瞳孔收缩",
         "camera": "close up", "emotion": "suspense"},
        {"panel": 3, "scene": "旧档案室", "characters": ["侦探"],
         "action": "远处传来脚步声, 侦探猛地回头",
         "camera": "over shoulder", "emotion": "mysterious"},
        {"panel": 4, "scene": "学校走廊", "characters": ["侦探"],
         "action": "侦探冲出档案室, 消失在走廊尽头, 灯闪烁",
         "camera": "dutch angle", "emotion": "tense"},
    ],
    audience_appeal="悬疑题材制造紧张感和好奇心。深夜调查+秘密档案+脚步声的经典组合让人欲罢不能。"
)

# ════════════════════════════════════════════════════════════
# 7) 治愈·雨过天晴
# ════════════════════════════════════════════════════════════

register(
    "治愈·雨过天晴",
    name="雨过天晴",
    genre="治愈",
    summary="女主角因为某些事情心情低落, 独自在窗边看雨。男朋友发现了她, 没有说话, 只是安静地坐在她旁边, 陪她一起看雨。雨停了, 阳光透进来。",
    arcs=["忧郁→沉默→温暖→希望"],
    characters=[
        {"name": "女主角", "gender": "女", "age": "青年", "archetype": "内向/敏感"},
        {"name": "男朋友", "gender": "男", "age": "青年", "archetype": "温柔/体贴"},
    ],
    scenes=["窗边", "阳台"],
    beats=[
        {"panel": 1, "scene": "窗边", "characters": ["女主角"],
         "action": "女主角望着窗外的雨, 表情落寞",
         "camera": "medium close", "emotion": "melancholic"},
        {"panel": 2, "scene": "窗边", "characters": ["女主角", "男朋友"],
         "action": "男朋友默默走来, 端着一杯热茶, 放在她手边",
         "camera": "medium shot", "emotion": "peaceful"},
        {"panel": 3, "scene": "窗边", "characters": ["女主角", "男朋友"],
         "action": "两人并肩坐着看雨, 没有说话, 气氛温馨",
         "camera": "close up", "emotion": "romantic"},
        {"panel": 4, "scene": "阳台", "characters": ["女主角", "男朋友"],
         "action": "雨停, 阳光照射进来, 女主角露出微笑",
         "camera": "wide shot", "emotion": "joyful"},
    ],
    audience_appeal="治愈系需要细腻的情感刻画。雨→天晴是经典的象征手法, 「什么都不用说, 我陪你」的温暖感。"
)

# ════════════════════════════════════════════════════════════
# 8) 喜剧·便当战争
# ════════════════════════════════════════════════════════════

register(
    "喜剧·便当战争",
    name="便当交换",
    genre="日常喜剧",
    summary="午休时间, 女主角打开便当盒发现——是男主角做的! 原来两个人拿错了便当。女主角尴尬又害羞, 男主角却很自然地开始吃她的便当。",
    arcs=["惊讶→尴尬→甜蜜→心动"],
    characters=[
        {"name": "女主角", "gender": "女", "age": "高中生", "archetype": "爱面子/傲娇"},
        {"name": "男主角", "gender": "男", "age": "高中生", "archetype": "天然/温柔"},
    ],
    scenes=["教室(午休)", "天台"],
    beats=[
        {"panel": 1, "scene": "教室(午休)", "characters": ["女主角", "男主角"],
         "action": "女主角打开便当, 发现是男主的料理, 震惊",
         "camera": "close up", "emotion": "exciting"},
        {"panel": 2, "scene": "教室(午休)", "characters": ["女主角", "男主角"],
         "action": "男主角若无其事地吃她的便当, 称赞好吃",
         "camera": "medium shot", "emotion": "joyful"},
        {"panel": 3, "scene": "教室(午休)", "characters": ["女主角"],
         "action": "女主角脸红, 低头吃男主做的料理",
         "camera": "medium close", "emotion": "romantic"},
        {"panel": 4, "scene": "天台", "characters": ["女主角", "男主角"],
         "action": "两人在天台一起吃剩下的便当, 阳光正好",
         "camera": "two shot", "emotion": "peaceful"},
    ],
    audience_appeal="便当交换是日常系漫画的经典桥段。意外的亲密+料理的温暖+青涩的甜蜜, 幽默又温馨。"
)

# ════════════════════════════════════════════════════════════
# 统计
# ════════════════════════════════════════════════════════════

PLOT_SUMMARY = {
    "total_templates": len(PLOT_TEMPLATES),
    "genres": list(sorted(set(t.genre for t in PLOT_TEMPLATES.values()))),
    "total_panels": sum(t.panel_count for t in PLOT_TEMPLATES.values()),
    "templates": list(PLOT_TEMPLATES.keys()),
}


def get_plot_prompt(plot_id: str) -> str:
    """生成可用于 LLM 故事板输入的剧本文本"""
    t = PLOT_TEMPLATES.get(plot_id)
    if not t:
        return ""
    
    lines = [f"# {t.name}\n"]
    lines.append(f"类型: {t.genre}")
    lines.append(f"梗概: {t.summary}")
    lines.append("")
    
    for b in t.beats:
        chars = "、".join(b["characters"])
        cam = b["camera"]
        emo = b["emotion"]
        lines.append(f"第{b['panel']}镜: [{cam}] {chars} — {b['action']} ({emo})")
    
    return "\n".join(lines)


def verify_plot_coverage() -> dict:
    """验证情节模板覆盖率"""
    genres = {}
    for t in PLOT_TEMPLATES.values():
        genres[t.genre] = genres.get(t.genre, 0) + 1
    
    return {
        "总模板数": len(PLOT_TEMPLATES),
        "覆盖类型": len(genres),
        "类型分布": genres,
        "总分镜数": sum(t.panel_count for t in PLOT_TEMPLATES.values()),
        "总角色数": sum(t.character_count for t in PLOT_TEMPLATES.values()),
    }


if __name__ == "__main__":
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║         大众喜闻乐见的情节模板库 v1.0                        ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    print()
    
    stats = verify_plot_coverage()
    for k, v in stats.items():
        print(f"  {k}: {v}")
    
    print("\n" + "━" * 55)
    for tid, t in PLOT_TEMPLATES.items():
        print(f"\n📌 {t.name} [{t.genre}]")
        print(f"   {t.summary[:80]}...")
        print(f"   情感弧: {' → '.join(t.arcs)}")
        print(f"   角色: {t.character_count}人, 分镜: {t.panel_count}格")
        print(f"   受众: {t.audience_appeal[:60]}...")
    
    print("\n" + "━" * 55)
    print("\n📋 验证: 每个情节可输入 LLM 故事板检查生成质量")
    for tid in PLOT_TEMPLATES:
        prompt = get_plot_prompt(tid)
        print(f"\n─── {tid} ───")
        print(prompt[:120] + "...")
