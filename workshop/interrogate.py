#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/interrogate.py — 图片反推提示词（B-interrogate）v1.0
==============================================================
B站超火场景：图片 → 提示词（反推）。用于：
  - 复刻风格/构图（"用AI复制任何图片风格" 25K）
  - 训练数据准备（caption）
  - 灵感逆向（看到好图想知道 prompt）

方法：
  1. 本地 VLM（qwen3-vl:8b）视觉反推（支持中文输出 + 多种风格格式）
  2. 输出：自然语言描述 / SDXL prompt 格式 / 训练用 tag 格式

用法:
  python -m agents workshop interrogate <图片> [--format sdxl|tag|natural] [--detail high]
"""

import argparse, base64, json, os, sys, urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent

VLM_URLS = [
    'http://172.22.175.253:11434',
    'http://127.0.0.1:11434',
]
VLM_MODEL = 'qwen3-vl:8b'

# 反推格式模板
FORMATS = {
    "natural": "用中文自然语言详细描述这张图片：主体、动作、表情、服装、背景、光线、色调、风格。尽量完整。",
    "sdxl": (
        "You are a prompt engineer. Reverse-engineer this image into a detailed SDXL prompt. "
        "Output ONLY the English prompt, comma-separated keywords, including: subject, appearance, "
        "clothing, pose, expression, background, lighting, color palette, art style, camera angle, "
        "quality tags. No explanation."
    ),
    "tag": (
        "You are a tagger for training data. Output ONLY comma-separated Danbooru-style tags "
        "describing this image: character features, clothing, pose, expression, background, "
        "style. Use underscores for multi-word tags. No explanation, no numbering."
    ),
}


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


def interrogate(image_path, fmt='sdxl', detail='high', max_len=600):
    """图片反推提示词。

    Args:
        image_path: 图片路径
        fmt: natural(中文描述)/sdxl(英文prompt)/tag(训练tag)
        detail: low/high（影响 prompt 细节）

    Returns:
        反推文本
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f'图片不存在: {image_path}')
    if fmt not in FORMATS:
        raise ValueError(f'格式可选: {list(FORMATS.keys())}')
    # 校验图片可读（损坏 → 友好错误，不先查 VLM）
    from workshop.image_utils import open_image_safe
    open_image_safe(image_path)

    with open(image_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode()

    base_prompt = FORMATS[fmt]
    if detail == 'high':
        base_prompt += ' Be extremely detailed, mention specific colors, materials, and composition elements.'

    body = json.dumps({
        'model': VLM_MODEL, 'stream': False, 'think': False,
        'prompt': base_prompt,
        'images': [b64],
    }).encode()
    req = urllib.request.Request(_vlm_url() + '/api/generate', data=body,
                                 headers={'Content-Type': 'application/json'})
    resp = json.loads(_http().open(req, timeout=180).read())
    out = resp.get('response', '').strip()

    # 截断
    if len(out) > max_len:
        out = out[:max_len]
    return out


def batch_interrogate(image_dir: str, fmt='sdxl', detail='low', glob_pattern='*.png'):
    """批量反推目录内所有图片 → 逐图保存 prompts.txt（训练数据准备）。

    Args:
        image_dir: 图片目录
        fmt: 输出格式
        detail: low（批量默认低细节省 token）
        glob_pattern: 匹配模式（*.png/*.jpg）

    Returns:
        {图片路径: 反推文本}
    """
    import glob
    imgs = sorted(glob.glob(os.path.join(image_dir, glob_pattern)))
    if not imgs:
        print(f'⚠️ {image_dir} 下无 {glob_pattern} 文件')
        return {}
    out_file = os.path.join(image_dir, 'prompts.txt')
    results = {}
    print(f'📚 批量反推 {len(imgs)} 张（{fmt}）...')
    with open(out_file, 'w', encoding='utf-8') as f:
        for i, img in enumerate(imgs):
            try:
                text = interrogate(img, fmt=fmt, detail=detail)
                results[img] = text
                f.write(f'[{os.path.basename(img)}]\n{text}\n\n')
                print(f'  ✅ {i+1}/{len(imgs)} {os.path.basename(img)} ({len(text)}字)')
            except Exception as e:
                print(f'  ⚠️ {os.path.basename(img)} 失败: {str(e)[:60]}')
    print(f'\n💾 全部反推已存: {out_file}')
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop interrogate', description='图片反推提示词')
    ap.add_argument('image', help='图片路径')
    ap.add_argument('--format', choices=list(FORMATS.keys()), default='sdxl',
                    help='输出格式: natural(中文)/sdxl(英文prompt)/tag(训练tag)')
    ap.add_argument('--detail', choices=['low', 'high'], default='high')
    ap.add_argument('--save', default=None, help='保存到文件')
    ap.add_argument('--recreate', action='store_true',
                    help='反推后直接重新生成（一键复刻风格——闭环）')
    ap.add_argument('--recreate-count', type=int, default=2, help='复刻生成张数')
    ap.add_argument('--dir', default=None, help='批量反推目录（所有 png/jpg → prompts.txt）')
    ap.add_argument('--edit', default=None,
                    help='反推后按修改描述编辑 prompt 再生成（如 "把头发变红"）')
    ap.add_argument('--lora-hint', action='store_true',
                    help='LoRA 触发词检测（反推时标注角色名/风格词候选——训练用）')
    args = ap.parse_args(argv)

    # 批量模式
    if args.dir:
        try:
            batch_interrogate(args.dir, fmt=args.format, detail=args.detail)
            return 0
        except Exception as e:
            print(f'❌ 批量反推失败: {str(e)[:150]}')
            return 1

    try:
        text = interrogate(args.image, fmt=args.format, detail=args.detail)
        print(f'\n📝 反推结果（{args.format}）:\n')
        print(text)
        if args.save:
            Path(args.save).write_text(text, encoding='utf-8')
            print(f'\n💾 已保存: {args.save}')

        # LoRA 触发词检测（DF-11：识别角色名/风格词候选——训练数据准备）
        if args.lora_hint:
            try:
                hint = interrogate(args.image, fmt='natural', detail='low')
                print(f'\n  🏷️ LoRA 触发词建议:\n  {hint[:300]}')
            except Exception as e:
                print(f'  ⚠️ 触发词检测失败: {str(e)[:80]}')

        # 反推 + 修改组合（DF-6：反推 → 编辑 prompt → 生成）
        if args.edit:
            if args.format != 'sdxl':
                print('\n⚠️ 编辑模式建议用 --format sdxl（英文 prompt 直喂生图）')
            try:
                from workshop.layer import _translate_desc
                edit_en = _translate_desc(args.edit)
                modified = f"{text}, {edit_en}"
                print(f'\n  ✏️ 修改: {args.edit}')
                print(f'  新 prompt: ...{modified[-120:]}')
                from workshop.create import create_from_nl
                import tempfile
                out_dir = Path(tempfile.mkdtemp(prefix='interrogate_edit_'))
                create_from_nl(
                    modified, count=2, model_type='sdxl',
                    seed=-1, prompt_ready=True, inspect=False, dry_run=False,
                    output_dir=str(out_dir),
                )
                print(f'  📁 修改生成输出: {out_dir}')
            except Exception as e:
                print(f'  ⚠️ 编辑生成失败: {str(e)[:100]}')

        # 反推 → 生成闭环（一键复刻，DF-1 恢复）
        if args.recreate and not args.edit:
            if args.format != 'sdxl':
                print('\n⚠️ 复刻模式建议用 --format sdxl（英文 prompt 直喂生图）')
            try:
                from workshop.create import create_from_nl
                import tempfile
                out_dir = Path(tempfile.mkdtemp(prefix='recreate_'))
                print(f'\n  🎨 复刻生成中（{args.recreate_count} 张）...')
                create_from_nl(
                    text, count=args.recreate_count, model_type='sdxl',
                    seed=-1, prompt_ready=True, inspect=False, dry_run=False,
                    output_dir=str(out_dir),
                )
                print(f'  📁 复刻输出: {out_dir}')
            except Exception as e:
                print(f'  ⚠️ 复刻失败: {str(e)[:100]}')
        return 0
    except Exception as e:
        print(f'❌ 反推失败: {str(e)[:150]}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
