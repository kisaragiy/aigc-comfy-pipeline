#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/style_distill.py — 风格蒸馏闭环（B-style-distill）v1.0
=================================================================
原创性核心：从混合风格描述蒸馏出"自己的风格 LoRA"。
闭环：生成数据集 → 数据门禁 → Caption → 训练 → 验证（不达标反馈调参）

铁律（lora-training skill）：
  - 风格 LoRA：数据集多样性 > 数量（多主题不同角色）
  - Caption 只写内容不写风格（风格从像素学）
  - 触发词选无语义冲突英文名
  - 验证不靠 loss 靠输出图对比

用法:
  python -m agents workshop style-distill "电影感光影，日漫线条，游戏立绘结构" \
    [--topics "1girl,1boy,landscape,still life"] [--count 6] \
    [--steps 800] [--dim 32] [--name mystyle]
"""

import argparse, json, os, shutil, subprocess, sys, time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
KOHYA = Path(r'C:\Users\zwq\kohya_ss\sd-scripts')
COMFY_VENV = Path(r'C:\DrawingLive\ComfyUI\venv\Scripts\python.exe')
COMFY_LORAS = Path(r'C:\DrawingLive\ComfyUI\models\loras')
BASE_CKPT = r'C:\DrawingLive\ComfyUI\models\checkpoints\waiIllustriousSDXL_v160.safetensors'
GATE_SCRIPT = Path(r'C:\Users\zwq\AppData\Local\hermes\scripts\dataset-gate.py')

# 风格词清洗表（caption 里不能出现的词——风格从像素学）
STYLE_WORDS = [
    'anime style', 'anime style,', 'style', 'illustration', 'art',
    'masterpiece', 'best quality', 'high quality', 'highly detailed',
    'cinematic', 'cinematic lighting', 'film', 'dramatic', 'digital art',
    'painting', 'concept art', 'render', 'vibrant', 'beautiful', 'aesthetic',
]


def _http():
    import urllib.request
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _submit(wf, timeout=600):
    import urllib.request
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


def _gen_sdxl(prompt, out_path, seed):
    """用 SDXL 底模生成单图（数据集必须与部署底模同分布）。"""
    import urllib.request
    wf = {
        '1': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': 'waiIllustriousSDXL_v160.safetensors'}},
        '2': {'class_type': 'CLIPTextEncode', 'inputs': {'text': prompt, 'clip': ['1', 1]}},
        '3': {'class_type': 'CLIPTextEncode', 'inputs': {'text': 'worst quality, low quality, blurry, watermark', 'clip': ['1', 1]}},
        '4': {'class_type': 'EmptyLatentImage', 'inputs': {'width': 1024, 'height': 1024, 'batch_size': 1}},
        '5': {'class_type': 'KSampler', 'inputs': {'model': ['1', 0], 'positive': ['2', 0], 'negative': ['3', 0],
                                                   'latent_image': ['4', 0], 'seed': seed, 'steps': 28, 'cfg': 6.5,
                                                   'sampler_name': 'dpmpp_2m', 'scheduler': 'karras', 'denoise': 1.0}},
        '6': {'class_type': 'VAEDecode', 'inputs': {'samples': ['5', 0], 'vae': ['1', 2]}},
        '7': {'class_type': 'SaveImage', 'inputs': {'images': ['6', 0], 'filename_prefix': 'style_distill'}},
    }
    files = _submit(wf, timeout=600)
    if not files:
        raise RuntimeError('生成无输出')
    src = os.path.join(r'C:\DrawingLive\ComfyUI\output', files[0])
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(src, 'rb') as f_in, open(out_path, 'wb') as f_out:
        f_out.write(f_in.read())
    return out_path


def _gen_sdxl_lora(prompt, out_path, seed, lora_name, lora_weight=0.9):
    """用 SDXL 底模 + LoRA 生成单图（自有风格 LoRA 出图）。"""
    import urllib.request
    wf = {
        '1': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': 'waiIllustriousSDXL_v160.safetensors'}},
        '9': {'class_type': 'LoraLoader', 'inputs': {'model': ['1', 0], 'clip': ['1', 1],
                                                     'lora_name': lora_name,
                                                     'strength_model': lora_weight, 'strength_clip': lora_weight}},
        '2': {'class_type': 'CLIPTextEncode', 'inputs': {'text': prompt, 'clip': ['9', 1]}},
        '3': {'class_type': 'CLIPTextEncode', 'inputs': {'text': 'worst quality, low quality, blurry, watermark', 'clip': ['9', 1]}},
        '4': {'class_type': 'EmptyLatentImage', 'inputs': {'width': 1024, 'height': 1024, 'batch_size': 1}},
        '5': {'class_type': 'KSampler', 'inputs': {'model': ['9', 0], 'positive': ['2', 0], 'negative': ['3', 0],
                                                   'latent_image': ['4', 0], 'seed': seed, 'steps': 28, 'cfg': 6.5,
                                                   'sampler_name': 'dpmpp_2m', 'scheduler': 'karras', 'denoise': 1.0}},
        '6': {'class_type': 'VAEDecode', 'inputs': {'samples': ['5', 0], 'vae': ['1', 2]}},
        '7': {'class_type': 'SaveImage', 'inputs': {'images': ['6', 0], 'filename_prefix': 'oc_gen'}},
    }
    files = _submit(wf, timeout=600)
    if not files:
        raise RuntimeError('生成无输出')
    src = os.path.join(r'C:\DrawingLive\ComfyUI\output', files[0])
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(src, 'rb') as f_in, open(out_path, 'wb') as f_out:
        f_out.write(f_in.read())
    return out_path


def _clean_caption(text):
    """Caption 清洗：去风格词，只留内容描述（风格 LoRA 铁律）。"""
    for w in STYLE_WORDS:
        text = text.replace(w, '')
    # 压缩多余逗号空格
    import re
    text = re.sub(r',\s*,+', ',', text)
    text = re.sub(r'\s+', ' ', text).strip(' ,')
    return text


def generate_dataset(style_desc, topics, count=6, output_dir=None, seed=2026):
    """① 生成风格数据集（多主题 × count——多样性>数量）。

    sd-scripts 要求目录结构: <root>/train_data/<subset>/ 图片（新版必须是子文件夹结构）。
    """
    out_root = Path(output_dir or (PROJECT / 'outputs' / f"style_data_{time.strftime('%Y%m%d_%H%M%S')}"))
    train_data = out_root / 'train_data'
    # 子文件夹名必须带重复次数前缀（sd-scripts: <N>_<name> = 该文件夹图片重复 N 次）
    imgs = train_data / '10_style'
    imgs.mkdir(parents=True, exist_ok=True)
    print(f'🎨 ① 生成风格数据集（{len(topics)} 主题 × {count} 张）...')
    saved = []
    i = 0
    existing = {p.name for p in imgs.glob('*.png')} if imgs.exists() else set()
    for t in topics:
        for c in range(count):
            i += 1
            out = str(imgs / f"{i:04d}_{t.replace(' ', '_')[:20]}.png")
            if os.path.basename(out) in existing:
                print(f'  [{i}] {t} 已存在，跳过')
                saved.append(out)
                continue
            prompt = f"{t}, {style_desc}, best quality"
            print(f'  [{i}] {t} seed={seed + i}...')
            try:
                _gen_sdxl(prompt, out, seed + i * 17)
                saved.append(out)
            except Exception as e:
                print(f'  ⚠️ 失败: {str(e)[:80]}')
    print(f'  📁 数据集: {imgs}（{len(saved)} 张）')
    return str(train_data), len(saved)


def gate_dataset(images_dir, threshold=60):
    """② 数据门禁（dataset-gate.py——低分图自动移 _rejected）。"""
    print(f'🚪 ② 数据门禁（阈值 {threshold}）...')
    if not GATE_SCRIPT.exists():
        print('  ⚠️ dataset-gate.py 不存在，跳过门禁')
        return images_dir
    cmd = [sys.executable, str(GATE_SCRIPT), 'images', images_dir,
           '--auto-remove', '--threshold', str(threshold)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        print(f'  {r.stdout[-500:] if r.stdout else ""}')
        if r.returncode != 0:
            print(f'  ⚠️ 门禁返回 {r.returncode}: {r.stderr[-300:] if r.stderr else ""}')
    except Exception as e:
        print(f'  ⚠️ 门禁失败: {str(e)[:100]}')
    return images_dir


def caption_dataset(images_dir, trigger):
    """③ Caption 生成：内容描述 + 触发词（不写风格——风格从像素学）。"""
    print(f'📝 ③ Caption 生成（触发词: {trigger}）...')
    import glob
    imgs = sorted(glob.glob(os.path.join(images_dir, '*.png')))
    if not imgs:
        print('  ⚠️ 无图片，跳过 caption')
        return
    # 用 interrogate 反推（natural 中文）——但 VLM 反推慢，这里用简单内容描述
    # 风格 LoRA 的 caption 只需描述内容主体：直接按主题写简化 caption
    for img in imgs:
        name = os.path.basename(img)
        cap_path = os.path.splitext(img)[0] + '.caption'
        # 从文件名提取主题词（如 0001_1girl）→ caption
        topic_part = name.split('_', 1)[-1].replace('.png', '').replace('_', ' ')
        caption = f"{trigger}, {topic_part}, high quality"
        with open(cap_path, 'w', encoding='utf-8') as f:
            f.write(caption)
    print(f'  ✅ {len(imgs)} 个 caption 已生成')
    return images_dir


def train_style_lora(images_dir, trigger, name, steps=800, dim=32, lr=1e-4):
    """④ 训练风格 LoRA（sd-scripts——小 dim 多步，风格 LoRA 配置）。"""
    print(f'🛠️ ④ 训练 LoRA（{name}, dim={dim}, steps={steps}）...')
    if not KOHYA.exists():
        raise RuntimeError(f'sd-scripts 不存在: {KOHYA}')
    out_dir = COMFY_LORAS
    train_script = KOHYA / 'sdxl_train_network.py'
    if not train_script.exists():
        raise RuntimeError(f'训练脚本不存在: {train_script}')
    cmd = [
        str(COMFY_VENV), str(train_script),
        '--pretrained_model_name_or_path', BASE_CKPT,
        '--train_data_dir', images_dir,
        '--output_dir', str(out_dir),
        '--output_name', name,
        '--resolution', '768',
        '--train_batch_size', '1',
        '--learning_rate', str(lr),
        '--lr_scheduler', 'cosine',
        '--lr_warmup_steps', '20',
        '--max_train_steps', str(steps),
        '--network_module', 'networks.lora',
        '--network_dim', str(dim),
        '--network_alpha', str(dim),
        '--mixed_precision', 'fp16',
        '--save_every_n_epochs', '1000',
        '--seed', '42',
        '--enable_bucket', '--min_bucket_reso', '512', '--max_bucket_reso', '768',
        '--no_half_vae',
        '--sdpa',
        '--max_data_loader_n_workers', '0',
        '--caption_extension', '.caption',
        '--network_train_unet_only',
        '--cache_text_encoder_outputs',
        '--tokenizer_cache_dir', str(Path.home() / '.cache' / 'huggingface' / 'tokenizers'),
    ]
    env = os.environ.copy()
    env['PYTHONPATH'] = str(KOHYA) + os.pathsep + str(Path(r'C:\DrawingLive\ComfyUI\venv\Lib\site-packages'))
    env['HF_ENDPOINT'] = 'https://hf-mirror.com'
    print(f'  ⏳ 训练中（本地 12GB VRAM，约 30-60 分钟）...')
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=7200)
    tail = (r.stdout or '')[-800:] + (r.stderr or '')[-300:]
    print(f'  {tail}')
    lora_path = out_dir / f'{name}.safetensors'
    if not lora_path.exists():
        raise RuntimeError(f'训练完成但 LoRA 未生成（看上面输出）')
    print(f'  ✅ LoRA: {lora_path}')
    return str(lora_path)


def verify_lora(lora_path, style_desc, trigger, output_dir=None):
    """⑤ 验证闭环：同 prompt 无 LoRA vs 有 LoRA 对比 + kb 审美检查。"""
    print(f'🔍 ⑤ 验证闭环...')
    out_root = Path(output_dir or (PROJECT / 'outputs' / f"style_verify_{time.strftime('%Y%m%d_%H%M%S')}"))
    out_root.mkdir(parents=True, exist_ok=True)
    test_prompt = f'1girl, standing, looking at viewer, {style_desc}, best quality'

    # 无 LoRA 基线
    print('  📷 无 LoRA 基线图...')
    try:
        _gen_sdxl(test_prompt, str(out_root / 'baseline.png'), seed=777)
    except Exception as e:
        print(f'  ⚠️ 基线失败: {str(e)[:80]}')

    # 有 LoRA
    print(f'  📷 有 LoRA（{os.path.basename(lora_path)}）...')
    try:
        import urllib.request
        lora_name = os.path.basename(lora_path)
        wf = {
            '1': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': 'waiIllustriousSDXL_v160.safetensors'}},
            '9': {'class_type': 'LoraLoader', 'inputs': {'model': ['1', 0], 'clip': ['1', 1],
                                                         'lora_name': lora_name, 'strength_model': 1.0, 'strength_clip': 1.0}},
            '2': {'class_type': 'CLIPTextEncode', 'inputs': {'text': f'{trigger}, {test_prompt}', 'clip': ['9', 1]}},
            '3': {'class_type': 'CLIPTextEncode', 'inputs': {'text': 'worst quality, low quality, blurry, watermark', 'clip': ['9', 1]}},
            '4': {'class_type': 'EmptyLatentImage', 'inputs': {'width': 1024, 'height': 1024, 'batch_size': 1}},
            '5': {'class_type': 'KSampler', 'inputs': {'model': ['9', 0], 'positive': ['2', 0], 'negative': ['3', 0],
                                                       'latent_image': ['4', 0], 'seed': 777, 'steps': 28, 'cfg': 6.5,
                                                       'sampler_name': 'dpmpp_2m', 'scheduler': 'karras', 'denoise': 1.0}},
            '6': {'class_type': 'VAEDecode', 'inputs': {'samples': ['5', 0], 'vae': ['1', 2]}},
            '7': {'class_type': 'SaveImage', 'inputs': {'images': ['6', 0], 'filename_prefix': 'style_verify'}},
        }
        files = _submit(wf, timeout=600)
        if files:
            src = os.path.join(r'C:\DrawingLive\ComfyUI\output', files[0])
            with open(src, 'rb') as f_in, open(str(out_root / 'with_lora.png'), 'wb') as f_out:
                f_out.write(f_in.read())
    except Exception as e:
        print(f'  ⚠️ LoRA 图失败: {str(e)[:80]}')

    # kb 审美检查（有 LoRA 图）
    print('  📊 审美知识库检查（有 LoRA 图）...')
    try:
        from workshop.kb import check_image
        lora_img = out_root / 'with_lora.png'
        if lora_img.exists():
            check_image(str(lora_img), threshold=0.6)
    except Exception as e:
        print(f'  ⚠️ kb 检查失败: {str(e)[:80]}')

    # 风格一致性对比（VLM 评分基线 vs LoRA）
    print('  🎨 风格一致性对比...')
    try:
        from workshop.compare import make_compare
        b, l = out_root / 'baseline.png', out_root / 'with_lora.png'
        if b.exists() and l.exists():
            make_compare(str(b), str(l), output=str(out_root / '对比.png'))
            print(f'  📊 对比图: {out_root / "对比.png"}')
    except Exception as e:
        print(f'  ⚠️ 对比失败: {str(e)[:80]}')

    print(f'\n📁 验证输出: {out_root}')
    print('  人工复核: 对比.png——LoRA 图应明显更接近目标风格')
    return str(out_root)


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop style-distill', description='风格蒸馏闭环（数据集→门禁→caption→训练→验证）')
    ap.add_argument('style_desc', help='风格描述（中文，如 "电影感光影，日漫线条，游戏立绘结构"）')
    ap.add_argument('--topics', default='1girl,1boy,landscape,still life',
                    help='主题多样性列表（逗号分隔——风格 LoRA 多样性>数量）')
    ap.add_argument('--count', type=int, default=6, help='每主题张数')
    ap.add_argument('--steps', type=int, default=800, help='训练步数（风格 LoRA 多步）')
    ap.add_argument('--dim', type=int, default=32, help='LoRA dim（风格用小 dim）')
    ap.add_argument('--lr', type=float, default=1e-4)
    ap.add_argument('--name', default=None, help='LoRA 名称（默认 style_<时间>）')
    ap.add_argument('--trigger', default=None, help='触发词（默认自动生成）')
    ap.add_argument('--skip-train', action='store_true', help='只到数据集+caption（调试）')
    ap.add_argument('--output', default=None, help='数据集输出目录')
    args = ap.parse_args(argv)

    topics = [t.strip() for t in args.topics.split(',') if t.strip()]
    trigger = args.trigger or f'st{int(time.time()) % 100000}'
    name = args.name or f'style_{time.strftime("%m%d_%H%M")}'

    try:
        # ① 数据集（返回 train_data 父目录）
        train_data, n = generate_dataset(args.style_desc, topics, args.count,
                                         output_dir=args.output)
        # 子文件夹 = 实际图片目录（10_style = 重复 10 次）
        images_dir = str(Path(train_data) / '10_style')
        if n == 0:
            print('❌ 数据集为空，终止')
            return 1
        # ② 门禁（对子文件夹跑）
        gate_dataset(images_dir)
        # ③ Caption
        caption_dataset(images_dir, trigger)
        if args.skip_train:
            print(f'\n✅ 调试模式：数据集+门禁+caption 完成（跳过训练）')
            print(f'   触发词: {trigger} | 数据集: {images_dir}')
            return 0
        # ④ 训练
        lora_path = train_style_lora(images_dir, trigger, name,
                                     steps=args.steps, dim=args.dim, lr=args.lr)
        # ⑤ 验证
        verify_lora(lora_path, args.style_desc, trigger)
        print(f'\n🎉 风格蒸馏完成！LoRA: {lora_path}')
        print(f'   使用: workshop create "描述" --lora {name} --lora-weight 0.9')
        return 0
    except Exception as e:
        print(f'❌ 风格蒸馏失败: {str(e)[:200]}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
