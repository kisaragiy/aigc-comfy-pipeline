#!/usr/bin/env python3
"""Robust recursive namu wiki Closers crawler - restarts browser periodically"""
from playwright.sync_api import sync_playwright
import os, time, re, json, requests, urllib.parse

KBASE = r'C:\Users\zwq\knowledge\closers-lore\namu-wiki'
IMG_DIR = os.path.join(KBASE, 'images')
STATE_FILE = os.path.join(KBASE, '_crawl_state.json')
QUEUE_FILE = os.path.join(KBASE, '_crawl_queue.json')
os.makedirs(IMG_DIR, exist_ok=True)

CLOSERS_KW = [
    '클로저스', '클로저', '위상력', '차원종', '유니온', '벌처스',
    '프로비던스', '힐데가르트', '군단장', '레이드', '에피소드',
    '이세하', '이슬비', '서유리', '제이', '미스틸테인',
    '레비아', '티나', '바이올렛', '나타', '하피',
    '제나', '미래', '소영', '송은이', '김유정',
    '파이', '루나', '벨', '세트', '시바',
    '백', '소마', '윤리아', '모야', '에이리',
    '김철수', '김기태', '박진성', '선우란',
    '헤카톤', '벨페고르', '아스모데우스', '베히모스',
    '프로메테우스', 'D 백작',
    '불꽃의 딸', '하얀 악마', '데이비드', '한기남',
    '등장인물', '던전', '장비', '코스튬', '시스템',
    '세계관', '서비스', '성우', '영상', '테마송',
    '울프팩', '스칼렛', '오메가', '레기온',
    '특수 경찰', '특경대', '부산', '민수호',
    '처리부대', '트레이너', '루퍼스', '김도윤',
    '슈나이더', '레온', '허프만', 'PvP',
]

def is_closers_url(url):
    if not url.startswith('https://namu.wiki/w/'):
        return False
    path = url[20:]
    for skip in ['분류:', '사용자:', '파일:', '틀:', '템플릿:', '나무위키:', '토론']:
        if path.startswith(skip): return False
    decoded = urllib.parse.unquote(path)
    return any(kw in decoded for kw in CLOSERS_KW)

def load_state():
    visited = set()
    queue = []
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f: visited = set(json.load(f))
    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE) as f: queue = json.load(f)
    # Seed if empty
    if not queue and not visited:
        queue = ['https://namu.wiki/w/%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4']
    return visited, queue

def save_state(visited, queue):
    with open(STATE_FILE, 'w') as f: json.dump(list(visited), f)
    with open(QUEUE_FILE, 'w') as f: json.dump(queue, f)

def scrape_page(page, url):
    """Scrape a single page and return (title, text, image_count, new_links)"""
    page.goto(url, wait_until='domcontentloaded', timeout=30000)
    time.sleep(3)
    
    if '페이지를 찾을 수 없습니다' in page.title():
        return None, None, 0, []
    
    # Expand foldable sections
    for btn in page.query_selector_all('button, summary, [class*="fold"]'):
        try:
            txt = btn.inner_text()
            if any(kw in txt for kw in ['더 보기', '펼치기', '접기']):
                btn.click(); time.sleep(0.3)
        except: pass
    for d in page.query_selector_all('details:not([open])'):
        try: d.click(); time.sleep(0.2)
        except: pass
    time.sleep(2)
    
    art = page.query_selector('article')
    if not art: return None, None, 0, []
    
    text = art.inner_text()
    if len(text) < 100: return None, None, 0, []
    
    title = page.title().replace(' - 나무위키', '').strip()
    
    # Download images
    img_n = 0
    for img in art.query_selector_all('img[src*="namu.wiki"]')[:30]:
        src = img.get_attribute('src')
        if src and 'svg' not in src:
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
    
    # Extract links
    new_links = []
    seen = set()
    for a in art.query_selector_all('a[href^="/w/"]'):
        href = a.get_attribute('href')
        if href:
            full = f'https://namu.wiki{href}'
            if full not in seen:
                seen.add(full)
                new_links.append(full)
    
    return title, text, img_n, new_links

# Main
visited, queue = load_state()
print(f'Visited: {len(visited)}, Queue: {len(queue)}')

crawled_this_run = 0
max_per_browser = 15  # Restart browser after this many pages
max_total = 300

while queue and len(visited) < max_total:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True,
            proxy={'server': 'http://127.0.0.1:7890'})
        page = browser.new_page(viewport={'width':1920,'height':1080}, locale='ko-KR')
        
        batch_count = 0
        while queue and batch_count < max_per_browser and len(visited) < max_total:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            
            print(f'\n[{crawled_this_run+1}/{len(visited)}] {url[:70]}')
            try:
                title, text, img_n, new_links = scrape_page(page, url)
                
                if title and text:
                    safe = re.sub(r'[\\/:*?"<>|]', '_', title)[:60]
                    path = os.path.join(KBASE, f'{safe}.md')
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(f'# {title}\n> {url}\n\n{text}')
                    print(f'  ✅ {safe} ({len(text)} chars, {img_n} imgs)')
                    crawled_this_run += 1
                    batch_count += 1
                    
                    # Add new links
                    added = 0
                    for link in new_links:
                        if link not in visited and link not in queue and is_closers_url(link):
                            queue.append(link)
                            added += 1
                    print(f'  🔗 {added} new links in queue (total queue: {len(queue)})')
                else:
                    print(f'  ⏭️ Skip')
                
            except Exception as e:
                print(f'  ❌ {str(e)[:80]}')
                # If browser died, restart
                if 'socket' in str(e).lower() or 'target' in str(e).lower() or 'browser' in str(e).lower():
                    print('  🔄 Browser error, restarting...')
                    break
            
            # Save progress
            if crawled_this_run % 5 == 0:
                save_state(visited, queue)
        
        browser.close()
    
    save_state(visited, queue)
    print(f'\n📊 Progress: {len(visited)} visited, {len(queue)} in queue')

print(f'\n{"="*40}')
print(f'Final: {len(visited)} visited, {len(queue)} remaining')
print(f'Saved to {STATE_FILE} and {QUEUE_FILE}')
print(f'{"="*40}')
