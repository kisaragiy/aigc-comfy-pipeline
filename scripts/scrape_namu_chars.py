#!/usr/bin/env python3
"""Scrape Closers-related namu wiki sub-pages (characters + lore)"""
from playwright.sync_api import sync_playwright
import os, time, re, requests

KBASE = r'C:\Users\zwq\knowledge\closers-lore\namu-wiki'
IMG_DIR = os.path.join(KBASE, 'images')
os.makedirs(IMG_DIR, exist_ok=True)

# Only Closers lore/character/story related pages
TARGETS = [
    # Individual Characters (개별 캐릭터)
    ('%EC%9D%B4%EC%84%B8%ED%95%98', 'Character_李世赫'),
    ('%EC%9D%B4%EC%8A%AC%EB%B9%84(%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4)', 'Character_李瑟钰'),
    ('%EC%A0%9C%EC%9D%B4(%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4)', 'Character_J'),
    ('%EB%AF%B8%EC%8A%A4%ED%8B%B8%ED%85%8C%EC%9D%B8(%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4)', 'Character_米斯丁'),
    ('%EB%A0%88%EB%B9%84%EC%95%84(%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4)', 'Character_蕾比雅'),
    ('%ED%8B%B0%EB%82%98(%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4)', 'Character_缇娜'),
    ('%EB%B0%94%EC%9D%B4%EC%98%AC%EB%A0%9B(%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4)', 'Character_薇尔莉'),
    ('%ED%95%98%ED%94%BC(%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4)', 'Character_哈比'),
    ('%EB%82%98%ED%83%80(%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4)', 'Character_纳塔'),
    ('%EC%84%9C%EC%9C%A0%EB%A6%AC(%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4)', 'Character_徐有利'),
    ('%EC%86%A1%EC%9D%80%EC%9D%B4(%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4)', 'Character_宋恩伊'),
    ('%EC%86%8C%EC%98%81(%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4)', 'Character_素英'),
    ('%EA%B9%80%EC%9C%A0%EC%A0%95(%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4)', 'Character_金有贞'),
    ('%EC%A0%9C%EB%82%98(%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4)', 'Character_婕娜'),
    ('%EB%8D%B0%EC%9D%B4%EB%B9%84%EB%93%9C%20%EB%A6%AC(%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4)', 'Character_大卫李'),
    ('%EC%84%A0%EC%9A%B0%EB%9E%80', 'Character_鲜于兰'),
    
    # Lore pages (already confirmed to exist)
    ('%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4/%EC%84%B8%EA%B3%84%EA%B4%80%20%EC%97%B0%ED%91%9C', 'Timeline'),
    ('%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4/%EB%93%B1%EC%9E%A5%EC%9D%B8%EB%AC%BC/%EC%B0%A8%EC%9B%90%EC%A2%85', 'Dimensional_Beings_Detail'),
    ('%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4/%EB%8D%98%EC%A0%84', 'Dungeons'),
    ('%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4/%EC%8B%9C%EC%8A%A4%ED%85%9C', 'System'),
    ('%EC%9C%A0%EB%8B%88%EC%98%A8(%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4)', 'Union'),
    ('%EB%B2%8C%EC%B2%98%EC%8A%A4', 'Vultures'),
    ('%ED%94%84%EB%A1%9C%EB%B9%84%EB%8D%98%EC%8A%A4%20%26%20%ED%94%84%EB%A1%9C%EB%AF%B8%EB%84%8C%EC%8A%A4', 'Providence_Prominence'),
    ('%ED%9E%90%EB%8D%B0%EA%B0%80%EB%A5%B4%ED%8A%B8%20%EA%B8%B0%EA%B4%80', 'Hildegart'),
    ('%ED%81%B4%EB%A1%9C%EC%A0%80(%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4)', 'Closer_Concept'),
    
    # Story
    ('%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4%20SIDE%20BLACKLAMBS', 'Anime_Side_BlackLams'),
    ('%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4RT:%20%EB%89%B4%20%EC%98%A4%EB%8D%94', 'ClosersRT_NewOrder'),
]

visited = set()
results = []
total_chars = 0
total_imgs = 0

with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True,
        proxy={'server': 'http://127.0.0.1:7890'})
    context = browser.new_context(viewport={'width': 1920, 'height': 1080}, locale='ko-KR')
    page = context.new_page()
    
    for doc_name, title in TARGETS:
        if doc_name in visited: continue
        visited.add(doc_name)
        
        url = f'https://namu.wiki/w/{doc_name}'
        print(f'\n▶️ {title}')
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=20000)
            time.sleep(3)
            
            if '페이지를 찾을 수 없습니다' in page.title():
                print(f'  ⏭️ Page not found')
                continue
            
            article = page.query_selector('article')
            if not article:
                print(f'  ⏭️ No article')
                continue
            
            text = article.inner_text()
            if len(text) < 100:
                print(f'  ⏭️ Too short ({len(text)} chars)')
                continue
            
            safe_name = re.sub(r'[\\/:*?"<>|]', '_', title)[:50]
            path = os.path.join(KBASE, f'{safe_name}.md')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(f'# {title}\n> Source: {url}\n> Scraped: {time.strftime("%Y-%m-%d %H:%M")}\n\n{text}')
            
            img_count = 0
            imgs = article.query_selector_all('img[src*="namu.wiki"]')
            for img in imgs:
                src = img.get_attribute('src')
                if src and 'namu.wiki' in src and 'svg' not in src:
                    try:
                        url_img = f'https:{src}' if src.startswith('//') else src
                        r = requests.get(url_img, proxies={'http':'http://127.0.0.1:7890','https':'http://127.0.0.1:7890'}, timeout=10)
                        if r.status_code == 200:
                            ext = src.split('.')[-1][:4] if '.' in src else 'jpg'
                            with open(os.path.join(IMG_DIR, f'{safe_name}_{img_count}.{ext}'), 'wb') as f:
                                f.write(r.content)
                            img_count += 1
                    except: pass
            
            print(f'  ✅ {len(text)} chars, {img_count} images')
            total_chars += len(text)
            total_imgs += img_count
            results.append((title, len(text), img_count))
            
        except Exception as e:
            print(f'  ❌ {str(e)[:60]}')
    
    browser.close()

print(f'\n{"="*40}')
print(f'Done: {len(results)} pages, {total_chars} chars, {total_imgs} images')
print(f'{"="*40}')
for title, chars, imgs in results:
    print(f'  {title:30s} {chars:>6} chars {imgs:>3} imgs')
