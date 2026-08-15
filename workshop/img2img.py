#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/img2img.py — 通用图生图（B-img2img）v1.0
==================================================
核心生图操作：图生图（img2img）。
  - denoise 控制相似度：0.3=微调 / 0.6=变体 / 0.85=大幅重绘
  - 支持中文描述（自动翻译）
  - 同图多变体（count N 不同 seed）

用法:
  python -m agents workshop img2img <原图> "新描述" [--denoise 0.6] [--count 3]
"""

import argparse, json, os, sys, time, urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent


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


def _save_params(out_dir: Path, params: dict):
    """生成参数记录（可复现——seed/prompt/denoise 等）。"""
    try:
        (out_dir / 'params.json').write_text(
            json.dumps(params, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass


def _load_image_file(image_path):
    COMFY = 'http://127.0.0.1:8188'
    import mimetypes
    boundary = '----hermesboundary' + str(time.time()).replace('.', '')
    fname = os.path.basename(image_path)
    mtype = mimetypes.guess_type(fname)[0] or 'image/png'
    with open(image_path, 'rb') as f:
        data = f.read()
    body = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="image"; filename="{fname}"\r\n'
        f'Content-Type: {mtype}\r\n\r\n'
    ).encode() + data + f'\r\n--{boundary}--\r\n'.encode()
    req = urllib.request.Request(COMFY + '/upload/image', data=body,
                                 headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
    r = json.loads(_http().open(req, timeout=60).read())
    return r['name']


def _build_img2img_wf(upload_name, prompt, negative, seed, denoise=0.6):
    """img2img 工作流（VAEEncode + denoise 控制相似度）"""
    wf = {}
    # 加载原图
    wf['10'] = {'class_type': 'LoadImage', 'inputs': {'image': upload_name}}
    # VAE 编码为 latent（img2img 起点）
    wf['11'] = {'class_type': 'VAEEncode', 'inputs': {'pixels': ['10', 0], 'vae': ['1', 2]}}
    # 模型
    wf['1'] = {'class_type': 'CheckpointLoaderSimple',
               'inputs': {'ckpt_name': 'waiIllustriousSDXL_v160.safetensors'}}
    wf['2'] = {'class_type': 'CLIPTextEncode',
               'inputs': {'text': prompt, 'clip': ['1', 1]}}
    wf['3'] = {'class_type': 'CLIPTextEncode',
               'inputs': {'text': negative or 'worst quality, blurry, low quality, deformed', 'clip': ['1', 1]}}
    wf['5'] = {'class_type': 'KSampler',
               'inputs': {'model': ['1', 0], 'positive': ['2', 0], 'negative': ['3', 0],
                          'latent_image': ['11', 0], 'seed': seed, 'steps': 28, 'cfg': 6.0,
                          'sampler_name': 'dpmpp_2m', 'scheduler': 'karras', 'denoise': denoise}}
    wf['6'] = {'class_type': 'VAEDecode', 'inputs': {'samples': ['5', 0], 'vae': ['1', 2]}}
    wf['7'] = {'class_type': 'SaveImage',
               'inputs': {'images': ['6', 0], 'filename_prefix': 'img2img'}}
    return wf


def img2img(source_image, desc, denoise=0.6, seed=-1, count=1,
            output_dir=None, negative=None, faceid=False):
    """通用图生图。

    Args:
        source_image: 原图路径
        desc: 修改描述（中文自动翻译）
        denoise: 重绘强度 0-1（0.3 微调 / 0.6 变体 / 0.85 大幅重绘）
        count: 变体数（同图多 seed）
        faceid: InstantID 保脸（改背景/换装时人脸不变形）

    Returns:
        [输出路径...]
    """
    if not os.path.exists(source_image):
        raise FileNotFoundError(f'原图不存在: {source_image}')
    if not 0 < denoise <= 1:
        raise ValueError('denoise 应在 (0, 1]')

    # 中文翻译
    prompt_en = desc
    try:
        from workshop.layer import _translate_desc
        prompt_en = _translate_desc(desc) if desc else ""
    except Exception:
        pass

    COMFY_OUTPUT = r'C:\DrawingLive\ComfyUI\output'
    out_dir = Path(output_dir or (PROJECT / 'outputs' / f"img2img_{time.strftime('%Y%m%d_%H%M%S')}"))
    out_dir.mkdir(parents=True, exist_ok=True)

    base_seed = seed if seed >= 0 else int(time.time()) % 2**31
    mode = '微调' if denoise < 0.4 else ('变体' if denoise < 0.75 else '大幅重绘')
    print(f'  🎨 img2img | denoise={denoise} ({mode}) | prompt: {prompt_en[:60]}')

    # InstantID 保脸模式（复用 create 的 faceid 链路）
    if faceid:
        print(f'  🪪 InstantID 保脸（人脸不变形）...')
        try:
            from workshop.create import create_from_nl
            saved = []
            for i in range(count):
                s = base_seed + i * 17
                sub = out_dir / f"v_{i+1:02d}"
                sub.mkdir(parents=True, exist_ok=True)
                create_from_nl(
                    prompt_en, count=1, model_type='sdxl', seed=s,
                    ref_path=source_image, ip_weight=0.6, faceid=True,
                    prompt_ready=True, inspect=False, dry_run=False,
                    output_dir=str(sub),
                )
                best = sub / 'best.png'
                if best.exists():
                    saved.append(str(best))
                    print(f'  ✅ {best}')
            print(f'\n📁 输出目录: {out_dir}')
            return saved
        except Exception as e:
            print(f'  ⚠️ 保脸模式失败，回退普通 img2img: {str(e)[:100]}')

    up_name = _load_image_file(source_image)
    saved = []
    for i in range(count):
        s = base_seed + i * 17
        wf = _build_img2img_wf(up_name, prompt_en, negative, s, denoise)
        print(f'  ⏳ 变体 {i+1}/{count} (seed={s})...')
        try:
            files = _submit(wf, timeout=600)
        except Exception as e:
            print(f'  ⚠️ 失败: {str(e)[:100]}')
            continue
        if not files:
            print(f'  ⚠️ 无输出')
            continue
        src = os.path.join(COMFY_OUTPUT, files[0])
        if not os.path.exists(src):
            continue
        out_path = out_dir / f"v_{i+1:02d}.png"
        with open(src, 'rb') as f_in, open(out_path, 'wb') as f_out:
            f_out.write(f_in.read())
        print(f'  ✅ {out_path}')
        saved.append(str(out_path))

    # 参数记录（可复现）
    _save_params(out_dir, {
        'op': 'img2img', 'source': os.path.basename(source_image),
        'prompt': desc, 'prompt_en': prompt_en, 'denoise': denoise,
        'seeds': [base_seed + i * 17 for i in range(count)],
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
    })

    print(f'\n📁 输出目录: {out_dir}')
    return saved


def batch_img2img(image_dir, desc, denoise=0.6, seed=-1, glob_pattern='*.png',
                  output_dir=None, compare=False):
    """批量图生图（目录内所有图统一处理——批量变体/统一风格）。

    Args:
        image_dir: 图片目录
        desc: 修改描述
        denoise: 重绘强度
        glob_pattern: 匹配模式
        output_dir: 输出目录
        compare: 每张输出前后对比图

    Returns:
        [输出路径...]
    """
    import glob
    imgs = sorted(glob.glob(os.path.join(image_dir, glob_pattern)))
    if not imgs:
        print(f'⚠️ {image_dir} 下无 {glob_pattern} 文件')
        return []
    out_root = Path(output_dir or (PROJECT / 'outputs' / f"batch_img2img_{time.strftime('%Y%m%d_%H%M%S')}"))
    saved = []
    print(f'📚 批量 img2img {len(imgs)} 张 (denoise={denoise})...')
    for i, img in enumerate(imgs):
        print(f'\n  [{i+1}/{len(imgs)}] {os.path.basename(img)}')
        try:
            results = img2img(img, desc, denoise=denoise, seed=seed + i * 7,
                              output_dir=str(out_root / f"img_{i+1:02d}"))
            saved.extend(results)
            if compare and results:
                from workshop.compare import make_compare
                make_compare(img, results[0],
                             output=str(out_root / f"img_{i+1:02d}_对比.png"))
        except Exception as e:
            print(f'  ⚠️ 失败: {str(e)[:80]}')
    print(f'\n📁 批量输出: {out_root}（{len(saved)} 张）')
    return saved


def pick_best(images, desc):
    """VLM 评分选最佳变体（auto-best）。

    Args:
        images: [路径...]
        desc: 原始描述（评分参考）

    Returns:
        最佳路径
    """
    if len(images) <= 1:
        return images[0] if images else None
    try:
        import base64, json, urllib.request
        scores = []
        for img in images:
            with open(img, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode()
            body = json.dumps({
                'model': 'qwen3-vl:8b', 'stream': False, 'think': False,
                'prompt': f'Rate this image 0-10 for quality and how well it matches: {desc}. Output ONLY the number.',
                'images': [b64],
            }).encode()
            req = urllib.request.Request('http://172.22.175.253:11434/api/generate', data=body,
                                         headers={'Content-Type': 'application/json'})
            resp = json.loads(urllib.request.urlopen(req, timeout=120).read())
            text = resp.get('response', '')
            import re
            m = re.search(r'(\d+(?:\.\d+)?)', text)
            scores.append(float(m.group(1)) if m else 0.0)
        best_idx = scores.index(max(scores))
        print(f'  🏆 变体评分: {[f"{s:.1f}" for s in scores]} → 最佳: {os.path.basename(images[best_idx])}')
        return images[best_idx]
    except Exception as e:
        print(f'  ⚠️ VLM 评分失败（返回第一张）: {str(e)[:80]}')
        return images[0]


def pipeline(source_image, edit_desc, denoise=0.7, seed=-1, count=2,
             output_dir=None, compare=True):
    """组合管线：反推 → 修改 → 生成 → 对比（一条命令完成全流程）。

    Args:
        source_image: 原图路径
        edit_desc: 修改描述（中文，如 "把背景换成海边"）
        denoise: 重绘强度
        count: 生成张数
        output_dir: 输出目录
        compare: 是否输出对比图

    Returns:
        [输出路径...]
    """
    from workshop.interrogate import interrogate
    print(f'  🔄 管线启动: 反推 → 修改 → 生成 → 对比')
    print(f'  ⏳ 1/4 反推原图 prompt...')
    prompt_en = interrogate(source_image, fmt='sdxl', detail='high')
    print(f'      → {prompt_en[:80]}...')

    print(f'  ✏️ 2/4 应用修改: {edit_desc}')
    try:
        from workshop.layer import _translate_desc
        edit_en = _translate_desc(edit_desc)
        modified = f"{prompt_en}, {edit_en}"
    except Exception:
        modified = f"{prompt_en}, {edit_desc}"
    print(f'      → ...{modified[-100:]}')

    print(f'  🎨 3/4 生成（{count} 张, denoise={denoise}）...')
    out_root = Path(output_dir or (PROJECT / 'outputs' / f"pipeline_{time.strftime('%Y%m%d_%H%M%S')}"))
    out_root.mkdir(parents=True, exist_ok=True)
    # 直接用修改后 prompt 生成（ref 原图 + faceid 保脸）
    results = []
    try:
        from workshop.create import create_from_nl
        base_seed = seed if seed >= 0 else 20260814
        for i in range(count):
            sub = out_root / f"v_{i+1:02d}"
            sub.mkdir(parents=True, exist_ok=True)
            create_from_nl(
                modified, count=1, model_type='sdxl', seed=base_seed + i * 17,
                ref_path=source_image, ip_weight=0.5, faceid=True,
                prompt_ready=True, inspect=False, dry_run=False,
                output_dir=str(sub),
            )
            best = sub / 'best.png'
            if best.exists():
                results.append(str(best))
    except Exception as e:
        print(f'  ⚠️ 生成失败: {str(e)[:100]}')
    if not results:
        print(f'  ⚠️ 管线生成无输出')
        return []

    print(f'  🖼️ 4/4 对比图...')
    if compare and results:
        try:
            from workshop.compare import make_compare
            cmp_path = str(out_root / '对比.png')
            make_compare(source_image, results[0], output=cmp_path)
            print(f'      → {cmp_path}')
        except Exception as e:
            print(f'  ⚠️ 对比失败: {str(e)[:80]}')

    # 保存修改后 prompt
    (out_root / 'modified_prompt.txt').write_text(modified, encoding='utf-8')
    print(f'\n📁 管线输出: {out_root}')
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop img2img', description='通用图生图（denoise 控制相似度）')
    ap.add_argument('image', help='原图路径')
    ap.add_argument('desc', nargs='*', help='修改描述（中文）')
    ap.add_argument('--denoise', type=float, default=0.6,
                    help='重绘强度 0-1（0.3微调/0.6变体/0.85大幅重绘）')
    ap.add_argument('--count', type=int, default=1, help='变体数')
    ap.add_argument('--output', default=None, help='输出目录')
    ap.add_argument('--seed', type=int, default=-1)
    ap.add_argument('--dir', default=None, help='批量处理目录（所有 png/jpg）')
    ap.add_argument('--compare', action='store_true', help='每张输出前后对比图')
    ap.add_argument('--faceid', action='store_true', help='InstantID 保脸（改背景/换装脸不变形）')
    ap.add_argument('--pipeline', action='store_true',
                    help='组合管线：反推→修改→生成→对比（一条命令全流程）')
    ap.add_argument('--auto-best', action='store_true',
                    help='多变体 VLM 评分自动选最佳（输出 best.png + 对比）')
    args = ap.parse_args(argv)

    desc = ' '.join(args.desc)
    if not desc:
        print('用法: img2img <原图|--dir 目录> "修改描述" [--denoise 0.6] [--count 3] [--compare]')
        print('       img2img <原图> "修改" --pipeline（反推→修改→生成→对比）')
        return 1

    # 管线模式
    if args.pipeline:
        try:
            pipeline(args.image, desc, denoise=args.denoise, seed=args.seed,
                     count=args.count, output_dir=args.output)
            return 0
        except Exception as e:
            print(f'❌ 管线失败: {str(e)[:150]}')
            return 1

    # 批量模式
    if args.dir:
        try:
            batch_img2img(args.dir, desc, denoise=args.denoise, seed=args.seed,
                          output_dir=args.output, compare=args.compare)
            return 0
        except Exception as e:
            print(f'❌ 批量 img2img 失败: {str(e)[:150]}')
            return 1

    try:
        results = img2img(args.image, desc, denoise=args.denoise, seed=args.seed,
                          count=args.count, output_dir=args.output, faceid=args.faceid)
        # 变体自动选择
        if args.auto_best and results:
            best = pick_best(results, desc)
            best_dir = Path(args.output) if args.output else Path(results[0]).parent
            import shutil
            best_out = best_dir / 'best.png'
            shutil.copy(best, best_out)
            print(f'  🏆 最佳变体已存: {best_out}')
            try:
                from workshop.compare import make_compare
                make_compare(args.image, str(best_out),
                             output=str(best_dir / '对比.png'))
            except Exception as e:
                print(f'  ⚠️ 对比失败: {str(e)[:80]}')
        return 0
    except Exception as e:
        print(f'❌ 图生图失败: {str(e)[:150]}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
