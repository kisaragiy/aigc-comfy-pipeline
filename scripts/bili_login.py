#!/usr/bin/env python3
"""B站登录 → 导出Cookie — 使用Edge浏览器"""
from playwright.sync_api import sync_playwright
import json, os, time

COOKIE_FILE = os.path.expanduser(r'~/hermes-workspace/bili_cookies.json')
os.makedirs(os.path.dirname(COOKIE_FILE), exist_ok=True)

print("=" * 50)
print("B站 登录 Cookie 导出器")
print("=" * 50)
print()
print("请在打开的浏览器窗口中登录B站。")
print("登录成功后按 Enter 键导出Cookie。")
print()

with sync_playwright() as p:
    browser = p.chromium.launch(
        channel='msedge',
        headless=False,  # 显示浏览器窗口
        proxy={'server': 'http://127.0.0.1:7890'}
    )
    context = browser.new_context(
        viewport={'width': 1280, 'height': 800},
        locale='zh-CN'
    )
    page = context.new_page()
    
    print("打开B站登录页面...")
    page.goto('https://www.bilibili.com/', wait_until='domcontentloaded', timeout=30000)
    
    # 点击登录按钮
    try:
        login_btn = page.wait_for_selector('.header-login-entry', timeout=5000)
        login_btn.click()
        print("请在弹出的登录窗口中输入手机号并登录...")
    except:
        print("自动点击登录按钮失败，请手动点击右上角「登录」")
    
    # 等待用户完成登录
    input("登录完成后，按 Enter 继续...")
    time.sleep(2)
    
    # 导出Cookie
    cookies = context.cookies()
    print(f"\n获取到 {len(cookies)} 个Cookie")
    
    # 保存到文件
    with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"Cookie已保存到: {COOKIE_FILE}")
    
    # 提取关键cookie
    bili_cookies = {c['name']: c['value'] for c in cookies if 'bili' in c['name'].lower() or 'sid' == c['name']}
    print(f"\n关键Cookie: {list(bili_cookies.keys())}")
    
    # 验证登录状态
    page.goto('https://api.bilibili.com/x/web-interface/nav', wait_until='domcontentloaded', timeout=15000)
    body = page.inner_text('body')
    import json as j
    try:
        data = j.loads(body)
        is_login = data.get('data', {}).get('isLogin', False)
        uname = data.get('data', {}).get('uname', '')
        if is_login:
            print(f"\n✅ 登录成功! 用户名: {uname}")
        else:
            print("\n⚠️ 似乎未登录成功")
    except:
        print(f"\n⚠️ 验证失败: {body[:100]}")
    
    browser.close()
    print("\n✅ 完成!")
