#!/usr/bin/env python3
"""Scrape remaining character/NPC pages"""
from playwright.sync_api import sync_playwright
import os, time, re, requests

KBASE = r'C:\Users\zwq\knowledge\closers-lore\namu-wiki'
IMG_DIR = os.path.join(KBASE, 'images')
os.makedirs(IMG_DIR, exist_ok=True)

CHARACTERS = [
    ('%EB%A3%A8%EB%82%98', 'Character_露娜'),
    ('%EC%9D%80%ED%95%98', 'Character_银河'),
    ('%EB%A3%A8%EC%8B%9C', 'Character_露西'),
    ('%EB%B2%A8', 'Character_贝尔'),
    ('%EC%84%B8%ED%8A%B8', 'Character_塞特'),
    ('%EC%8B%9C%EB%B0%94', 'Character_西瓦'),
    ('%ED%8C%8C%EC%9D%B4', 'Character_派伊'),
    ('%EB%AF%B8%EB%9E%98', 'Character_未来'),
    ('%EB%B0%B1', 'Character_白'),
    ('%EC%86%8C%EB%A7%88', 'Character_索玛'),
    ('%EC%9C%A4%EB%A6%AC%EC%95%84', 'Character_尹莉娅'),
    ('%EB%AA%A8%EC%95%BC', 'Character_莫亚'),
    ('%EC%97%90%EC%9D%B4%EB%A6%AC', 'Character_艾莉'),
    ('%EA%B9%80%EC%B2%A0%EC%88%98', 'Character_金哲秀'),
    ('%EA%B9%80%EA%B8%B0%ED%83%9C', 'Character_金基泰'),
    ('%EB%B0%95%EC%A7%84%EC%84%B1', 'Character_朴进成'),
]

with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True,
        proxy={'server':'http://127.0.0.1:7890'})
    page = browser.new_page(viewport={'width':1920,'height':1080}, locale='ko-KR')
    
    for doc, title in CHARACTERS:
        url = f'https://namu.wiki/w/{doc}'
        print(f'▶️ {title}')
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=20000)
            time.sleep(3)
            art = page.query_selector('article')
            if not art: print('  ⏭️ No article'); continue
            text = art.inner_text()
            if len(text) < 100: print(f'  ⏭️ Short ({len(text)}c)'); continue
            
            safe = re.sub(r'[\\/:*?"<>|]', '_', title)[:50]
            path = os.path.join(KBASE, f'{safe}.md')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(f'# {title}\n> {url}\n\n{text}')
            
            # Download images
            imgs = art.query_selector_all('img[src*="namu.wiki"]')
            img_n = 0
            for img in imgs:
                src = img.get_attribute('src')
                if src and 'namu.wiki' in src and 'svg' not in src:
                    try:
                        iurl = f'https:{src}' if src.startswith('//') else src
                        r = requests.get(iurl, proxies={'http':'http://127.0.0.1:7890','https':'http://127.0.0.1:7890'}, timeout=10)
                        if r.status_code == 200:
                            ext = src.split('.')[-1][:4] if '.' in src else 'jpg'
                            with open(os.path.join(IMG_DIR, f'{safe}_{img_n}.{ext}'), 'wb') as f:
                                f.write(r.content)
                            img_n += 1
                    except: pass
            
            print(f'  ✅ {len(text)} chars, {img_n} imgs')
        except Exception as e:
            print(f'  ❌ {str(e)[:60]}')
    
    browser.close()
print('✅ Done')
