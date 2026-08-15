#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/finalcheck.py — 终检清单（画师 final pass 的自动化版）v1.0
====================================================================
画师收尾检查: 退后一步看整体——透视/比例/光影/边缘/色彩/崩坏。
自动化: VLM 六项检查 → PASS/FAIL + 建议 + 总分。

用法:
  python -m agents workshop finalcheck <图片> [--ref 参考图] [--threshold 7.0]
      [--fix 建议自动转 fix/notes]
"""

import argparse, json, os, re, sys, urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
OLLAMA = os.environ.get('FINALCHECK_OLLAMA', 'http://172.22.175.253:11434')

FINAlCHECK_PROMPT = '''Review this illustration as a professional art director (final pass).
Check these 6 aspects, output ONLY a JSON array:
[{"item":"perspective","score":0,"pass":true,"issue":"","suggestion":""},
 {"item":"proportion","score":0,"pass":true,"issue":"","suggestion":""},
 {"item":"lighting","score":0,"pass":true,"issue":"","suggestion":""},
 {"item":"edges","score":0,"pass":true,"issue":"","suggestion":""},
 {"item":"color","score":0,"pass":true,"issue":"","suggestion":""},
 {"item":"anatomy","score":0,"pass":true,"issue":"","suggestion":""}]
Score 0-10, pass if >=7. issue=specific problem, suggestion=actionable fix. JSON only.'''

_ITEM_CN = {'perspective': '透视', 'proportion': '比例', 'lighting': '光影',
            'edges': '边缘', 'color': '色彩', 'anatomy': '崩坏',
            'composition': '构图', 'symmetry': '对称'}

# M2: 倒置/镜像检查 prompt（画师技法：倒置看构图平衡，镜像看对称）
FLIP_CHECK_PROMPT = '''You are a professional art director doing the "flip test" (画师倒置/镜像检查法).
Image 1 = artwork flipped upside down (构图平衡测试——倒置后构图失衡会暴露).
Image 2 = artwork mirrored horizontally (对称/习惯手测试——镜像后不对称/左右失衡会暴露).
Evaluate ONLY these 2 aspects, output ONLY a JSON array:
[{"item":"composition","score":0,"pass":true,"issue":"","suggestion":""},
 {"item":"symmetry","score":0,"pass":true,"issue":"","suggestion":""}]
Score 0-10, pass if >=7. composition = 倒置后是否仍有平衡构图（无元素悬空/重心失衡）.
symmetry = 镜像后是否左右平衡（无单侧过重/视线被拉偏）. JSON only.'''

# M3: 焦点引导检查 prompt（画师技法：一眼看到主体）
FOCUS_CHECK_PROMPT = '''You are a professional art director checking visual hierarchy (焦点引导).
Image = the artwork. Evaluate: 主体是否一眼可见? 视觉层级是否清晰（主体>次要素>背景）?
亮度/对比/边缘引导是否把视线引向主体? Output ONLY a JSON array:
[{"item":"focus","score":0,"pass":true,"issue":"","suggestion":""}]
Score 0-10, pass if >=7. issue=specific problem, suggestion=actionable fix. JSON only.'''


def _flip_variants(path, max_dim=768):
    """生成倒置 + 镜像变体（画师 flip test）→ 返回 base64 列表"""
    import base64, io
    from PIL import Image
    img = Image.open(path)
    if max(img.size) > max_dim:
        r = max_dim / max(img.size)
        img = img.resize((int(img.width * r), int(img.height * r)), Image.LANCZOS)
    flipped = img.transpose(Image.FLIP_TOP_BOTTOM)   # 倒置
    mirrored = img.transpose(Image.FLIP_LEFT_RIGHT)  # 镜像
    out = []
    for v in (flipped, mirrored):
        buf = io.BytesIO()
        v.save(buf, format='PNG')
        out.append(base64.b64encode(buf.getvalue()).decode())
    return out


def _vlm_json(images, prompt):
    """VLM 生成 JSON 结果（复用 finalcheck 的 ollama 调用模式）"""
    body = json.dumps({
        'model': 'qwen3-vl:8b', 'stream': False, 'think': False,
        'options': {'temperature': 0.1},
        'prompt': prompt, 'images': images,
    }).encode()
    req = urllib.request.Request(OLLAMA + '/api/generate', data=body,
                                 headers={'Content-Type': 'application/json'})
    resp = json.loads(_http().open(req, timeout=240).read())
    out = resp.get('response', '')
    m = re.search(r'\[[\s\S]*\]', out)
    if not m:
        return []
    try:
        items = json.loads(m.group(0))
        return [it for it in items if isinstance(it, dict) and it.get('item')]
    except Exception:
        return []


def flipcheck(image_path, verbose=True):
    """M2: 倒置/镜像检查 → 返回 (items, total)"""
    variants = _flip_variants(image_path)
    items = _vlm_json(variants, FLIP_CHECK_PROMPT)
    total = sum(it.get('score', 0) for it in items) / len(items) if items else 0
    if verbose and items:
        for it in items:
            mark = '✅' if it.get('pass') else '❌'
            cn = _ITEM_CN.get(it.get('item'), it.get('item'))
            print(f"{mark} {cn}: {it.get('score',0)}/10")
            if it.get('issue'):
                print(f"     ↳ {it.get('issue','')[:100]}")
            if it.get('suggestion'):
                print(f"     ↳ 建议: {it.get('suggestion','')[:120]}")
    return items, total


def focuscheck(image_path, verbose=True):
    """M3: 焦点引导检查 → 返回 (items, total)"""
    items = _vlm_json([_encode_img(image_path)], FOCUS_CHECK_PROMPT)
    total = sum(it.get('score', 0) for it in items) / len(items) if items else 0
    if verbose and items:
        for it in items:
            mark = '✅' if it.get('pass') else '❌'
            print(f"{mark} 焦点引导: {it.get('score',0)}/10")
            if it.get('issue'):
                print(f"     ↳ {it.get('issue','')[:100]}")
            if it.get('suggestion'):
                print(f"     ↳ 建议: {it.get('suggestion','')[:120]}")
    return items, total

def _http():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))

def _encode_img(path, max_dim=768):
    import base64, io
    from PIL import Image
    img = Image.open(path)
    if max(img.size) > max_dim:
        r = max_dim / max(img.size)
        img = img.resize((int(img.width * r), int(img.height * r)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode()

def finalcheck(image_path, ref_path=None, verbose=True):
    """VLM 六项终检 → 返回 (items, total_score)"""
    images = [_encode_img(image_path)]
    if ref_path and os.path.exists(ref_path):
        images.append(_encode_img(ref_path))
        prompt = FINAlCHECK_PROMPT + '\nImage 1 = final artwork, Image 2 = reference (compare consistency).'
    else:
        prompt = FINAlCHECK_PROMPT
    body = json.dumps({
        'model': 'qwen3-vl:8b', 'stream': False, 'think': False,
        'options': {'temperature': 0.1},
        'prompt': prompt, 'images': images,
    }).encode()
    req = urllib.request.Request(OLLAMA + '/api/generate', data=body,
                                 headers={'Content-Type': 'application/json'})
    resp = json.loads(_http().open(req, timeout=240).read())
    out = resp.get('response', '')
    m = re.search(r'\[[\s\S]*\]', out)
    if not m:
        return [], 0.0
    try:
        items = json.loads(m.group(0))
    except Exception:
        return [], 0.0
    items = [it for it in items if isinstance(it, dict) and it.get('item')]
    total = sum(it.get('score', 0) for it in items) / len(items) if items else 0
    if verbose:
        for it in items:
            mark = '✅' if it.get('pass') else '❌'
            cn = _ITEM_CN.get(it.get('item'), it.get('item'))
            print(f"{mark} {cn}: {it.get('score',0)}/10")
            if it.get('issue'):
                print(f"     ↳ {it.get('issue','')[:100]}")
            if it.get('suggestion'):
                print(f"     ↳ 建议: {it.get('suggestion','')[:120]}")
        print(f'\n# 总分: {total:.1f}/10')
    return items, total

def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop finalcheck', description='终检清单（画师 final pass）')
    ap.add_argument('image', help='待检图片')
    ap.add_argument('--ref', default=None, help='参考图（对比一致性）')
    ap.add_argument('--threshold', type=float, default=7.0, help='通过阈值（默认 7.0）')
    ap.add_argument('--flip', action='store_true', help='M2 倒置/镜像检查（画师 flip test）')
    ap.add_argument('--focus', action='store_true', help='M3 焦点引导检查（视觉层级）')
    ap.add_argument('--json', action='store_true', help='JSON 输出')
    args = ap.parse_args(argv)

    img = os.path.expanduser(args.image)
    m = re.match(r'^/([a-zA-Z])/(.*)$', img)
    if m:
        img = m.group(1) + ':/' + m.group(2)
    if not os.path.exists(img):
        print(f'图片不存在: {img}')
        return

    items, total = finalcheck(img, args.ref)
    if not items:
        print('⚠️ VLM 无有效输出（重试或检查 ollama）')
        return
    # M2: 倒置/镜像检查（画师 flip test）
    flip_items, flip_total = [], 0.0
    if args.flip:
        print('\n# M2 倒置/镜像检查（flip test）')
        flip_items, flip_total = flipcheck(img, verbose=not args.json)
    # M3: 焦点引导检查
    focus_items, focus_total = [], 0.0
    if args.focus:
        print('\n# M3 焦点引导检查（视觉层级）')
        focus_items, focus_total = focuscheck(img, verbose=not args.json)
    if args.json:
        print(json.dumps({
            'total': round(total, 2),
            'items': items,
            'flip': {'total': round(flip_total, 2), 'items': flip_items} if args.flip else None,
            'focus': {'total': round(focus_total, 2), 'items': focus_items} if args.focus else None,
        }, ensure_ascii=False, indent=2))
        return
    fails = [it for it in items if not it.get('pass')]
    if total >= args.threshold and not fails:
        print('✅ 终检通过，可以交付。')
    else:
        print(f'⚠️ 终检未过（{total:.1f} < {args.threshold}），问题项:')
        for it in fails:
            cn = _ITEM_CN.get(it.get('item'), it.get('item'))
            print(f'  - {cn}: {it.get("suggestion","")[:100]}')
        print('\n# 建议: 用 workshop fix 局部修复问题区域，或 converge --pick --notes 带建议重画')

if __name__ == '__main__':
    main()
