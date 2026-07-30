#!/usr/bin/env python3
"""Scrape namu wiki - click all expand buttons, get full content"""
from playwright.sync_api import sync_playwright
import os, time, json

KBASE = r'C:\Users\zwq\knowledge\closers-lore\namu-wiki'
os.makedirs(KBASE, exist_ok=True)

URL = 'https://namu.wiki/w/%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4'

with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True,
        proxy={'server': 'http://127.0.0.1:7890'})
    page = browser.new_page(viewport={'width': 1920, 'height': 1080}, locale='ko-KR')
    
    page.goto(URL, wait_until='domcontentloaded', timeout=30000)
    page.wait_for_selector('article', timeout=15000)
    time.sleep(2)
    
    # Click ALL expandable elements
    selectors = [
        'button:has-text("더 보기")',
        'button:has-text("펼치기")',
        'button:has-text("접기")',
        '[class*="fold"]',
        '[class*="expand"]',
        '.wiki-fold',
        'button',
        'summary',
    ]
    
    clicked = 0
    for sel in selectors:
        buttons = page.query_selector_all(sel)
        for btn in buttons:
            try:
                txt = btn.inner_text()
                if any(kw in txt for kw in ['더 보기', '펼치기', '접기', 'fold', 'expand', 'show']):
                    btn.click()
                    clicked += 1
                    time.sleep(0.3)
            except: pass
    
    # Also try clicking details/summary elements
    details = page.query_selector_all('details')
    for d in details:
        try:
            d.click()
            clicked += 1
            time.sleep(0.3)
        except: pass
    
    print(f'Clicked {clicked} expandable elements')
    time.sleep(2)
    
    # Get full rendered text
    text = page.inner_text('article')
    print(f'Full article: {len(text)} chars')
    
    # Save
    path = os.path.join(KBASE, 'full.md')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f'# 클로저스 - 나무위키 (전체)\n> Scraped: {time.strftime("%Y-%m-%d %H:%M")}\n\n{text}')
    print(f'Saved: {path}')
    
    # Also get character links specifically
    char_links = page.eval_on_selector_all('article a[href*="클로저스/"]',
        'els => els.map(e => ({href: e.getAttribute("href"), text: e.innerText})).filter(l => l.text.length > 1)')
    
    path2 = os.path.join(KBASE, 'character_links.json')
    with open(path2, 'w', encoding='utf-8') as f:
        json.dump(list(set(tuple(sorted(l.items())) for l in char_links)), f, ensure_ascii=False)
    print(f'Character links: {len(char_links)}')
    
    browser.close()
print('✅ Done')
