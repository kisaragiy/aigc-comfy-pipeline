#!/usr/bin/env python3
"""
深度背景知识体系 — 从场景描述到构图参数

你在问: 背景、人物形象设计是否缺失。

本系统回答: "一个场景到底是什么?"
不是表层标签, 而是:
  - 这个场景有哪些必备视觉元素
  - 什么光线/色彩/氛围
  - 什么视角最有表现力
  - 同一个场景在不同情绪下如何变化
  - 场景与角色的视觉关系
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

# ════════════════════════════════════════════════════════════
# 基础: 镜头语言
# ════════════════════════════════════════════════════════════

CAMERA_SHOTS = {
    "extreme wide":   {"name": "超远景", "frame": "人极小, 环境为主", "用途": ["交代环境", "史诗感", "开场"]},
    "wide shot":      {"name": "远景", "frame": "全身+大量环境", "用途": ["位置关系", "动作场景", "风景"]},
    "medium wide":    {"name": "中远景", "frame": "膝上+环境", "用途": ["场景+角色结合", "站姿对话"]},
    "medium shot":    {"name": "中景", "frame": "腰上", "用途": ["对话", "互动", "标准叙事"]},
    "medium close":   {"name": "中近景", "frame": "胸上", "用途": ["强调表情+上半身语言", "亲密对话"]},
    "close up":       {"name": "特写", "frame": "脸占画面2/3", "用途": ["表情", "情绪高潮", "细节"]},
    "extreme close":  {"name": "超特写", "frame": "眼/嘴/手局部", "用途": ["情绪峰值", "关键细节", "悬疑"]},
    "two shot":       {"name": "双人镜", "frame": "两人同框", "用途": ["对话", "对峙", "关系展示"]},
    "over shoulder":  {"name": "过肩", "frame": "从一人背后看另一人", "用途": ["对话", "对峙", "场景带入"]},
    "point of view":  {"name": "主观视角", "frame": "角色的视角", "用途": ["沉浸", "代入", "恐怖"]},
    "dutch angle":    {"name": "斜角", "frame": "画面倾斜", "用途": ["不安", "疯狂", "紧张", "失衡"]},
    "bird's eye":     {"name": "俯瞰", "frame": "正上方", "用途": ["规模展示", "布局", "无力感"]},
    "worm's eye":     {"name": "仰视", "frame": "正下方向上", "用途": ["高大", "威严", "仰望"]},
}

CAMERA_ANGLES = {
    "eye level":  {"name": "平视", "情绪": ["中立", "自然", "代入"]},
    "low angle":  {"name": "低角度", "情绪": ["强大", "威压", "仰慕"]},
    "high angle": {"name": "高角度", "情绪": ["弱小", "脆弱", "俯瞰"]},
    "tilt up":    {"name": "仰拍", "情绪": ["渐渐展示", "揭示", "震撼"]},
    "tilt down":  {"name": "俯拍", "情绪": ["俯视", "全貌", "结束感"]},
    "dutch":      {"name": "荷兰角", "情绪": ["不安", "失衡", "精神异常"]},
    "overhead":   {"name": "顶拍", "情绪": ["抽象", "布局感", "客观"]},
}

# ════════════════════════════════════════════════════════════
# 光线类型
# ════════════════════════════════════════════════════════════

LIGHTING_SETUPS = {
    "黄金时间":    {"type": "natural", "color": "暖金", "source": "低角度夕阳/朝阳", "vibe": ["浪漫","温暖","怀旧","梦幻"]},
    "蓝色时刻":    {"type": "natural", "color": "冷蓝", "source": "日出前/日落后的天光", "vibe": ["忧郁","宁静","神秘","孤独"]},
    "逆光/剪影":   {"type": "natural", "color": "边缘光", "source": "背后光源", "vibe": ["神秘","浪漫","戏剧","神圣"]},
    "教室日光":    {"type": "indirect", "color": "白/暖白", "source": "大窗户散射光", "vibe": ["日常","透明感","青春","回忆"]},
    "蜡烛/篝火":   {"type": "warm", "color": "橙红(暖)", "source": "火焰", "vibe": ["亲密","原始","魔幻","古老"]},
    "霓虹夜":      {"type": "artificial", "color": "青紫/粉/青", "source": "霓虹灯+街灯", "vibe": ["都市","赛博","孤独","时髦"]},
    "月光":        {"type": "night", "color": "冷蓝/银", "source": "月亮", "vibe": ["神秘","浪漫","孤寂","幻想"]},
    "阴天漫射光":  {"type": "diffuse", "color": "灰白/冷", "source": "云层散射", "vibe": ["忧郁","安静","压抑","平淡"]},
    "舞台光":      {"type": "spot", "color": "聚光暖", "source": "上方聚光灯", "vibe": ["戏剧","聚焦","表演","审视"]},
    "侧光/明暗":   {"type": "hard", "color": "强对比", "source": "侧面强光源", "vibe": ["戏剧","硬朗","神秘","格调"]},
    "伦勃朗光":    {"type": "classic", "color": "三角光", "source": "45°侧上", "vibe": ["古典","格调","正式","油画感"]},
    "游戏UI光":    {"type": "game", "color": "过饱和", "source": "多光源混合", "vibe": ["游戏","华丽","CG","非现实"]},
}

# ════════════════════════════════════════════════════════════
# 色彩氛围
# ════════════════════════════════════════════════════════════

COLOR_GRADING = {
    "夏日限定":     {"palette": ["青", "白", "黄"], "temp": "暖", "vibe": "明亮, 青春, 怀旧感"},
    "赛博朋克":     {"palette": ["青紫", "粉", "青"], "temp": "冷+暖混", "vibe": "都市夜, 科技, 孤独"},
    "昭和怀旧":     {"palette": ["黄棕", "橙", "暗红"], "temp": "暖", "vibe": "怀旧, 温暖, 褪色"},
    "森系/治愈":    {"palette": ["绿", "棕", "米白"], "temp": "中性偏暖", "vibe": "自然, 治愈, 安静"},
    "黑暗奇幻":     {"palette": ["黑", "紫", "深蓝"], "temp": "冷", "vibe": "神秘, 危险, 厚重"},
    "少女漫画":     {"palette": ["粉", "白", "淡紫"], "temp": "暖", "vibe": "甜美, 浪漫, 轻快"},
    "浮世绘风":     {"palette": ["朱红", "靛蓝", "墨", "金"], "temp": "中性", "vibe": "和风, 传统, 装饰性"},
    "西部":         {"palette": ["橙黄", "棕", "暗红"], "temp": "暖", "vibe": "荒凉, 粗犷, 夕阳"},
    "北欧冷调":     {"palette": ["灰蓝", "白", "灰绿"], "temp": "冷", "vibe": "冷淡, 简约, 孤独"},
    "水彩淡彩":     {"palette": ["低饱和所有色"], "temp": "中性", "vibe": "轻, 透明感, 文艺"},
}

# ════════════════════════════════════════════════════════════
# 深度场景数据库
# ════════════════════════════════════════════════════════════

@dataclass
class SceneDB:
    """深度场景知识"""
    name: str
    category: str                 # 校园/都市/自然/幻想/特殊
    mood: list[str]               # 常见氛围
    key_elements: list[str]       # 必备元素
    lighting_options: list[str]   # 推荐光线
    color_palette: list[str]      # 推荐色板
    camera_suggestions: list[dict]  # 推荐镜头+理由
    time_of_day: list[str]
    weather_options: list[str]
    prompt_tags: str
    continuity_elements: list[str]  # 跨镜一致性关键元素

SCENES_DB = {
    # ══════════════════ 校园 ══════════════════
    "教室(窗边)": SceneDB(
        "教室(窗边)", "校园",
        ["日常","青春","回忆","孤独","交流"],
        ["窗(大, 多扇)", "课桌椅", "黑板", "窗帘(白)", "日光灯"],
        ["教室日光", "黄金时间(夕阳光从窗入)", "阴天漫射光"],
        ["白+木色", "暖白+中绿", "夕照金色"],
        [
            {"shot": "medium shot", "reason": "标准对话/上课镜头, 自然"},
            {"shot": "wide shot", "reason": "交代教室环境, 位置关系"},
            {"shot": "over shoulder", "reason": "从背后看角色看窗外"},
            {"shot": "close up", "reason": "表情捕捉, 窗边逆光"},
        ],
        ["清晨", "上午", "中午", "放学后(夕照)"],
        ["晴", "阴", "雨(窗外)", "雪(窗外)"],
        "classroom, desks, blackboard, window, white curtain, {time}, school supplies",
        ["窗外风景(树/操场)", "窗帘状态", "光线方向"]
    ),
    "教室(无人)": SceneDB(
        "教室(无人)", "校园",
        ["孤独","回忆","秘密","忧伤"],
        ["课桌椅(空)", "夕阳/月光的窗", "黑板(擦一半)", "时钟"],
        ["黄金时间", "蓝色时刻", "月光"],
        ["暖橙(夕)", "冷蓝(夜)", "灰白(阴)"],
        [
            {"shot": "wide shot", "reason": "强调空无一人的教室感"},
            {"shot": "dutch angle", "reason": "不安/异常感"},
            {"shot": "point of view", "reason": "从座位视角看空教室"},
        ],
        ["放学后", "夜晚"],
        ["晴(夕)", "雨", "雪"],
        "empty classroom, after school, sunset, empty desks, silence, melancholy",
        ["光线色温", "窗外天色"]
    ),
    "体育馆": SceneDB(
        "体育馆", "校园",
        ["活力","比赛","青春","汗水"],
        ["木质地板", "观众席", "篮球架/球网", "大窗(高)", "记分牌"],
        ["顶灯照明", "大窗自然光", "舞台光(聚光灯)"],
        ["木色+白+红", "冷白(日光灯)"],
        [
            {"shot": "wide shot", "reason": "比赛全景, 空间感"},
            {"shot": "low angle", "reason": "强调高大空间"},
            {"shot": "action shot", "reason": "运动中抓拍, 动态感"},
        ],
        ["下午", "黄昏"],
        ["晴"],
        "gymnasium, wooden floor, basketball court, spectators stands, sports",
        ["地面反光", "观众席布置"]
    ),
    "校门口": SceneDB(
        "校门口", "校园",
        ["相遇","等待","放学","离别"],
        ["校门(铁栅)", "校名牌", "樱花树", "自行车停车场"],
        ["黄金时间", "逆光", "阴天"],
        ["金色(夕)", "粉色(樱)"],
        [
            {"shot": "long shot", "reason": "校门全景, 等待/相遇的构图"},
            {"shot": "medium shot", "reason": "角色站在门口, 回头"},
        ],
        ["早上(上学)", "下午(放学)", "黄昏"],
        ["晴", "樱花季", "雨"],
        "school gate, entrance, cherry blossom, sunset, after school",
        ["校门样式", "樱花状态(满开/落叶)"]
    ),
    
    # ══════════════════ 都市 ══════════════════
    "樱花树道(春季)": SceneDB(
        "樱花树道", "都市",
        ["浪漫","相遇","离别","春"],
        ["樱花树(满开)", "花瓣飘落", "长椅", "路灯", "石板路"],
        ["黄金时间", "逆光", "柔光(阴天)"],
        ["粉+白+金(夕)", "粉+灰(阴)"],
        [
            {"shot": "wide shot", "reason": "树道全景, 花瓣满屏"},
            {"shot": "medium shot", "reason": "角色站在树下, 花瓣飘落"},
            {"shot": "close up", "reason": "伸手接花瓣, 表情特写"},
            {"shot": "low angle", "reason": "仰视樱花树冠+天空"},
            {"shot": "overhead", "reason": "俯拍树道上的人, 花瓣铺路"},
        ],
        ["清晨", "午后", "黄昏"],
        ["晴", "微风", "雨后"],
        "cherry blossom avenue, blooming sakura, falling petals, pink and white, spring breeze, stone path",
        ["花瓣量(满开vs落叶)", "树冠密度", "光线穿透樱花"]
    ),
    "夜晚街道": SceneDB(
        "夜晚街道", "都市",
        ["孤独","都市","夜","思考"],
        ["街灯(暖色)", "店铺招牌", "电线杆", "自动贩卖机", "湿路面(反射)"],
        ["霓虹夜", "月光", "蓝色时刻+街灯"],
        ["暖橙(街灯)+暗蓝(夜)", "霓虹紫粉"],
        [
            {"shot": "wide shot", "reason": "街道纵深感"},
            {"shot": "eye level", "reason": "行人视角, 自然"},
            {"shot": "dutch angle", "reason": "不安/迷离感"},
            {"shot": "close up", "reason": "表情, 反射在玻璃上的光"},
        ],
        ["深夜", "清晨前"],
        ["晴", "小雨(路面积水反射)"],
        "night street, street lamp, store sign, vending machine, wet asphalt, reflection, neon lights",
        ["街灯色温", "商店招牌内容"]
    ),
    "车站月台": SceneDB(
        "车站月台", "都市",
        ["离别","出发","等待","旅途"],
        ["铁轨延伸", "列车进站", "月台长椅", "时刻表", "天桥", "雨棚"],
        ["黄金时间", "蓝色时刻", "逆光(列车进站)"],
        ["冷蓝+暖灯", "金色夕阳"],
        [
            {"shot": "long shot", "reason": "列车进站, 延伸的铁轨"},
            {"shot": "over shoulder", "reason": "从角色背后看列车"},
            {"shot": "two shot", "reason": "月台上的离别/重逢"},
            {"shot": "point of view", "reason": "从列车窗内看月台"},
        ],
        ["清晨", "黄昏", "夜晚"],
        ["晴", "雨", "雪"],
        "train platform, railway tracks, train arriving, station roof, bench, departure, travel",
        ["列车型号", "月台编号", "时间表"]
    ),
    "咖啡厅窗边": SceneDB(
        "咖啡厅", "都市",
        ["治愈","都市日常","等待","观察"],
        ["窗(大)", "咖啡杯", "甜点", "木桌", "暖色灯光", "绿植"],
        ["教室日光(日)", "台灯暖光(夜)"],
        ["暖棕色+绿植", "暖光+窗外冷蓝"],
        [
            {"shot": "over shoulder", "reason": "从窗内看窗外街景"},
            {"shot": "medium close", "reason": "喝咖啡/看书的角色"},
            {"shot": "wide shot", "reason": "店内氛围, 空间感"},
        ],
        ["早上", "下午", "夜晚"],
        ["晴", "雨(窗上有雨滴)"],
        "cafe, coffee shop, window seat, wooden table, coffee cup, dessert, warm lighting",
        ["窗外街景", "店内装修风格"]
    ),
    
    # ══════════════════ 自然 ══════════════════
    "海边黄昏": SceneDB(
        "海边黄昏", "自然",
        ["浪漫","回忆","自由","伤感"],
        ["海(广阔)", "沙滩", "浪花", "夕阳", "岩石", "灯塔(远)"],
        ["黄金时间", "蓝色时刻(日落之后)"],
        ["橙+金+紫", "蓝+粉(过渡)"],
        [
            {"shot": "wide shot", "reason": "海天一体, 宏大浪漫"},
            {"shot": "silhouette", "reason": "逆光剪影, 氛围极强"},
            {"shot": "low angle", "reason": "浪花在脚下+夕阳"},
        ],
        ["日落前后30min"],
        ["晴", "微云(火烧云)"],
        "beach, ocean, sunset, golden hour, waves seashore, silhouette, romantic, evening sky",
        ["潮位", "夕阳位置"]
    ),
    "星空草原": SceneDB(
        "星空草原", "自然",
        ["幻想","宁静","广阔","神秘"],
        ["草原(广阔)", "星空(银河)", "风", "草(随风)"],
        ["月光", "星光"],
        ["深蓝+银+紫(夜空)", "暗绿(草)"],
        [
            {"shot": "wide shot", "reason": "天地浩瀚"},
            {"shot": "low angle", "reason": "躺下看星空"},
            {"shot": "silhouette", "reason": "人物剪影+星空"},
        ],
        ["深夜"],
        ["晴(无云)"],
        "starry sky, milky way, grassland, night, wind, nature, vast landscape",
        ["银河方向", "草的高度和颜色"]
    ),
    "竹林雨": SceneDB(
        "竹林雨", "自然",
        ["幽静","禅意","哀","净化"],
        ["竹林(密)", "雨丝", "石板路", "石灯笼", "水洼"],
        ["阴天漫射光", "蓝色时刻"],
        ["翠绿+灰白", "青绿"],
        [
            {"shot": "medium shot", "reason": "竹林中, 仰视竹竿"},
            {"shot": "wide shot", "reason": "竹林小径, 延伸感"},
            {"shot": "close up", "reason": "竹叶上的雨滴"},
        ],
        ["雨中", "雨后"],
        ["雨"],
        "bamboo forest, rain, mist, green, wet stone path, tranquil, japanese garden",
        ["竹子的密度"]
    ),
    
    # ══════════════════ 幻想 ══════════════════
    "异世界城堡": SceneDB(
        "异世界城堡", "幻想",
        ["冒险","神秘","壮丽","危险"],
        ["尖塔", "城墙(石)", "吊桥", "旗帜", "山巅/悬崖"],
        ["黄金时间", "逆光(从城堡后)", "月光"],
        ["灰石+蓝旗", "金(夕)+紫(影)"],
        [
            {"shot": "wide shot", "reason": "城堡全景, 宏大"},
            {"shot": "low angle", "reason": "仰望城堡, 压迫感"},
            {"shot": "bird's eye", "reason": "城堡布局+周边地形"},
        ],
        ["黄昏", "夜晚(灯亮)"],
        ["晴", "雾", "日落"],
        "fantasy castle, towering spires, stone walls, drawbridge, mountain peak, medieval, epic",
        ["旗帜纹章", "塔楼数量"]
    ),
    "浮空岛": SceneDB(
        "浮空岛", "幻想",
        ["幻想","飞翔","非现实","冒险"],
        ["浮岛(倒锥形)", "瀑布(从岛边流下)", "云海", "古树/遗迹"],
        ["黄金时间", "逆光(从云海上)"],
        ["金/粉(云上)", "翠绿(岛)"],
        [
            {"shot": "wide shot", "reason": "浮岛全景+云海"},
            {"shot": "worm's eye", "reason": "从下方仰望浮岛"},
        ],
        ["日出", "黄昏", "夜晚(星空)"],
        ["晴(云海)"],
        "floating island, waterfalls falling through clouds, sky, fantasy landscape, impossible geometry",
        ["云海厚度"]
    ),
    "龙栖山顶": SceneDB(
        "龙栖山顶", "幻想",
        ["传说","挑战","超越","终结"],
        ["山巅", "龙(盘踞/飞)", "云海(山脚)", "风暴/雷云"],
        ["逆光(从龙后)", "风暴光(紫黑云)"],
        ["暗紫+金(龙眼)", "灰+白(风暴)"],
        [
            {"shot": "wide shot", "reason": "山顶+巨龙+风暴, 宏大"},
            {"shot": "low angle", "reason": "仰望巨龙, 压倒性"},
            {"shot": "close up", "reason": "龙眼特写"},
        ],
        ["风暴中", "黎明前"],
        ["风暴", "雷云"],
        "mountain peak, dragon, storm clouds, lightning, epic battle, fantasy, scale",
        ["风暴的紫黑色程度"]
    ),
    
    # ══════════════════ 特殊情境 ══════════════════
    "雨中共享伞": SceneDB(
        "雨中共享伞", "特殊",
        ["暧昧","亲密","浪漫","偶然"],
        ["雨(中雨)", "一把伞(过小)", "积水", "街灯(反射)"],
        ["阴天漫射光", "霓虹夜+伞下暖"],
        ["灰蓝(雨)+暖(伞下光)"],
        [
            {"shot": "medium close", "reason": "两人挤在一把伞下, 近距离"},
            {"shot": "over shoulder", "reason": "从一人背后看另一人侧脸"},
            {"shot": "wide shot", "reason": "雨中街道, 只有一把伞"},
        ],
        ["傍晚", "夜"],
        ["雨"],
        "rain, shared umbrella, close together, wet street, reflection, puddle, intimacy",
        ["伞的颜色", "雨的大小"]
    ),
    "病床": SceneDB(
        "病房", "特殊",
        ["病弱","看望","孤独","康复"],
        ["病床", "点滴架", "窗帘(半开)", "窗外天气", "鲜花(探病)"],
        ["柔和的室内光", "窗外自然光", "逆光(窗)"],
        ["白+淡蓝(医院)", "暖(鲜花)+冷(整体)"],
        [
            {"shot": "medium shot", "reason": "床头, 看望视角"},
            {"shot": "point of view", "reason": "从病床看窗外/来人"},
            {"shot": "close up", "reason": "苍白的手/微笑"},
        ],
        ["白天", "黄昏"],
        ["晴", "雪"],
        "hospital room, bed, IV drip, window, flowers, get well, recovery, quiet",
        ["窗外天气"]
    ),
    "婚礼": SceneDB(
        "婚礼", "特殊",
        ["幸福","神圣","感动","承诺"],
        ["新娘(白婚纱)", "教堂/神社", "花瓣/彩纸", "家人朋友", "戒指"],
        ["教堂彩绘玻璃光", "黄金时间(户外)"],
        ["白+金+花色彩"],
        [
            {"shot": "wide shot", "reason": "教堂/会场全景"},
            {"shot": "close up", "reason": "交换戒指"},
            {"shot": "over shoulder", "reason": "从背后看新人"},
        ],
        ["上午", "黄昏"],
        ["晴"],
        "wedding, bride, white dress, church, flowers, ceremony, happiness, sacred",
        ["婚纱设计", "花种类"]
    ),
    "浴衣花火": SceneDB(
        "夏日花火", "特殊",
        ["夏日","青春","浪漫","回忆"],
        ["浴衣(两人)", "花火(夜空)", "提灯", "屋台", "人群(背景)"],
        ["花火五彩(上)+暖提灯(下)"],
        ["深蓝(夜空)+五彩(花火)+暖色(提灯)"],
        [
            {"shot": "wide shot", "reason": "花火+浴衣人物, 经典构图"},
            {"shot": "medium close", "reason": "花火反射在眼中"},
            {"shot": "silhouette", "reason": "花火下两人的背影"},
        ],
        ["夜晚(祭典)"],
        ["晴"],
        "summer festival, yukata, fireworks, night sky, lanterns, romantic, japanese summer",
        ["花火颜色分布", "浴衣花纹"]
    ),
}


# ════════════════════════════════════════════════════════════
# 场景组合分析
# ════════════════════════════════════════════════════════════

def analyze_scene(scene_name: str, mood: str = "", time: str = "") -> dict:
    """分析一个场景并返回完整的镜头参数"""
    scene = SCENES_DB.get(scene_name)
    if not scene:
        return {"found": False}
    
    lighting = scene.lighting_options[0] if scene.lighting_options else "natural"
    color = scene.color_palette[0] if scene.color_palette else "natural"
    camera = scene.camera_suggestions[0] if scene.camera_suggestions else {"shot": "medium shot"}
    
    # 根据情绪微调
    if mood in ["伤感", "孤独"] and len(scene.lighting_options) > 1:
        lighting = scene.lighting_options[1]
    if mood in ["浪漫", "幸福"]:
        lighting = "黄金时间" if "黄金时间" in scene.lighting_options else scene.lighting_options[0]
    
    return {
        "found": True,
        "name": scene_name,
        "category": scene.category,
        "mood": mood or scene.mood[0],
        "key_elements": scene.key_elements,
        "recommended_lighting": lighting,
        "color_palette": color,
        "camera": {"shot": camera["shot"], "reason": camera["reason"]},
        "prompt_base": scene.prompt_tags,
        "continuity_keys": scene.continuity_elements,
    }


def scene_continuity_plan(scene_name: str, panel_count: int) -> list[dict]:
    """
    生成跨分镜的背景连续性方案
    
    同一场景的 N 个分镜:
      - 共享相同的背景prompt基础
      - 每个分镜只有视角/光线细微变化
      - 关键元素保持不变 (continuity_elements)
    """
    scene = SCENES_DB.get(scene_name)
    if not scene:
        return []
    
    plans = []
    shots = scene.camera_suggestions
    
    for i in range(panel_count):
        camera = shots[i % len(shots)]
        variation = f"same scene, {camera['shot']} view, {camera['reason']}"
        plans.append({
            "panel": i + 1,
            "scene": scene_name,
            "camera": camera["shot"],
            "variation_prompt": variation,
            "shared_base": scene.prompt_tags,
            "keep_consistent": scene.continuity_elements,
        })
    
    return plans


# ════════════════════════════════════════════════════════════
# 背景合成提示词
# ════════════════════════════════════════════════════════════

def build_background_prompt(scene_name: str, mood: str = "", time: str = "", weather: str = "") -> str:
    """从场景数据库构建完整的背景提示词"""
    scene = SCENES_DB.get(scene_name)
    if not scene:
        return scene_name
    
    prompt = scene.prompt_tags
    replacements = {}
    
    if time:
        replacements["{time}"] = time
    if weather:
        prompt += f", {weather}"
    if mood:
        prompt += f", {mood} mood"
    
    # 替换时间占位符
    if "{time}" in prompt:
        prompt = prompt.replace("{time}", time or scene.time_of_day[0] if scene.time_of_day else "day")
    
    return prompt


def build_full_prompt(character_prompt: str, scene_name: str, 
                      mood: str = "", camera: str = "medium shot") -> str:
    """合成角色+场景的完整提示词"""
    bg = build_background_prompt(scene_name, mood)
    return f"{character_prompt}, {bg}, {camera}, masterpiece, best quality, highres"


if __name__ == "__main__":
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║         深度背景知识体系 v1.0                                ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    
    print(f"""
