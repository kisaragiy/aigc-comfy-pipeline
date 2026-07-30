#!/usr/bin/env python3
"""
B站 黑客式 API 客户端 — Cookie持久化 + 智能频率控制

核心思想：
  B站不同API的保护力度不同。视频信息API几乎无保护，搜索API重保护。
  与其硬破搜索，不如找其他入口（空间API、推荐API）绕过。
  
  秘密: Session + Cookie 持久化能显著提高频率限额。
"""
import requests, time, random, hashlib, json, os
from pathlib import Path

# ── Session 管理器 ──
class BiliSession:
    """带Cookie持久化的B站会话"""
    
    COOKIE_FILE = Path.home() / "hermes-workspace" / "bili_cookies.json"
    
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
            "Referer": "https://www.bilibili.com/",
            "Origin": "https://www.bilibili.com",
        })
        self._load_cookies()
        self.wbi_keys = None
    
    def _load_cookies(self):
        if self.COOKIE_FILE.exists():
            with open(self.COOKIE_FILE) as f:
                cookies = json.load(f)
            for name, value in cookies.items():
                self.s.cookies.set(name, value)
            print(f"  [BiliSession] 加载 {len(cookies)} 个cookie")
    
    def save_cookies(self):
        self.COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
        cookies = dict(self.s.cookies)
        # Keep only B站 cookies
        bili_cookies = {k: v for k, v in cookies.items() if k.startswith(('buvid', 'b_lsid', '_uuid', 'sid', 'bp'))}
        with open(self.COOKIE_FILE, 'w') as f:
            json.dump(bili_cookies, f)
        print(f"  [BiliSession] 保存 {len(bili_cookies)} 个cookie")
    
    def warmup(self):
        """首次访问B站首页获取cookie"""
        r = self.s.get("https://www.bilibili.com/", timeout=10)
        if r.status_code == 200:
            self.save_cookies()
            return True
        return False
    
    def refresh_wbi(self):
        """获取最新的WBI密钥"""
        r = self.s.get("https://api.bilibili.com/x/web-interface/nav", timeout=10)
        if r.status_code != 200:
            return False
        data = r.json()
        if data.get('code') != 0 and data.get('code') != -101:
            return False
        wbi = data.get('data', {}).get('wbi_img', {})
        if not wbi:
            return False
        self.wbi_keys = {
            'img': wbi['img_url'].rsplit('/', 1)[1].rsplit('.', 1)[0],
            'sub': wbi['sub_url'].rsplit('/', 1)[1].rsplit('.', 1)[0],
        }
        return True
    
    def sign_wbi(self, params: dict) -> dict:
        """对参数进行WBI签名"""
        if not self.wbi_keys:
            self.refresh_wbi()
        mixin = self.wbi_keys['img'][:4] + self.wbi_keys['sub'][:4]
        p = params.copy()
        keys = sorted(p.keys())
        query = "&".join(f"{k}={p[k]}" for k in keys)
        sign = hashlib.md5((query + mixin).encode()).hexdigest()
        p["w_rid"] = sign
        p["wts"] = str(int(time.time()))
        return p
    
    def get(self, url, params=None, signed=False):
        """带自动重试和频率控制的GET请求"""
        if signed and params:
            params = self.sign_wbi(params)
        r = self.s.get(url, params=params, timeout=15)
        
        # 处理412 - 频率限制
        if r.status_code == 412:
            print(f"  ⚠️ 412: 频率限制, 等待重试...")
            time.sleep(random.uniform(5, 15))
            r = self.s.get(url, params=params, timeout=15)
        
        # 处理空响应
        if r.status_code == 200 and len(r.text) < 50:
            print(f"  ⚠️ 空响应, 可能被限流")
            time.sleep(random.uniform(3, 8))
            r = self.s.get(url, params=params, timeout=15)
        
        return r


