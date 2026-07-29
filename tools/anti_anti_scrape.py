#!/usr/bin/env python3
"""通用反反爬虫工具集 — HTTP请求层
requests/curl 层面应对反爬虫的策略合集，不依赖浏览器。

用法:
  python anti_anti_scrape.py probe <url>           # 探测目标的反爬策略
  python anti_anti_scrape.py fetch <url>            # 智能获取(自动降级)
  python anti_anti_scrape.py session <url> <n>      # 批量请求(测试频率限制)
"""
import sys, json, time, random, urllib.parse, hashlib, hmac

# ── 请求头池 ──
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]

REFERERS = {
    "www.zhipin.com": "https://www.zhipin.com/",
    "www.jd.com": "https://www.jd.com/",
    "www.taobao.com": "https://www.taobao.com/",
    "www.bilibili.com": "https://www.bilibili.com/",
    "api.bilibili.com": "https://www.bilibili.com/",
    "namu.wiki": "https://namu.wiki/",
}

PROXIES = [
    None,                                    # 直连
    "http://127.0.0.1:7890",                 # Clash
]

# ── 频率控制 ──
class RateLimiter:
    """请求频率控制器：随机间隔 + 退避"""
    def __init__(self, min_delay=2.0, max_delay=5.0):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._last_req = {}
    
    def wait(self, domain="default"):
        """根据域名控制请求间隔"""
        now = time.time()
        last = self._last_req.get(domain, 0)
        elapsed = now - last
        delay = random.uniform(self.min_delay, self.max_delay)
        if elapsed < delay:
            sleep_time = delay - elapsed
            time.sleep(sleep_time)
        self._last_req[domain] = time.time()

# ── 请求头生成 ──
def build_headers(url: str) -> dict:
    """生成随机化的请求头"""
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc
    
    ua = random.choice(USER_AGENTS)
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    if domain in REFERERS:
        headers["Referer"] = REFERERS[domain]
    # 部分站点需要 Cache-Control
    if domain in ("www.jd.com", "www.taobao.com"):
        headers["Cache-Control"] = "max-age=0"
    return headers

# ── B站 WBI 签名 ──
def bili_wbi_sign(params: dict, img_key: str, sub_key: str) -> dict:
    """B站 WBI 签名 (用于需要签名的API)"""
    mixin = img_key[:4] + sub_key[:4]  # 实际需要从 nav 接口获取
    keys = sorted(params.keys())
    query = "&".join(f"{k}={params[k]}" for k in keys)
    sign = hashlib.md5((query + mixin).encode()).hexdigest()
    params["wts"] = str(int(time.time()))
    params["w_rid"] = sign
    return params

# ── 探针 ──
def probe(url: str):
    """探测目标网站的反爬策略"""
    import requests as req
    print(f"\n{'='*50}")
    print(f"探针: {url}")
    print(f"{'='*50}")
    
    strategies = {}
    
    # 测试1: 无头请求
    try:
        r = req.get(url, headers=build_headers(url), timeout=10, proxies={"http":"","https":""})
        strategies["no_detect"] = f"HTTP {r.status_code} ({len(r.content)} bytes)"
        if len(r.text) < 200 or "captcha" in r.text.lower() or "验证" in r.text:
            strategies["no_detect"] += " ⚠️ 可能触发验证码/风控"
    except Exception as e:
        strategies["no_detect"] = f"❌ {e}"
    
    # 测试2: 通过代理
    try:
        r = req.get(url, headers=build_headers(url), timeout=10, 
                    proxies={"http":"http://127.0.0.1:7890", "https":"http://127.0.0.1:7890"})
        strategies["via_proxy"] = f"HTTP {r.status_code} ({len(r.content)} bytes)"
    except Exception as e:
        strategies["via_proxy"] = f"❌ {e}"
    
    # 分析结果
    for name, result in strategies.items():
        print(f"  [{name:12s}] {result}")
    
    # 判断主要防御
    print(f"\n  分析:")
    if "验证" in str(strategies) or "captcha" in str(strategies).lower():
        print("  🛡️ 验证码/CAPTCHA — 需要浏览器自动化")
    if "403" in str(strategies) or "412" in str(strategies):
        print("  🛡️ HTTP 403/412 — 请求头校验 / WAF")
    if "999" in str(strategies) or "302" in str(strategies):
        print("  🛡️ 重定向验证 — Cookie/JS检查")
    if "000" in str(strategies) or "timeout" in str(strategies).lower():
        print("  🛡️ 连接超时/被墙 — 需要代理/VPN")
    
    return strategies

# ── 智能获取 ──
def smart_fetch(url: str):
    """智能获取：自动降级策略"""
    import requests as req
    
    rate = RateLimiter(min_delay=1.0, max_delay=3.0)
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc
    
    strategies = [
        {"proxy": None, "desc": "直连"},
        {"proxy": "http://127.0.0.1:7890", "desc": "Clash代理"},
    ]
    
    last_error = None
    for s in strategies:
        rate.wait(domain)
        try:
            headers = build_headers(url)
            proxies = {"http": s["proxy"], "https": s["proxy"]} if s["proxy"] else {"http":"","https":""}
            r = req.get(url, headers=headers, proxies=proxies, timeout=15)
            if r.status_code == 200 and len(r.text) > 500:
                return r.text, s["desc"]
            elif r.status_code == 412:
                print(f"  ⚠️ 412 预制条件失败 ({s['desc']}), 切换策略...")
                time.sleep(random.uniform(3, 8))
            elif r.status_code == 403:
                print(f"  ⚠️ 403 禁止访问 ({s['desc']}), 切换策略...")
            else:
                print(f"  ⚠️ HTTP {r.status_code} ({s['desc']})")
        except Exception as e:
            last_error = str(e)
            print(f"  ❌ {s['desc']}: {e}")
    
    return None, last_error

# ── CLI ──
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    cmd = sys.argv[1]
    
    if cmd == "probe" and len(sys.argv) >= 3:
        probe(sys.argv[2])
    elif cmd == "fetch" and len(sys.argv) >= 3:
        text, err = smart_fetch(sys.argv[2])
        if text:
            print(f"✅ 成功 ({len(text)} bytes)")
        else:
            print(f"❌ 失败: {err}")
    elif cmd == "session":
        url = sys.argv[2]
        n = int(sys.argv[3]) if len(sys.argv) >= 4 else 5
        rate = RateLimiter(min_delay=1.5, max_delay=3.0)
        for i in range(n):
            rate.wait()
            text, method = smart_fetch(url)
            status = "✅" if text else "❌"
            print(f"  [{i+1}/{n}] {status} via {method}")
    else:
        print(f"未知命令: {cmd}")
        print(__doc__)

if __name__ == "__main__":
    main()
