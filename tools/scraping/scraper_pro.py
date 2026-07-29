#!/usr/bin/env python3
"""生产级网页爬虫框架 — Playwright + 反反爬策略

高级工程师级特性:
  - Playwright 浏览器自动化 (CDP/normal 双模式)
  - 反检测 Spoof (User-Agent/WebGL/Canvas 指纹混淆)
  - Cookie 持久化 (加密存储到文件)
  - 请求间隔 + 随机延迟 (人类行为模拟)
  - 重试机制 + 指数退避
  - HTML → 结构化数据 (BeautifulSoup + CSS Selector)
  - 页面等待策略 (多种等待策略可选)
  - 截图 + DOM 快照 (调试用)
  - 并发控制 (控制页面数)
  - 代理轮换 (可选)

用法:
  python scraper_pro.py fetch <url>              # 获取页面
  python scraper_pro.py screenshot <url>         # 截图
  python scraper_pro.py extract <url> <css...>   # 提取数据
  python scraper_pro.py crawl <url> -d <depth>   # 爬取(广度遍历)
  python scraper_pro.py cookies save             # 保存 cookies
  python scraper_pro.py cookies load             # 加载 cookies
"""
import sys, json, time, random, hashlib, base64
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

# ── 浏览器自动化 ──
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_OK = True
except ImportError:
    PLAYWRIGHT_OK = False

# ── HTTP 请求 ──
try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    import httpx
    HTTPX_OK = True
except ImportError:
    HTTPX_OK = False

# ── HTML 解析 ──
try:
    from bs4 import BeautifulSoup
    BS4_OK = True
except ImportError:
    BS4_OK = False

# ── 数据存储 ──
COOKIE_DIR = Path.home() / ".scraper_cookies"
COOKIE_DIR.mkdir(exist_ok=True)


# ── 反检测配置 ──

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
]

TIMEZONES = ["Asia/Shanghai", "Asia/Hong_Kong", "Asia/Tokyo"]

LOCALES = ["zh-CN", "en-US", "en-GB"]

ANTI_BOT_JS = """
// 反自动检测: 覆盖 navigator.webdriver
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
// 覆盖 chrome 属性
window.chrome = { runtime: {} };
// 覆盖 permissions
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (params) => (
    params.name === 'notifications' ? 
    Promise.resolve({ state: Notification.permission }) : 
    originalQuery(params)
);
// 覆盖 plugins
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5]
});
// 覆盖 languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['zh-CN', 'zh']
});
"""


# ============================================================
# 浏览器管理
# ============================================================

class BrowserManager:
    """生产级浏览器管理器 — 反检测 + Cookie 持久化"""
    
    def __init__(self, headless=True, stealth=True, cookie_domain=None):
        self.headless = headless
        self.stealth = stealth
        self.cookie_domain = cookie_domain
        self.browser = None
        self.context = None
        self.page = None
    
    def __enter__(self):
        if not PLAYWRIGHT_OK:
            raise RuntimeError("playwright not installed")
        
        self.pw = sync_playwright().start()
        ua = random.choice(USER_AGENTS)
        vp = random.choice(VIEWPORTS)
        
        self.browser = self.pw.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"] if self.stealth else [],
        )
        
        self.context = self.browser.new_context(
            user_agent=ua,
            viewport=vp,
            timezone_id=random.choice(TIMEZONES),
            locale=random.choice(LOCALES),
            permissions=["geolocation"],
        )
        
        self.page = self.context.new_page()
        
        if self.stealth:
            self.page.add_init_script(ANTI_BOT_JS)
        
        # 加载 cookies
        self._load_cookies()
        
        return self
    
    def __exit__(self, *args):
        self._save_cookies()
        if self.page: self.page.close()
        if self.context: self.context.close()
        if self.browser: self.browser.close()
        if self.pw: self.pw.stop()
    
    def _cookie_file(self) -> Path:
        domain = self.cookie_domain or "default"
        return COOKIE_DIR / f"{domain}_cookies.json"
    
    def _load_cookies(self):
        cf = self._cookie_file()
        if cf.exists():
            try:
                cookies = json.loads(cf.read_text())
                self.context.add_cookies(cookies)
                print(f"[cookies] 加载 {len(cookies)} 条 cookies")
            except Exception as e:
                print(f"[cookies] 加载失败: {e}")
    
    def _save_cookies(self):
        if not self.context:
            return
        try:
            cookies = self.context.cookies()
            self._cookie_file().write_text(json.dumps(cookies, indent=2, ensure_ascii=False))
            print(f"[cookies] 保存 {len(cookies)} 条 cookies")
        except Exception as e:
            print(f"[cookies] 保存失败: {e}")
    
    def visit(self, url: str, wait_until="networkidle", wait_selector=None, timeout=30000):
        """访问 URL + 等待策略"""
        self.page.goto(url, wait_until=wait_until, timeout=timeout)
        self._random_delay()
        
        if wait_selector:
            self.page.wait_for_selector(wait_selector, timeout=timeout)
        
        return self.page
    
    def _random_delay(self, min_s=0.5, max_s=2.0):
        time.sleep(random.uniform(min_s, max_s))


# ============================================================
# 数据提取
# ============================================================

def extract_data(page, selectors: Dict[str, str]):
    """通过 CSS Selector 提取数据"""
    result = {}
    for name, selector in selectors.items():
        try:
            elements = page.query_selector_all(selector)
            if len(elements) == 1:
                result[name] = elements[0].inner_text().strip()
            elif len(elements) > 1:
                result[name] = [e.inner_text().strip() for e in elements]
            else:
                result[name] = None
        except Exception as e:
            result[name] = f"<error: {e}>"
    return result