# ── 智能频率控制器 ──
class RateController:
    """
    自适应频率控制。
    每个API端点独立跟踪成功/失败，动态调整间隔。
    """
    def __init__(self, base_interval=1.5):
        self.base = base_interval
        self.multipliers = {}  # endpoint → current multiplier
        self.success_count = {} 
        self.fail_count = {}
    
    def _key(self, url):
        return url.split('?')[0].rsplit('/', 1)[-1]
    
    def wait(self, url):
        key = self._key(url)
        mult = self.multipliers.get(key, 1.0)
        delay = self.base * mult * random.uniform(0.8, 1.2)  # jitter
        time.sleep(delay)
    
    def report_success(self, url):
        key = self._key(url)
        self.success_count[key] = self.success_count.get(key, 0) + 1
        # 连续成功 → 降低multiplier (加速)
        if self.success_count[key] >= 5:
            self.multipliers[key] = max(0.5, self.multipliers.get(key, 1.0) * 0.9)
            self.success_count[key] = 0
    
    def report_fail(self, url):
        key = self._key(url)
        self.fail_count[key] = self.fail_count.get(key, 0) + 1
        # 失败 → 指数退避
        self.multipliers[key] = min(60.0, self.multipliers.get(key, 1.0) * 2.0)
        self.success_count[key] = 0
    
    def status(self):
        for key in set(list(self.multipliers.keys()) + list(self.success_count.keys())):
            m = self.multipliers.get(key, 1.0)
            s = self.success_count.get(key, 0)
            f = self.fail_count.get(key, 0)
            status = "🟢" if m <= 1.0 else "🟡" if m <= 5.0 else "🔴"
            print(f"  {status} {key:20s} mult:{m:.1f}x  ok:{s} fail:{f}")


# ── 空间API替代搜索 ──
def get_user_videos(session: BiliSession, mid: int, page: int = 1):
    """
    通过空间API获取UP主视频列表。
    这个API的保护比搜索API弱得多。
    """
    url = "https://api.bilibili.com/x/space/arc/search"
    params = {"mid": mid, "ps": 30, "pn": page, "order": "pubdate"}
    r = session.get(url, params=params, signed=True)
    if r.status_code != 200:
        return None
    try:
        data = r.json()
    except:
        return None
    if data.get('code') != 0:
        print(f"  ❌ 空间API: {data.get('message','?')}")
        return None
    vlist = data.get('data', {}).get('list', {}).get('vlist', [])
    return vlist


# ── 测试 ──
def main():
    print("=" * 50)
    print("B站 黑客式API客户端 — 测试")
    print("=" * 50)
    
    s = BiliSession()
    rc = RateController()
    
    # Step 1: Warmup → 获取Cookie
    print("\n[1/4] Warmup (获取cookie)...")
    if not s.warmup():
        print("  ❌ 无法获取cookie")
        return
    print("  ✅ Cookie已获取")
    
    # Step 2: 刷新WBI密钥
    print("\n[2/4] 获取WBI密钥...")
    if not s.refresh_wbi():
        print("  ❌ 无法获取WBI密钥")
        return
    print(f"  ✅ WBI密钥: img={s.wbi_keys['img'][:8]}... sub={s.wbi_keys['sub'][:8]}...")
    
    # Step 3: 空间API替代搜索 (使用已知的封印者UID)
    print("\n[3/4] 通过空间API获取封印者视频列表...")
    videos = get_user_videos(s, 52229030)
    if videos:
        print(f"  ✅ 获取到 {len(videos)} 个视频:")
        for v in videos[:10]:
            print(f"    {v['title'][:40]:40s} {v['play']:>8}播放 BV{v['bvid']}")
    else:
        print("  ❌ 空间API失败")
    
    # Step 4: 测试频率控制
    print("\n[4/4] 连续请求测试 (5次)...")
    for i in range(5):
        rc.wait("https://api.bilibili.com/x/web-interface/view")
        r = s.get("https://api.bilibili.com/x/web-interface/view", 
                   params={"aid": 170001})
        if r.status_code == 200 and len(r.text) > 100:
            rc.report_success("video_info")
            print(f"  [{i+1}/5] ✅ HTTP 200 (正常)")
        else:
            rc.report_fail("video_info")
            print(f"  [{i+1}/5] ❌ HTTP {r.status_code}")
    
    print("\n  频率状态:")
    rc.status()
    print("\n✅ 测试完成")

if __name__ == "__main__":
    main()
