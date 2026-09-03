# 商业插画叙事场景词库 v2（2026-08-17 强化版）
# v1 问题（VLM 三方评审一致）：构图呆板居中、光影扁平、背景空洞 → 商业感不足
# v2 强化：① 构图：off-center + 前景元素 + 明确角度 ② 光影：volumetric/dramatic/强轮廓光
#         ③ 背景：具体场景细节词（非"detailed background"空泛词）
# 底子：NoobAI + style_cine_manga(mystyle)，由 run_commercial_scenes/commercial_flow 拼接

BASE = "1girl, short black hair, Chinese high school girl, school uniform"

SCENES = {
    # ① 夕阳天桥——v3：构图非居中 + 光影强化 + 背景细节（VLM 评审修正）
    "sunset_bridge": {
        "prompt": (
            "looking back over shoulder, skirt blowing in wind, "
            "after-school city bridge at golden hour, "
            "low angle looking up, off-center composition, subject on right side, "
            "strong golden backlight, dramatic rim light on hair and shoulders, "
            "volumetric sun rays through bridge structure, "
            "foreground petals out of focus, "
            "detailed bridge railing, city skyline and telephone wires in background, "
            "warm atmosphere, cinematic depth"
        ),
        "desc": "放学天桥·黄昏逆光·仰拍",
    },
    # ② 教室窗边——v3：高马尾 + 构图非居中 + 教室细节（VLM 评审修正）
    "classroom_window": {
        "prompt": (
            "high ponytail, sitting by classroom window, holding book, "
            "looking out thoughtfully, "
            "morning sunlight streaming through window, "
            "volumetric light beam, floating dust particles, "
            "detailed classroom interior, wooden desks, blackboard, chalk dust, "
            "autumn leaves and window glass reflection outside, "
            "three-quarter view, off-center composition, subject on left side, "
            "warm tones, shallow depth of field, cinematic depth"
        ),
        "desc": "教室窗边·高马尾·晨光尘埃",
    },
    # ③ 樱花道——短发+侧辫（用户指定：靠近耳朵前侧的小辫子）
    # v7：NoobAI 是 danbooru 训练，(side braid:1.4) 加权标签 + 放最前防稀释
    "cherry_blossom": {
        "prompt": (
            "(short hair:1.3), (side braid:1.4), black hair, "
            "solo, upper body, facing viewer, gentle smile, "
            "cherry blossoms in background, spring morning, "
            "soft backlight through cherry trees, sun rays through branches, "
            "foreground petals out of focus, bokeh, "
            "dreamy atmosphere, off-center composition, cinematic depth"
        ),
        "desc": "樱花道·侧辫·晨光樱林",
    },
}
