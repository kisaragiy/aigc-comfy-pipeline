#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/emotes.py — 角色表情包/差分批量生成（B-emote）v1.0
============================================================
B站二创刚需：同一角色多表情批量（高兴/生气/哭泣/惊讶/害羞...）。
核心：角色描述固定 + 表情变化 → 批量出图，角色一致性靠 prompt 锚定。

用法:
  python -m agents workshop emotes "角色描述" [--emotes "高兴,生气,哭泣"]
      [--count 1] [--name 角色名] [--output 目录]
"""

import argparse, json, os, re, sys, time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent

# 默认表情库（B站二创高频）
DEFAULT_EMOTES = ["高兴", "生气", "哭泣", "惊讶", "害羞", "微笑"]

# 表情 → 英文 prompt 映射（SDXL 理解中文差，必须英文）
EMOTE_MAP = {
    # ── 基础（casual 日常向）──
    "高兴": "happy, big smile, joyful expression, sparkling eyes, cheerful",
    "生气": "angry, pouting, furrowed brows, flushed cheeks, tsundere angry",
    "哭泣": "crying, teary eyes, tears streaming, sad expression, pouting",
    "惊讶": "surprised, wide eyes, open mouth, shocked expression, hands on cheeks",
    "害羞": "embarrassed, blushing, shy expression, averting gaze, red cheeks",
    "微笑": "gentle smile, soft expression, warm eyes, calm and composed",
    "无语": "speechless, deadpan, flat expression, unamused, blank stare",
    "得意": "smug, confident smirk, raised eyebrow, proud expression",
    "困": "sleepy, half-closed eyes, yawning, tired expression, drowsy",
    "认真": "focused, serious expression, determined eyes, concentrated",
    "委屈": "wronged, teary eyes, trembling lip, pouting, hurt expression",
    "坏笑": "mischievous grin, sly smile, playful expression, raised eyebrow",
    # ── galgame 差分（视觉小说标准差分体系）──
    "心动": "lovestruck, heart-shaped pupils, dreamy eyes, gentle blush, smitten",
    "脸红": "deep blush, red cheeks, flustered, embarrassed smile, averting eyes",
    "流泪": "tears welling up, glossy eyes, emotional, trembling lips, touched",
    "黑化": "dark expression, shadowed eyes, ominous smile, menacing aura, yandere",
    "嫌弃": "disgusted, wrinkled nose, unimpressed stare, turned away, eww",
    "吃醋": "jealous, pouting, narrowed eyes, crossed arms, sulking",
    "冷静": "calm, composed, steady gaze, relaxed expression, collected",
    "疲惫": "tired, heavy eyelids, weary expression, exhausted, drained",
    # ── 漫画夸张（manga 高表现力）──
    "汗颜": "sweat drop on forehead, awkward smile, nervous laugh, embarrassed",
    "石化": "shocked frozen, wide blank eyes, open mouth, stunned, speechless",
    "星星眼": "sparkling star-shaped eyes, excited, amazed, dazzling smile",
    "流口水": "drooling, hungry gaze, longing eyes, mouth open, craving",
    "炸毛": "shocked hair standing up, wide eyes, surprised, startled, cat-like",
    "叹气": "sighing, exasperated, shoulders slumped, resigned expression",
    # ── 成人向（ecchi 软色情）──
    "色气": "seductive gaze, half-lidded eyes, alluring smile, suggestive, adult woman",
    "挑逗": "teasing smirk, playful wink, provocative pose, tempting, adult woman",
    "魅惑": "charming, bewitching eyes, alluring aura, captivating smile, adult woman",
    "娇喘": "breathless, flushed face, parted lips, panting, heavy breathing, adult woman",
    "坏心思": "mischievous plotting, sly eyes, cunning smile, scheming, playful intent",
    # ── 猎奇向（horror 心理恐怖/氛围——12魔器风格）──
    "狂气": "mad grin, unhinged eyes, manic laughter, insanity, twisted smile",
    "崩坏": "broken expression, hollow empty eyes, despair, shattered psyche, dead inside",
    "病娇": "yandere smile, dark obsessive loving gaze, knife in hand, unsettling sweetness",
    "空洞": "empty dead eyes, lifeless stare, emotionless, hollow gaze, doll-like",
    "痴笑": "hysterical laughter, wide unblinking eyes, manic joy, unhinged glee",
    "怨念": "deep resentment, cursed glare, dark aura, grudge, vengeful eyes",
    "泪笑": "smiling through tears, broken smile, glossy despairing eyes, bittersweet",
    "恐惧": "terrified wide eyes, pale face, trembling, catatonic shock, horror",
    "癫狂": "frenzied expression, wild rolling eyes, chaotic energy, raving madness",
    "冰冷": "cold emotionless stare, icy killer gaze, deadpan psychopath, chilling calm",
    "濒死": "dying gaze, pale fading eyes, barely alive, fading light in eyes, last breath",
    "极黑": "darkest sinister smile, bloodlust in eyes, predatory grin, ultimate darkness",
}# 表情集预设（来源域）
EMOTE_SETS = {
    "casual": ["高兴", "生气", "哭泣", "惊讶", "害羞", "微笑", "无语", "得意", "困", "认真", "委屈", "坏笑", "坏心思"],
    "galgame": ["微笑", "高兴", "生气", "哭泣", "惊讶", "害羞", "心动", "脸红", "流泪", "黑化", "嫌弃", "吃醋", "冷静", "疲惫"],
    "manga": ["高兴", "生气", "惊讶", "汗颜", "石化", "星星眼", "流口水", "炸毛", "坏笑", "无语", "叹气"],
    "ecchi": ["色气", "挑逗", "魅惑", "娇喘", "脸红", "害羞", "心动"],
    "horror": ["狂气", "崩坏", "病娇", "空洞", "痴笑", "怨念", "泪笑", "恐惧", "癫狂", "冰冷", "濒死", "极黑"],
}


def _emoji(emote: str) -> str:
    """表情 → emoji（文件名用）"""
    return {"高兴": "😊", "生气": "😠", "哭泣": "😢", "惊讶": "😲",
            "害羞": "😳", "微笑": "🙂", "无语": "😑", "得意": "😏",
            "困": "🥱", "认真": "🧐", "委屈": "🥺", "坏笑": "😏",
            "心动": "💗", "脸红": "😳", "流泪": "🥲", "黑化": "😈",
            "嫌弃": "🙄", "吃醋": "😒", "冷静": "😌", "疲惫": "😮‍💨",
            "汗颜": "😅", "石化": "😶", "星星眼": "🤩", "流口水": "🤤",
            "炸毛": "😱", "叹气": "😮‍💨", "色气": "😏", "挑逗": "😉",
            "魅惑": "✨", "娇喘": "🥵", "坏心思": "🦊",
            "狂气": "😜", "崩坏": "💔", "病娇": "🔪", "空洞": "🫥",
            "痴笑": "😆", "怨念": "👿", "泪笑": "😭", "恐惧": "😨",
            "癫狂": "🌀", "冰冷": "🧊", "濒死": "🕯️", "极黑": "🖤"}.get(emote, "😐")


# ── 微信表情开放平台上架规范（B站 1.38M 热度场景的变现细节）──
WX_SPECS = {
    "main": (240, 240),      # 表情主图（PNG 透明底，每张 ≤500KB）
    "thumb": (120, 120),     # 表情缩略图（PNG，每张 ≤100KB）
    "banner": (750, 400),    # 表情包横幅（封面 banner，PNG ≤200KB）
    "cover": (240, 240),     # 详情页封面（PNG ≤200KB）
    "artist": (750, 750),    # 艺术家头像（PNG ≤200KB）
    "title": (750, 560),     # 表情包标题图（PNG ≤200KB）
}


def _export_wx_specs(emote_images: dict[str, str], out_dir: Path) -> dict[str, str]:
    """把表情图导出为微信上架全套规格（主图/缩略图/横幅/封面/头像/标题图）。

    Args:
        emote_images: {emote_name: 图片路径}（透明底 PNG 最佳）
        out_dir: 输出目录（wx_export/ 子目录）

    Returns:
        {"main_0.png": 路径, ...}
    """
    from PIL import Image, ImageDraw, ImageFont

    wx_dir = out_dir / "wx_export"
    wx_dir.mkdir(parents=True, exist_ok=True)  # parents=True：父目录不存在也创建
    exported: dict[str, str] = {}

    # 1. 主图 + 缩略图（每个表情）
    for i, (name, path) in enumerate(emote_images.items()):
        img = Image.open(path).convert("RGBA")
        # 主图 240×240（contain 缩放 + 透明底）
        main = Image.new("RGBA", WX_SPECS["main"], (0, 0, 0, 0))
        img.thumbnail((240, 240), Image.LANCZOS)
        main.paste(img, ((240 - img.width) // 2, (240 - img.height) // 2), img)
        mpath = wx_dir / f"main_{i+1:02d}_{name}.png"
        main.save(mpath)
        exported[f"main_{i+1:02d}"] = str(mpath)
        # 缩略图 120×120
        thumb = main.resize(WX_SPECS["thumb"], Image.LANCZOS)
        tpath = wx_dir / f"thumb_{i+1:02d}_{name}.png"
        thumb.save(tpath)
        exported[f"thumb_{i+1:02d}"] = str(tpath)

    # 2. 横幅 750×400（前 3 个表情平铺）
    banner = Image.new("RGBA", WX_SPECS["banner"], (255, 255, 255))
    items = list(emote_images.items())[:3]
    if items:
        cell_w = 750 // len(items)
        for i, (name, path) in enumerate(items):
            im = Image.open(path).convert("RGBA")
            im.thumbnail((cell_w - 20, 380), Image.LANCZOS)
            x = i * cell_w + (cell_w - im.width) // 2
            y = (400 - im.height) // 2
            banner.paste(im, (x, y), im)
    bpath = wx_dir / "banner_750x400.png"
    banner.save(bpath)
    exported["banner"] = str(bpath)

    # 3. 详情页封面 240×240（第 1 个表情 + 白底）
    cover = Image.new("RGBA", WX_SPECS["cover"], (255, 255, 255))
    if items:
        im = Image.open(items[0][1]).convert("RGBA")
        im.thumbnail((220, 220), Image.LANCZOS)
        cover.paste(im, ((240 - im.width) // 2, (240 - im.height) // 2), im)
    cpath = wx_dir / "cover_240x240.png"
    cover.save(cpath)
    exported["cover"] = str(cpath)

    # 4. 艺术家头像 750×750（第 1 个表情放大 + 白底圆角）
    artist = Image.new("RGBA", WX_SPECS["artist"], (255, 255, 255))
    if items:
        im = Image.open(items[0][1]).convert("RGBA")
        im.thumbnail((700, 700), Image.LANCZOS)
        artist.paste(im, ((750 - im.width) // 2, (750 - im.height) // 2), im)
    apath = wx_dir / "artist_750x750.png"
    artist.save(apath)
    exported["artist"] = str(apath)

    # 5. 标题图 750×560（白底 + 首表情 + 文字）
    title = Image.new("RGBA", WX_SPECS["title"], (255, 255, 255))
    if items:
        im = Image.open(items[0][1]).convert("RGBA")
        im.thumbnail((400, 400), Image.LANCZOS)
        title.paste(im, ((750 - im.width) // 2, 40), im)
    tpath = wx_dir / "title_750x560.png"
    title.save(tpath)
    exported["title"] = str(tpath)

    return exported


def generate_emotes(character_desc: str, emotes: list[str] | None = None,
                    name: str = "character", count: int = 1,
                    output_dir: str | None = None, seed: int = -1,
                    gif: bool = False, wx: bool = False,
                    lora_name: str | None = None, lora_strength: float = 1.0,
                    outfit_style: str | None = None):
    """同一角色批量表情生成。

    Args:
        character_desc: 角色描述（发色/瞳色/服装/特征，固定锚点）
        emotes: 表情列表（中文名，映射 EMOTE_MAP）
        name: 角色名（输出目录/文件名）
        count: 每表情张数
        output_dir: 输出目录
        gif: 生成动态表情（用随机种子多帧合成 GIF，帧间小变化=动态感）
        wx: 导出微信表情开放平台上架全套规格（主图/缩略图/横幅/封面/头像/标题图）
        outfit_style: 服装风格名（wardrobe 风格——表情穿指定风格服装）

    Returns:
        [{"emote": 表情, "files": [路径...]}, ...]
    """
    from workshop.create import create_from_nl
    # 服装风格展开（emotes 联动 wardrobe——表情穿指定风格服装）
    if outfit_style:
        try:
            from workshop.wardrobe import build_outfit
            character_desc = f'{character_desc}, {build_outfit(outfit_style)}'
        except Exception as e:
            print(f'  ⚠️ 服装风格展开失败（{e}），使用原描述')

    # 空描述校验（角色锚点必须有）
    if not character_desc or not character_desc.strip():
        raise ValueError('角色描述不能为空（emotes 需要角色锚点描述）')
    emote_list = emotes or DEFAULT_EMOTES
    # 表情名校验（非法表情 → 友好报错，列出可用）
    unknown = [e for e in emote_list if e not in EMOTE_MAP]
    if unknown:
        raise ValueError(f'未知表情: {unknown}（可用: {list(EMOTE_MAP.keys())}）')
    # 去重（重复表情只生成一次——防浪费）
    emote_list = list(dict.fromkeys(emote_list))
    # 名字清洗（防路径字符创建嵌套目录）
    import re as _re
    name = _re.sub(r'[\\/:*?"<>|]', '_', name).strip() or 'character'
    out_dir = Path(output_dir or (PROJECT / 'outputs' / f"emotes_{name}_{time.strftime('%Y%m%d_%H%M%S')}"))
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    base_seed = seed if seed >= 0 else 20260814
    for i, emote in enumerate(emote_list):
        emote_en = EMOTE_MAP.get(emote, emote)
        print(f'\n  [{i+1}/{len(emote_list)}] {emote} {_emoji(emote)}')
        # 角色锚点 + 表情变化（角色固定，表情变）
        prompt = f"{character_desc}, {emote_en}, bust shot, upper body, looking at viewer"
        sub = out_dir / f"{i+1:02d}_{emote}"
        files = []

        # GIF 动态模式：4 帧小变化（同 seed 族，帧间相似=动态感）
        if gif:
            frames = []
            for j in range(4):
                s = base_seed + i * 100 + j
                try:
                    create_from_nl(prompt, count=1, model_type='sdxl', seed=s,
                                   prompt_ready=True, inspect=False, dry_run=False,
                                   output_dir=str(sub / f"frame{j}"),
                                   lora_name=lora_name, lora_strength=lora_strength)
                    best = sub / f"frame{j}" / 'best.png'
                    if best.exists():
                        frames.append(str(best))
                except Exception as e:
                    print(f'    ⚠️ 帧{j} 失败: {str(e)[:80]}')
            if len(frames) >= 2:
                try:
                    from PIL import Image
                    imgs = [Image.open(f).convert('RGB') for f in frames]
                    # 统一尺寸
                    w = min(i.width for i in imgs)
                    h = min(i.height for i in imgs)
                    imgs = [i.resize((w, h), Image.LANCZOS) for i in imgs]
                    gif_path = sub / f"{emote}.gif"
                    imgs[0].save(gif_path, save_all=True, append_images=imgs[1:],
                                 duration=250, loop=0)
                    files.append(str(gif_path))
                    print(f'  🎞️ 动态表情: {gif_path} ({len(frames)}帧)')
                except Exception as e:
                    print(f'    ⚠️ GIF 合成失败: {str(e)[:80]}')
            continue

        for j in range(count):
            s = base_seed + i * 100 + j
            try:
                create_from_nl(prompt, count=1, model_type='sdxl', seed=s,
                               prompt_ready=True, inspect=False, dry_run=False,
                               lora_name=lora_name, lora_strength=lora_strength,
                               output_dir=str(sub))
                best = sub / 'best.png'
                if best.exists():
                    files.append(str(best))
            except Exception as e:
                print(f'    ⚠️ 失败: {str(e)[:80]}')
        if files:
            results.append({"emote": emote, "files": files})
            print(f'  ✅ {emote}: {len(files)} 张')

    # 汇总拼版（横向拼接，表情包常用）
    if results:
        try:
            from PIL import Image
            rows = []
            row = []
            for r in results:
                for f in r["files"]:
                    row.append(Image.open(f))
                    if len(row) == 4:
                        h = max(i.height for i in row)
                        w = sum(i.width for i in row)
                        sheet = Image.new('RGB', (w, h), (255, 255, 255))
                        x = 0
                        for i in row:
                            sheet.paste(i, (x, 0))
                            x += i.width
                        rows.append(sheet)
                        row = []
            if row:
                h = max(i.height for i in row)
                w = sum(i.width for i in row)
                sheet = Image.new('RGB', (w, h), (255, 255, 255))
                x = 0
                for i in row:
                    sheet.paste(i, (x, 0))
                    x += i.width
                rows.append(sheet)
            for ri, s in enumerate(rows):
                sp = out_dir / f"sheet_{ri+1}.png"
                s.save(sp)
                print(f'  🎨 表情包拼版: {sp}')
        except Exception as e:
            print(f'  ⚠️ 拼版失败: {str(e)[:80]}')

    # 微信上架规格导出（变现细节）
    if wx:
        try:
            emote_images = {}
            for r in results:
                for f in r["files"]:
                    if f.endswith(".png"):
                        emote_images[r["emote"]] = f
                        break
            if emote_images:
                exported = _export_wx_specs(emote_images, out_dir)
                print(f'\n  📱 微信表情上架规格（{len(exported)} 张）:')
                for k, v in exported.items():
                    print(f'    {k}: {v}')
                print(f'  💡 规格: 主图240×240 / 缩略图120×120 / 横幅750×400 / 封面240×240 / 头像750×750 / 标题图750×560')
        except Exception as e:
            print(f'  ⚠️ 微信规格导出失败: {str(e)[:80]}')

    print(f'\n📁 表情包目录: {out_dir}')
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop emotes', description='角色表情包/差分批量生成')
    ap.add_argument('character_desc', nargs='*', help='角色描述（发色/瞳色/服装/特征，固定锚点）')
    ap.add_argument('--emotes', default=None, help='表情列表（逗号分隔）: 高兴,生气,哭泣')
    ap.add_argument('--set', default=None, choices=list(EMOTE_SETS.keys()),
                    help=f'表情集预设: {"/".join(EMOTE_SETS.keys())}（galgame差分/manga夸张/ecchi成人向）')
    ap.add_argument('--count', type=int, default=1, help='每表情张数')
    ap.add_argument('--gif', action='store_true', help='动态表情（4帧GIF，微信可用）')
    ap.add_argument('--wx', action='store_true', help='导出微信表情上架全套规格')
    ap.add_argument('--name', default='character', help='角色名')
    ap.add_argument('--lora', default=None, help='角色 LoRA 名（锁身份一致性，自动补 .safetensors）')
    ap.add_argument('--lora-weight', type=float, default=0.9)
    ap.add_argument('--outfit', dest='outfit_style', default=None,
                    help='服装风格名（wardrobe 风格如 gothic/arknight——表情穿指定风格服装）')
    ap.add_argument('--output', default=None, help='输出目录')
    ap.add_argument('--seed', type=int, default=-1)
    args = ap.parse_args(argv)

    desc = ' '.join(args.character_desc)
    if not desc:
        print('用法: emotes "角色描述" [--emotes "高兴,生气,哭泣"] [--name 角色名]')
        return 1
    emotes = [e.strip() for e in args.emotes.split(',')] if args.emotes else None
    # --set 表情集预设（与 --emotes 互斥，--set 优先）
    if args.set:
        emotes = list(EMOTE_SETS[args.set])
        print(f'📚 表情集: {args.set}（{len(emotes)} 个表情）')
    # LoRA 名自动补 .safetensors
    lora = args.lora
    if lora and not lora.endswith('.safetensors'):
        lora = lora + '.safetensors'
    generate_emotes(desc, emotes=emotes, name=args.name, count=args.count,
                    output_dir=args.output, seed=args.seed, gif=args.gif, wx=args.wx,
                    lora_name=lora, lora_strength=args.lora_weight,
                    outfit_style=args.outfit_style)
    return 0


if __name__ == '__main__':
    sys.exit(main())
