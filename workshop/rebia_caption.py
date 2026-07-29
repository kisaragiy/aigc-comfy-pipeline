#!/usr/bin/env python3
"""标图: Ollama qwen3-vl:8b 分析训练图 → .caption 文件。
用法: python rebia_caption.py
"""
import os, sys, time
from pathlib import Path

# 加到 sys.path 让 agents 可导入
sys.path.insert(0, str(Path(__file__).parent))

from agents.vlm_analyzer import generate_caption

TRAIN_DIR = r'C:\Users\zwq\kohya_ss\train_data\rebia\100_luna_character'
TRIGGER = "luna_character"
CAPTION_PROMPT = (
    "Describe this EXACT image as comma-separated tags. "
    "Be SPECIFIC about colors. Include ALL visible features. "
    "Describe: hairstyle+color, eye color+shape, skin tone, "
    "outfit colors+style, accessories, pose, camera view, expression, background. "
    "Output ONLY the tags, no explanations.\n\n"
    "Example:\n"
    "luna_character, 1girl, long silver white hair, straight hair, "
    "purple eyes, pale skin, black futuristic bodysuit, white armor, "
    "full body, standing, looking at viewer, calm expression, holding scythe"
)

images = sorted([f for f in os.listdir(TRAIN_DIR) if f.endswith('.png')])
print(f'Found {len(images)} images')

for i, fname in enumerate(images):
    path = os.path.join(TRAIN_DIR, fname)
    caption_path = os.path.join(TRAIN_DIR, Path(fname).stem + '.caption')
    
    if os.path.exists(caption_path):
        print(f'  [{i+1}/{len(images)}] {fname} ⏭️ 已有 caption')
        continue

    print(f'  [{i+1}/{len(images)}] {fname}...', end=' ', flush=True)
    
    result = generate_caption(path, trigger_word=TRIGGER, format='tags')
    
    if result.get('available'):
        caption = result['response'].strip()
        # 确保以 trigger word 开头
        if not caption.lower().startswith(TRIGGER.lower()):
            caption = f"{TRIGGER}, {caption}"
        # 写入 .caption 文件
        with open(caption_path, 'w', encoding='utf-8') as f:
            f.write(caption)
        print(f'✅ ({len(caption)} chars)')
    else:
        print(f'❌ {result.get("error","?")}')
        time.sleep(2)
        continue

    # 每张间隔 5 秒，避免 Ollama 过载
    time.sleep(5)

print(f'\nDone! Check {TRAIN_DIR} for .caption files')
