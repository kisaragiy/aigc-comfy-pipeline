#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/kb.py — 审美知识库检查器（B-kb）v1.0
==============================================
把"好看"标准写成可执行规则（kb_rules.json），双引擎检查：
  - VLM 规则：自然语言 prompt → qwen3-vl 0-1 评分
  - 像素规则：PIL/numpy 直接计算（分辨率/亮度/死黑死白）

用法:
  python -m agents workshop kb list [--category 构图]
  python -m agents workshop kb check <图> [--category 色彩] [--rules COMP-01,LIGHT-01] [--threshold 0.6]
  python -m agents workshop kb report <图>   （详细报告含建议）
"""

import argparse, json, os, sys, time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
RULES_PATH = Path(__file__).resolve().parent / 'kb_rules.json'

# VLM 评分方向：prompt 问"越高越好"的规则（正向） vs "越高越差"（反向）
# 反向规则（score=1-raw）: COMP-02(裁切), TECH-03(文字), STYLE-01(签名)
INVERT_RULES = {'COMP-02', 'TECH-03', 'STYLE-01'}


def _load_rules():
    with open(RULES_PATH, encoding='utf-8') as f:
        return json.load(f)


def _vlm_score(prompt, image_path):
    """qwen3-vl 本地 VLM 评分 0-1（0 token 成本）。"""
    import base64, re, urllib.request
    with open(image_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode()
    body = json.dumps({
        'model': 'qwen3-vl:8b', 'stream': False, 'think': False,
        'prompt': f'{prompt} Output ONLY the number between 0 and 1.',
        'images': [b64],
    }).encode()
    req = urllib.request.Request('http://172.22.175.253:11434/api/generate', data=body,
                                 headers={'Content-Type': 'application/json'})
    resp = json.loads(urllib.request.urlopen(req, timeout=120).read())
    text = resp.get('response', '')
    m = re.search(r'(\d+(?:\.\d+)?)', text)
    return float(m.group(1)) if m else 0.5


def _pixel_check(rule, image_path):
    """像素规则检查。"""
    from PIL import Image
    from workshop.image_utils import open_image_safe
    import numpy as np
    img = np.array(open_image_safe(image_path).convert('L'))
    h, w = img.shape
    r = rule['id']
    if r == 'TECH-01':  # 分辨率达标
        score = 1.0 if min(w, h) >= 512 else min(w, h) / 512
    elif r == 'COLOR-04':  # 对比度：直方图三段分布均衡
        hist, _ = np.histogram(img, bins=16, range=(0, 256))
        total = hist.sum() + 1e-6
        dark = hist[:4].sum() / total
        mid = hist[4:12].sum() / total
        bright = hist[12:].sum() / total
        # 理想：中间调占比高，暗亮不过分极端
        score = min(1.0, mid / 0.5) * (1.0 - abs(dark - 0.2)) * (1.0 - abs(bright - 0.2))
        score = max(0.0, min(1.0, score))
    elif r == 'LIGHT-03':  # 无过曝死黑
        dead_black = (img < 10).mean()
        dead_white = (img > 245).mean()
        score = 1.0 - min(1.0, (dead_black + dead_white) / 0.1)
    else:
        score = 0.5
    return score


def check_image(image_path, category=None, rules=None, threshold=0.6):
    """对图片跑审美知识库检查。

    Args:
        image_path: 图片路径
        category: 只查某类（构图/色彩/光影/造型/技术/风格）
        rules: 指定规则 id 列表（逗号分隔）
        threshold: 通过阈值

    Returns:
        (总评分, [规则结果...])
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f'图片不存在: {image_path}')
    if not 0 <= threshold <= 1:
        raise ValueError(f'阈值应在 [0, 1]（当前: {threshold}）')

    db = _load_rules()
    all_rules = db['rules']
    if category:
        all_rules = [r for r in all_rules if r['category'] == category]
    if rules:
        ids = set(x.strip() for x in rules.split(','))
        all_rules = [r for r in all_rules if r['id'] in ids]
    if not all_rules:
        raise ValueError('无匹配规则')

    results = []
    vlm_rules = [r for r in all_rules if r['type'] == 'vlm' and r.get('enabled', True)]
    pixel_rules = [r for r in all_rules if r['type'] == 'pixel' and r.get('enabled', True)]

    # 像素规则（本地计算，快）
    for r in pixel_rules:
        raw = _pixel_check(r, image_path)
        score = 1.0 - raw if r['id'] in INVERT_RULES else raw
        results.append({'id': r['id'], 'category': r['category'], 'name': r['name'],
                        'desc': r['desc'], 'score': round(score, 2),
                        'pass': score >= threshold, 'type': 'pixel'})
        print(f"  {'✅' if score >= threshold else '❌'} [{r['id']}] {r['name']}: {score:.2f}")

    # VLM 规则（本地 qwen3-vl，0 token）
    for r in vlm_rules:
        raw = _vlm_score(r['prompt'], image_path)
        score = 1.0 - raw if r['id'] in INVERT_RULES else raw
        results.append({'id': r['id'], 'category': r['category'], 'name': r['name'],
                        'desc': r['desc'], 'score': round(score, 2),
                        'pass': score >= threshold, 'type': 'vlm'})
        print(f"  {'✅' if score >= threshold else '❌'} [{r['id']}] {r['name']}: {score:.2f}")

    if not results:
        print('  ⚠️ 无规则可跑')
        return 0.0, []

    # 加权总评分
    total_w = sum(r.get('weight', 1.0) for r in all_rules)
    total = sum(res['score'] * all_rules[[x['id'] for x in all_rules].index(res['id'])].get('weight', 1.0)
                for res in results) / total_w if total_w else 0
    print(f'\n  📊 总评分: {total:.2f} / 1.00（阈值 {threshold}）')
    return round(total, 2), results


