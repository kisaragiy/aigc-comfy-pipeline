#!/usr/bin/env python3
"""Scrape namu wiki Closers sub-pages with images"""
from playwright.sync_api import sync_playwright
import os, time, json, re, requests

KBASE = r'C:\Users\zwq\knowledge\closers-lore\namu-wiki'
IMG_DIR = os.path.join(KBASE, 'images')
os.makedirs(IMG_DIR, exist_ok=True)

# Core Closers pages to scrape (filtered from 201 sub-page links)
TARGETS = [
    # Playable Characters (플레이어블 캐릭터)
    ('클로저스/플레이어블 캐릭터', 'Playable Characters'),
    ('클로저스/플레이어블 캐릭터/검은양', 'Black Sheep Team'),
    ('클로저스/플레이어블 캐릭터/늑대개', 'Wolf Dogs Team'),
    ('클로저스/플레이어블 캐릭터/사냥터지기', 'Hunting Grounds Team'),
    ('클로저스/플레이어블 캐릭터/시궁쥐', 'Sewer Rats Team'),
    
    # Characters & NPCs (등장인물)
    ('클로저스/등장인물', 'Characters & NPCs'),
    ('클로저스/등장인물/유니온', 'Union'),
    ('클로저스/등장인물/벌처스', 'Vultures'),
    ('클로저스/등장인물/프로비던스', 'Providence'),
    ('클로저스/등장인물/힐데가르트 기관', 'Hildegart Organization'),
    
    # World & Lore
    ('클로저스/세계관', 'World View'),
    ('클로저스/설정', 'Settings'),
    ('위상력', 'Phase Power'),
    ('차원종', 'Dimensional Beings'),
    
    # Raids (레이드)
    ('클로저스/레이드', 'Raids'),
    
    # Episodes
    ('클로저스/에피소드', 'Episodes'),
    ('클로저스/에피소드/검은양', 'Black Sheep Episodes'),
    ('클로저스/에피소드/늑대개', 'Wolf Dogs Episodes'),
    ('클로저스/에피소드/사냥터지기', 'Hunting Grounds Episodes'),
    ('클로저스/에피소드/시궁쥐', 'Sewer Rats Episodes'),
    
    # Dungeons
    ('클로저스/던전 및 거점', 'Dungeons & Bases'),
    
    # Equipment & Costumes
    ('클로저스/장비', 'Equipment'),
    ('클로저스/코스튬', 'Costumes'),
]

def save_page(page, title, doc_name):
    """Extract text + images from a page"""
    time.sleep(2)  # Let Vue render
    
    # Get article text
    article = page.query_selector('article')
    text = article.inner_text() if article else page.inner_text('body')
    
    # Save text
    safe_name = re.sub(r'[\\/:*?"<>|]', '_', title)[:50]
    path = os.path.join(KBASE, f'{safe_name}.md')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f'# {title}\n')
        f.write(f'> Source: https://namu.wiki/w/{doc_name}\n')
        f.write(f'> Scraped: {time.strftime("%Y-%m-%d %H:%M")}\n\n')
        f.write(text)
    print(f'  📄 Saved: {safe_name}.md ({len(text)} chars)')
    
    # Download images
    imgs = page.query_selector_all('article img[src*="namu.wiki"]')
    img_count = 0
    for img in imgs:
        src = img.get_attribute('src')
        if src and 'namu.wiki' in src:
            alt = img.get_attribute('alt') or 'img'
            try:
                url = f'https:{src}' if src.startswith('//') else src
                r = requests.get(url, proxies={'http':'http://127.0.0.1:7890','https':'http://127.0.0.1:7890'}, timeout=10)
                if r.status_code == 200:
                    ext = src.split('.')[-1][:4] if '.' in src else 'jpg'
                    img_name = f'{safe_name}_{img_count}.{ext}'
                    with open(os.path.join(IMG_DIR, img_name), 'wb') as f:
                        f.write(r.content)
                    img_count += 1
            except:
                pass
    
    print(f'  🖼️ Downloaded {img_count} images')
    return len(text), img_count

with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True,
        proxy={'server': 'http://127.0.0.1:7890'})
    context = browser.new_context(viewport={'width': 1920, 'height': 1080}, locale='ko-KR')
    page = context.new_page()
    
    total_chars = 0
    total_imgs = 0
    success = 0
    failed = 0
    
    for doc_name, title in TARGETS:
        url = f'https://namu.wiki/w/{doc_name}'
        print(f'\n▶️ {title} ({doc_name})')
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=20000)
            time.sleep(3)
            
            # Check if page exists
            if '페이지를 찾을 수 없습니다' in page.title() or 'NotFound' in page.title():
                print(f'  ⏭️ Page not found')
                failed += 1
                continue
            
            chars, imgs = save_page(page, title, doc_name)
            total_chars += chars
            total_imgs += imgs
            success += 1
        except Exception as e:
            print(f'  ❌ Error: {str(e)[:60]}')
            failed += 1
    
    browser.close()

print(f'\n{"="*40}')
print(f'Done: {success} OK, {failed} failed')
print(f'Total: {total_chars} chars, {total_imgs} images')
print(f'{"="*40}')
