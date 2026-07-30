#!/usr/bin/env python3
"""Scrape remaining raid bosses + NPCs"""
from playwright.sync_api import sync_playwright
import os, time, re, requests

KBASE = r'C:\Users\zwq\knowledge\closers-lore\namu-wiki'
IMG_DIR = os.path.join(KBASE, 'images')
os.makedirs(IMG_DIR, exist_ok=True)

# Boss pages + NPCs confirmed to exist
TARGETS = [
    ('%EB%B2%A8%ED%8E%98%EA%B3%A0%EB%A5%B4', 'RaidBoss_机械王_贝尔菲戈尔'),
    ('%EC%95%84%EC%8A%A4%EB%AA%A8%EB%8D%B0%EC%9A%B0%EC%8A%A4', 'RaidBoss_阿斯摩太_海团'),
    ('%EB%B2%A0%ED%9E%88%EB%AA%A8%EC%8A%A4', 'RaidBoss_贝希摩斯_野兽团'),
    ('%ED%94%84%EB%A1%9C%EB%A9%94%ED%85%8C%EC%9A%B0%EC%8A%A4', 'RaidBoss_普罗米修斯_火焰王'),
    ('D%20%EB%B0%B1%EC%9E%91', 'RaidBoss_D伯爵'),
    ('%ED%95%98%EC%96%80%20%EC%95%85%EB%A7%88', 'NPC_白色恶魔'),
    
    # Try boss pages with "클로저스" prefix
    ('%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4/%EB%A0%88%EC%9D%B4%EB%93%9C/%EA%B5%B0%EB%8B%A8%EC%9E%A5', 'Raids_CorpsCommanders'),
    
    # Key NPC organizations detailed
    ('%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4/%EB%93%B1%EC%9E%A5%EC%9D%B8%EB%AC%BC/%EC%9C%A0%EB%8B%88%EC%98%A8', 'NPCs_Union_Detailed'),
    ('%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4/%EB%93%B1%EC%9E%A5%EC%9D%B8%EB%AC%BC/%EC%95%85%EC%97%AD', 'NPCs_Antagonists'),
    
    # More characters from the teams (checking if these exist)
    ('%EA%B9%80%EC%9C%A0%EC%A0%95(%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4)', 'Character_金有贞(Closers)'),
    ('%EC%A0%9C%EB%82%98(%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4)', 'Character_婕娜(Closers)'),
]

with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True,
        proxy={'server':'http://127.0.0.1:7890'})
    page = browser.new_page(viewport={'width':1920,'height':1080}, locale='ko-KR')
    
    total_c = 0
    total_i = 0
    for doc, title in TARGETS:
        url = f'https://namu.wiki/w/{doc}'
        print(f'▶️ {title}')
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=20000)
            time.sleep(3)
            if '페이지를 찾을 수 없습니다' in page.title(): print('  ⏭️ Not found'); continue
            art = page.query_selector('article')
            if not art: print('  ⏭️ No article'); continue
            text = art.inner_text()
            if len(text) < 100: print(f'  ⏭️ Short ({len(text)}c)'); continue
            
            safe = re.sub(r'[\\/:*?"<>|]', '_', title)[:50]
            path = os.path.join(KBASE, f'{safe}.md')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(f'# {title}\n> {url}\n\n{text}')
            
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
            total_c += len(text)
            total_i += img_n
        except Exception as e:
            print(f'  ❌ {str(e)[:60]}')
    
    browser.close()

print(f'\n✅ Total: {total_c} chars, {total_i} images')
