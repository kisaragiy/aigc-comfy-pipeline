#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/biztext.py — 商业图文字合成（B-biztext）v1.0
=====================================================
商业图核心流程：AI 生成图保持无文字 → 后期 PIL 合成标题文字。
（AI 生成文字易崩乱码——正确做法是后期排版）

能力：
  - 中文标题 + 副标题（微软雅黑/黑体）
  - 位置预设：top-center / bottom-center / bottom-left / center
  - 描边/阴影（白字黑描边——任何背景可读）
  - 装饰线 + 渐变色块

用法:
  python -m agents workshop biztext <图> "标题" [--sub 副标题] [--pos top-center] [--size 64]
"""

import argparse, os, sys, time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent

FONTS = {
    'yahei': r'C:\Windows\Fonts\msyh.ttc',     # 微软雅黑
    'yahei_bold': r'C:\Windows\Fonts\msyhbd.ttc',
    'simhei': r'C:\Windows\Fonts\simhei.ttf',  # 黑体
}

POSITIONS = {
    'top-center': (0.5, 0.12),
    'top-left': (0.06, 0.10),
    'bottom-center': (0.5, 0.85),
    'bottom-left': (0.06, 0.82),
    'center': (0.5, 0.5),
}


def _load_font(size, font_name='yahei_bold'):
    from PIL import ImageFont
    path = FONTS.get(font_name, FONTS['yahei_bold'])
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        # 兜底：PIL 默认字体（中文可能不显示，但不会崩）
        return ImageFont.load_default()


TEMPLATES = {
    "default": {},  # 标准（标题+副标题+装饰线）
    "sale": {  # 促销（大字标题 + 副标题 + 底部价格/日期条）
        "title_size_scale": 1.25,
        "price_bar": True,
    },
    "event": {  # 活动（居中大字 + 日期副标题）
        "pos": "center",
        "title_size_scale": 1.4,
    },
}


def _wrap_text(draw, text, font, max_width):
    """多行自动换行（长标题/长副标题）。"""
    lines = []
    cur = ''
    for ch in text:
        test = cur + ch
        if draw.textlength(test, font=font) > max_width and cur:
            lines.append(cur)
            cur = ch
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines


def add_text(image_path, title, sub=None, pos='bottom-center', font_size=72,
             sub_size=36, font='yahei_bold', output=None, title_color=(255, 255, 255),
             stroke=True, template='default', price_text=None, date_text=None):
    """给商业图合成标题文字。

    Args:
        image_path: 无文字商业图
        title: 主标题（中文）
        sub: 副标题（可选）
        pos: 位置预设
        font_size: 主标题字号
        sub_size: 副标题字号
        font: 字体（yahei/yahei_bold/simhei）
        output: 输出路径
        title_color: 标题颜色（默认白）
        stroke: 描边（白字黑描边——任何背景可读）
        template: 模板（default/sale/event）
        price_text: 促销价格文字（如 "¥199 限时 5 折"）
        date_text: 活动日期（如 "8月18日-8月31日"）

    Returns:
        输出路径
    """
    from PIL import Image, ImageDraw, ImageFont

    if not os.path.exists(image_path):
        raise FileNotFoundError(f'图片不存在: {image_path}')
    if pos not in POSITIONS:
        raise ValueError(f'位置可选: {list(POSITIONS.keys())}')
    if template not in TEMPLATES:
        raise ValueError(f'模板可选: {list(TEMPLATES.keys())}')
    if not title or not title.strip():
        raise ValueError('标题不能为空')
    if font_size <= 0 or sub_size <= 0:
        raise ValueError('字号必须为正数')

    tpl = TEMPLATES[template]
    if tpl.get("pos"):
        pos = tpl["pos"]
    scale = tpl.get("title_size_scale", 1.0)
    font_size = int(font_size * scale)
    from workshop.image_utils import open_image_safe
    img = open_image_safe(image_path).convert('RGB')
    w, h = img.size
    draw = ImageDraw.Draw(img)

    # 半透明色块（提高文字可读性）
    block_alpha = 90
    overlay = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)

    # 主标题（多行自动换行）
    font = _load_font(font_size, font)
    max_tw = int(w * 0.86)
    title_lines = _wrap_text(draw, title, font, max_tw)
    line_h = font_size + 8
    tw = max(draw.textlength(l, font=font) for l in title_lines)
    # sale 模板：标题上移到 0.62（避开底部价格条）
    if template == 'sale':
        x = int(POSITIONS[pos][0] * w - tw / 2)
        y = int(0.62 * h) - (len(title_lines) - 1) * line_h // 2
    else:
        x = int(POSITIONS[pos][0] * w - tw / 2)
        y = int(POSITIONS[pos][1] * h)

    # 半透明黑色圆角色块（约文字区域）
    pad = 24
    block_h = line_h * len(title_lines) + pad
    bx0, by0 = x - pad, y - pad // 2
    bx1, by1 = x + tw + pad, y + block_h
    odraw.rounded_rectangle([bx0, by0, bx1, by1], radius=12, fill=(0, 0, 0, block_alpha))

    # 副标题（主标题下方）
    if sub:
        sfont = _load_font(sub_size, 'yahei')
        stw = draw.textlength(sub, font=sfont)
        sx = int(POSITIONS[pos][0] * w - stw / 2)
        sy = y + font_size + 12
        odraw.rounded_rectangle([sx - pad, sy - pad // 2, sx + stw + pad, sy + sub_size + pad],
                                radius=10, fill=(0, 0, 0, block_alpha))

    img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
    draw = ImageDraw.Draw(img)

    # 主标题（多行逐行绘制，白字 + 黑描边）
    for li, line in enumerate(title_lines):
        ly = y + li * line_h
        if stroke:
            draw.text((x, ly), line, font=font, fill=title_color,
                      stroke_width=max(2, font_size // 24), stroke_fill=(0, 0, 0))
        else:
            draw.text((x, ly), line, font=font, fill=title_color)

    # 副标题
    if sub:
        sfont = _load_font(sub_size, 'yahei')
        stw = draw.textlength(sub, font=sfont)
        sx = int(POSITIONS[pos][0] * w - stw / 2)
        sy = y + line_h * len(title_lines) + 12
        if stroke:
            draw.text((sx, sy), sub, font=sfont, fill=(230, 230, 230),
                      stroke_width=max(1, sub_size // 30), stroke_fill=(0, 0, 0))
        else:
            draw.text((sx, sy), sub, font=sfont, fill=(230, 230, 230))

    # 装饰线（标题上方金色细线——海报感，多行时在首行上方）
    line_w = int(tw * 0.35)
    lx = int(POSITIONS[pos][0] * w - line_w / 2)
    ly = y - 16
    draw.line([(lx, ly), (lx + line_w, ly)], fill=(255, 200, 80), width=3)

    # 促销价格条（sale 模板）
    if tpl.get("price_bar") and (price_text or date_text):
        pf = _load_font(max(28, sub_size), 'yahei_bold')
        pf_red = (255, 80, 60)
        bar_items = []
        if price_text:
            bar_items.append(price_text)
        if date_text:
            bar_items.append(date_text)
        # 底部横条（金色底 + 深色文字）
        bar_h = max(40, sub_size + 24)
        bar_w = w - 80
        bar_x, bar_y = 40, h - bar_h - 30
        draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h],
                               radius=8, fill=(255, 200, 80))
        # 价格（红）左、日期（深）右
        if price_text:
            draw.text((bar_x + 30, bar_y + (bar_h - sub_size) // 2), price_text,
                      font=pf, fill=pf_red)
        if date_text:
            dt_w = draw.textlength(date_text, font=pf)
            draw.text((bar_x + bar_w - dt_w - 30, bar_y + (bar_h - sub_size) // 2),
                      date_text, font=pf, fill=(40, 40, 40))

    out_path = output or str(PROJECT / 'outputs' / f"biztext_{time.strftime('%Y%m%d_%H%M%S')}.png")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    from workshop.image_utils import save_image_with_meta
    save_image_with_meta(img, out_path, source_path=image_path,
                         extra_meta={'biztext': 'true',
                                     'biztext_title': title,
                                     'biztext_template': template})
    print(f'  📝 文字合成完成: {out_path}')
    print(f'      标题: {title}' + (f' | 副标题: {sub}' if sub else '') + f' | 位置: {pos}')
    return out_path


def batch_add_text(image_dir, title, sub=None, pos='bottom-center', font_size=72,
                   glob_pattern='*.png', output_dir=None, template='default',
                   price_text=None, date_text=None):
    """批量文字合成（目录内所有图加同款标题——批量海报系列）。

    Args:
        image_dir: 图片目录
        title/sub/pos/font_size/template: 同 add_text
        glob_pattern: 匹配模式
        output_dir: 输出目录

    Returns:
        [输出路径...]
    """
    import glob
    imgs = sorted(glob.glob(os.path.join(image_dir, glob_pattern)))
    if not imgs:
        print(f'⚠️ {image_dir} 下无 {glob_pattern} 文件')
        return []
    out_root = Path(output_dir or (PROJECT / 'outputs' / f"biztext_batch_{time.strftime('%Y%m%d_%H%M%S')}"))
    out_root.mkdir(parents=True, exist_ok=True)
    saved = []
    print(f'📚 批量文字合成 {len(imgs)} 张 (标题: {title})...')
    for i, img in enumerate(imgs):
        try:
            out = add_text(img, title, sub=sub, pos=pos, font_size=font_size,
                           output=str(out_root / f"t_{i+1:02d}.png"),
                           template=template, price_text=price_text,
                           date_text=date_text)
            if out:
                saved.append(out)
        except Exception as e:
            print(f'  ⚠️ 第{i+1}张失败: {str(e)[:80]}')
    print(f'\n📁 批量输出: {out_root}（{len(saved)} 张）')
    return saved


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop biztext', description='商业图文字合成（PIL 后期排版）')
    ap.add_argument('image', help='无文字商业图路径')
    ap.add_argument('title', help='主标题（中文）')
    ap.add_argument('--sub', default=None, help='副标题')
    ap.add_argument('--pos', choices=list(POSITIONS.keys()), default='bottom-center',
                    help='位置预设')
    ap.add_argument('--size', type=int, default=72, help='主标题字号')
    ap.add_argument('--sub-size', type=int, default=36, help='副标题字号')
    ap.add_argument('--font', choices=list(FONTS.keys()), default='yahei_bold',
                    help='字体')
    ap.add_argument('--template', choices=list(TEMPLATES.keys()), default='default',
                    help='模板（default/sale/event）')
    ap.add_argument('--price', default=None, help='促销价格文字（sale 模板）')
    ap.add_argument('--date', default=None, help='活动日期（sale 模板）')
    ap.add_argument('--dir', default=None, help='批量加文字目录（所有 png/jpg）')
    ap.add_argument('--output', default=None, help='输出路径/目录')
    args = ap.parse_args(argv)

    # 批量模式
    if args.dir:
        try:
            batch_add_text(args.dir, args.title, sub=args.sub, pos=args.pos,
                           font_size=args.size, output_dir=args.output,
                           template=args.template, price_text=args.price,
                           date_text=args.date)
            return 0
        except Exception as e:
            print(f'❌ 批量文字合成失败: {str(e)[:150]}')
            return 1

    try:
        add_text(args.image, args.title, sub=args.sub, pos=args.pos,
                 font_size=args.size, sub_size=args.sub_size, font=args.font,
                 output=args.output, template=args.template,
                 price_text=args.price, date_text=args.date)
        return 0
    except Exception as e:
        print(f'❌ 文字合成失败: {str(e)[:150]}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
