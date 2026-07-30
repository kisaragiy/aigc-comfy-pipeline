#!/usr/bin/env python3
"""Final focused crawler - only lore pages, skip meta pages"""
from playwright.sync_api import sync_playwright
import os, time, re, json, requests, urllib.parse

KBASE = r'C:\Users\zwq\knowledge\closers-lore\namu-wiki'
IMG_DIR = os.path.join(KBASE, 'images')
os.makedirs(IMG_DIR, exist_ok=True)

# Pages to SKIP (non-lore)
SKIP_PATTERNS = [
    '업데이트', '이벤트', '밸런스', '패치', '비판', '문제점',
    '사건', '커뮤니티', '갤러리', '서버', '선택', '화면',
    '정식서비스', '이전', '베타', '출시', '개발진',
    '성우진', '성우', '논란', '사고',
    '일본', '중국', '북미', '대만', '태국', '해외',
    '웹툰', '애니메이션',
]

# Only keep pages with these keywords (lore/story related)
LORE_KEYWORDS = [
    '에피소드', '던전', '거점', '지역', '장비', '코스튬',
    '캐릭터', '등장인물', 'NPC', '군단', '레이드',
    '세계관', '연표', '타임라인',
    '스토리', '시나리오', '퀘스트',
    '결전', '승급', '전직',
    'PNA', '스킬', '특성',
]

def is_lore_page(url):
    if not url.startswith('https://namu.wiki/w/클로저스'):
        return False
    path = url[20:]
    decoded = urllib.parse.unquote(path)
    
    # Skip meta pages
    for skip in SKIP_PATTERNS:
        if skip in decoded:
            return False
    
    # Must have lore keyword OR be a character/detail page
    if any(kw in decoded for kw in LORE_KEYWORDS):
        return True
    
    # Individual equipment/dungeon pages (have numeric IDs or specific names)
    if decoded.count('/') >= 2:  # 클로저스/장비/XXX
        return True
    
    return False

visited = set()
if os.path.exists(os.path.join(KBASE, '_v2_visited.json')):
    with open(os.path.join(KBASE, '_v2_visited.json')) as f:
        visited = set(json.load(f))

queue = ['https://namu.wiki/w/%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4/%EC%97%90%ED%94%BC%EC%86%8C%EB%93%9C']
crawled = 0
max_total = 200

while queue and len(visited) < max_total:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True,
            proxy={'server': 'http://127.0.0.1:7890'})
        page = browser.new_page(viewport={'width':1920,'height':1080}, locale='ko-KR')
        
        batch = 0
        while queue and batch < 15 and len(visited) < max_total:
            url = queue.pop(0)
            if url in visited: continue
            visited.add(url)
            
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=20000)
                time.sleep(2)
                
                if '페이지를 찾을 수 없습니다' in page.title(): continue
                
                # Expand
                for btn in page.query_selector_all('button, summary'):
                    try:
                        t = btn.inner_text()
                        if any(k in t for k in ['더 보기','펼치기']): btn.click()
                    except: pass
                time.sleep(1)
                
                art = page.query_selector('article')
                if not art: continue
                text = art.inner_text()
                if len(text) < 200: continue
                
                title = page.title().replace(' - 나무위키', '').strip()
                safe = re.sub(r'[\\/:*?"<>|]', '_', title)[:60]
                path = os.path.join(KBASE, f'{safe}.md')
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(f'# {title}\n> {url}\n\n{text}')
                
                crawled += 1; batch += 1
                print(f'[{crawled}] {safe} ({len(text)}c)')
                
                # Find new lore links
                for a in art.query_selector_all('a[href^="/w/클로저스"]'):
                    href = a.get_attribute('href')
                    if href:
                        full = f'https://namu.wiki{href}'
                        if full not in visited and full not in queue and is_lore_page(full):
                            queue.append(full)
                
            except Exception as e:
                if 'socket' in str(e).lower() or 'target' in str(e).lower():
                    break
                continue
        
        browser.close()
    
    # Save state
    with open(os.path.join(KBASE, '_v2_visited.json'), 'w') as f:
        json.dump(list(visited), f)
    print(f'\n📊 {len(visited)} visited, {len(queue)} queue\n')

print(f'✅ Done: {crawled} new pages, {len(visited)} total visited')
