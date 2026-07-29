#!/usr/bin/env python3
"""淘宝自动化工具 — Playwright + 反爬策略

功能:
  - 商品搜索 (关键词 → 商品列表)
  - 商品详情 (标题/价格/月销量/评价数/店铺名)
  - 商品收藏 (需要已登录)
  - 购物车管理 (需要已登录)
  - 价格追踪 (历史价格存储)
  - 多关键词监控 (定期搜索 + 推送)

依赖: playwright, bs4, lxml, captcha_solver.py (可选)

用法:
  python taobao_auto.py search <keyword>           # 搜索商品
  python taobao_auto.py detail <item_id>           # 商品详情
  python taobao_auto.py monitor <keyword>          # 监控价格 (保存到JSON)
  python taobao_auto.py login                      # 登录淘宝 (二维码)
  python taobao_auto.py cart                       # 查看购物车
"""
import sys, json, os, time, random, re
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

# ── 浏览器 ──
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    sync_playwright = None
    
# ── HTML 解析 ──
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

# ── 数据存储 ──
DATA_DIR = Path.home() / ".taobao_data"
DATA_DIR.mkdir(exist_ok=True)
PRICE_HISTORY = DATA_DIR / "price_history.json"
MONITOR_LIST = DATA_DIR / "monitor_list.json"

# ── 淘宝 URL ──
TAOBAO = "https://www.taobao.com"
TAOBAO_LOGIN = "https://login.taobao.com"
TAOBAO_SEARCH = "https://s.taobao.com/search?q="
TAOBAO_DETAIL = "https://item.taobao.com/item.htm?id="
TAOBAO_CART = "https://cart.taobao.com/cart.htm"
TAOBAO_FAV = "https://favorite.taobao.com"