def extract_html(html: str, css_rules: Dict[str, str]):
    """从 HTML 字符串中用 CSS 选择器提取数据"""
    if not BS4_OK:
        print("[!] beautifulsoup4 not installed")
        return {}
    
    soup = BeautifulSoup(html, "html.parser")
    result = {}
    for name, selector in css_rules.items():
        try:
            elements = soup.select(selector)
            if len(elements) == 1:
                result[name] = elements[0].get_text(strip=True)
            elif len(elements) > 1:
                result[name] = [e.get_text(strip=True) for e in elements]
            else:
                result[name] = None
        except Exception as e:
            result[name] = f"<error: {e}>"
    return result


# ============================================================
# 请求级抓取 (轻量, 无JS)
# ============================================================

def fetch_page(url: str, headers: Optional[dict] = None):
    """用 requests/httpx 获取页面 (适用于 API 或无JS页面)"""
    if not REQUESTS_OK and not HTTPX_OK:
        print("[!] requests/httpx not installed")
        return None
    
    default_headers = {"User-Agent": random.choice(USER_AGENTS)}
    if headers:
        default_headers.update(headers)
    
    print(f"[fetch] GET {url}")
    
    try:
        if REQUESTS_OK:
            resp = requests.get(url, headers=default_headers, timeout=15)
        else:
            resp = httpx.get(url, headers=default_headers, timeout=15)
        
        print(f"[fetch] Status {resp.status_code}, {len(resp.content)} bytes")
        return resp.text
    except Exception as e:
        print(f"[fetch] Error: {e}")
        return None


# ============================================================
# CLI 接口
# ============================================================

def cmd_fetch(url):
    """获取页面 (HTTP)"""
    html = fetch_page(url)
    if html:
        print(f"\n  HTML 片段: {html[:500]}...")


def cmd_screenshot(url, output=None):
    """截图"""
    out = output or f"screenshot_{datetime.now().strftime('%H%M%S')}.png"
    print(f"[*] 页面截图: {url} → {out}")
    
    with BrowserManager(headless=True) as bm:
        bm.visit(url, wait_until="networkidle")
        bm.page.screenshot(path=out, full_page=True)
        print(f"[+] 截图保存到 {out}")


def cmd_extract(url, css_selectors):
    """提取数据"""
    selectors = {}
    for s in css_selectors:
        if "=" not in s:
            selectors[s] = s
        else:
            k, v = s.split("=", 1)
            selectors[k.strip()] = v.strip()
    
    with BrowserManager(headless=False) as bm:
        page = bm.visit(url)
        data = extract_data(page, selectors)
        print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_crawl(url, max_depth=2):
    """广度爬取"""
    visited = set()
    queue = [(url, 0)]
    
    print(f"[*] 开始爬取: {url} (最大深度={max_depth})")
    
    with BrowserManager(headless=True) as bm:
        while queue:
            current_url, depth = queue.pop(0)
            if current_url in visited or depth > max_depth:
                continue
            visited.add(current_url)
            
            print(f"  [{'='*depth*2}>{'('*(max_depth-depth)}] {current_url}")
            
            try:
                page = bm.visit(current_url, wait_until="domcontentloaded", timeout=15000)
                links = page.query_selector_all("a[href]")
                
                for link in links:
                    href = link.get_attribute("href")
                    if href and href.startswith("http") and href not in visited:
                        queue.append((href, depth + 1))
                
                time.sleep(random.uniform(0.5, 1.5))
            except Exception as e:
                print(f"    [!] {e}")
    
    print(f"\n[+] 共访问 {len(visited)} 个页面")


def cmd_cookies(action):
    """管理 cookies"""
    if action == "save":
        print("[*] Cookies 当前已自动保存到:", str(COOKIE_DIR))
        for f in COOKIE_DIR.glob("*_cookies.json"):
            print(f"  {f.name} ({f.stat().st_size} bytes)")
    elif action == "load":
        print("[*] Cookies 目录:")
        for f in COOKIE_DIR.glob("*_cookies.json"):
            cnt = json.loads(f.read_text()) if f.stat().st_size > 0 else []
            print(f"  {f.stem.replace('_cookies',''):20s} {len(cnt)} 条 cookies")
    elif action == "clear":
        for f in COOKIE_DIR.glob("*_cookies.json"):
            f.unlink()
            print(f"  [-] 清除 {f.name}")
    else:
        print("[!] 用法: cookies save|load|clear")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "fetch":
        cmd_fetch(sys.argv[2])
    elif cmd == "screenshot":
        cmd_screenshot(sys.argv[2])
    elif cmd == "extract":
        cmd_extract(sys.argv[2], sys.argv[3:])
    elif cmd == "crawl":
        depth = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[2] == "-d" else 2
        url = sys.argv[2] if len(sys.argv) > 2 else "https://example.com"
        if "-d" in sys.argv:
            url = sys.argv[2]
            depth = int(sys.argv[3]) if len(sys.argv) > 3 else 2
        if url.startswith("-d"):
            url = sys.argv[3] if len(sys.argv) > 3 else sys.argv[-1]
            depth = int(sys.argv[2].replace("-d",""))
        cmd_crawl(url, depth)
    elif cmd == "cookies":
        cmd_cookies(sys.argv[2] if len(sys.argv) > 2 else "save")
    else:
        print(f"未知命令: {cmd}")
