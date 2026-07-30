#!/usr/bin/env python3
"""Recursive namu wiki Closers crawler - scrape ALL related sub-pages"""
from playwright.sync_api import sync_playwright
import os, time, re, json, requests

KBASE = r'C:\Users\zwq\knowledge\closers-lore\namu-wiki'
IMG_DIR = os.path.join(KBASE, 'images')
STATE_FILE = os.path.join(KBASE, '_crawl_state.json')
os.makedirs(IMG_DIR, exist_ok=True)

# Load visited pages
visited = set()
if os.path.exists(STATE_FILE):
    with open(STATE_FILE) as f: visited = set(json.load(f))

# Closers-related patterns (only scrape these)
CLOSERS_PATTERNS = [
    '/w/%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4',  # 클로저스
    '/w/%ED%81%B4%EB%A1%9C%EC%A0%80',  # 클로저
    '/w/%EC%9C%84%EC%83%81%EB%A0%A5',  # 위상력
    '/w/%EC%B0%A8%EC%9B%90%EC%A2%85',  # 차원종
    '/w/%EC%9C%A0%EB%8B%88%EC%98%A8',  # 유니온
    '/w/%EB%B2%8C%EC%B2%98%EC%8A%A4',  # 벌처스
    '/w/%ED%94%84%EB%A1%9C%EB%B9%84%EB%8D%98%EC%8A%A4',  # 프로비던스
    '/w/%ED%9E%90%EB%8D%B0%EA%B0%80%EB%A5%B4%ED%8A%B8',  # 힐데가르트
]
CHAR_PATTERNS = ['/w/', '(클로저스)']  # Character pages

def is_closers_page(url):
    """Only scrape pages that are Closers game content"""
    if not url.startswith('https://namu.wiki/w/'):
        return False
    path = url[20:]
    
    # Skip non-content
    skip_prefix = ['분류:', '사용자:', '파일:', '틀:', '템플릿:', '나무위키:', '토론', '틀:', '틀:']
    if any(path.startswith(s) for s in skip_prefix):
        return False
    
    # Must be Closers-related: check if decoded path contains Closers keywords
    import urllib.parse
    decoded = urllib.parse.unquote(path)
    
    closers_keywords = [
        '클로저스', '클로저', '위상력', '차원종', '유니온', '벌처스',
        '프로비던스', '힐데가르트', '군단장', '레이드', '에피소드',
        '이세하', '이슬비', '서유리', '제이', '미스틸테인',
        '레비아', '티나', '바이올렛', '나타', '하피',
        '제나', '미래', '소영', '송은이', '김유정',
        '파이', '루나', '벨', '세트', '시바',
        '백', '소마', '윤리아', '모야', '에이리',
        '김철수', '김기태', '박진성',
        '헤카톤', '벨페고르', '아스모데우스', '베히모스',
        '프로메테우스', 'D 백작',
        '불꽃의 딸', '하얀 악마', '데이비드', '한기남',
        # Sub-page patterns
        '등장인물', '던전', '장비', '코스튬', '시스템',
        '세계관', '서비스', '성우', '영상', '테마송',
        '일본', '비판', '사건',
        # NPC organizations
        '울프팩', '스칼렛', '오메가', '레기온',
        '특수 경찰', '특경대', '부산', '민수호',
        '처리부대', '트레이너', '루퍼스', '김도윤',
        '슈나이더', '레온', '허프만',
    ]
    
    return any(kw in decoded for kw in closers_keywords)

def save_page(page, title, url, text, img_count):
    safe = re.sub(r'[\\/:*?"<>|]', '_', title)[:60]
    path = os.path.join(KBASE, f'{safe}.md')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f'# {title}\n> {url}\n\n{text}')
    print(f'  ✅ {safe} ({len(text)} chars, {img_count} imgs)')

with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True,
        proxy={'server': 'http://127.0.0.1:7890'})
    page = browser.new_page(viewport={'width': 1920, 'height': 1080}, locale='ko-KR')
    
    # Seed: Closers main page + key sub-pages
    seed_urls = [
        'https://namu.wiki/w/%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4',
    ]
    
    queue = list(seed_urls)
    crawled = 0
    max_pages = 100  # Safety limit
    
    while queue and crawled < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        
        print(f'\n[{crawled+1}] {url[:60]}')
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=20000)
            time.sleep(3)
            
            if '페이지를 찾을 수 없습니다' in page.title():
                print('  ⏭️ Not found')
                continue
            
            # Expand all foldable sections to reveal links
            buttons = page.query_selector_all('button, [class*="fold"], details summary')
            for btn in buttons:
                try:
                    txt = btn.inner_text()
                    if any(kw in txt for kw in ['더 보기', '펼치기', '접기', 'show', 'expand']):
                        btn.click()
                        time.sleep(0.3)
                except: pass
            
            # Also try clicking details elements
            for d in page.query_selector_all('details:not([open])'):
                try: d.click(); time.sleep(0.2)
                except: pass
            
            time.sleep(2)
            
            art = page.query_selector('article')
            if not art:
                print('  ⏭️ No article')
                continue
            
            text = art.inner_text()
            if len(text) < 100:
                print(f'  ⏭️ Too short ({len(text)}c)')
                continue
            
            # Extract a good title
            title = page.title().replace(' - 나무위키', '').strip()
            
            # Download images
            imgs = art.query_selector_all('img[src*="namu.wiki"]')
            img_n = 0
            for img in imgs[:30]:  # Limit 30 images per page
                src = img.get_attribute('src')
                if src and 'namu.wiki' in src and 'svg' not in src:
                    try:
                        iurl = f'https:{src}' if src.startswith('//') else src
                        r = requests.get(iurl, proxies={'http':'http://127.0.0.1:7890','https':'http://127.0.0.1:7890'}, timeout=10)
                        if r.status_code == 200:
                            ext = src.split('.')[-1][:4] if '.' in src else 'jpg'
                            safe = re.sub(r'[\\/:*?"<>|]', '_', title)[:60]
                            with open(os.path.join(IMG_DIR, f'{safe}_{img_n}.{ext}'), 'wb') as f:
                                f.write(r.content)
                            img_n += 1
                    except: pass
            
            save_page(page, title, url, text, img_n)
            crawled += 1
            
            # Find new Closers-related links
            links = art.query_selector_all('a[href^="/w/"]')
            seen_in_queue = set(queue)
            for link in links:
                href = link.get_attribute('href')
                if href:
                    full_url = f'https://namu.wiki{href}'
                    if full_url not in visited and full_url not in seen_in_queue and is_closers_page(full_url):
                        queue.append(full_url)
                        seen_in_queue.add(full_url)
            
        except Exception as e:
            print(f'  ❌ {str(e)[:60]}')
    
    browser.close()
    
    # Save state
    with open(STATE_FILE, 'w') as f:
        json.dump(list(visited), f)
    
    print(f'\n{"="*40}')
    print(f'Crawled: {crawled} pages, Queue remaining: {len(queue)}')
    print(f'Total visited (all time): {len(visited)}')
    print(f'{"="*40}')
