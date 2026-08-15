#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/wardrobe.py — 衣品知识库（B-wardrobe）v1.0
====================================================
解决"衣服丑"：服装描述太笼统 → SDXL 只能给通用款。
衣品词库：风格 × 款式/剪裁/材质/装饰/配色/鞋袜配套 的完整英文设计描述。

用法:
  python -m agents workshop wardrobe list                # 列出风格
  python -m agents workshop wardrobe show <风格>          # 查看风格模板
  python -m agents workshop wardrobe build <风格> [--color 配色]  # 生成完整英文服装描述
"""

import argparse, json, sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent

# ── 服装风格库（款式+剪裁+材质+装饰+鞋袜配套）──
WARDROBE_STYLES = {
    "gothic": {
        "desc": "哥特（暗黑优雅）",
        "outfit": "black gothic dress, corset waistline, high collar with lace trim, long flowing skirt with layered ruffles, sheer lace sleeves, silver cross pendant, dark romantic",
        "shoes": "black platform boots, silver buckles, lace-up detail",
        "socks": "black sheer stockings, gothic lace pattern",
        "palette": ["black", "deep purple", "blood red", "silver"],
    },
    "lolita": {
        "desc": "洛丽塔（甜系蓬裙）",
        "outfit": "sweet lolita dress, puffed short sleeves, high-waist A-line skirt with petticoat, ribbon bow at chest, lace hem, pastel frills, head bow",
        "shoes": "white mary jane shoes, round toe, small heel",
        "socks": "white knee-high socks, lace trim top",
        "palette": ["white", "pink", "baby blue", "cream"],
    },
    "wafuku": {
        "desc": "和风（振袖/浴衣）",
        "outfit": "traditional japanese kimono, long flowing sleeves (furisode), silk fabric with floral pattern, obi sash with decorative knot, layered collar",
        "shoes": "traditional zori sandals, white tabi socks",
        "socks": "white tabi socks, split toe",
        "palette": ["crimson", "gold", "indigo", "sakura pink"],
    },
    "hanfu": {
        "desc": "汉服（襦裙/齐胸）",
        "outfit": "chinese hanfu, cross-collar ruqun, flowing floor-length skirt, wide sleeves, embroidered cloud pattern, silk ribbon sash, jade pendant",
        "shoes": "embroidered cloth shoes, soft sole",
        "socks": "plain white socks",
        "palette": ["celadon green", "apricot", "ink black", "vermilion"],
    },
    "military": {
        "desc": "军装（制服）",
        "outfit": "military uniform jacket, double-breasted with brass buttons, epaulettes, high collar, belted waist, riding pants, officer cap, peaked",
        "shoes": "black leather combat boots, polished",
        "socks": "black wool socks",
        "palette": ["olive drab", "navy", "black", "brass gold"],
    },
    "office": {
        "desc": "职场（OL 西装）",
        "outfit": "elegant office suit, fitted blazer with single button, white silk blouse, pencil skirt above knee, tailored waist, minimalist",
        "shoes": "black stiletto heels, pointed toe, 8cm",
        "socks": "nude sheer pantyhose",
        "palette": ["charcoal", "beige", "white", "navy"],
    },
    "school": {
        "desc": "校服（水手/西式）",
        "outfit": "sailor school uniform, white blouse with sailor collar and red neckerchief, pleated navy skirt, ribbon tie, button cardigan optional",
        "shoes": "brown loafers, white ankle socks",
        "socks": "white ankle socks, folded cuff",
        "palette": ["navy", "white", "red", "grey"],
    },
    "swim": {
        "desc": "泳装（海边）",
        "outfit": "stylish bikini with trendy cut, delicate straps, subtle texture, sarong wrap optional, beach style",
        "shoes": "barefoot or strappy sandals",
        "socks": "none",
        "palette": ["coral", "teal", "white", "sunset orange"],
    },
    "casual": {
        "desc": "日常休闲",
        "outfit": "relaxed streetwear, oversized graphic tee tucked at front, high-waist mom jeans, cropped hoodie layer, sneakers, effortless cool",
        "shoes": "white chunky sneakers",
        "socks": "visible crew socks, contrasting color",
        "palette": ["cream", "denim blue", "black", "olive"],
    },
    "cyber": {
        "desc": "未来机能",
        "outfit": "cyberpunk bodysuit, high-tech fabric with panel lines, neon accent strips, asymmetrical zipper, techwear harness, holographic details, futuristic",
        "shoes": "neon-accent tech boots, chunky sole",
        "socks": "mesh cyber socks",
        "palette": ["black", "neon cyan", "magenta", "gunmetal"],
    },
    "fantasy": {
        "desc": "幻想铠甲",
        "outfit": "fantasy battle armor, ornate breastplate with gold filigree, pauldrons, flowing cape, leather waist belt, metal greaves, heroic fantasy",
        "shoes": "leather armored boots, metal toe",
        "socks": "dark cloth wrappings",
        "palette": ["steel", "gold", "crimson", "dark leather"],
    },
    "qipao": {
        "desc": "旗袍（修身）",
        "outfit": "elegant chinese qipao, figure-hugging silhouette, mandarin collar, frog buttons, high side slit, satin fabric with subtle floral embroidery",
        "shoes": "delicate heeled shoes, embroidered",
        "socks": "none (bare legs) or sheer stockings",
        "palette": ["emerald", "gold", "crimson", "jade"],
    },
    "arknight": {
        "desc": "方舟风（复杂绑带设计）",
        "outfit": "arknights-style tactical outfit, intricate strap harness across chest and thighs, layered asymmetrical coat over bodysuit, decorative belts and buckles, metal armor plates on shoulders, high collar with visor, mechanical details, excessive decorative straps, complex multi-layer design, military chic",
        "shoes": "heavy tactical boots, metal buckles, reinforced",
        "socks": "black thigh-high stockings with strap garter",
        "palette": ["charcoal", "white", "accent red", "gold trim"],
    },
}

# ── 衣装变体（穿/不穿双版本）──
OUTFIT_VARIANTS = {
    "full": "",  # 完整着装
    "swim": ", bikini swimsuit, stylish cut, beachwear, revealing but tasteful",  # 泳装版
    "lingerie": ", elegant lingerie set, lace details, matching bra and panties, adult woman, suggestive but classy",  # 内衣版
    "artistic": ", artistic nude figure study, elegant pose, proper anatomy, soft lighting, fine art style, tasteful",  # 艺术人体版
}

# ── 子部件词库（身材/脸/眼睛/发型/鞋袜细节）──
BODY_PARTS = {
    "body": {
        "petite": "petite slim build, small frame",
        "curvy": "curvy hourglass figure, full bust, narrow waist, wide hips",
        "slim": "slim athletic figure, long legs",
        "tall": "tall elegant stature, model-like proportions",
        "muscular": "toned muscular build, defined shoulders",
    },
    "face": {
        "oval": "oval face shape, soft features",
        "round": "round face shape, youthful cheeks",
        "pointed": "pointed chin, sharp jawline, elegant",
        "baby": "baby face, large forehead, innocent look",
        "mature": "mature elegant face, high cheekbones",
    },
    "eyes": {
        "almond": "almond-shaped eyes, gentle gaze",
        "round": "large round eyes, sparkling highlights",
        "upturned": "upturned fox eyes, sharp gaze",
        "downturned": "downturned puppy eyes, soft look",
        "narrow": "narrow slit eyes, calm cold gaze",
        "detail": "detailed iris, catchlight reflection, long eyelashes, defined eyeliner",
    },
    "hair": {
        "long": "very long flowing hair, waist-length",
        "medium": "medium-length hair, shoulder-length",
        "short": "short bob cut, neat",
        "straight": "straight silky hair, smooth shine",
        "wavy": "soft wavy hair, natural volume",
        "curly": "curly voluminous hair, bouncy",
        "twintails": "twin tails, high pigtails with ribbons",
        "ponytail": "high ponytail, flowing",
        "bun": "elegant bun with hairpin",
        "detail": "detailed hair strands, gradient hair coloring, hair highlights, soft shine",
    },
    "shoes": {
        "heels": "stiletto heels, elegant",
        "boots": "knee-high boots, sleek",
        "sneakers": "clean white sneakers, casual",
        "sandals": "strappy sandals, summer",
        "loafers": "polished loafers, preppy",
        "detail": "detailed shoe design, glossy finish, brand-less clean design",
    },
    "socks": {
        "thighhigh": "thigh-high stockings, snug fit",
        "kneehigh": "knee-high socks, folded top",
        "ankle": "ankle socks, sporty",
        "pantyhose": "sheer pantyhose, natural tone",
        "fishnet": "fishnet stockings, edgy",
        "detail": "detailed knit texture, lace trim, elastic band detail",
    },
    # ── 人体层（不穿衣服的基本功——结构正确不崩坏）──
    "figure": {
        "proportion": "well-proportioned figure, correct head-to-body ratio, balanced silhouette",
        "bones": "visible collarbones, defined waist, natural joint articulation",
        "muscle": "subtle muscle definition, smooth curves, natural anatomy",
        "skin": "smooth skin with soft sheen, subtle blush tone, natural highlights",
        "artistic": "artistic nude study, elegant classical pose, fine art quality, correct anatomy",
        "detail": "natural body contours, graceful lines, realistic shading on skin",
    },
    # ── 姿势层（怎么摆）──
    "pose": {
        "standing": "standing pose, natural weight distribution, relaxed",
        "sitting": "sitting pose, elegant posture, legs together",
        "walking": "walking pose, dynamic stride, motion",
        "fighting": "fighting stance, ready pose, dynamic tension",
        "lying": "lying pose, relaxed, graceful line",
        "dancing": "dancing pose, flowing movement, graceful",
    },
    # ── 手部细节（人物细节关键：手崩坏是 SDXL 硬伤）──
    "hand": {
        "natural": "natural hand positions, relaxed fingers, anatomically correct hands",
        "gesture": "expressive hand gesture, elegant finger positioning",
        "holding": "holding item naturally, proper grip, fingers wrapping naturally",
        "clasped": "hands clasped together, delicate interlocked fingers",
        "detail": "detailed hands, natural finger positions, expressive gestures, five fingers clearly",
    },
}

# ── 配饰词库（B4：首饰/挂件/武器挂载/头饰）──
ACCESSORIES = {
    "jewelry": "delicate silver jewelry, pendant necklace, earrings, rings",
    "headwear": "decorative headdress, hair ornaments, tiara, hairpins",
    "weapon": "weapon holster, thigh strap for weapon, combat gear attachment",
    "bag": "elegant handbag, crossbody strap bag",
    "tech": "tech accessories, earpiece, wrist computer, glowing devices",
    "magic": "magic accessories, floating crystals, rune charms, mystic ornaments",
    "detail": "detailed accessory design, polished metal finish, gemstone sparkle",
}

# ── 异质特征词库（A5：种族特征——方舟系）──
RACIAL_FEATURES = {
    "animal_ears": "animal ears, cat ears, expressive ear movement",
    "horns": "elegant curved horns, dark horn color, ornate horn details",
    "wings": "large feathered wings, folded wings, angelic wings",
    "tail": "long tail, fluffy tail, expressive tail",
    "scales": "subtle scales on skin, reptilian features, iridescent scales",
    "halo": "floating halo, glowing halo, angelic ring",
    "fangs": "small fangs, sharp canines, cute fang",
    "elf": "pointed elf ears, long elegant ears",
    "detail": "detailed racial features, natural integration with character design",
}

# ── 光影词库（F：氛围光/轮廓光/逆光/体积光）──
LIGHTING_STYLES = {
    "rim": "rim lighting, golden rim light on edges, dramatic silhouette",
    "backlight": "backlit scene, soft glow behind character, halo effect",
    "volumetric": "volumetric light rays, god rays through atmosphere, dust particles",
    "moody": "moody low-key lighting, deep shadows, cinematic contrast",
    "warm": "warm golden hour light, cozy atmosphere, orange glow",
    "cool": "cool moonlight, blue tones, night atmosphere, silver highlights",
    "neon": "neon light glow, cyberpunk color lighting, vibrant reflections",
    "studio": "studio softbox lighting, even illumination, professional look",
    "detail": "natural light direction consistency, soft shadow falloff, realistic highlights",
}

# ── 点睛裸露设计词库（制服与身体的对比——好看+够烧的关键）──
APPEAL_ACCENTS = {
    "slit": "high side slit on dress, revealing leg line, elegant",
    "thigh_strap": "thigh strap garter, leg harness detail, accent",
    "waist_chain": "decorative waist chain, dangling hip chain, accent",
    "off_shoulder": "off-shoulder top, showing collarbone and shoulders, elegant",
    "backless": "backless design, elegant exposed back, curve accent",
    "cropped": "cropped top, showing midriff, youthful sexy",
    "stocking_line": "visible stocking top line, thigh-high contrast, accent",
    "tight_fit": "form-fitting silhouette, hugging curves, bodycon design",
    "sheer_panel": "sheer fabric panels, see-through accents, suggestive",
    "wet_look": "wet look clothing, clinging to body, water glistening",
    "detail": "strategic exposure design, balance of covered and revealed, tasteful allure",
}

# ── 记忆点/概念锚词库（角色一眼认出的独特征象）──
MEMORY_POINTS = {
    "silhouette": "unique silhouette, distinctive outline, recognizable shape",
    "color_anchor": "signature color scheme, one dominant anchor color",
    "symbol": "signature symbol, iconic emblem, recognizable mark",
    "hair_sign": "signature hairstyle, iconic hair shape, instantly recognizable",
    "weapon": "signature weapon, iconic weapon design, memorable",
    "accessory": "signature accessory, unique item, memorable prop",
    "animal": "signature animal companion, iconic pet, recognizable",
    "detail": "distinctive design details, memorable accents, unique features",
}

# ── 世界观锚词库（服装与背景绑定）──
WORLDVIEW_ANCHORS = {
    "fantasy": "fantasy world, magical elements, enchanted atmosphere",
    "military": "military world, disciplined uniform, rank insignia",
    "sci-fi": "sci-fi world, futuristic tech, advanced civilization",
    "school": "school world, academy setting, student life",
    "ancient": "ancient world, traditional culture, historical atmosphere",
    "modern": "modern world, contemporary fashion, urban life",
    "postapoc": "post-apocalyptic world, survival gear, worn aesthetic",
    "myth": "mythological world, legendary beings, divine atmosphere",
    "detail": "worldview-consistent design, outfit matches world lore",
}

IP_STYLES = {
    "原神": "genshin-inspired fantasy outfit, elemental motifs, regional cultural fusion design, detailed trims",
    "鸣潮": "wuthering waves style, post-apocalyptic techwear, flowing fabric with holographic accents",
    "未来战": "counter-side style, korean sci-fi military uniform, sleek futuristic lines",
    "怪物猎人": "monster hunter armor set, beast hide and scale armor, layered hunter gear, claw ornaments",
    "碧蓝幻想": "granblue fantasy style, grand fantasy armor, ornate knight design, jeweled details",
    "近月少女的礼仪": "noble academy uniform, deep navy blazer, pleated skirt, refined elegance, perfect maid uniform, fashion designer aesthetic",
    "影之实力者": "shadow garden style, dark noble assassin outfit, black and silver, elegant cloak, mage knight academy uniform",
    "回复术士": "redo of healer style, dark fantasy adventurer gear, practical yet stylish",
    "柚子社": "yuzusoft style, clean modern school uniform, soft pastel accents, everyday casual elegance",
    "泰坦陨落2": "titanfall pilot suit, tactical jumpsuit with armored plates, sci-fi military, insignia patches",
    "转生史莱姆": "that time i got reincarnated style, isekai noble outfit, fantasy formalwear with magic accents",
    "天才王子": "genius prince style, medieval royal outfit, rich velvet, gold embroidery, regal cape",
    "叹息的亡灵": "tale of the heartless style, adventurer leather gear, bandolier, practical fantasy outfit",
    "魔女之旅": "wandering witch style, black witch dress, wide-brim witch hat, crescent moon motifs, dark fantasy",
    "影之诗": "shadowverse style, card game fantasy outfit, ethereal magical design, glowing runes",
    "世界顶尖暗杀者": "world's finest assassin style, sleek black assassin outfit, hidden weapon straps, tactical elegance",
    "少女前线": "girls frontline style, tactical military uniform, modular gear, gun accessories, military chic",
    "碧蓝航线": "azur lane style, naval military uniform, sailor suit with ship motifs, elegant military fashion",
    "战舰少女": "warship girls style, naval dress uniform, nautical details, white and navy, costume variants (maid outfit etc)",
    "战双帕弥什": "punishing gray raven style, post-apocalyptic combat suit, mechanical exoskeleton, dark tech",
    "OVERLORD": "overlord style, dark fantasy royal armor, bone and black gold motifs, menacing elegance",
    "命运石之门": "steins gate style, casual lab coat, modern everyday outfit, subtle tech accessories",
    "魔鬼恋人": "diabolik lovers style, dark vampire noble outfit, crimson and black, gothic aristocracy",
    "约会大作战": "date a live style, spirit astral dress (灵装 - unique named armor per spirit), ethereal luminous battle dress, floating light fabric, angelic weapon motifs",
    "崩坏三": "honkai impact style, sci-fi battlesuit, futuristic combat armor, high-tech details",
    "最终幻想": "final fantasy style, iconic fantasy outfit, dramatic silhouette, class-based design",
    "实况主的逃脱游戏": "escape game style, kimono with wooden clogs and mask character, doctor lab coat over uniform, playful contrasting designs",
    "实教": "classroom of the elite style, elite academy uniform, white blazer, refined modern",
    "海王星": "neptunia style, game goddess outfit, colorful digital fantasy, playful armor",
    "碧蓝之海": "grand blue style, diving gear and swimwear, beach casual, sporty",
    "战女神": "eushully style, fantasy war goddess armor, divine white and gold, layered battle dress",
    "反转练习生": "reversal trainee style, idol stage outfit, glittering performance wear, showy design",
    "进击的巨人": "attack on titan style, survey corps uniform, brown jacket with hood, vertical maneuvering gear straps",
    "RE0": "re zero style, isekai fantasy outfit, elegant maid uniform and knight design, lace maid apron, noble fantasy clothing",
    "Fate": "fate style, mage and servant battle outfit, heroic armor, mythical elegance, command seal motifs",
    "斗罗大陆": "soul land style, chinese fantasy cultivation outfit, spirit soul motifs, flowing battle robes",
}



def build_outfit(style, color=None, mix=None, variant='full', ip=None):
    """风格 → 完整英文服装描述（支持混搭 + 双版本 + IP 风格锚）。

    Args:
        style: 主风格名
        color: 自定义配色
        mix: 混搭风格名或列表
        variant: full/swim/lingerie/artistic
        ip: IP 参考风格（如 '原神'/'少女前线'——注入作品服装设计特征）

    Returns:
        完整英文服装描述
    """
    if style not in WARDROBE_STYLES:
        raise ValueError(f'未知风格: {style}（可用: {list(WARDROBE_STYLES.keys())}）')
    if variant not in OUTFIT_VARIANTS:
        raise ValueError(f'未知变体: {variant}（可用: {list(OUTFIT_VARIANTS.keys())}）')
    if ip and ip not in IP_STYLES:
        raise ValueError(f'未知 IP: {ip}（可用: {list(IP_STYLES.keys())}）')
    tpl = WARDROBE_STYLES[style]
    # 变体替换主服装（泳装版=泳装不是"战术装+泳装"）
    if variant == 'full':
        parts = [tpl['outfit']]
    else:
        parts = [OUTFIT_VARIANTS[variant].lstrip(', ')]
        # 保留风格精髓：主服装的核心元素作为风格锚（仅保留首元素）
        parts.append(f'{style} style hint: {tpl["outfit"].split(",")[0].strip()}')

    # 混搭：追加混搭风格的服装元素（设计融合）
    mixes = mix if isinstance(mix, (list, tuple)) else ([mix] if mix else [])
    for m in mixes:
        if m not in WARDROBE_STYLES:
            raise ValueError(f'未知混搭风格: {m}（可用: {list(WARDROBE_STYLES.keys())}）')
        mt = WARDROBE_STYLES[m]
        parts.append(f'{m} style elements: {mt["outfit"].split(",")[0].strip()}')
        if mt.get('shoes') and 'shoes' not in parts:
            parts.append(mt['shoes'])

    # IP 风格锚注入（参考作品服装设计特征）
    if ip:
        parts.append(IP_STYLES[ip])

    # 变体不是 full 时鞋袜可简化（泳装/内衣/艺术版不穿鞋袜）
    if variant == 'full':
        if tpl.get('shoes'):
            parts.append(tpl['shoes'])
        if tpl.get('socks'):
            parts.append(tpl['socks'])
    if color:
        parts.append(color)
    else:
        palette = tpl.get('palette', [])
        if palette:
            parts.append(f'color scheme: {" ".join(palette)}')
    return ', '.join(parts)


def build_body_parts(**kwargs):
    """子部件 → 完整描述（身材/脸/眼睛/发型/鞋袜）。"""
    parts = []
    for key, val in kwargs.items():
        if not val:
            continue
        if key == 'body_detail' and val in BODY_PARTS['body']:
            parts.append(BODY_PARTS['body'][val])
        elif key == 'face_shape' and val in BODY_PARTS['face']:
            parts.append(BODY_PARTS['face'][val])
        elif key == 'eye_style' and val in BODY_PARTS['eyes']:
            parts.append(BODY_PARTS['eyes'][val])
        elif key == 'hair_style' and val in BODY_PARTS['hair']:
            parts.append(BODY_PARTS['hair'][val])
        elif key == 'shoes_style' and val in BODY_PARTS['shoes']:
            parts.append(BODY_PARTS['shoes'][val])
        elif key == 'socks_style' and val in BODY_PARTS['socks']:
            parts.append(BODY_PARTS['socks'][val])
        elif key == 'figure_style' and val in BODY_PARTS['figure']:
            parts.append(BODY_PARTS['figure'][val])
        elif key == 'pose_style' and val in BODY_PARTS['pose']:
            parts.append(BODY_PARTS['pose'][val])
        elif key == 'hand_style' and val in BODY_PARTS['hand']:
            parts.append(BODY_PARTS['hand'][val])
        elif key == 'accessory' and val in ACCESSORIES:
            parts.append(ACCESSORIES[val])
        elif key == 'racial' and val in RACIAL_FEATURES:
            parts.append(RACIAL_FEATURES[val])
        elif key == 'lighting' and val in LIGHTING_STYLES:
            parts.append(LIGHTING_STYLES[val])
        elif key == 'accent' and val in APPEAL_ACCENTS:
            parts.append(APPEAL_ACCENTS[val])
        elif key == 'memory' and val in MEMORY_POINTS:
            parts.append(MEMORY_POINTS[val])
        elif key == 'worldview' and val in WORLDVIEW_ANCHORS:
            parts.append(WORLDVIEW_ANCHORS[val])
        elif key in ('accent_detail', 'memory_detail', 'worldview_detail') and val:
            _dk = {'accent_detail': 'detail', 'memory_detail': 'detail',
                   'worldview_detail': 'detail'}[key]
            _base = {'accent_detail': APPEAL_ACCENTS, 'memory_detail': MEMORY_POINTS,
                     'worldview_detail': WORLDVIEW_ANCHORS}[key]
            if _dk in _base:
                parts.append(_base[_dk])
        elif key in ('accessory_detail', 'racial_detail', 'lighting_detail') and val:
            _dk = {'accessory_detail': 'detail', 'racial_detail': 'detail',
                   'lighting_detail': 'detail'}[key]
            _base = {'accessory_detail': ACCESSORIES, 'racial_detail': RACIAL_FEATURES,
                     'lighting_detail': LIGHTING_STYLES}[key]
            if _dk in _base:
                parts.append(_base[_dk])
        elif key in ('eye_detail', 'hair_detail', 'shoes_detail', 'socks_detail') and val:
            detail_key = {'eye_detail': 'eyes', 'hair_detail': 'hair',
                          'shoes_detail': 'shoes', 'socks_detail': 'socks'}[key]
            if detail_key in BODY_PARTS and 'detail' in BODY_PARTS[detail_key]:
                parts.append(BODY_PARTS[detail_key]['detail'])
    return ', '.join(p for p in parts if p)


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop wardrobe', description='衣品知识库（风格服装+子部件词库）')
    sub = ap.add_subparsers(dest='cmd', required=True)

    sub.add_parser('list', help='列出风格')
    p_show = sub.add_parser('show', help='查看风格模板')
    p_show.add_argument('style')
    p_build = sub.add_parser('build', help='生成完整英文服装描述')
    p_build.add_argument('style')
    p_build.add_argument('--color', default=None, help='配色（如 "white and gold"）')
    p_build.add_argument('--mix', default=None, help='混搭风格（逗号分隔: cyber,military——异世界/ARPG 组合）')
    p_build.add_argument('--variant', default='full', choices=list(OUTFIT_VARIANTS.keys()),
                         help='衣装变体: full/swim/lingerie/artistic（穿/不穿双版本）')
    p_build.add_argument('--ip', default=None,
                         help='IP 参考风格（原神/少女前线/碧蓝航线等——注入作品服装特征）')
    p_body = sub.add_parser('body', help='子部件词库')
    p_body.add_argument('--body', default=None, help='身材: petite/curvy/slim/tall/muscular')
    p_body.add_argument('--face', default=None, help='脸型: oval/round/pointed/baby/mature')
    p_body.add_argument('--eyes', default=None, help='眼型: almond/round/upturned/downturned/narrow')
    p_body.add_argument('--hair', default=None, help='发型: long/medium/short/straight/wavy/curly/twintails/ponytail/bun')
    p_body.add_argument('--shoes', default=None, help='鞋: heels/boots/sneakers/sandals/loafers')
    p_body.add_argument('--socks', default=None, help='袜: thighhigh/kneehigh/ankle/pantyhose/fishnet')
    p_body.add_argument('--figure', default=None, help='人体: proportion/bones/muscle/skin/artistic')
    p_body.add_argument('--pose', default=None, help='姿势: standing/sitting/walking/fighting/lying/dancing')
    p_body.add_argument('--hand', default=None, help='手部: natural/gesture/holding/clasped/detail')
    p_body.add_argument('--accessory', default=None, help='配饰: jewelry/headwear/weapon/bag/tech/magic')
    p_body.add_argument('--racial', default=None, help='异质特征: animal_ears/horns/wings/tail/scales/halo/fangs/elf')
    p_body.add_argument('--lighting', default=None, help='光影: rim/backlight/volumetric/moody/warm/cool/neon/studio')
    p_body.add_argument('--accent', default=None, help='点睛裸露: slit/thigh_strap/waist_chain/off_shoulder/backless/cropped/stocking_line/tight_fit/sheer_panel/wet_look')
    p_body.add_argument('--memory', default=None, help='记忆点: silhouette/color_anchor/symbol/hair_sign/weapon/accessory/animal')
    p_body.add_argument('--worldview', default=None, help='世界观: fantasy/military/sci-fi/school/ancient/modern/postapoc/myth')
    p_body.add_argument('--detail', action='store_true', help='加细节描述（眼神光/发丝高光等）')

    args = ap.parse_args(argv)

    try:
        if args.cmd == 'list':
            print(f'\n👗 衣品风格库（{len(WARDROBE_STYLES)} 类）:')
            for k, v in WARDROBE_STYLES.items():
                print(f'  {k}: {v["desc"]}')
            print(f'\n📺 IP 参考风格库（{len(IP_STYLES)} 个作品）:')
            print(f'  {" / ".join(IP_STYLES.keys())}')
            print(f'\n🧩 子部件词库: {list(BODY_PARTS.keys())}')
        elif args.cmd == 'show':
            if args.style not in WARDROBE_STYLES:
                raise ValueError(f'未知风格: {args.style}（可用: {list(WARDROBE_STYLES.keys())}）')
            tpl = WARDROBE_STYLES[args.style]
            print(f'\n👗 {args.style}（{tpl["desc"]}）')
            print(f'  服装: {tpl["outfit"]}')
            print(f'  鞋: {tpl.get("shoes", "无")}')
            print(f'  袜: {tpl.get("socks", "无")}')
            print(f'  配色: {", ".join(tpl.get("palette", []))}')
        elif args.cmd == 'build':
            mixes = [m.strip() for m in args.mix.split(',')] if args.mix else None
            print(build_outfit(args.style, args.color, mix=mixes, variant=args.variant,
                               ip=args.ip))
        elif args.cmd == 'body':
            print(build_body_parts(
                body_detail=args.body, face_shape=args.face, eye_style=args.eyes,
                hair_style=args.hair, shoes_style=args.shoes, socks_style=args.socks,
                figure_style=args.figure, pose_style=args.pose, hand_style=args.hand,
                accessory=args.accessory, racial=args.racial, lighting=args.lighting,
                accent=args.accent, memory=args.memory, worldview=args.worldview,
                accent_detail=args.detail, memory_detail=args.detail,
                worldview_detail=args.detail,
                accessory_detail=args.detail, racial_detail=args.detail,
                lighting_detail=args.detail,
                eye_detail=args.detail, hair_detail=args.detail,
                shoes_detail=args.detail, socks_detail=args.detail))
        return 0
    except Exception as e:
        print(f'❌ wardrobe 失败: {str(e)[:150]}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