def list_rules(category=None):
    """列出知识库规则。"""
    db = _load_rules()
    rules = db['rules']
    if category:
        rules = [r for r in rules if r['category'] == category]
    print(f"\n📚 审美知识库 v{db['version']}（{len(rules)} 条规则）")
    print(f"  {'ID':<12} {'类别':<6} {'名称':<14} {'类型':<6} {'权重':<5} 描述")
    print(f"  {'-' * 80}")
    cats = {}
    for r in rules:
        cats.setdefault(r['category'], []).append(r)
        print(f"  {r['id']:<12} {r['category']:<6} {r['name']:<14} {r['type']:<6} {r.get('weight',1.0):<5.1f} {r['desc'][:30]}")
    print(f"\n  类别分布: {', '.join(f'{k}({len(v)})' for k, v in cats.items())}")
    return rules


def report_image(image_path, threshold=0.6):
    """详细报告（含违规项建议）。"""
    print(f'\n🔍 审美检查报告: {os.path.basename(image_path)}')
    total, results = check_image(image_path, threshold=threshold)
    failed = [r for r in results if not r['pass']]
    print(f'\n  ⚠️ 违规 {len(failed)} 项:')
    for r in failed:
        print(f"    ❌ [{r['id']}] {r['name']}: {r['score']:.2f}")
        print(f"       建议: {r['desc']}")
    if not failed:
        print(f'    🎉 全部通过——审美达标')
    return total, results


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop kb', description='审美知识库（可执行审美规则检查）')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p_list = sub.add_parser('list', help='列出规则')
    p_list.add_argument('--category', default=None, help='类别过滤')

    p_check = sub.add_parser('check', help='检查图片')
    p_check.add_argument('image')
    p_check.add_argument('--category', default=None, help='类别过滤')
    p_check.add_argument('--rules', default=None, help='指定规则 COMP-01,LIGHT-01')
    p_check.add_argument('--threshold', type=float, default=0.6)

    p_report = sub.add_parser('report', help='详细报告')
    p_report.add_argument('image')
    p_report.add_argument('--threshold', type=float, default=0.6)

    args = ap.parse_args(argv)

    try:
        if args.cmd == 'list':
            list_rules(args.category)
        elif args.cmd == 'check':
            check_image(args.image, category=args.category, rules=args.rules,
                        threshold=args.threshold)
        elif args.cmd == 'report':
            report_image(args.image, threshold=args.threshold)
        return 0
    except Exception as e:
        print(f'❌ kb 失败: {str(e)[:150]}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
