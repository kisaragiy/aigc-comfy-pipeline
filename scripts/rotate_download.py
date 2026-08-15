#!/usr/bin/env python3
"""B站视频下载 — 轮换Clash节点突破限流"""
import subprocess, time, os, json, requests as req

WORK = r'C:\Users\zwq\hermes-workspace\downloads'
os.makedirs(WORK, exist_ok=True)
os.chdir(WORK)

CLASH_API = 'http://127.0.0.1:1361'
SECRET = '92a83c35-9c1b-4d48-8a2c-06db53f33440'
HEADERS = {'Authorization': f'Bearer {SECRET}'}

# 所有可用节点 (TapFog订阅)
NODES = [
    'Bronze-日本-01', 'Bronze-韩国-01', 'Bronze-台湾-01',
    'Bronze-香港-BGP-01', 'Bronze-香港-HKT-02', 'Bronze-香港-HGC-03',
    'Bronze-香港-HGC-04', 'Bronze-香港-BGP-05',
    'Bronze-新加坡-01', 'Bronze-美国-onep-01',
    'Bronze-美国-onep-02', 'Bronze-美国-CHI-03',
    'Silver-香港-HKG-01', 'Silver-韩国-商宽-01',
    'Silver-台湾-Hinet-01', 'Silver-美国-Host-01',
]

# 待下载的BV号
BVS = [
    'BV1dt411P72S', 'BV1cJ411T75k', 'BV1RJ411K7Ei', 'BV11E411b7v1',
    'BV13541187eN', 'BV1PM4y1L7HJ', 'BV1xL4y187hY', 'BV1344y1t7vA',
    'BV1Kb4y1a78n', 'BV1Af4y1u7tm', 'BV1Qu411d7ou', 'BV1aP4y1L7LG',
    'BV1d3411h7HJ', 'BV1VS4y1C7yp', 'BV1ML4y1M75H', 'BV1Aa411v7YW',
    'BV1eG411b7Jn', 'BV12W411U74u', 'BV1L54y1A7KQ', 'BV1Km4y1j7Sf',
    'BV1z94y1r7ko', 'BV17mCzY4EnK', 'BV1WbeMzNEvY', 'BV1krqGBYErN',
]

def log(m): print(f'[{time.strftime("%H:%M:%S")}] {m}', flush=True)

def switch_node(node_name):
    """通过Clash API切换到指定节点"""
    try:
        r = req.put(f'{CLASH_API}/proxies/GLOBAL', 
                   headers=HEADERS, json={'name': node_name},
                   timeout=5, proxies={'http':'','https':''})
        return r.status_code == 204
    except: return False

def get_playurl(bv, cid):
    """通过当前Clash节点获取下载URL"""
    try:
        r = req.get(f'https://api.bilibili.com/x/player/playurl?bvid={bv}&cid={cid}&qn=16&platform=html5',
                   headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.bilibili.com/'},
                   proxies={'http':'http://127.0.0.1:7890','https':'http://127.0.0.1:7890'},
                   timeout=15)
        d = r.json()
        if d.get('code') == 0 and d.get('data',{}).get('durl'):
            return d['data']['durl'][0]['url']
    except: pass
    return None

def download_via_node(vurl, out, node_name):
    """通过特定节点下载视频文件"""
    # Switch to node
    if not switch_node(node_name):
        return False
    time.sleep(1)  # Wait for switch
    
    # Download through Clash proxy
    r = subprocess.run(['curl', '-L', '--max-time', '120', '-x', 'http://127.0.0.1:7890',
        '-H', 'User-Agent: Mozilla/5.0', '-o', out, vurl],
        capture_output=True, text=True, timeout=130)
    return os.path.exists(out) and os.path.getsize(out) > 10000

# Main
log(f'轮换下载启动: {len(BVS)} 个视频, {len(NODES)} 个节点')
node_idx = 0
ok, fail = 0, 0

for bv in BVS:
    # Check if already downloaded
    existing = [f for f in os.listdir('.') if f.startswith(bv) and f.endswith('.mp4')]
    if existing:
        log(f'  ⏭️ 已存在: {bv}')
        ok += 1
        continue
    
    # Try each node in round-robin
    downloaded = False
    for attempt in range(min(3, len(NODES))):
        node = NODES[node_idx % len(NODES)]
        node_idx += 1
        
        log(f'  ▶️ {bv} @ {node}')
        try:
            # Get video info first
            r = req.get(f'https://api.bilibili.com/x/web-interface/view?bvid={bv}',
                       headers={'User-Agent':'Mozilla/5.0'},
                       proxies={'http':'http://127.0.0.1:7890','https':'http://127.0.0.1:7890'},
                       timeout=10)
            info = r.json().get('data', {})
            cid = info.get('cid')
            if not cid: raise Exception('no cid')
            
            # Get playurl through this node
            vurl = get_playurl(bv, cid)
            if not vurl: raise Exception('no playurl')
            
            # Log the CDN
            import urllib.parse
            cdn = urllib.parse.urlparse(vurl).hostname
            log(f'    CDN: {cdn}')
            
            # Download
            out = f'{bv}.mp4'
            r = subprocess.run(['curl', '-L', '--max-time', '120', '-x', 'http://127.0.0.1:7890',
                '-H', 'User-Agent: Mozilla/5.0', '-o', out, vurl],
                capture_output=True, text=True, timeout=130)
            
            if os.path.exists(out) and os.path.getsize(out) > 10000:
                sz = os.path.getsize(out) // 1024
                log(f'    ✅ {sz}KB via {node}')
                downloaded = True
                ok += 1
                break
            else:
                raise Exception(f'small file ({os.path.getsize(out) if os.path.exists(out) else 0}b)')
        except Exception as e:
            log(f'    ❌ {str(e)[:60]}')
    
    if not downloaded:
        fail += 1
        log(f'  ❌ 全部节点失败: {bv}')
    
    time.sleep(5)  # Brief pause between videos

log(f'\n✅ 完成! 成功:{ok} 失败:{fail}')
