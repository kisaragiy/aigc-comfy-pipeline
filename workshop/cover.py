#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/cover.py — B站视频封面生成（B-cover）v1.0
====================================================
B站 UP 主最高频生图场景：视频封面 = 点击率的 80%。
封面要素（B站爆款封面规律）：
  1. 16:9 高清（B站封面标准比例 1920x1080）
  2. 高冲击力构图（主体大、对比强、情绪浓）
  3. 文字留白区（标题位置——B站封面强制叠标题，主体不能占满）
  4. 面部/情绪优先（人像封面点击率 > 风景）

用法:
  python -m agents workshop cover "描述" [--title 标题文字] [--output 路径]
      # 生成 16:9 封面（自动留白 + 可选标题文字渲染）
"""

import argparse, json, os, re, sys, time, urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent

# ── 封面类型规格（B站实证：视频封面 16:9 / 直播封面 16:9 横 / 小说封面 2:3 竖）──
COVER_TYPES = {
    "video": (1344, 768,  "video cover art, 16:9 widescreen, high impact"),
    "live":  (1344, 768,  "live stream cover art, 16:9 widescreen, eye-catching, vibrant"),
    "novel": (768, 1152,  "novel cover art, 2:3 vertical, dramatic composition, mysterious atmosphere"),
    "poster": (896, 1344, "poster design, A4 vertical, professional layout, striking visual centerpiece, modern graphic design, space for typography at top and bottom"),
    # 商业图扩展（轻小说插画/游戏宣传）
    "illustration": (1024, 1536, "light novel illustration, 2:3 vertical, character in scene, story moment, atmospheric background with detailed scenery, cinematic lighting, detailed rendering, professional anime illustration, rich background environment, setting details"),
    "game_kv": (1344, 768, "game key visual, 16:9 widescreen, epic promotional art, main character center stage, dramatic scene background, cinematic composition, AAA game art quality, logo space reserved"),
}

# 封面构图增强（高冲击力）：主体放大 + 强对比 + 情绪
_COVER_STYLE = (
    "video cover art, youtube thumbnail style, high impact composition, "
    "subject occupying 60-70% of frame, dramatic lighting, high contrast, "
    "strong rim light, vivid saturated colors, expressive face close-up, "
    "dynamic angle, professional clickbait thumbnail, 16:9 widescreen"
)

# 留白区（标题位）配置：左上角 40% 区域做暗化处理（让白字可读）
_TITLE_ZONE = (0.05, 0.05, 0.55, 0.28)  # (x%, y%, w%, h%)


def _norm(p):
    p = os.path.expanduser(p)
    m = re.match(r'^/([a-zA-Z])/(.*)$', p)
    if m:
        p = m.group(1) + ':/' + m.group(2)
    return p


def _http():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _submit(wf, timeout=300):
    """提交工作流，等结果，返回输出文件列表"""
    COMFY = 'http://127.0.0.1:8188'
    # 队列深度检查：排队任务太多时提前告知（避免"等不到就超时"假失败）
    try:
        q = json.loads(_http().open(COMFY + '/queue', timeout=5).read())
        n_run = len(q.get('queue_running', []))
        n_pend = len(q.get('queue_pending', []))
        if n_pend > 0:
            print(f'  ⏳ ComfyUI 队列: 运行中 {n_run}，等待 {n_pend}（预计需排队等待）')
    except Exception:
        pass
    body = json.dumps({'prompt': wf}).encode()
    req = urllib.request.Request(COMFY + '/prompt', data=body,
                                 headers={'Content-Type': 'application/json'})
    r = json.loads(_http().open(req, timeout=30).read())
    if 'error' in r:
        raise RuntimeError(str(r['error'])[:200])
    pid = r['prompt_id']
    # 超时考虑排队：等待时间 = timeout + 排队任务数 × 每张预估 90s
    est = timeout + n_pend * 90 if 'n_pend' in dir() else timeout
    deadline = time.time() + est
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
    raise TimeoutError(f'生成超时（等待 {int(est)}s 仍无输出，队列可能拥堵）')


def _build_cover_wf(prompt, negative, seed, width=1344, height=768):
    """SDXL 封面工作流（waiIllustrious + 高冲击力风格，16:9 或 2:3）"""
    wf = {}
    wf['1'] = {'class_type': 'CheckpointLoaderSimple',
               'inputs': {'ckpt_name': 'waiIllustriousSDXL_v160.safetensors'}}
    wf['2'] = {'class_type': 'CLIPTextEncode',
               'inputs': {'text': prompt, 'clip': ['1', 1]}}
    wf['3'] = {'class_type': 'CLIPTextEncode',
               'inputs': {'text': negative or ('worst quality, blurry, low quality, watermark, text, '
                            'bad anatomy, bad hands, extra fingers, fused fingers, missing fingers, '
                            'extra limbs, deformed face, mutated hands, bad proportions, '
                            'duplicate, cropped, jpeg artifacts, signature'), 'clip': ['1', 1]}}
    wf['4'] = {'class_type': 'EmptyLatentImage',
               'inputs': {'width': width, 'height': height, 'batch_size': 1}}
    wf['5'] = {'class_type': 'KSampler',
               'inputs': {'model': ['1', 0], 'positive': ['2', 0], 'negative': ['3', 0],
                          'latent_image': ['4', 0], 'seed': seed, 'steps': 28, 'cfg': 6.5,
                          'sampler_name': 'dpmpp_2m', 'scheduler': 'karras', 'denoise': 1.0}}
    wf['6'] = {'class_type': 'VAEDecode', 'inputs': {'samples': ['5', 0], 'vae': ['1', 2]}}
    wf['7'] = {'class_type': 'SaveImage',
               'inputs': {'images': ['6', 0], 'filename_prefix': 'cover'}}
    return wf


def _add_title_zone(image_path, output_path, title=None, subtitle=None, ctype="video"):
    """叠加标题留白区（左上暗化 + 可选标题文字渲染）。

    poster 类型：大标题（占宽 80%）+ 底部副标题区（海报排版）
    """
    from PIL import Image, ImageDraw, ImageFont, ImageEnhance

    img = Image.open(image_path).convert('RGB')
    w, h = img.size
    # 左上角暗化（文字可读区）
    zone = (int(w * _TITLE_ZONE[0]), int(h * _TITLE_ZONE[1]),
            int(w * _TITLE_ZONE[2]), int(h * _TITLE_ZONE[3]))
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle(zone, radius=12, fill=(0, 0, 0, 140))
    img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')

    # 标题文字（poster 类型左上角不画小标题——避免与底部大标题重复，VLM 实测发现）
    if title and ctype != "poster":
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", int(h * 0.06))
        except OSError:
            try:
                font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", int(h * 0.06))
            except OSError:
                font = ImageFont.load_default()
        # 自动换行（按 45% 宽）
        max_chars = int(w * 0.40 / (h * 0.06))
        lines = [title[i:i + max_chars] for i in range(0, len(title), max_chars)]
        lines = lines[:2]
        text_y = zone[1] + int(h * 0.02)
        for line in lines:
            draw.text((zone[0] + int(w * 0.02), text_y), line,
                      fill=(255, 255, 255), font=font, stroke_width=3, stroke_fill=(0, 0, 0))
            text_y += int(h * 0.07)

    # poster 底部副标题（海报排版：大标题 + 底部信息区）
    if ctype == "poster" and title:
        draw = ImageDraw.Draw(img)
        try:
            font_big = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", int(h * 0.09))
        except OSError:
            font_big = ImageFont.load_default()
        # 底部暗化条（信息区）
        bar_h = int(h * 0.18)
        draw.rectangle([0, h - bar_h, w, h], fill=(0, 0, 0, 160))
        # 大标题居中偏下
        big_title = title if len(title) <= 8 else title[:8] + "…"
        tw = draw.textlength(big_title, font=font_big)
        draw.text(((w - tw) // 2, h - bar_h + int(bar_h * 0.2)), big_title,
                  fill=(255, 255, 255), font=font_big, stroke_width=3, stroke_fill=(0, 0, 0))
        # 副标题小字
        if subtitle:
            try:
                font_sub = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", int(h * 0.035))
            except OSError:
                font_sub = ImageFont.load_default()
            stw = draw.textlength(subtitle, font=font_sub)
            draw.text(((w - stw) // 2, h - bar_h + int(bar_h * 0.55)), subtitle,
                      fill=(230, 230, 230), font=font_sub)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path)
    return output_path


def generate_cover(desc, title=None, seed=-1, output=None, negative=None, ctype="video",
                   subtitle=None, series=1, verify=False, outfit_style=None, kb_check=False):
    """生成封面（视频/直播/小说/海报/插画/游戏KV）。

    ctype: video(16:9 视频封面) / live(16:9 直播封面) / novel(2:3 小说封面) / poster(A4 海报)
           / illustration(2:3 轻小说插画) / game_kv(16:9 游戏宣传主视觉)
    series: 批量生成 N 张（同 prompt 不同 seed，系列封面）
    verify: 系列一致性 VLM 检查（series>1 时，用首张做锚验证其余）
    outfit_style: 服装风格名（wardrobe 风格如 gothic/arknight——封面角色穿风格服装）

    Returns:
        [输出路径...]
    """
    if ctype not in COVER_TYPES:
        print(f"⚠️ 未知类型 {ctype}，可选: {list(COVER_TYPES.keys())}")
        return []
    width, height, type_style = COVER_TYPES[ctype]
    # 复杂场景聚焦标记（COMM-4 实测：多主体 SDXL 只抓最强元素）——翻译后追加聚焦指令
    need_focus = (ctype == 'game_kv' and len(desc) > 15)
    # 服装风格展开（封面角色穿指定风格服装——wardrobe 联动）
    if outfit_style:
        try:
            from workshop.wardrobe import build_outfit
            desc = f'{desc}, {build_outfit(outfit_style)}'
            print(f'  👗 服装风格: {outfit_style}（已展开）')
        except Exception as e:
            print(f'  ⚠️ 服装风格展开失败: {str(e)[:60]}')
    # 中文翻译（SDXL 对中文理解差）
    try:
        from workshop.layer import _translate_desc
        desc_en = _translate_desc(desc)
        if desc_en != desc:
            print(f'  封面 prompt(英文): {desc_en[:100]}')
    except Exception:
        desc_en = desc

    # 游戏 KV 复杂场景聚焦（翻译后追加——避免中文混入）
    if need_focus:
        desc_en = (f'{desc_en}, focus on the main character, '
                   'single hero center composition, clear subject, '
                   'other elements as background')
        print('  🎯 游戏 KV 已自动聚焦主角色（SDXL 多主体局限规避）')

    full_prompt = f"{desc_en}, {type_style}, {_COVER_STYLE}"
    base_seed = seed if seed >= 0 else int(time.time()) % 2**31
    out_paths = []
    for i in range(max(1, series)):
        s = base_seed + i * 13
        wf = _build_cover_wf(full_prompt, negative, s, width, height)
        print(f'  提交封面工作流 ({ctype} {width}x{height}, seed={s})...')
        # 自动重试：超时/失败重试最多 2 次（队列拥堵/显存累积是常见假失败）
        files = None
        for attempt in range(3):
            try:
                files = _submit(wf, timeout=600)
                break
            except Exception as e:
                if attempt < 2:
                    wait = 20 * (attempt + 1)
                    print(f'  ⚠️ 第{i+1}张第{attempt+1}次失败: {str(e)[:60]} → {wait}s 后重试（先等队列清空防双份）')
                    time.sleep(wait)
                    # 重试前等队列清空（避免上次提交还在执行导致双份僵尸任务）
                    for _ in range(30):
                        try:
                            q = json.loads(_http().open('http://127.0.0.1:8188/queue', timeout=5).read())
                            if not q.get('queue_running') and not q.get('queue_pending'):
                                break
                        except Exception:
                            break
                        time.sleep(10)
                else:
                    print(f'  ⚠️ 第{i+1}张失败(3次): {str(e)[:80]}')
        if not files:
            continue

        # 从 ComfyUI 输出复制
        COMFY_OUTPUT = r'C:\DrawingLive\ComfyUI\output'
        src = os.path.join(COMFY_OUTPUT, files[0])
        if not os.path.exists(src):
            print(f'  ⚠️ 输出文件不存在: {src}')
            continue

        if series > 1:
            out_path = output or str(PROJECT / 'outputs' / f"cover_{ctype}_{time.strftime('%Y%m%d_%H%M%S')}_{i+1}.png")
        else:
            out_path = output or str(PROJECT / 'outputs' / f"cover_{time.strftime('%Y%m%d_%H%M%S')}.png")
        _add_title_zone(src, out_path, title, subtitle=subtitle, ctype=ctype)
        print(f'  🎨 封面 {i+1}/{series}: {out_path}')
        out_paths.append(out_path)

    if title:
        print(f'  📝 已渲染标题: {title}')
    if subtitle:
        print(f'  📝 副标题: {subtitle}')

    # 系列一致性 VLM 检查（用首张做锚验证其余——角色/风格是否一致）
    if verify and len(out_paths) > 1:
        try:
            from workshop.oc import verify_consistency_paths
            ok, detail = verify_consistency_paths(out_paths)
            print(f'  🔍 系列一致性: {"✅ " + detail if ok else "⚠️ " + detail}')
        except Exception as e:
            print(f'  ⚠️ 一致性检查不可用: {str(e)[:60]}')

    # 商业图 kb 质量门禁（构图/色彩/光影/技术/服装/吸引力全规则检查）
    if kb_check and out_paths:
        try:
            from workshop.kb import check_image
            for p_ in out_paths:
                score, detail = check_image(p_)
                flag = '✅' if score >= 0.6 else '❌'
                print(f'  {flag} kb 质量门禁 {os.path.basename(p_)}: {score:.2f}（阈值 0.6）')
        except Exception as e:
            print(f'  ⚠️ kb 门禁不可用: {str(e)[:60]}')

    print(f'  💡 提示: B站封面建议 1920x1080，上传时裁剪到 16:9')
    return out_paths


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop cover', description='封面生成（视频/直播/小说）')
    ap.add_argument('desc', nargs='*', help='封面内容描述')
    ap.add_argument('--title', default=None, help='封面标题文字（自动留白+渲染）')
    ap.add_argument('--subtitle', default=None, help='副标题（poster 海报用）')
    ap.add_argument('--type', choices=list(COVER_TYPES.keys()), default='video',
                    help='类型: video(16:9)/live(直播16:9)/novel(小说2:3)/poster(海报A4)')
    ap.add_argument('--output', default=None, help='输出路径')
    ap.add_argument('--seed', type=int, default=-1)
    ap.add_argument('--series', type=int, default=1, help='批量生成 N 张（系列封面，不同 seed）')
    ap.add_argument('--verify', action='store_true', help='系列一致性 VLM 检查（series>1 时）')
    ap.add_argument('--check', dest='kb_check', action='store_true', help='生成后 kb 质量门禁（29 规则全检查）')
    ap.add_argument('--outfit', default=None, help='服装风格名（wardrobe：gothic/arknight 等——封面角色穿风格服装）')
    args = ap.parse_args(argv)

    desc = ' '.join(args.desc)
    if not desc:
        print('用法: cover "描述" [--title "标题"] [--type video|live|novel|poster] [--subtitle] [--series N]')
        return 1
    try:
        generate_cover(desc, title=args.title, seed=args.seed, output=args.output,
                       ctype=args.type, subtitle=args.subtitle, series=args.series,
                       verify=args.verify, outfit_style=args.outfit, kb_check=args.kb_check)
        return 0
    except Exception as e:
        print(f'❌ 封面生成失败: {str(e)[:150]}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