class TaobaoAuto:
    """淘宝自动化核心"""
    
    def __init__(self, headless=False):
        self.headless = headless
        self.pw = None
        self.browser = None
        self.context = None
        self.page = None
        
        # 反检测脚本
        self.anti_detect_js = """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        window.chrome = { runtime: {} };
        """
    
    def __enter__(self):
        if sync_playwright is None:
            raise RuntimeError("playwright not installed")
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"]
        )
        self.context = self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        self.context.add_init_script(self.anti_detect_js)
        self._load_cookies()
        self.page = self.context.new_page()
        return self
    
    def __exit__(self, *args):
        self._save_cookies()
        if self.page: self.page.close()
        if self.context: self.context.close()
        if self.browser: self.browser.close()
        if self.pw: self.pw.stop()
    
    def _cookie_path(self):
        return DATA_DIR / "taobao_cookies.json"
    
    def _load_cookies(self):
        cp = self._cookie_path()
        if cp.exists():
            try:
                cookies = json.loads(cp.read_text())
                self.context.add_cookies(cookies)
                print(f"[cookies] 加载 {len(cookies)} 条 cookies")
            except: pass
    
    def _save_cookies(self):
        try:
            cookies = self.context.cookies()
            self._cookie_path().write_text(json.dumps(cookies, indent=2, ensure_ascii=False))
            print(f"[cookies] 保存 {len(cookies)} 条 cookies")
        except: pass
    
    def _random_delay(self, a=1.0, b=3.0):
        time.sleep(random.uniform(a, b))
    
    # ── 登录 ──
    
    def login(self):
        """淘宝二维码登录"""
        print("[*] 打开淘宝登录页...")
        self.page.goto(TAOBAO_LOGIN, wait_until="networkidle")
        self._random_delay()
        
        print("\n  ℹ️  手动扫码登录流程:")
        print("    1. 页面已打开淘宝登录页")
        print("    2. 用淘宝/支付宝 App 扫码")
        print("    3. 扫码成功后按 Enter 继续")
        print("    4. Cookies 会自动保存, 下次不用再登\n")
        
        input("     按 Enter 继续...")
        self._save_cookies()
        
        # 验证是否登录成功
        self.page.goto(TAOBAO, wait_until="networkidle")
        if "login" in self.page.url.lower():
            print("[-] 登录似乎失败, 请重试")
            return False
        
        print("[+] 登录成功!")
        return True
    
    # ── 搜索 ──
    
    def search(self, keyword: str, max_pages=1):
        """搜索商品并提取列表"""
        url = TAOBAO_SEARCH + keyword
        print(f"[*] 搜索: {keyword}")
        self.page.goto(url, wait_until="networkidle")
        self._random_delay()
        
        # 处理可能的滑块验证
        if "captcha" in self.page.url.lower() or self._check_captcha():
            print("[!] 遇到验证码, 尝试处理...")
            self._handle_captcha()
        
        items = []
        
        for page_num in range(max_pages):
            self._random_delay(2, 4)
            
            # 提取商品列表
            html = self.page.content()
            if BeautifulSoup:
                items += self._parse_search_results(html, keyword)
            
            # 翻页
            if page_num < max_pages - 1:
                next_btn = self.page.query_selector("a.next:not(.disabled)")
                if next_btn:
                    next_btn.click()
                    self.page.wait_for_load_state("networkidle")
                else:
                    print("[*] 没有更多页")
                    break
        
        print(f"\n[+] 找到 {len(items)} 个商品")
        
        # 保存搜索结果
        outfile = DATA_DIR / f"search_{keyword}_{datetime.now():%Y%m%d%H%M}.json"
        DATA_DIR.mkdir(exist_ok=True)
        outfile.write_text(json.dumps(items, ensure_ascii=False, indent=2))
        print(f"[+] 保存到 {outfile}")
        
        for item in items[:5]:
            print(f"\n  📦 {item.get('title','?')[:50]}")
            print(f"     💰 {item.get('price','?')}  |  📊 {item.get('deal','?')}  |  🏪 {item.get('shop','?')}")
        
        return items
    
    def _parse_search_results(self, html: str, keyword: str) -> List[Dict]:
        """解析搜索结果HTML"""
        if BeautifulSoup is None:
            return []
        
        soup = BeautifulSoup(html, "lxml")
        items = []
        
        # 淘宝搜索结果结构 (可能有变, 多个备选选择器)
        selectors = [
            "div.items div.item",            # PC版旧
            "div[J_ItemBody]",               # PC版新
            "div[data-index]",               # 新版
            "div.item.J_MouserOnverReq",     # 另一个
        ]
        
        containers = []
        for sel in selectors:
            containers = soup.select(sel)
            if containers:
                break
        
        if not containers:
            # 尝试通用: 找有 title + price 的块
            for div in soup.find_all("div", recursive=True):
                if div.get("data-category", "") == "auction":
                    containers.append(div)
        
        for container in containers:
            try:
                # 标题
                title_el = container.select_one("a[title]") or container.select_one(".title a")
                title = title_el.get("title") or title_el.get_text(strip=True) if title_el else "?"
                
                # 价格
                price_el = container.select_one(".price") or container.select_one("[class*=price]")
                price = price_el.get_text(strip=True) if price_el else "?"
                
                # 链接 + ID
                link_el = title_el or container.select_one("a[href*=item]")
                link = link_el.get("href", "") if link_el else ""
                item_id = re.search(r'id=(\d+)', link)
                item_id = item_id.group(1) if item_id else "?"
                
                # 月销量
                deal_el = container.select_one(".deal-cnt") or container.select_one("[class*=deal]")
                deal = deal_el.get_text(strip=True) if deal_el else "?"
                
                # 店铺名
                shop_el = container.select_one(".shop") or container.select_one("[class*=shop]")
                shop = shop_el.get_text(strip=True) if shop_el else "?"
                
                # 图片
                img_el = container.select_one("img[src]")
                img = img_el.get("src") or img_el.get("data-src") if img_el else "?"
                
                items.append({
                    "keyword": keyword,
                    "item_id": item_id,
                    "title": title,
                    "price": price,
                    "deal": deal,
                    "shop": shop,
                    "img": img,
                    "link": link if link.startswith("http") else f"https:{link}",
                    "time": datetime.now().isoformat(),
                })
            except Exception as e:
                pass
        
        return items
    
    # ── 商品详情 ──
    
    def detail(self, item_id: str):
        """获取商品详情"""
        url = TAOBAO_DETAIL + item_id
        print(f"[*] 商品详情: {url}")
        self.page.goto(url, wait_until="networkidle")
        self._random_delay()
        
        html = self.page.content()
        if BeautifulSoup:
            soup = BeautifulSoup(html, "lxml")
            
            info = {"item_id": item_id, "url": url, "time": datetime.now().isoformat()}
            
            # 标题
            title_el = soup.select_one("h1.tb-main-title") or soup.select_one("[class*=title] h1") or soup.select_one("title")
            info["title"] = title_el.get_text(strip=True) if title_el else "?"
            
            # 价格
            price_el = soup.select_one(".tm-price") or soup.select_one("[class*=price]")
            info["price"] = price_el.get_text(strip=True) if price_el else "?"
            
            # 销量
            deal_el = soup.select_one(".tm-count") or soup.select_one("[class*=sale]")
            info["deal"] = deal_el.get_text(strip=True) if deal_el else "?"
            
            # 店铺
            shop_el = soup.select_one(".shop-name a") or soup.select_one("[class*=shop] a")
            info["shop"] = shop_el.get_text(strip=True) if shop_el else "?"
            
            # 参数
            params = {}
            for li in soup.select(".attributes-list li"):
                text = li.get_text(strip=True)
                if ":" in text:
                    k, v = text.split(":", 1)
                    params[k.strip()] = v.strip()
            info["params"] = params
            
            print(f"\n  📦 {info['title'][:60]}")
            print(f"     💰 {info.get('price','?')}  |  📊 {info.get('deal','?')}")
            print(f"     🏪 {info.get('shop','?')}")
            print(f"     📋 参数: {len(params)} 项")
            
            # 记录价格历史
            self._record_price(item_id, info)
            
            return info
    
    # ── 价格历史 ──
    
    def _record_price(self, item_id, info):
        """记录价格到历史"""
        history = {}
        if PRICE_HISTORY.exists():
            try:
                history = json.loads(PRICE_HISTORY.read_text())
            except: pass
        
        if item_id not in history:
            history[item_id] = {"title": info.get("title","?"), "records": []}
        
        history[item_id]["records"].append({
            "price": info.get("price","?"),
            "deal": info.get("deal","?"),
            "time": info["time"],
        })
        
        PRICE_HISTORY.write_text(json.dumps(history, ensure_ascii=False, indent=2))
        print(f"     💾 价格已记录 ({len(history[item_id]['records'])} 次)")
    
    # ── 监控 ──
    
    def monitor(self, keyword: str, check_interval_hours=24):
        """监控关键词"""
        print(f"[*] 添加监控: '{keyword}' (每 {check_interval_hours}h)")
        
        monitors = {}
        if MONITOR_LIST.exists():
            try:
                monitors = json.loads(MONITOR_LIST.read_text())
            except: pass
        
        monitors[keyword] = {
            "keyword": keyword,
            "interval": check_interval_hours,
            "added": datetime.now().isoformat(),
            "last_check": None,
        }
        
        MONITOR_LIST.write_text(json.dumps(monitors, ensure_ascii=False, indent=2))
        print(f"[+] 当前监控: {len(monitors)} 个关键词")
        
        return list(monitors.keys())
    
    def run_all_monitors(self):
        """执行所有监控搜索"""
        if not MONITOR_LIST.exists():
            print("[-] 没有监控项"); return
        
        monitors = json.loads(MONITOR_LIST.read_text())
        print(f"[*] 执行 {len(monitors)} 个监控...")
        
        for keyword, config in monitors.items():
            print(f"\n  ── {keyword} ──")
            self.search(keyword)
            
            config["last_check"] = datetime.now().isoformat()
        
        MONITOR_LIST.write_text(json.dumps(monitors, ensure_ascii=False, indent=2))
    
    # ── 验证码检测 ──
    
    def _check_captcha(self) -> bool:
        """检测页面是否被验证码拦截"""
        indicators = [
            "验证码", "captcha", "slide", "滑块",
            "请按住", "拖动", "验证",
        ]
        body = self.page.content().lower() if self.page else ""
        return any(ind in body for ind in indicators)
    
    def _handle_captcha(self):
        """尝试处理验证码"""
        print("    检测到验证码, 尝试自动处理...")
        
        # 截图
        captcha_path = str(DATA_DIR / f"captcha_{datetime.now():%H%M%S}.png")
        self.page.screenshot(path=captcha_path)
        print(f"    验证码截图: {captcha_path}")
        
        print("""
    ── 验证码处理策略 ──
    策略1 (滑块): 
      运行 captcha_solver.py 分析缺口
      然后用 Playwright 拖拽
    
    策略2 (文本/点选):
      用 agent 的 vision_analyze 工具识别
      然后自动填写/点击
    
    策略3 (手动):
      - 如果是手机验证码, 你可以在代理中接收
      - 如果是滑块, 改 headless=False 手动划
      
    策略4 (等待):
      - 等5分钟再重试 (淘宝短期封)
      - 如果频繁触发, 需要降低请求频率
        """)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    
    cmd = sys.argv[1]
    
    with TaobaoAuto(headless=False) as tb:
        if cmd == "login":
            tb.login()
        elif cmd == "search":
            keyword = sys.argv[2]
            tb.search(keyword)
        elif cmd == "detail":
            item_id = sys.argv[2]
            tb.detail(item_id)
        elif cmd == "monitor":
            keyword = sys.argv[2]
            tb.monitor(keyword)
        elif cmd == "monitors-run":
            tb.run_all_monitors()
        elif cmd == "cart":
            tb.page.goto(TAOBAO_CART, wait_until="networkidle")
            print(f"[*] 购物车: {tb.page.url}")
            input("按 Enter 继续...")
        else:
            print(f"未知命令: {cmd}")
