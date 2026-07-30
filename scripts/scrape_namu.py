#!/usr/bin/env python3
"""Scrape namu wiki Closers page and save to knowledge base"""
from playwright.sync_api import sync_playwright
import os, re, time

KBASE = r'C:\Users\zwq\knowledge\closers-lore\namu-wiki'
os.makedirs(KBASE, exist_ok=True)

URL = 'https://namu.wiki/w/%ED%81%B4%EB%A1%9C%EC%A0%80%EC%8A%A4'

with sync_playwright() as p:
    browser = p.chromium.launch(
        channel='msedge', headless=True,
        proxy={'server': 'http://127.0.0.1:7890'}
    )
    page = browser.new_page(viewport={'width': 1920, 'height': 1080}, locale='ko-KR')
    
    print('Navigating...')
    page.goto(URL, wait_until='domcontentloaded', timeout=30000)
    page.wait_for_selector('article', timeout=15000)
    time.sleep(3)
    
    # Click all "더 보기" (show more) buttons to expand content
    expanded = 0
    while True:
        buttons = page.query_selector_all('button:has-text("더 보기"), button:has-text("펼치기"), button:has-text("접기")')
        if not buttons:
            break
        for btn in buttons:
            try:
                btn.click()
                expanded += 1
                time.sleep(0.5)
            except:
                pass
        time.sleep(1)
    
    print(f'Expanded {expanded} sections')
    
    # Get all text
    text = page.inner_text('article')
    print(f'Total: {len(text)} chars')
    
    # Get all sub-page links (internal wiki links)
    links = page.eval_on_selector_all('article a[href^="/w/"]', 
        'els => els.map(e => ({href: e.getAttribute("href"), text: e.innerText})).filter(l => l.text.length > 0)')
    
    # Save main page
    main_file = os.path.join(KBASE, 'main.md')
    with open(main_file, 'w', encoding='utf-8') as f:
        f.write(f'# 클로저스 - 나무위키\n\n')
        f.write(f'> Source: {URL}\n')
        f.write(f'> Scraped: {time.strftime("%Y-%m-%d %H:%M")}\n\n')
        f.write(text)
    print(f'Saved: {main_file}')
    
    # Save link index
    link_file = os.path.join(KBASE, 'subpages.md')
    unique_links = list(set((l['href'], l['text']) for l in links))
    with open(link_file, 'w', encoding='utf-8') as f:
        f.write(f'# Sub-pages ({len(unique_links)})\n\n')
        for href, text in sorted(unique_links, key=lambda x: x[1]):
            f.write(f'- [{text}](https://namu.wiki{href})\n')
    print(f'Saved: {link_file} ({len(unique_links)} links)')
    
    browser.close()

print('✅ Done')
