#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/verify_page.py — 漫画跨页角色一致检查（DFS-5）v1.0
============================================================
漫画长故事痛点：跨页同角色可能画崩（发色/服装/特征漂移）。
方法：VLM 对比两页/两张图中同角色——"是否是同一角色"一致性评分。

用法:
  python -m agents workshop verify-page <图A> <图B> [--role 角色名]
"""

import argparse, json, os, sys, time, urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent

# 本地 VLM（qwen3-vl:8b 视觉评估）
VLM_URLS = [
    'http://172.22.175.253:11434',
    'http://127.0.0.1:11434',
]
VLM_MODEL = 'qwen3-vl:8b'


def _http():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _vlm_url():
    for u in VLM_URLS:
        try:
            _http().open(u + '/api/tags', timeout=3).read()
            return u
        except Exception:
            continue
    raise RuntimeError('VLM 不可用（Ollama 未启动）')


def _vlm_compare(img_a, img_b, role=None):
    """VLM 对比两张图中角色一致性 → (score 0-10, reason)"""
    import base64

    def b64(p):
        with open(p, 'rb') as f:
            return base64.b64encode(f.read()).decode()

    prompt = (
        f'对比两张图中的角色（{role or "主角"}）是否同一人。'
        '评估：发色/发型/瞳色/服装/面部特征是否一致。'
        '输出 JSON: {"same": true/false, "score": 0-10, "reason": "简短原因"}'
    )
    body = json.dumps({
        'model': VLM_MODEL, 'stream': False, 'think': False,
        'prompt': prompt,
        'images': [b64(img_a), b64(img_b)],
    }).encode()
    req = urllib.request.Request(_vlm_url() + '/api/generate', data=body,
                                 headers={'Content-Type': 'application/json'})
    resp = json.loads(_http().open(req, timeout=120).read())
    out = resp.get('response', '')
    # 解析 JSON（容错）
    try:
        import re
        m = re.search(r'\{[^}]*\}', out)
        if m:
            d = json.loads(m.group(0))
            return d.get('score', 5), d.get('reason', out[:80])
    except Exception:
        pass
    return 5, out[:100]


def verify_consistency(img_a, img_b, role=None, threshold=7.0):
    """跨图角色一致性检查。

    Returns:
        {"score": float, "same": bool, "reason": str}
    """
    score, reason = _vlm_compare(img_a, img_b, role)
    same = score >= threshold
    print(f'  🔍 一致性评分: {score}/10 {"✅ 一致" if same else "❌ 不一致"}')
    print(f'  💬 {reason}')
    if not same:
        print(f'  ⚠️ 建议: 用角色参考图（--ref）+ LoRA 重新生成不一致页')
    return {"score": score, "same": same, "reason": reason}


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop verify-page', description='漫画跨页角色一致检查')
    ap.add_argument('img_a', help='图A（角色基准）')
    ap.add_argument('img_b', help='图B（待检查）')
    ap.add_argument('--role', default=None, help='角色名')
    ap.add_argument('--threshold', type=float, default=7.0, help='一致性阈值（默认 7.0）')
    args = ap.parse_args(argv)

    for p in (args.img_a, args.img_b):
        if not os.path.exists(p):
            print(f'❌ 图片不存在: {p}')
            return 1
    try:
        verify_consistency(args.img_a, args.img_b, args.role, args.threshold)
        return 0
    except Exception as e:
        print(f'❌ 检查失败: {str(e)[:150]}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