📊 内容统计:
   景别:     {len(CAMERA_SHOTS)} 种 (含超远景→超特写/双人镜/过肩/主观视角/斜角...)
   角度:     {len(CAMERA_ANGLES)} 种 (平视/低/高/仰/俯/荷兰/顶)
   光线:     {len(LIGHTING_SETUPS)} 种 (黄金时间/蓝色时刻/逆光/霓虹夜/月光/伦勃朗光...)
   色调:     {len(COLOR_GRADING)} 种 (夏日限定/赛博朋克/昭和怀旧/森系/浮世绘风...)
   深度场景: {len(SCENES_DB)} 种 (含校园/都市/自然/幻想/特殊五大类别)
""")
    
    print("🔍 场景分析: 樱花树道(浪漫)")
    analysis = analyze_scene("樱花树道(春季)", "浪漫")
    if analysis["found"]:
        for k, v in analysis.items():
            if k != "found":
                print(f"  {k}: {v}")
    
    print("\n🔍 跨镜连续性方案: 教室(窗边) × 3镜")
    plans = scene_continuity_plan("教室(窗边)", 3)
    for p in plans:
        print(f"  镜{p['panel']}: {p['camera']} — {p['keep_consistent']}")
        print(f"    → {p['variation_prompt'][:70]}")
    
    print("\n🔍 完整合成提示词:")
    prompt = build_full_prompt(
        "1girl, long black hair, violet eyes, school uniform",
        "教室(窗边)", mood="青春", camera="medium shot"
    )
    print(f"  {prompt}")
    
    print("\n🔍 跨情绪场景变化: 同一个场景不同情绪")
    for mood in ["青春", "孤独", "回忆"]:
        p = build_background_prompt("教室(窗边)", mood, "夕"),
        print(f"  {mood}: {p[0]}")
