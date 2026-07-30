#!/usr/bin/env python3
"""B站 Login → Cookie Export — watches for login completion automatically"""
from playwright.sync_api import sync_playwright
import json, os, time, json as j

COOKIE_FILE = os.path.expanduser(r'~/hermes-workspace/bili_cookies.json')
os.makedirs(os.path.dirname(COOKIE_FILE), exist_ok=True)

print("=" * 50)
print("B站 登录 Cookie 导出器")
print("=" * 50)
print("浏览器已打开，请在窗口中登录B站")
print("脚本会自动检测登录完成...\n")

with sync_playwright() as p:
    browser = p.chromium.launch(
        channel='msedge', headless=False,
        proxy={'server': 'http://127.0.0.1:7890'}
    )
    context = browser.new_context(viewport={'width': 1280, 'height': 800})
    page = context.new_page()
    
    page.goto('https://www.bilibili.com/', wait_until='domcontentloaded', timeout=30000)
    
    # Click login button
    try:
        page.click('.header-login-entry', timeout=5000)
        print("✅ 登录窗口已弹出")
    except:
        print("⚠️ 请手动点击右上角「登录」")
    
    # Wait for login by checking for username element
    logged_in = False
    for i in range(120):  # 10 minutes max
        try:
            # Check if "我的" or user avatar appears (login success signal)
            user_elem = page.query_selector('.header-avatar, .user-con, [class*="user"]')
            if user_elem:
                # Also verify via API
                page.goto('https://api.bilibili.com/x/web-interface/nav', wait_until='domcontentloaded', timeout=10000)
                body = page.inner_text('body')
                try:
                    data = j.loads(body)
                    if data.get('data', {}).get('isLogin'):
                        uname = data['data'].get('uname', '')
                        print(f"\n✅ 登录成功! 用户: {uname}")
                        logged_in = True
                        break
                except:
                    pass
                page.go_back()
        except:
            pass
        
        if i % 10 == 0:
            print(f"  等待登录中... ({i//2}分钟)", flush=True)
        time.sleep(5)
    
    if not logged_in:
        print("\n⚠️ 登录超时，请重试")
        browser.close()
        exit(1)
    
    # Export cookies
    all_cookies = context.cookies()
    bili_only = [c for c in all_cookies if any(k in c['name'].lower() for k in ['buvid', 'b_lsid', '_uuid', 'sid', 'bp', 'session', 'DedeUserID', 'bili_jct', 'SESSDATA'])]
    
    print(f"\n导出 {len(bili_only)} 个B站Cookie")
    
    # Save as Netscape format for yt-dlp
    netscape_file = COOKIE_FILE.replace('.json', '.txt')
    with open(netscape_file, 'w') as f:
        f.write("# Netscape HTTP Cookie File\n")
        for c in bili_only:
            domain = c.get('domain', '.bilibili.com')
            flag = "TRUE" if domain.startswith('.') else "FALSE"
            path = c.get('path', '/')
            secure = "TRUE" if c.get('secure', False) else "FALSE"
            expiry = str(int(c.get('expires', 2147483647)))
            f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{c['name']}\t{c['value']}\n")
    print(f"Netscape格式: {netscape_file} (供yt-dlp使用)")
    
    # Save as JSON too
    with open(COOKIE_FILE, 'w') as f:
        json.dump(bili_only, f, indent=2)
    print(f"JSON格式: {COOKIE_FILE}")
    
    # Test login with yt-dlp
    print("\n测试已登录下载...")
    r = __import__('subprocess').run(
        ['yt-dlp', '--no-warnings', '--cookies', netscape_file, 
         '-f', '30015+30216', '--limit-rate', '500K',
         'https://www.bilibili.com/video/BV1dt411P72S',
         '-o', 'login_test.mp4'],
        capture_output=True, text=True, timeout=120)
    if os.path.exists('login_test.mp4') and os.path.getsize('login_test.mp4') > 10000:
        print(f"✅ 下载成功! ({os.path.getsize('login_test.mp4')//1024}KB)")
        os.remove('login_test.mp4')
    else:
        print(f"⚠️ 下载测试结果: {r.stderr[-200:] if r.stderr else 'unknown'}")
    
    browser.close()
    print("\n✅ 完成!")
