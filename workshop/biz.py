#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/biz.py — 商业图生成（B-biz）v1.0
==========================================
商业图流程（B站/业界标准）：
  1. 主题规格表（尺寸/构图/风格约束）
  2. qwen-image 模型（原生中文理解——UI 元素/中文场景不用翻译）
  3. 无文字铁律（AI 生成文字易崩——默认强制无文字）
  4. 品牌风格参数（--style 统一系列感）

主题：
  avatar(头像1:1) / cover(文章封面16:9) / poster(海报2:3) /
  dashboard(数据大屏16:9) / mockup(UI界面16:10) / banner(横幅21:9) /
  logo(Logo1:1) / product(产品图4:3)

用法:
  python -m agents workshop biz <主题> "描述" [--style 品牌风格] [--size 自定义]
  python -m agents workshop biz batch "主题1,主题2..."（批量多主题）
"""

import argparse, json, os, sys, time, urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent

# 主题规格表（尺寸 + 构图约束 + 风格约束）
BIZ_TOPICS = {
    "avatar": {
        "size": (1024, 1024), "ratio": "1:1",
        "constraint": "professional headshot, centered face, simple clean background, high detail, 头像特写",
        "desc": "头像",
    },
    "cover": {
        "size": (1536, 864), "ratio": "16:9",
        "constraint": "article cover art, modern flat design, strong visual hierarchy, no text, 文章封面",
        "desc": "文章封面",
    },
    "poster": {
        "size": (896, 1344), "ratio": "2:3",
        "constraint": "promotional poster, dramatic composition, high impact, cinematic lighting, no text, 宣传海报",
        "desc": "宣传海报",
    },
    "dashboard": {
        "size": (1536, 864), "ratio": "16:9",
        "constraint": "data visualization dashboard concept, dark theme, glowing blue charts, line bar pie charts, tech style, high quality, 数据大屏",
        "desc": "数据大屏",
    },
    "mockup": {
        "size": (1536, 960), "ratio": "16:10",
        "constraint": "app UI design concept, modern clean interface, rounded cards, light theme, apple design style, product showcase, no text gibberish, 应用界面",
        "desc": "UI 界面",
    },
    "banner": {
        "size": (1792, 768), "ratio": "21:9",
        "constraint": "wide banner design, modern minimal, brand atmosphere, clear composition, no text, 横幅",
        "desc": "横幅 Banner",
    },
    "logo": {
        "size": (1024, 1024), "ratio": "1:1",
        "constraint": "logo design, minimalist iconic symbol, clean vector style, white background, brand identity, no text, Logo",
        "desc": "Logo 设计",
    },
    "product": {
        "size": (1344, 1008), "ratio": "4:3",
        "constraint": "product photography, studio lighting, clean background, commercial quality, high detail, 产品图",
        "desc": "产品图",
    },
    "og": {
        "size": (1200, 630), "ratio": "1.9:1",
        "constraint": "social share preview card (OG image), bold visual, brand identity, modern composition, no text, 分享预览图",
        "desc": "OG 分享预览图",
    },
    "card": {
        "size": (1050, 700), "ratio": "3:2",
        "constraint": "business card design, clean professional layout, modern typography space, brand colors, no text, 商务名片",
        "desc": "商务名片",
    },
}

# 品牌风格预设
BIZ_STYLES = {
    "default": "",
    "tech": "tech blue gradient, futuristic, clean modern, 科技蓝渐变",
    "minimal": "minimalist, lots of white space, elegant, 极简留白",
    "luxury": "luxury gold black, premium feel, elegant lighting, 奢华金黑",
    "fresh": "fresh green natural, bright airy, 清新自然",
    "warm": "warm orange cream, cozy friendly, 温暖橙调",
}

# 电商产品主图 5 件套（多规格标准）
PRODUCT_SHOTS = {
    "white": "white background, pure product shot, e-commerce main image, even lighting, no shadow, 纯白底电商主图",
    "scene": "product in lifestyle scene, natural environment, e-commerce scene image, 场景图",
    "detail": "extreme close-up detail shot of product texture and craftsmanship, macro, 细节特写",
    "angle": "three-quarter angle product shot, dynamic composition, e-commerce angle image, 45度角展示图",
    "size": "product with hand holding for size reference, e-commerce size image, 手持比例图",
}

# 多尺寸适配（一张主图出多规格）
VARIANT_SIZES = {
    "cover16x9": (1536, 864),    # 文章封面
    "avatar1x1": (1024, 1024),   # 头像
    "social3x4": (1080, 1440),   # 小红书/朋友圈
    "banner21x9": (1792, 768),   # 横幅
    "mini1x1": (512, 512),       # 小图/缩略图
}

# 社交封面主题
SOCIAL_TOPIC = {
    "size": (1080, 1440), "ratio": "3:4",
    "constraint": "social media cover, eye-catching composition, modern aesthetic, no text, 社交封面",
    "desc": "社交封面",
}

# 海报模板系列（新品/招聘/节日——prompt 预设）
POSTER_TEMPLATES = {
    "new_product": "new product launch poster, product centered, dramatic lighting, bold modern design, 新品发布海报",
    "recruit": "job recruitment poster, professional corporate style, clean modern layout, 招聘海报",
    "festival": "festival celebration poster, warm festive colors, celebration atmosphere, 节日海报",
    "event": "event announcement poster, energetic dynamic design, eye-catching, 活动海报",
    "thank": "customer appreciation poster, warm grateful tone, elegant design, 感恩回馈海报",
}

# Banner 模板系列（促销/活动/新品——横幅预设）
BANNER_TEMPLATES = {
    "sale": "big sale banner, bold discount visual, hot red orange colors, eye-catching, 大促横幅",
    "new": "new arrival banner, fresh modern design, product showcase, 上新横幅",
    "brand": "brand promotion banner, elegant premium feel, brand atmosphere, 品牌宣传横幅",
    "holiday": "holiday season banner, festive decoration, warm celebration, 节日横幅",
}


def _http():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _submit(wf, timeout=600):
    COMFY = 'http://127.0.0.1:8188'
    body = json.dumps({'prompt': wf}).encode()
    req = urllib.request.Request(COMFY + '/prompt', data=body,
                                 headers={'Content-Type': 'application/json'})
    r = json.loads(_http().open(req, timeout=30).read())
    if 'error' in r:
        raise RuntimeError(str(r['error'])[:200])
    pid = r['prompt_id']
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            d = json.loads(_http().open(COMFY + f'/history/{pid}', timeout=5).read())
            if pid in d:
                files = []
                for node in d[pid].get('outputs', {}).values():
                    files += [img['filename'] for img in node.get('images', [])]
                if files:
                    return files
        except Exception:
            pass
        time.sleep(2)
    raise TimeoutError('生成超时')


def _build_biz_wf(prompt, width, height, seed):
    """qwen-image 商业图工作流（原生中文理解）"""
    wf = {}
    wf['1'] = {'class_type': 'UnetLoaderGGUF',
               'inputs': {'unet_name': 'qwen-image\\qwen-image-2512-Q3_K_M.gguf', 'weight_dtype': 'default'}}
    wf['2'] = {'class_type': 'CLIPLoader',
               'inputs': {'clip_name': 'qwen-image\\qwen_2.5_vl_7b_fp8_scaled.safetensors',
                          'type': 'qwen_image', 'device': 'default'}}
    wf['3'] = {'class_type': 'VAELoader', 'inputs': {'vae_name': 'qwen_image_vae.safetensors'}}
    wf['4'] = {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['2', 0], 'text': prompt}}
    wf['5'] = {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['2', 0], 'text': ''}}
    wf['6'] = {'class_type': 'EmptyLatentImage',
               'inputs': {'width': width, 'height': height, 'batch_size': 1}}
    wf['7'] = {'class_type': 'KSampler',
               'inputs': {'model': ['1', 0], 'positive': ['4', 0], 'negative': ['5', 0],
                          'latent_image': ['6', 0], 'seed': seed, 'steps': 28, 'cfg': 1.0,
                          'sampler_name': 'euler', 'scheduler': 'simple', 'denoise': 1.0}}
    wf['8'] = {'class_type': 'VAEDecode', 'inputs': {'samples': ['7', 0], 'vae': ['3', 0]}}
    wf['9'] = {'class_type': 'SaveImage',
               'inputs': {'images': ['8', 0], 'filename_prefix': 'biz'}}
    return wf


def biz_generate(topic, desc, style='default', seed=-1, output=None, no_text=True,
                 custom_size=None):
    """商业图生成。

    Args:
        topic: 主题（avatar/cover/poster/dashboard/mockup/banner/logo/product）
        desc: 内容描述（中文直喂 qwen-image）
        style: 品牌风格（default/tech/minimal/luxury/fresh/warm）
        no_text: 无文字铁律（默认 True——AI 生成文字易崩）
        custom_size: 自定义尺寸 (w, h)

    Returns:
        输出路径
    """
    if topic not in BIZ_TOPICS:
        raise ValueError(f'主题可选: {list(BIZ_TOPICS.keys())}')
    if style not in BIZ_STYLES:
        raise ValueError(f'风格可选: {list(BIZ_STYLES.keys())}')

    spec = BIZ_TOPICS[topic]
    width, height = custom_size or spec['size']
    style_hint = BIZ_STYLES[style]
    text_rule = ", 画面中不要出现任何文字和字母" if no_text else ""

    prompt = f"{desc}, {spec['constraint']}{', ' + style_hint if style_hint else ''}{text_rule}"
    print(f'  🎨 biz[{topic}] {spec["desc"]} {width}x{height} | 风格: {style}')
    print(f'      prompt: {prompt[:100]}...')

    seed_actual = seed if seed >= 0 else int(time.time()) % 2**31
    wf = _build_biz_wf(prompt, width, height, seed_actual)
    print(f'  ⏳ 生成中 (seed={seed_actual})...')
    files = _submit(wf, timeout=600)
    if not files:
        raise RuntimeError('无输出')

    COMFY_OUTPUT = r'C:\DrawingLive\ComfyUI\output'
    src = os.path.join(COMFY_OUTPUT, files[0])
    out_path = output or str(PROJECT / 'outputs' / f"biz_{topic}_{time.strftime('%Y%m%d_%H%M%S')}.png")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(src, 'rb') as f_in, open(out_path, 'wb') as f_out:
        f_out.write(f_in.read())
    print(f'  ✅ 商业图完成: {out_path}')
    return out_path


def batch_biz(topics_desc, style='default', seed=-1, output_dir=None):
    """批量多主题生成（统一风格——品牌系列感）。

    Args:
        topics_desc: [(topic, desc), ...]
        style: 统一品牌风格
        output_dir: 输出目录

    Returns:
        [输出路径...]
    """
    out_root = Path(output_dir or (PROJECT / 'outputs' / f"biz_batch_{time.strftime('%Y%m%d_%H%M%S')}"))
    out_root.mkdir(parents=True, exist_ok=True)
    saved = []
    print(f'📚 批量商业图 {len(topics_desc)} 个主题 (风格: {style})...')
    for i, (topic, desc) in enumerate(topics_desc):
        print(f'\n  [{i+1}/{len(topics_desc)}] {topic}: {desc[:40]}')
        try:
            out = biz_generate(topic, desc, style=style, seed=seed + i * 37,
                               output=str(out_root / f"{topic}_{i+1:02d}.png"))
            if out:
                saved.append(out)
        except Exception as e:
            print(f'  ⚠️ 失败: {str(e)[:80]}')
    print(f'\n📁 批量输出: {out_root}（{len(saved)} 张）')
    return saved


def product_set(product_desc, style='default', seed=-1, output_dir=None,
                shots=None, no_text=True):
    """电商产品主图 5 件套（白底/场景/细节/角度/手持——多规格标准）。

    Args:
        product_desc: 产品描述
        style: 品牌风格
        shots: 选择拍摄类型（默认全部 5 张）
        output_dir: 输出目录

    Returns:
        [输出路径...]
    """
    selected = shots or list(PRODUCT_SHOTS.keys())
    out_root = Path(output_dir or (PROJECT / 'outputs' / f"biz_product_{time.strftime('%Y%m%d_%H%M%S')}"))
    out_root.mkdir(parents=True, exist_ok=True)
    saved = []
    print(f'📦 产品主图多规格 {len(selected)} 张: {", ".join(selected)}')
    for i, shot in enumerate(selected):
        if shot not in PRODUCT_SHOTS:
            print(f'  ⚠️ 未知规格 {shot}（可选: {list(PRODUCT_SHOTS.keys())}）')
            continue
        print(f'\n  [{i+1}/{len(selected)}] {shot}...')
        try:
            out = biz_generate('product', f"{product_desc}, {PRODUCT_SHOTS[shot]}",
                               style=style, seed=seed + i * 41,
                               output=str(out_root / f"{shot}.png"),
                               no_text=no_text)
            if out:
                saved.append(out)
        except Exception as e:
            print(f'  ⚠️ 失败: {str(e)[:80]}')
    print(f'\n📁 产品套图输出: {out_root}（{len(saved)} 张）')
    return saved


def make_variants(source_image, output_dir=None):
    """多尺寸适配（一张主图出多规格——封面/头像/社交/横幅/小图）。

    Args:
        source_image: 主图路径
        output_dir: 输出目录

    Returns:
        [输出路径...]
    """
    from PIL import Image
    if not os.path.exists(source_image):
        raise FileNotFoundError(f'图片不存在: {source_image}')

    out_root = Path(output_dir or (PROJECT / 'outputs' / f"biz_variants_{time.strftime('%Y%m%d_%H%M%S')}"))
    out_root.mkdir(parents=True, exist_ok=True)
    from workshop.image_utils import open_image_safe
    src = open_image_safe(source_image).convert('RGB')
    saved = []
    print(f'📐 多尺寸适配（{len(VARIANT_SIZES)} 规格）...')
    for name, (w, h) in VARIANT_SIZES.items():
        # cover（contain 居中白底）
        ratio = min(w / src.width, h / src.height)
        nw, nh = max(1, int(src.width * ratio)), max(1, int(src.height * ratio))
        resized = src.resize((nw, nh), Image.LANCZOS)
        canvas = Image.new('RGB', (w, h), (255, 255, 255))
        canvas.paste(resized, ((w - nw) // 2, (h - nh) // 2))
        out = str(out_root / f"{name}.png")
        from workshop.image_utils import save_image_with_meta
        save_image_with_meta(canvas, out, source_path=source_image,
                             extra_meta={'biz_variant': str(name)})
        saved.append(out)
        print(f'  ✅ {name}: {w}x{h}')
    print(f'\n📁 多规格输出: {out_root}（{len(saved)} 张）')
    return saved


def check_text(image_path, threshold=0.5):
    """VLM 文字检查门禁（商业图质量门禁——检测意外文字）。

    Args:
        image_path: 图片路径
        threshold: 0-1 接受阈值（默认 0.5——超过即视为有文字）

    Returns:
        (有无文字, 评分0-1)
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f'图片不存在: {image_path}')
    try:
        import base64, urllib.request
        with open(image_path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode()
        body = json.dumps({
            'model': 'qwen3-vl:8b', 'stream': False, 'think': False,
            'prompt': ('Rate 0-1 how much text/letters/numbers appear in this image '
                       '(0=no text at all, 1=lots of text). Output ONLY the number.'),
            'images': [b64],
        }).encode()
        req = urllib.request.Request('http://172.22.175.253:11434/api/generate', data=body,
                                     headers={'Content-Type': 'application/json'})
        resp = json.loads(urllib.request.urlopen(req, timeout=120).read())
        text = resp.get('response', '')
        import re
        m = re.search(r'(\d+(?:\.\d+)?)', text)
        score = float(m.group(1)) if m else 0.0
        has_text = score > threshold
        print(f'  🔤 文字检查: {"⚠️ 有文字" if has_text else "✅ 无文字"} (评分 {score:.2f})')
        return has_text, score
    except Exception as e:
        print(f'  ⚠️ 文字检查失败: {str(e)[:80]}')
        return False, 0.0


def brand_vi(brand_desc, style='default', seed=-1, output_dir=None):
    """品牌 VI 全套（logo/名片/封面/头像——统一风格品牌识别系列）。

    Args:
        brand_desc: 品牌描述
        style: 品牌风格
        output_dir: 输出目录

    Returns:
        [输出路径...]
    """
    out_root = Path(output_dir or (PROJECT / 'outputs' / f"biz_vi_{time.strftime('%Y%m%d_%H%M%S')}"))
    out_root.mkdir(parents=True, exist_ok=True)
    saved = []
    print(f'🏢 品牌 VI 全套（logo/card/cover/avatar）风格: {style}...')
    items = [
        ('logo', f"{brand_desc}, brand logo mark"),
        ('card', f"{brand_desc}, business card"),
        ('cover', f"{brand_desc}, brand article cover"),
        ('avatar', f"{brand_desc}, brand avatar"),
        ('banner', f"{brand_desc}, brand banner"),
        ('social', f"{brand_desc}, brand social media cover"),
    ]
    for i, (topic, desc) in enumerate(items):
        print(f'\n  [{i+1}/{len(items)}] {topic}...')
        try:
            out = biz_generate(topic, desc, style=style, seed=seed + i * 53,
                               output=str(out_root / f"{topic}.png"))
            if out:
                saved.append(out)
        except Exception as e:
            print(f'  ⚠️ 失败: {str(e)[:80]}')
    print(f'\n📁 VI 输出: {out_root}（{len(saved)} 张）')
    return saved


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop biz', description='商业图生成（8 主题 + 品牌风格）')
    ap.add_argument('topic', nargs='?', help='主题: ' + '/'.join(BIZ_TOPICS.keys()))
    ap.add_argument('desc', nargs='*', help='内容描述（中文）')
    ap.add_argument('--style', choices=list(BIZ_STYLES.keys()), default='default',
                    help='品牌风格')
    ap.add_argument('--size', default=None, help='自定义尺寸 WxH（如 1200x800）')
    ap.add_argument('--allow-text', action='store_true', help='允许文字（默认无文字铁律）')
    ap.add_argument('--output', default=None, help='输出路径/目录')
    ap.add_argument('--seed', type=int, default=-1)
    ap.add_argument('--batch', default=None,
                    help='批量模式: "主题1:描述1,主题2:描述2"（统一风格）')
    ap.add_argument('--product-set', action='store_true',
                    help='产品主图 5 件套（白底/场景/细节/角度/手持）')
    ap.add_argument('--shots', default=None,
                    help='产品套图选择（逗号分隔，如 white,scene）')
    ap.add_argument('--variants', default=None,
                    help='多尺寸适配（对已生成主图，输出 5 规格）')
    ap.add_argument('--check-text', default=None,
                    help='VLM 文字检查（图片路径——质量门禁）')
    ap.add_argument('--social', action='store_true',
                    help='社交封面主题（3:4 小红书/朋友圈）')
    ap.add_argument('--vi', action='store_true',
                    help='品牌 VI 全套（logo/名片/封面/头像）')
    ap.add_argument('--resume', action='store_true',
                    help='简历头像（职业正装 1:1——求职场景）')
    ap.add_argument('--poster-template', choices=list(POSTER_TEMPLATES.keys()), default=None,
                    help='海报模板（新品/招聘/节日/活动/感恩）')
    ap.add_argument('--banner-template', choices=list(BANNER_TEMPLATES.keys()), default=None,
                    help='Banner 模板（大促/上新/品牌/节日）')
    args = ap.parse_args(argv)

    # 文字检查门禁
    if args.check_text:
        check_text(args.check_text)
        return 0

    # 多尺寸适配
    if args.variants:
        try:
            make_variants(args.variants, output_dir=args.output)
            return 0
        except Exception as e:
            print(f'❌ 多尺寸适配失败: {str(e)[:150]}')
            return 1

    # 产品主图 5 件套
    if args.product_set:
        if not args.desc:
            print('用法: biz --product-set "产品描述" [--shots white,scene]')
            return 1
        shots = args.shots.split(',') if args.shots else None
        try:
            product_set(' '.join(args.desc), style=args.style, seed=args.seed,
                        output_dir=args.output, shots=shots,
                        no_text=not args.allow_text)
            return 0
        except Exception as e:
            print(f'❌ 产品套图失败: {str(e)[:150]}')
            return 1

    # 批量模式
    if args.batch:
        try:
            topics = []
            for seg in args.batch.split(','):
                if ':' in seg:
                    t, d = seg.split(':', 1)
                    topics.append((t.strip(), d.strip()))
                else:
                    topics.append((seg.strip(), args.desc and ' '.join(args.desc) or ''))
            batch_biz(topics, style=args.style, seed=args.seed, output_dir=args.output)
            return 0
        except Exception as e:
            print(f'❌ 批量失败: {str(e)[:150]}')
            return 1

    # 海报模板（--poster-template 时 topic 强制 poster）
    if args.poster_template:
        if not args.desc:
            print('用法: biz --poster-template new_product "产品描述"')
            return 1
        try:
            tpl_prompt = POSTER_TEMPLATES[args.poster_template]
            biz_generate('poster', f"{' '.join(args.desc)}, {tpl_prompt}",
                         style=args.style, seed=args.seed, output=args.output,
                         no_text=not args.allow_text)
            return 0
        except Exception as e:
            print(f'❌ 海报模板失败: {str(e)[:150]}')
            return 1

    # Banner 模板
    if args.banner_template:
        if not args.desc:
            print('用法: biz --banner-template sale "产品描述"')
            return 1
        try:
            tpl_prompt = BANNER_TEMPLATES[args.banner_template]
            biz_generate('banner', f"{' '.join(args.desc)}, {tpl_prompt}",
                         style=args.style, seed=args.seed, output=args.output,
                         no_text=not args.allow_text)
            return 0
        except Exception as e:
            print(f'❌ Banner 模板失败: {str(e)[:150]}')
            return 1

    # 品牌 VI 全套
    if args.vi:
        if not args.desc:
            print('用法: biz --vi "品牌描述" [--style 风格]')
            return 1
        try:
            brand_vi(' '.join(args.desc), style=args.style, seed=args.seed,
                     output_dir=args.output)
            return 0
        except Exception as e:
            print(f'❌ VI 生成失败: {str(e)[:150]}')
            return 1

    # 简历头像
    if args.resume:
        if not args.desc:
            print('用法: biz --resume "形象描述"（如 年轻男程序员浅蓝衬衫）')
            return 1
        try:
            biz_generate('avatar', f"{' '.join(args.desc)}, professional business headshot, formal attire, clean solid background, front-facing, passport photo style, high resolution",
                         style='default', seed=args.seed, output=args.output,
                         no_text=True, custom_size=(1024, 1024))
            return 0
        except Exception as e:
            print(f'❌ 简历头像失败: {str(e)[:150]}')
            return 1

    # 社交封面模式
    if args.social:
        if not args.desc:
            print('用法: biz --social "内容描述" [--style 风格]')
            return 1
        try:
            biz_generate('social', ' '.join(args.desc), style=args.style,
                         seed=args.seed, output=args.output,
                         no_text=not args.allow_text,
                         custom_size=SOCIAL_TOPIC["size"])
            return 0
        except Exception as e:
            print(f'❌ 社交封面失败: {str(e)[:150]}')
            return 1

    if not args.topic or not args.desc:
        print('用法: biz <主题> "描述" [--style 风格]')
        print(f'      主题: {list(BIZ_TOPICS.keys())}')
        print(f'      风格: {list(BIZ_STYLES.keys())}')
        print('      批量: biz --batch "avatar:程序员头像,cover:技术博客封面"')
        return 1

    custom = None
    if args.size:
        try:
            w, h = args.size.split('x')
            custom = (int(w), int(h))
        except Exception:
            print('❌ --size 格式: 1200x800')
            return 1

    try:
        biz_generate(args.topic, ' '.join(args.desc), style=args.style,
                     seed=args.seed, output=args.output,
                     no_text=not args.allow_text, custom_size=custom)
        return 0
    except Exception as e:
        print(f'❌ 商业图失败: {str(e)[:150]}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
